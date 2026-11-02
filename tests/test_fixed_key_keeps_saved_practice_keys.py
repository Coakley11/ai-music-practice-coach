"""Fixed Key is a temporary override; each song's saved Practice Key stays untouched.

While Fixed Key holds, every reader of a song's Practice Key sees the fixed pair's
major/minor member (E♭ major / C minor: E♭ for a major song, Cm for a minor one), no
Practice Key control can change it, and nothing writes over the song's own saved key.
Turning Fixed Key off returns the song to that saved key, or to its Original Key when
it never had one. Generated Jam / Mission / Style Jam keys keep their own exception.

Before this, turning Fixed Key on (and every song visited while it was on) rewrote the
song's saved key to the family member and dropped its "chosen by the musician" stamp,
and the Songs card kept an editable dropdown that wrote straight through the lock.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from practice_key_mode import (
    MODE_FIXED,
    PRACTICE_KEY_MODE_WIDGET_KEY,
    disable_fixed_practice_key_mode,
    on_practice_key_mode_change,
    practice_key_edit_locked,
    resolve_practice_concert_key_for_song,
    set_fixed_practice_key_family,
    set_practice_key_mode,
)
from songs.key_state import PENDING_DISPLAY_KEY
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    catalog_pick_has_user_practice_key_override,
    clear_practice_concert_key,
    clear_practice_key_user_override,
    composition_practice_key_choice,
    get_practice_concert_key,
    mark_practice_key_user_override,
    record_composition_practice_key_choice,
    reset_practice_key_to_original_on_source_switch,
    saved_practice_concert_key,
    set_practice_concert_key,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY

ROOT = Path(__file__).resolve().parents[1]
LEAVES = "Jazz\x1fAutumn Leaves"  # G minor
SAY = "Pop\x1fSay — John Mayer"  # C major
CUSTOM = "custom::trial-song-uuid"
COMPOSITION = "composition::my-composition-uuid"


def _session(pick: str = LEAVES, original: str = "Gm") -> dict:
    return {
        "studio_page": "picker",
        ACTIVE_CATALOG_PICK_KEY: pick,
        "selected_song": {"song": "Autumn Leaves", "key": original, "genre": "Jazz"},
    }


def _choose(s: dict, pick: str, key: str) -> None:
    """A Practice Key the musician picked in standard mode."""
    set_practice_concert_key(s, key, pick_key=pick, allow_restore_original=True)
    mark_practice_key_user_override(s, pick)


def _fix(s: dict, family: str = "Eb|C", original: str = "Gm") -> None:
    set_fixed_practice_key_family(s, family)
    s[PRACTICE_KEY_MODE_WIDGET_KEY] = MODE_FIXED
    on_practice_key_mode_change(s, original_key=original)


def _raw(s: dict, pick: str) -> str:
    return str((s.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}).get(pick) or "")


def test_turning_fixed_key_on_leaves_the_saved_key_alone() -> None:
    s = _session()
    _choose(s, LEAVES, "Am")
    _fix(s)
    assert _raw(s, LEAVES) == "Am"
    assert catalog_pick_has_user_practice_key_override(s, LEAVES)
    assert saved_practice_concert_key(s, LEAVES) == "Am"
    # Every reader sees the fixed pair's minor member.
    assert get_practice_concert_key(s, LEAVES, default="Gm") == "Cm"
    assert resolve_practice_concert_key_for_song(s, "Gm", pick_key=LEAVES) == "Cm"
    assert s[PENDING_DISPLAY_KEY] == "Cm"


def test_major_and_minor_songs_take_their_own_side_of_the_pair() -> None:
    s = _session(SAY, "C")
    _choose(s, SAY, "D")
    _choose(s, LEAVES, "Am")
    _fix(s, original="C")
    assert get_practice_concert_key(s, SAY, default="C") == "Eb"
    assert get_practice_concert_key(s, LEAVES, default="Gm") == "Cm"


def test_no_writer_can_change_a_saved_key_while_fixed() -> None:
    s = _session()
    _choose(s, LEAVES, "Am")
    _fix(s)
    set_practice_concert_key(s, "Dm", pick_key=LEAVES, allow_restore_original=True)
    set_practice_concert_key(s, "Dm", pick_key=LEAVES, commit_catalog_practice_key=True)
    clear_practice_key_user_override(s, LEAVES)
    assert clear_practice_concert_key(s, LEAVES) is False
    record_composition_practice_key_choice(s, COMPOSITION, "D")
    mark_practice_key_user_override(s, SAY)
    assert _raw(s, LEAVES) == "Am"
    assert catalog_pick_has_user_practice_key_override(s, LEAVES)
    assert composition_practice_key_choice(s, COMPOSITION) == ""
    assert not catalog_pick_has_user_practice_key_override(s, SAY)
    assert practice_key_edit_locked(s)


def test_turning_fixed_key_off_returns_to_the_saved_key() -> None:
    s = _session()
    _choose(s, LEAVES, "Am")
    _fix(s)
    disable_fixed_practice_key_mode(s, original_key="Gm")
    assert not practice_key_edit_locked(s)
    assert s[PENDING_DISPLAY_KEY] == "Am"
    assert get_practice_concert_key(s, LEAVES) == "Am"


def test_turning_fixed_key_off_from_the_practice_panel_returns_to_the_saved_key() -> None:
    s = _session()
    _choose(s, LEAVES, "Am")
    _fix(s)
    s[PRACTICE_KEY_MODE_WIDGET_KEY] = "standard"
    on_practice_key_mode_change(s, original_key="Gm")
    assert s[PENDING_DISPLAY_KEY] == "Am"


def test_a_song_never_given_a_key_falls_back_to_its_original() -> None:
    s = _session()
    _fix(s)
    assert get_practice_concert_key(s, LEAVES, default="Gm") == "Cm"
    disable_fixed_practice_key_mode(s, original_key="Gm")
    assert s[PENDING_DISPLAY_KEY] == "Gm"


def test_song_switches_while_fixed_keep_each_songs_saved_key() -> None:
    s = _session()
    _choose(s, LEAVES, "Am")
    _choose(s, SAY, "D")
    _fix(s)
    s[ACTIVE_CATALOG_PICK_KEY] = SAY
    assert reset_practice_key_to_original_on_source_switch(s, pick_key=SAY, original_key="C") == "Eb"
    s[ACTIVE_CATALOG_PICK_KEY] = LEAVES
    assert reset_practice_key_to_original_on_source_switch(s, pick_key=LEAVES, original_key="Gm") == "Cm"
    assert (_raw(s, LEAVES), _raw(s, SAY)) == ("Am", "D")
    assert catalog_pick_has_user_practice_key_override(s, SAY)
    s[ACTIVE_CATALOG_PICK_KEY] = SAY
    disable_fixed_practice_key_mode(s, original_key="C")
    assert s[PENDING_DISPLAY_KEY] == "D"


def test_custom_and_composition_songs_keep_their_saved_keys() -> None:
    s = _session(CUSTOM, "D")
    _choose(s, CUSTOM, "F")
    record_composition_practice_key_choice(s, COMPOSITION, "A")
    set_practice_concert_key(s, "A", pick_key=COMPOSITION, allow_restore_original=True)
    _fix(s, original="D")
    assert get_practice_concert_key(s, CUSTOM, default="D") == "Eb"
    assert get_practice_concert_key(s, COMPOSITION, default="G") == "Eb"
    assert (_raw(s, CUSTOM), _raw(s, COMPOSITION)) == ("F", "A")
    assert composition_practice_key_choice(s, COMPOSITION) == "A"


def test_older_overwritten_keys_are_not_guessed() -> None:
    """An earlier version replaced the saved key with the family member.

    Where it also dropped the musician's stamp (every song visited while fixed),
    the leftover is residue and the song returns to its Original Key. Where the
    stamp survived (the song active when Fixed Key was turned on), the stored
    family member is the only saved key there is, and it is kept as is.
    """
    s = _session()
    set_practice_concert_key(s, "Cm", pick_key=LEAVES, allow_restore_original=True)
    set_fixed_practice_key_family(s, "Eb|C")
    set_practice_key_mode(s, MODE_FIXED)
    reset_practice_key_to_original_on_source_switch(s, pick_key=LEAVES, original_key="Gm")
    disable_fixed_practice_key_mode(s, original_key="Gm")
    assert s[PENDING_DISPLAY_KEY] == "Gm"

    s = _session()
    _choose(s, LEAVES, "Cm")
    set_fixed_practice_key_family(s, "Eb|C")
    set_practice_key_mode(s, MODE_FIXED)
    disable_fixed_practice_key_mode(s, original_key="Gm")
    assert s[PENDING_DISPLAY_KEY] == "Cm"


def test_backing_owner_and_key_cycling_start_from_the_fixed_key() -> None:
    from backing_key_cycle import current_backing_owner_practice_key
    from backing_practice_key_control import OWNER_CATALOG, canonical_concert_key_for_owner

    s = _session()
    _choose(s, LEAVES, "Dm")
    _fix(s)
    assert canonical_concert_key_for_owner(s, OWNER_CATALOG) == "Cm"
    s["studio_page"] = "backing"
    assert current_backing_owner_practice_key(s) == "Cm"


def test_generated_jam_keeps_its_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import workflow_key_identity

    s = _session()
    _choose(s, LEAVES, "Am")
    _fix(s)
    monkeypatch.setattr(workflow_key_identity, "generated_workflow_owns_practice_key", lambda _s: True)
    assert not practice_key_edit_locked(s)
    assert get_practice_concert_key(s, LEAVES) == "Am"


def test_songs_card_shows_a_locked_key_and_its_handler_refuses_edits() -> None:
    app = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    selector = app.split("def _render_card_practice_key_selector(", 1)[1].split("\ndef ", 1)[0]
    locked = selector.split("if practice_key_edit_locked(st.session_state):", 1)[1]
    # The locked branch shows the effective key as text and returns before the selectbox.
    assert "resolve_practice_concert_key_for_song(" in locked.split("return", 1)[0]
    assert "ui-practice-key-locked" in locked.split("return", 1)[0]
    assert selector.index("practice_key_edit_locked") < selector.index("st.selectbox(")
    handler = app.split("def _apply_card_practice_key_change(", 1)[1].split("\ndef ", 1)[0]
    body = handler.split('"""', 2)[2]
    assert body.index("practice_key_edit_locked(st.session_state)") < body.index('st.session_state["display_key"] = new_key')


