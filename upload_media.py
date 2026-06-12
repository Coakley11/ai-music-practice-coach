"""Prepare uploaded audio/video files for the recording analysis pipeline."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".avi"})
AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".webm"})

UPLOAD_ACCEPT_TYPES = [
    "wav",
    "mp3",
    "m4a",
    "ogg",
    "flac",
    "mp4",
    "mov",
    "m4v",
    "avi",
]

VIDEO_EXTRACTION_UNAVAILABLE_MSG = (
    "Video audio extraction is unavailable on this deployment. "
    "Upload MP3/WAV directly or use a deployment with ffmpeg enabled."
)


class VideoExtractionError(Exception):
    """Video could not be converted to analysis audio — includes diagnostics."""

    def __init__(self, message: str, *, meta: dict[str, Any]) -> None:
        super().__init__(message)
        self.meta = meta


def file_extension(filename: str) -> str:
    name = str(filename or "").strip().lower()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1]


def is_video_filename(filename: str) -> bool:
    return file_extension(filename) in VIDEO_EXTENSIONS


def is_audio_filename(filename: str) -> bool:
    ext = file_extension(filename)
    return ext in AUDIO_EXTENSIONS or ext == ""


def ffmpeg_status() -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    return {
        "ffmpeg_detected": bool(ffmpeg),
        "ffmpeg_path": ffmpeg or "",
        "ffprobe_detected": bool(ffprobe),
        "ffprobe_path": ffprobe or "",
    }


def _ffprobe_duration_seconds(path: str) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            return None
        return float(str(proc.stdout).strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _extract_with_ffmpeg(video_path: str, wav_path: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg_not_found")
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "1",
            wav_path,
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ffmpeg failed").strip()
        raise RuntimeError(err[-500:] if len(err) > 500 else err)


def _extract_with_librosa(video_path: str, wav_path: str) -> tuple[float, int]:
    import librosa
    import soundfile as sf

    y, sr = librosa.load(video_path, sr=44100, mono=True)
    sf.write(wav_path, y, sr, subtype="PCM_16")
    return float(len(y) / max(1, sr)), int(sr)


def _base_video_meta(filename: str, video_bytes: bytes) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "was_video": True,
        "source_filename": filename,
        "ok": False,
        "file_type": file_extension(filename) or "unknown",
        "file_size_bytes": len(video_bytes),
    }
    meta.update(ffmpeg_status())
    return meta


def extract_audio_from_video(video_bytes: bytes, filename: str) -> tuple[bytes, dict[str, Any]]:
    """Extract mono WAV audio from a video container."""
    ext = file_extension(filename) or ".mp4"
    meta = _base_video_meta(filename, video_bytes)
    video_path = ""
    wav_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(video_bytes)
            video_path = tmp.name
        meta["video_duration_sec"] = _ffprobe_duration_seconds(video_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav_tmp:
            wav_path = wav_tmp.name

        audio_duration: float | None = None
        sample_rate = 44100
        librosa_error = ""
        try:
            audio_duration, sample_rate = _extract_with_librosa(video_path, wav_path)
            meta["extractor"] = "librosa"
        except Exception as exc:
            librosa_error = str(exc)
            meta["failed_step"] = "librosa_load"
            meta["librosa_error"] = librosa_error
            if not meta.get("ffmpeg_detected"):
                meta["failed_step"] = "ffmpeg_missing"
                raise VideoExtractionError(VIDEO_EXTRACTION_UNAVAILABLE_MSG, meta=meta) from exc
            try:
                meta["failed_step"] = "ffmpeg_extract"
                _extract_with_ffmpeg(video_path, wav_path)
                meta["extractor"] = "ffmpeg"
                audio_duration = _ffprobe_duration_seconds(wav_path)
            except RuntimeError as ffmpeg_exc:
                if str(ffmpeg_exc) == "ffmpeg_not_found":
                    meta["failed_step"] = "ffmpeg_missing"
                    raise VideoExtractionError(
                        VIDEO_EXTRACTION_UNAVAILABLE_MSG, meta=meta
                    ) from ffmpeg_exc
                meta["ffmpeg_error"] = str(ffmpeg_exc)
                raise VideoExtractionError(
                    "Could not extract audio from this video file. "
                    "Try uploading MP3/WAV directly.",
                    meta=meta,
                ) from ffmpeg_exc

        wav_bytes = Path(wav_path).read_bytes()
        if not wav_bytes or len(wav_bytes) < 44:
            meta["failed_step"] = meta.get("failed_step") or "empty_output"
            raise VideoExtractionError(
                "Extracted audio was empty. Upload MP3/WAV directly.",
                meta=meta,
            )
        meta["ok"] = True
        meta["audio_duration_sec"] = audio_duration
        meta["sample_rate"] = sample_rate
        meta["extracted_wav_bytes"] = len(wav_bytes)
        return wav_bytes, meta
    except VideoExtractionError:
        raise
    except Exception as exc:
        meta.setdefault("failed_step", "unexpected")
        meta["error"] = str(exc)
        raise VideoExtractionError(
            "Could not extract audio from this video file. Upload MP3/WAV directly.",
            meta=meta,
        ) from exc
    finally:
        for path in (video_path, wav_path):
            if path:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass


def prepare_upload_for_analysis(
    file_bytes: bytes,
    filename: str,
) -> tuple[bytes, str, dict[str, Any]]:
    """Return audio bytes, analysis filename, and metadata for UI messaging."""
    name = str(filename or "upload.wav").strip() or "upload.wav"
    if not is_video_filename(name):
        return file_bytes, name, {"was_video": False, "ok": True, "source_filename": name}

    wav_bytes, meta = extract_audio_from_video(file_bytes, name)
    stem = Path(name).stem or "upload"
    return wav_bytes, f"{stem}.wav", meta


class PreparedUpload:
    """Minimal file-like object for Streamlit upload / analysis handlers."""

    def __init__(self, data: bytes, name: str, *, meta: dict[str, Any] | None = None) -> None:
        self._data = data
        self.name = name
        self.meta = meta or {}

    def getvalue(self) -> bytes:
        return self._data

    def read(self) -> bytes:
        return self._data

    @classmethod
    def from_uploaded(cls, uploaded: Any) -> "PreparedUpload":
        raw = uploaded.getvalue()
        raw_name = str(getattr(uploaded, "name", None) or "recording.wav")
        data, name, meta = prepare_upload_for_analysis(raw, raw_name)
        return cls(data, name, meta=meta)
