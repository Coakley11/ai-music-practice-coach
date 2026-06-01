"""Upload media helpers (video detection and audio prep)."""

from __future__ import annotations

import pytest

from upload_media import (
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
