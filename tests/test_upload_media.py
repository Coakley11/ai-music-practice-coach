"""Upload media helpers (video detection and audio prep)."""

from __future__ import annotations

import pytest

from upload_media import (
    VideoExtractionError,
    VIDEO_EXTRACTION_UNAVAILABLE_MSG,
    _resolve_ffmpeg_exe,
    extract_audio_from_video,
    ffmpeg_status,
    is_audio_filename,
    is_video_filename,
    prepare_upload_for_analysis,
)


def test_video_extension_detection():
    assert is_video_filename("take.MP4")
    assert is_video_filename("clip.mov")
    assert not is_video_filename("song.mp3")
    assert is_audio_filename("song.wav")


def test_prepare_upload_passthrough_audio():
    data, name, meta = prepare_upload_for_analysis(b"RIFF", "clip.wav")
    assert data == b"RIFF"
    assert name == "clip.wav"
    assert meta.get("was_video") is False


def test_extract_audio_from_video_requires_librosa_or_ffmpeg(monkeypatch, tmp_path):
    pytest.importorskip("numpy")
    try:
        import librosa  # noqa: F401
        import soundfile  # noqa: F401
    except ImportError:
        pytest.skip("librosa/soundfile not installed")

    import soundfile as sf
    import numpy as np

    wav_path = tmp_path / "fake.mp4"
    sr = 22050
    y = np.zeros(sr, dtype=np.float32)
    sf.write(str(wav_path), y, sr)
    video_bytes = wav_path.read_bytes()

    out_bytes, meta = extract_audio_from_video(video_bytes, "fake.mp4")
    assert meta.get("ok") is True
    assert meta.get("was_video") is True
    assert len(out_bytes) > 44
    assert out_bytes[:4] == b"RIFF"


def test_ffmpeg_status_keys():
    status = ffmpeg_status()
    assert "ffmpeg_detected" in status
    assert "ffmpeg_path" in status
    assert "ffmpeg_backend" in status
    assert "ffmpeg_version" in status
    assert "ffprobe_detected" in status
    assert "ffprobe_path" in status


def test_video_extraction_error_when_no_backend(monkeypatch, tmp_path):
    pytest.importorskip("numpy")
    try:
        import librosa  # noqa: F401
    except ImportError:
        pytest.skip("librosa not installed")

    monkeypatch.setattr("upload_media._resolve_ffmpeg_exe", lambda: ("", ""))

    bad_path = tmp_path / "broken.mp4"
    bad_path.write_bytes(b"not-a-video")
    with pytest.raises(VideoExtractionError) as exc_info:
        extract_audio_from_video(bad_path.read_bytes(), "broken.mp4")
    assert VIDEO_EXTRACTION_UNAVAILABLE_MSG in str(exc_info.value)
    assert exc_info.value.meta.get("failed_step") in {"ffmpeg_missing", "all_backends_failed"}
    assert exc_info.value.meta.get("ffmpeg_detected") is False
    assert exc_info.value.meta.get("file_type") == ".mp4"


def test_resolve_ffmpeg_prefers_system(monkeypatch):
    monkeypatch.setattr("upload_media.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    path, backend = _resolve_ffmpeg_exe()
    assert path == "/usr/bin/ffmpeg"
    assert backend == "system"


def test_extract_mp4_with_bundled_ffmpeg(monkeypatch, tmp_path):
    try:
        import imageio_ffmpeg  # noqa: F401
    except ImportError:
        pytest.skip("imageio-ffmpeg not installed")

    bundled = _resolve_ffmpeg_exe()
    if not bundled[0]:
        pytest.skip("No ffmpeg backend available in test environment")

    ffmpeg_exe, backend = bundled
    mp4_path = tmp_path / "tone.mp4"

    import subprocess

    proc = subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "0.5",
            "-c:a",
            "aac",
            str(mp4_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0 or not mp4_path.is_file():
        pytest.skip(f"Could not synthesize MP4 with ffmpeg ({backend}): {proc.stderr[:200]}")

    monkeypatch.setattr("upload_media._resolve_ffmpeg_exe", lambda: (ffmpeg_exe, backend))
    out_bytes, meta = extract_audio_from_video(mp4_path.read_bytes(), "tone.mp4")
    assert meta.get("ok") is True
    assert meta.get("extractor", "").startswith("ffmpeg")
    assert meta.get("ffmpeg_backend") == backend
    assert meta.get("extraction_success") is True
    assert len(out_bytes) > 44
    assert out_bytes[:4] == b"RIFF"
