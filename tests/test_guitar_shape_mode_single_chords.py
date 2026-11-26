"""Guitar Shape Mode shows the playable shapes as the only chord symbols; what sounds never changes.

User, 2026-11-25: concert C - F - G - C with A shapes and capo 3 reads A - D - E - A, with no second line of concert
chords, everywhere. Shape Mode off: the ordinary chart.
"""

from __future__ import annotations

import re

import pytest

from composition_melody_projection import concert_melody_events, project_melody_events
from media_tone_catalog import parse_note_token
from songs.backing_chart import render_backing_chord_chart

CONCERT = {"Verse": ["C", "F", "G", "C"]}


def _cells(html: str) -> list[str]:
    return [re.sub("<[^>]+>", "", c) for c in re.findall(r"<div class='chord-symbol'>(.*?)</div>", html, flags=re.S)]


def _sheet(sections, key="C", shape="A", fret=3, **kw):
    shapes = {n: list(c) for n, c in sections.items()} if shape else None
    return render_backing_chord_chart(
        "Song", {"title": "Song", "key": key}, sections, display_key=key,
        shape_sections=shapes, capo_fret=fret if shape else 0, capo_shape_key=shape, **kw,
    )


def _guitar(**kw):
    return {"instrument": "Guitar", "guitar_capo_enabled": True, "guitar_capo_shape_key": "A", **kw}


def test_c_f_g_c_with_a_shapes_and_capo_3_reads_a_d_e_a():
    html = _sheet(CONCERT)
    assert _cells(html) == ["A", "D", "E", "A"]
    assert " shape</div>" not in html and "capo 3" in html and "Key: C" in html


def test_shape_mode_off_is_the_ordinary_chart():
    assert _cells(_sheet(CONCERT, shape="")) == ["C", "F", "G", "C"]


def test_qualities_extensions_slash_basses_and_split_bars_survive():
    html = _sheet({"A": ["Cmaj7", "Am7b5", "C/E", "G7#9", "F6/9", "C|F", "N.C."]})
    cells = " ".join(_cells(html))
    for want in ("Amaj7", "F#m7b5", "A/C#", "E7#9", "D6/9", "N.C."):
        assert want in cells, (want, cells)
    assert "Cmaj7" not in cells and "C/E" not in cells


def test_the_callers_concert_sections_are_not_changed():
    sections = {"Verse": ["C", "F", "G", "C"]}
    _sheet(sections)
    assert sections == CONCERT


def test_a_minor_song_keeps_its_minor_shapes():
    html = _sheet({"A": ["Fm6", "Db7", "C7", "Fm"]}, key="Fm", shape="Dm", fret=3)
    assert _cells(html) == ["Dm6", "Bb7", "A7", "Dm"] and "Key: Fm" in html


def test_key_cycling_keeps_the_shapes_and_moves_current_next_to_them():
    from backing_key_cycle import display_projection_bundle, project_cycle_display_chord

    for sounding, concert in (("C", ["C", "F", "G"]), ("D", ["D", "G", "A"]), ("Eb", ["Eb", "Ab", "Bb"])):
        s = _guitar()
        assert [project_cycle_display_chord(s, c, sounding_key=sounding) for c in concert] == ["A", "D", "E"]
        assert display_projection_bundle(s, sounding_key=sounding, include_timelines=False)["readingKey"] == "A"


def test_the_creative_lines_and_jam_chips_show_the_shapes(monkeypatch):
    import creative_key_sync as cks

    s = _guitar(concert_key="C", display_key="C")
    assert cks.guitar_shape_sections(s, CONCERT, concert_key="C") == {"Verse": ["A", "D", "E", "A"]}
    assert cks.guitar_shape_sections({"instrument": "Guitar"}, CONCERT, concert_key="C") == CONCERT
    out = []

    class _St:
        def markdown(self, text, **_k):
            out.append(re.sub("<[^>]+>", "", text))

    cks.render_creative_progression_block(_St(), s, CONCERT, concert_key="C")
    text = " ".join(out)
    assert "A · D · E · A" in text and "C · F · G · C" not in text and "Practice concert key" in text


@pytest.mark.parametrize("shape,fret", [("A", 3), ("G", 5), ("C", 0), ("E", 8)])
def test_a_melody_is_fingered_a_capo_below_and_sounds_unchanged(shape, fret):
    events = [{"pitch": "C4"}, {"pitch": "E4"}, {"pitch": "rest"}, {"pitch": "G4"}]
    s = _guitar(guitar_capo_shape_key=shape)
    shown = project_melody_events(events, original_key="C", practice_key="C", instrument="Guitar", session_state=s, written=False)[0]
    plain = project_melody_events(
        events, original_key="C", practice_key="C", instrument="Guitar", session_state={"instrument": "Guitar"}, written=False
    )[0]
    for a, b in zip(shown, plain):
        if a["pitch"] != "rest":
            assert parse_note_token(a["pitch"]) == parse_note_token(b["pitch"]) - fret
    assert concert_melody_events(events, original_key="C", practice_key="C") == [dict(e) for e in events]


def test_another_instrument_ignores_the_guitars_capo():
    s = _guitar(instrument="Piano")
    events = [{"pitch": "C4"}]
    assert project_melody_events(events, original_key="C", practice_key="C", instrument="Piano", session_state=s, written=False)[0] == events


def test_a_cycle_sheet_prepared_before_shape_mode_is_rebuilt_in_shapes():
    """Browser 2026-11-25: Shape Mode switched on while cycling in G left that key's prepared sheet in concert chords."""
    import re as _re

    import backing_key_cycle as kc
    from backing_take_identity import capture_take_request

    s = {"instrument": "Guitar", "guitar_capo_enabled": False, "guitar_capo_shape_key": "D", "_kc_chart_bpm": 100}
    timeline = [{"section": "A", "bar_in_section": i + 1, "chord": c} for i, c in enumerate(["Gmaj7", "C7", "F7", "C7"])]
    s[kc.BACKING_KEY_CYCLE_PREPARED_KEY] = {"G": {
        "take_request": capture_take_request(s, prefetch=True), "chart_html": "<div class='chord-symbol'>Gmaj7</div>",
        "display": kc.cycle_display_signature(s), "timeline": timeline,
    }}
    assert "Gmaj7" in kc.prepared_cycle_chart_html(s, "G")
    s["guitar_capo_enabled"] = True  # Shape Mode on, D shapes
    html = kc.prepared_cycle_chart_html(s, "G")
    cells = [c for c in _re.findall(r"<div class='chord-symbol'>(.*?)</div>", html)]
    assert cells[:4] == ["Dmaj7", "G7", "C7", "G7"] and "capo 5" in html
