"""Nothing above the Lead Sheet comes and goes, so Streamlit never re-creates it mid-take.

Browser measurement (Just the Two of Us, 1500 / 390 px), each one a sheet that moved up and
was re-created, leaving the music paused:
- Play, then Open lead sheet. The opening run keeps the page player (4 elements) until the
  sheet's player takes over; the next run dropped it (any widget, Chord Tone Hints
  included, could be that run).
- Card Resume with the sheet open hid the "▶ Play Backing Track ..." caption above it.
Both are now the content of one always-present container, shown or not.

Opened over a paused take, the sheet's player takes the paused place (it mounted at 0:00
unless an earlier render's props happened to be frozen) and becomes the paused take, so
the card's Resume continues there instead of in the retired page player.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def test_page_player_block_lives_in_an_always_present_container() -> None:
    slot = 'with st.container(key="backing_page_player_slot"):\n'
    assert APP.count(slot) == 1
    before, after = APP.split(slot, 1)
    head = after.split("\n")
    # The container itself is unconditional (function-body level); the player block is its content.
    assert before.endswith("\n    ")
    assert head[0].startswith("        if _backing_audio_ready and (not _leadsheet_open or _sheet_taking_over)")
    assert head[1].strip().startswith('"_backing_transport_user_stopped"')
    assert head[3].strip() == 'st.markdown("#### Audio player")'


def test_play_hint_above_the_sheet_is_always_present() -> None:
    slot = 'with st.container(key="backing_leadsheet_play_hint_slot"):\n'
    assert APP.count(slot) == 1
    before, after = APP.split(slot, 1)
    assert before.endswith("\n        ")
    head = after.split("\n")
    assert head[0].strip() == "if not st.session_state.get(BACKING_AUTOPLAY, False):"
    assert "▶ Play Backing Track on the song card plays the track with this chart." in after.split("_karaoke_active", 1)[0]
    # No second, unwrapped copy of the caption.
    assert APP.count("▶ Play Backing Track on the song card plays the track with this chart.") == 1


def test_sheet_opened_over_a_paused_take_takes_its_place() -> None:
    assert "sheet_open_handoff=bool(_ls_handoff_autoplay)," in APP
    assert "sheet_open_handoff=bool(_ls_handoff_autoplay and _ls_autoplay)" not in APP
    paused = APP.split("if (h.playing === false) {{", 1)[1].split("return;", 1)[0]
    assert "audio.pause();" in paused
    assert "window.parent.__backingPausedTake = {{" in paused
    assert "el: audio," in paused
    # The card's identity for the sheet's player, never its data: URL.
    assert '"live-audio:" + (isFinite(audio.duration) ? audio.duration.toFixed(2) : "?")' in paused
    assert "currentSrc" not in paused
