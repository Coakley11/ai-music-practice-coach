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
        raise RuntimeError(
            "Video upload requires ffmpeg on the server. "
            "Install ffmpeg or convert the file to MP3/WAV first."
        )
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


def extract_audio_from_video(video_bytes: bytes, filename: str) -> tuple[bytes, dict[str, Any]]:
    """Extract mono WAV audio from a video container."""
    ext = file_extension(filename) or ".mp4"
    meta: dict[str, Any] = {
        "was_video": True,
        "source_filename": filename,
        "ok": False,
    }
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
        try:
            audio_duration, sample_rate = _extract_with_librosa(video_path, wav_path)
            meta["extractor"] = "librosa"
        except Exception:
            _extract_with_ffmpeg(video_path, wav_path)
            meta["extractor"] = "ffmpeg"
            audio_duration = _ffprobe_duration_seconds(wav_path)

        wav_bytes = Path(wav_path).read_bytes()
        meta["ok"] = True
        meta["audio_duration_sec"] = audio_duration
        meta["sample_rate"] = sample_rate
        meta["extracted_wav_bytes"] = len(wav_bytes)
        return wav_bytes, meta
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
