"""Upload media helpers (video detection and audio prep)."""

from __future__ import annotations

import pytest

from upload_media import (
    VideoExtractionError,
    VIDEO_EXTRACTION_UNAVAILABLE_MSG,
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

    # Minimal valid WAV as fake "video" path — librosa can load wav regardless of extension.
    import soundfile as sf
    import numpy as np

    wav_path = tmp_path / "fake.mp4"
    sr = 22050
    y = np.zeros(sr, dtype=np.float32)
    sf.write(str(wav_path), y, sr)
    video_bytes = wav_path.read_bytes()

    out_bytes, meta = __import__(
        "upload_media", fromlist=["extract_audio_from_video"]
    ).extract_audio_from_video(video_bytes, "fake.mp4")
    assert meta.get("ok") is True
    assert meta.get("was_video") is True
    assert len(out_bytes) > 44
    assert out_bytes[:4] == b"RIFF"


def test_ffmpeg_status_keys():
    status = ffmpeg_status()
    assert "ffmpeg_detected" in status
    assert "ffmpeg_path" in status
    assert "ffprobe_detected" in status
    assert "ffprobe_path" in status


def test_video_extraction_error_when_ffmpeg_missing(monkeypatch, tmp_path):
    pytest.importorskip("numpy")
    try:
        import librosa  # noqa: F401
    except ImportError:
        pytest.skip("librosa not installed")

    monkeypatch.setattr("upload_media.shutil.which", lambda _name: None)

    import numpy as np
    import soundfile as sf

    bad_path = tmp_path / "broken.mp4"
    bad_path.write_bytes(b"not-a-video")
    with pytest.raises(VideoExtractionError) as exc_info:
        __import__(
            "upload_media", fromlist=["extract_audio_from_video"]
        ).extract_audio_from_video(bad_path.read_bytes(), "broken.mp4")
    assert VIDEO_EXTRACTION_UNAVAILABLE_MSG in str(exc_info.value)
    assert exc_info.value.meta.get("failed_step") == "ffmpeg_missing"
    assert exc_info.value.meta.get("ffmpeg_detected") is False
    assert exc_info.value.meta.get("file_type") == ".mp4"
