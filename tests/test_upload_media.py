"""Upload media helpers (video detection and audio prep)."""

from __future__ import annotations

from pathlib import Path

import pytest

from upload_media import (
    UPLOAD_ACCEPT_TYPES,
    UPLOAD_AUDIO_FILE_TYPES,
    UPLOAD_MAX_SIZE_BYTES,
    UPLOAD_MAX_SIZE_MB,
    UnsupportedUploadTypeError,
    VIDEO_EXTRACTION_UNAVAILABLE_MSG,
    VideoExtractionError,
    _resolve_ffmpeg_exe,
    extract_audio_from_video,
    ffmpeg_status,
    is_accepted_upload_filename,
    is_audio_filename,
    is_video_filename,
    prepare_multitrack_track_payload,
    prepare_upload_for_analysis,
    upload_format_labels,
    upload_max_size_caption,
    validate_upload_filename,
)


def test_canonical_upload_types_include_mp4_and_match_alias():
    assert "mp4" in UPLOAD_AUDIO_FILE_TYPES
    assert UPLOAD_AUDIO_FILE_TYPES == [
        "wav",
        "mp3",
        "m4a",
        "mp4",
        "mov",
        "ogg",
        "flac",
    ]
    assert UPLOAD_ACCEPT_TYPES == UPLOAD_AUDIO_FILE_TYPES
    assert upload_format_labels() == ("WAV", "MP3", "M4A", "MP4", "MOV", "OGG", "FLAC")


def test_canonical_upload_max_size_is_500_mb():
    assert UPLOAD_MAX_SIZE_MB == 500
    assert UPLOAD_MAX_SIZE_BYTES == 500 * 1024 * 1024
    assert upload_max_size_caption() == "Maximum file size: 500 MB"


def test_streamlit_config_max_upload_size_matches_canonical():
    text = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert "maxUploadSize = 500" in text
    assert str(UPLOAD_MAX_SIZE_MB) in text


def test_format_chips_html_includes_size_limit_copy():
    from app_ui import upload_format_chips_html

    html = upload_format_chips_html()
    for label in upload_format_labels():
        assert label in html
    assert "Maximum file size: 500 MB" in html
    assert upload_max_size_caption() in html


def test_streamlit_analysis_uploaders_use_canonical_types_and_size_limit():
    text = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
    assert 'type=["wav", "mp3", "m4a", "ogg"]' not in text
    assert "type=UPLOAD_AUDIO_FILE_TYPES" in text
    # Single + Multitrack Upload Analysis + Multitrack Studio slots
    assert text.count("type=UPLOAD_AUDIO_FILE_TYPES") >= 3
    assert text.count("max_upload_size=UPLOAD_MAX_SIZE_MB") >= 3
    assert "analysis_audio_upload" in text
    assert "analysis_multitrack_upload" in text
    assert "mt_upload_{slot}" in text
    assert "Maximum file size: 500 MB" in text or "upload_max_size_caption" in text


def test_mission_upload_capture_uses_canonical_types_and_size_limit():
    text = Path("mission_upload_recording_ui.py").read_text(encoding="utf-8")
    assert "type=UPLOAD_AUDIO_FILE_TYPES" in text
    assert 'type=["wav", "mp3", "m4a", "ogg", "flac"]' not in text
    assert "max_upload_size=UPLOAD_MAX_SIZE_MB" in text
    assert "upload_max_size_caption" in text


def test_video_extension_detection():
    assert is_video_filename("take.MP4")
    assert is_video_filename("clip.mov")
    assert not is_video_filename("song.mp3")
    assert is_audio_filename("song.wav")
    assert is_accepted_upload_filename("take.mp4")
    assert is_accepted_upload_filename("song.flac")
    assert not is_accepted_upload_filename("clip.xyz")


def test_unsupported_extension_validation_message():
    with pytest.raises(UnsupportedUploadTypeError) as exc_info:
        validate_upload_filename("solo.xyz")
    assert "Unsupported file type" in str(exc_info.value)
    assert "MP4" in str(exc_info.value)
    with pytest.raises(UnsupportedUploadTypeError):
        prepare_upload_for_analysis(b"data", "solo.xyz")


def test_prepare_upload_passthrough_audio():
    data, name, meta = prepare_upload_for_analysis(b"RIFF", "clip.wav")
    assert data == b"RIFF"
    assert name == "clip.wav"
    assert meta.get("was_video") is False


@pytest.mark.parametrize("ext", ["wav", "mp3", "m4a", "ogg", "flac"])
def test_accepted_audio_extensions_passthrough(ext):
    data, name, meta = prepare_upload_for_analysis(b"bytes", f"take.{ext}")
    assert name == f"take.{ext}"
    assert meta.get("was_video") is False
    assert data == b"bytes"


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

    prepared = prepare_multitrack_track_payload(mp4_path.read_bytes(), "tone.mp4")
    assert prepared["filename"].endswith(".wav")
    assert prepared["bytes"][:4] == b"RIFF"
    assert prepared["upload_meta"].get("was_video") is True


def test_mp4_without_usable_audio_surfaces_error(monkeypatch, tmp_path):
    bundled = _resolve_ffmpeg_exe()
    if not bundled[0]:
        pytest.skip("No ffmpeg backend available in test environment")

    ffmpeg_exe, backend = bundled
    mp4_path = tmp_path / "silent_video_only.mp4"
    import subprocess

    # Color bars only — no audio stream.
    proc = subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x120:d=0.3",
            "-an",
            str(mp4_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0 or not mp4_path.is_file():
        pytest.skip(f"Could not synthesize video-only MP4: {proc.stderr[:200]}")

    monkeypatch.setattr("upload_media._resolve_ffmpeg_exe", lambda: (ffmpeg_exe, backend))
    with pytest.raises(VideoExtractionError) as exc_info:
        prepare_upload_for_analysis(mp4_path.read_bytes(), "silent_video_only.mp4")
    msg = str(exc_info.value).lower()
    assert "audio" in msg or "extract" in msg
    assert exc_info.value.meta.get("ok") is False