def test_shared_practice_key_callback_refuses_song_edits_while_fixed() -> None:
    src = (ROOT / "creative_key_sync.py").read_text(encoding="utf-8")
    cb = src.split("def on_sidebar_practice_concert_key_change()", 1)[1].split("\ndef ", 1)[0]
    guard = cb.index("practice_key_edit_locked(st.session_state)")
    assert guard < cb.index("mark_display_key_changed(st)")
    assert 'write_owner not in {"mission", "entry_jam"}' in cb[guard - 200 : guard + 200]


def test_backing_audio_renders_the_fixed_key_over_a_stale_card_value() -> None:
    from backing_context import build_regular_song_context, set_backing_context
    from backing_musical_state import resolve_current_backing_musical_state

    s = _session()
    _choose(s, LEAVES, "Dm")
    _fix(s)
    s["studio_page"] = "backing"
    # A late Songs-card value left behind from before the lock.
    s["display_key"] = s["concert_key"] = "Dm"
    set_backing_context(s, build_regular_song_context(s, pick_key=LEAVES))
    state = resolve_current_backing_musical_state(s, rec=s["selected_song"])
    assert state.practice_concert_key == "Cm"
    assert _raw(s, LEAVES) == "Dm"


def _fixed_backing_state(**extra):
    from backing_context import build_regular_song_context, set_backing_context
    from backing_musical_state import resolve_current_backing_musical_state

    s = _session(); _choose(s, LEAVES, "Dm"); _fix(s)
    s.update({"studio_page": "backing", "display_key": "Dm", "concert_key": "Dm"})
    s.update(extra)
    set_backing_context(s, build_regular_song_context(s, pick_key=LEAVES))
    return s, resolve_current_backing_musical_state(s, rec=s["selected_song"])


