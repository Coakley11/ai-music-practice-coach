"""Explicit section requests must resolve to the exactly named section, never a longer look-alike."""

from __future__ import annotations

import pytest

from music_coach_ami.musical_idea_knowledge import resolve_chart_section, resolve_practice_section_target

WONDERWALL = {
    "Intro": ["Em7", "G"],
    "Verse 1": ["Em7", "G"],
    "Chorus Prep / Bridge": ["Cadd9", "Dsus4", "Em7"],
    "Chorus": ["Cadd9", "Em7", "G"],
}


def test_chorus_prefers_exact_chorus_over_chorus_prep_bridge():
    res = resolve_chart_section("chorus", chart_sections=WONDERWALL)
    assert res["ok"] and res["section"] == "Chorus"


def test_chorus_does_not_fall_onto_chorus_prep_when_no_chorus_exists():
    only_prep = {k: v for k, v in WONDERWALL.items() if k != "Chorus"}
    res = resolve_chart_section("chorus", chart_sections=only_prep)
    assert not res["ok"] and res["section"] == "" and res["explicit"]
    assert "Chorus" in res["message"] and "Available sections" in res["message"]


def test_practice_target_reports_limitation_instead_of_substituting():
    only_prep = {k: v for k, v in WONDERWALL.items() if k != "Chorus"}
    res = resolve_practice_section_target("How should I practice the Chorus?", chart_sections=only_prep)
    assert not res["ok"] and res["section"] == ""


@pytest.mark.parametrize(
    ("requested", "sections", "expected"),
    [
        ("verse", {"Intro": [], "Verse 1": ["C"], "Verse 2": ["C"]}, "Verse 1"),
        ("chorus", {"Chorus 1": ["G"], "Chorus 2": ["G"]}, "Chorus 1"),
        ("chorus", {"Chorus (final)": ["G"]}, "Chorus (final)"),
        ("bridge", {"Bridge": ["F"], "Chorus Prep / Bridge": ["C"]}, "Bridge"),
        ("b", {"A Section": ["C"], "B Section": ["G"]}, "B Section"),
        ("b", {"Bridge": ["C"], "Part B": ["G"]}, "Part B"),
        ("a", {"A1": ["C"], "A": ["D"]}, "A"),
        ("intro", {"Intro": ["C"]}, "Intro"),
        ("outro", {"Final A / Outro": ["C"], "Outro": ["G"]}, "Outro"),
    ],
)
def test_existing_valid_resolutions_are_preserved(requested, sections, expected):
    res = resolve_chart_section(requested, chart_sections=sections)
    assert res["ok"] and res["section"] == expected


def test_numbered_variants_are_reported_as_alternates_not_hidden():
    res = resolve_chart_section("verse", chart_sections={"Verse 1": ["C"], "Verse 2": ["F"]})
    assert res["section"] == "Verse 1" and res["alternates"] == ["Verse 2"]


def test_bridge_never_matches_via_letter_b():
    res = resolve_chart_section("b", chart_sections={"Bridge": ["C"]})
    assert not res["ok"]
