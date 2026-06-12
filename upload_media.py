"""Prepare uploaded audio/video files for the recording analysis pipeline."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
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
    "Could not extract audio from this video on the server. "
    "Try a shorter clip or a different MP4/MOV file."
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


def _resolve_ffmpeg_exe() -> tuple[str, str]:
    """
    Resolve an ffmpeg executable for this deployment.

    Returns (path, backend) where backend is ``system`` or ``imageio-ffmpeg``.
    """
    system = shutil.which("ffmpeg")
    if system:
        return system, "system"
    try:
        import imageio_ffmpeg

        bundled = str(imageio_ffmpeg.get_ffmpeg_exe() or "").strip()
        if bundled and Path(bundled).is_file():
            return bundled, "imageio-ffmpeg"
    except Exception:
        pass
    return "", ""


def _ffmpeg_version_line(ffmpeg_exe: str) -> str:
    if not ffmpeg_exe:
        return ""
    try:
        proc = subprocess.run(
            [ffmpeg_exe, "-version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        text = (proc.stdout or proc.stderr or "").strip()
        return text.splitlines()[0].strip() if text else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def ffmpeg_status() -> dict[str, Any]:
    ffmpeg_exe, backend = _resolve_ffmpeg_exe()
    ffprobe = shutil.which("ffprobe")
    return {
        "ffmpeg_detected": bool(ffmpeg_exe),
        "ffmpeg_path": ffmpeg_exe,
        "ffmpeg_backend": backend or "none",
        "ffmpeg_version": _ffmpeg_version_line(ffmpeg_exe),
        "ffprobe_detected": bool(ffprobe),
        "ffprobe_path": ffprobe or "",
    }


def _duration_from_ffmpeg_stderr(stderr: str) -> float | None:
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr or "")
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _probe_duration_seconds(path: str, ffmpeg_exe: str) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            proc = subprocess.run(
                [
                    ffprobe,
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
            if proc.returncode == 0:
                return float(str(proc.stdout).strip())
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    if ffmpeg_exe:
        try:
            proc = subprocess.run(
                [ffmpeg_exe, "-hide_banner", "-i", path],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return _duration_from_ffmpeg_stderr(proc.stderr or proc.stdout or "")
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def _extract_with_ffmpeg(video_path: str, wav_path: str, *, ffmpeg_exe: str) -> None:
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg_not_found")
    proc = subprocess.run(
        [
            ffmpeg_exe,
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
    ffmpeg_exe, ffmpeg_backend = _resolve_ffmpeg_exe()
    meta["ffmpeg_backend"] = ffmpeg_backend or "none"
    video_path = ""
    wav_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(video_bytes)
            video_path = tmp.name
        meta["video_duration_sec"] = _probe_duration_seconds(video_path, ffmpeg_exe)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav_tmp:
            wav_path = wav_tmp.name

        audio_duration: float | None = None
        sample_rate = 44100
        extraction_errors: list[str] = []

        if ffmpeg_exe:
            try:
                meta["failed_step"] = "ffmpeg_extract"
                _extract_with_ffmpeg(video_path, wav_path, ffmpeg_exe=ffmpeg_exe)
                meta["extractor"] = f"ffmpeg ({ffmpeg_backend})"
                audio_duration = _probe_duration_seconds(wav_path, ffmpeg_exe)
            except RuntimeError as ffmpeg_exc:
                if str(ffmpeg_exc) == "ffmpeg_not_found":
                    extraction_errors.append("ffmpeg_not_found")
                else:
                    extraction_errors.append(str(ffmpeg_exc))
                    meta["ffmpeg_error"] = str(ffmpeg_exc)

        if meta.get("extractor") is None:
            try:
                meta["failed_step"] = "librosa_load"
                audio_duration, sample_rate = _extract_with_librosa(video_path, wav_path)
                meta["extractor"] = "librosa"
            except Exception as librosa_exc:
                extraction_errors.append(str(librosa_exc))
                meta["librosa_error"] = str(librosa_exc)

        if meta.get("extractor") is None:
            meta["failed_step"] = "ffmpeg_missing" if not ffmpeg_exe else "all_backends_failed"
            meta["extraction_errors"] = extraction_errors
            if not ffmpeg_exe:
                raise VideoExtractionError(VIDEO_EXTRACTION_UNAVAILABLE_MSG, meta=meta)
            raise VideoExtractionError(
                "Could not extract audio from this video file. "
                "Try a shorter clip or a different MP4/MOV file.",
                meta=meta,
            )

        wav_bytes = Path(wav_path).read_bytes()
        if not wav_bytes or len(wav_bytes) < 44:
            meta["failed_step"] = meta.get("failed_step") or "empty_output"
            raise VideoExtractionError(
                "Extracted audio was empty. Try a different video file.",
                meta=meta,
            )
        meta["ok"] = True
        meta["audio_duration_sec"] = audio_duration
        meta["sample_rate"] = sample_rate
        meta["extracted_wav_bytes"] = len(wav_bytes)
        meta["extraction_success"] = True
        return wav_bytes, meta
    except VideoExtractionError:
        meta["extraction_success"] = False
        raise
    except Exception as exc:
        meta.setdefault("failed_step", "unexpected")
        meta["error"] = str(exc)
        meta["extraction_success"] = False
        raise VideoExtractionError(
            "Could not extract audio from this video file.",
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