def test_transposing_instrument_reads_the_fixed_concert_key() -> None:
    from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY

    s, state = _fixed_backing_state(instrument="Trumpet", **{CHART_IN_INSTRUMENT_KEY_KEY: True})
    assert state.practice_concert_key == "Cm"  # what sounds
    assert state.written_key == "Dm"  # B♭ trumpet reads a whole step up
    assert state.chart_display_key == "Dm"
    assert _raw(s, LEAVES) == "Dm"
    assert s["selected_song"]["key"] == "Gm"  # Original Key untouched


def test_capo_shape_charts_over_the_fixed_concert_key() -> None:
    s, state = _fixed_backing_state(instrument="Guitar", guitar_capo_enabled=True, guitar_capo_shape_key="A")
    assert state.practice_concert_key == "Cm"
    assert state.chart_mode == "shape"
    assert state.chart_display_key == "Am"  # A-minor shapes, capo 3, sound C minor
    assert _raw(s, LEAVES) == "Dm"
    assert s["selected_song"]["key"] == "Gm"


@pytest.mark.parametrize(
    ("sax", "written"),
    [("Alto saxophone (Eb)", "Am"), ("Tenor saxophone (Bb)", "Dm")],
)
def test_saxophones_read_the_fixed_concert_key(sax: str, written: str) -> None:
    from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY, SELECTED_TRANSPOSING_INSTRUMENT_KEY

    s, state = _fixed_backing_state(
        instrument="Saxophone",
        **{SELECTED_TRANSPOSING_INSTRUMENT_KEY: sax, CHART_IN_INSTRUMENT_KEY_KEY: True},
    )
    assert state.practice_concert_key == "Cm"  # what sounds
    assert state.written_key == written  # E♭ alto reads a major sixth up, B♭ tenor a whole step up
    assert state.chart_display_key == written
    assert _raw(s, LEAVES) == "Dm"
    assert s["selected_song"]["key"] == "Gm"
