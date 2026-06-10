"""Written-key mode persists across practice-key changes; resets on instrument rules."""

from __future__ import annotations

from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
    chart_in_instrument_key,
    effective_chart_key,
    effective_practice_key,
    preserve_written_key_on_display_key_change,
    resolve_practice_keys,
    sync_written_key_instrument_anchor,
    written_key_for_type,
)


def _state(**kwargs):
    base = {
        WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
        SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
        CHART_IN_INSTRUMENT_KEY_KEY: True,
    }
    base.update(kwargs)
    return base


def test_tenor_written_key_follows_concert_practice_key():
    ss = _state()
    ctx_c = resolve_practice_keys(ss, "C", "Saxophone")
    assert ctx_c["chart_key_mode"] == "written"
    assert ctx_c["chart_key"] == written_key_for_type("C", "Tenor saxophone (Bb)")
    assert ctx_c["chart_key"] == "D"

    ctx_f = resolve_practice_keys(ss, "F", "Saxophone")
    assert chart_in_instrument_key(ss)
    assert ctx_f["chart_key_mode"] == "written"
    assert ctx_f["chart_key"] == "G"


def test_display_key_change_does_not_clear_written_mode():
    ss = _state()
    preserve_written_key_on_display_key_change(ss)
    resolve_practice_keys(ss, "Bb", "Saxophone")
    assert chart_in_instrument_key(ss) is True
    chart_k, mode = effective_chart_key("Bb", "Saxophone", ss)
    assert mode == "written"
    assert chart_k == written_key_for_type("Bb", "Tenor saxophone (Bb)")


def test_switch_to_piano_clears_written_mode():
    ss = _state()
    sync_written_key_instrument_anchor(ss, "Piano")
    assert chart_in_instrument_key(ss) is False
    ctx = resolve_practice_keys(ss, "F", "Piano")
    assert ctx["chart_key"] == "F"
    assert ctx["chart_key_mode"] == "concert"


def test_written_key_spelling_follows_concert_accidental_style():
    assert written_key_for_type("Db", "Alto saxophone (Eb)") == "Bb"
    assert written_key_for_type("F#", "Tenor saxophone (Bb)") == "G#"
    assert written_key_for_type("Ab", "Alto saxophone (Eb)") == "F"
    assert written_key_for_type("C#", "Tenor saxophone (Bb)") == "D#"


def test_effective_practice_key_written_mode_matches_chart_key():
    ss = _state()
    assert effective_practice_key(ss, "Db", "Saxophone") == written_key_for_type(
        "Db", "Tenor saxophone (Bb)"
    )
    assert effective_practice_key(ss, "Db", "Saxophone") == "Eb"


def test_effective_practice_key_concert_when_written_off():
    ss = _state()
    ss[CHART_IN_INSTRUMENT_KEY_KEY] = False
    assert effective_practice_key(ss, "Db", "Saxophone") == "Db"


def test_resolve_practice_keys_includes_effective_practice_key():
    ss = _state()
    ctx = resolve_practice_keys(ss, "F", "Saxophone")
    assert ctx["effective_practice_key"] == ctx["chart_key"] == "G"


def test_switch_sax_to_trumpet_keeps_written_mode():
    ss = _state()
    ss[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Bb Trumpet"
    sync_written_key_instrument_anchor(ss, "Trumpet")
    assert chart_in_instrument_key(ss) is True
    ctx = resolve_practice_keys(ss, "C", "Trumpet")
    assert ctx["chart_key_mode"] == "written"
    assert ctx["chart_key"] == written_key_for_type("C", "Bb Trumpet")
