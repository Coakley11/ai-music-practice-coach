"""Source-level contracts for the Backing async completion/install boundary."""

from pathlib import Path


APP_SOURCE = (
    Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
).read_text(encoding="utf-8")


def _generation_block() -> str:
    return APP_SOURCE.split("_wav_pending = False", 1)[1].split(
        "if _play_clicked:", 1
    )[0]


def test_pending_or_failed_wav_cannot_reach_b64_install_writer() -> None:
    generation = _generation_block()
    gate = generation.index("if _wav_pending or _wav_failed:")
    writer = generation.index(
        'st.session_state["_last_backing_wav_b64"] = _b64'
    )

    assert gate < writer
    assert "_arr_stale = bool(_wav_pending or _wav_failed)" in generation
    assert "if not _wav_pending and not _wav_failed:" in generation


def test_completed_background_build_is_a_generation_trigger() -> None:
    assert "_async_wav_ready = backing_wav_build_ready" in APP_SOURCE
    assert (
        "(_play_clicked and not _backing_audio_ready) or _async_wav_ready"
        in APP_SOURCE
    )


def test_poller_leaves_marker_for_full_run_consumer() -> None:
    poller = APP_SOURCE.split(
        "def _render_backing_wav_building_poller", 1
    )[1].split("BACKING_WAV_BUILDING_KEY", 1)[0]

    assert "backing_wav_build_ready" in poller
    assert "st.rerun(scope=\"app\")" in poller
    assert "_backing_clear_wav_building" not in poller


def test_generation_failure_has_bounded_non_autoplay_state() -> None:
    generation = _generation_block()
    failure = generation.split("if _wav_failed:", 1)[1].split(
        "elif _wav_pending:", 1
    )[0]

    assert 'st.session_state[BACKING_TRANSPORT_STATUS] = "error"' in failure
    assert "st.session_state[BACKING_AUTOPLAY] = False" in failure
    assert 'st.session_state.pop("_backing_play_request", None)' in failure
    assert "st.rerun()" not in failure
