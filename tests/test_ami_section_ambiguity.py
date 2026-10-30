"""Ambiguous numbered sections: identical chords use the first and say so; differing chords ask; Claude is never called until resolved."""

from __future__ import annotations

import json

import pytest

from music_coach_ami import claude_enrichment as ce
from music_coach_ami import claude_usage as cu
from music_coach_ami.claude_client import AnthropicTransport, TransportResult
from music_coach_ami.composer import compose_coach_markdown
from music_coach_ami.musical_idea_knowledge import resolve_chart_section, resolve_practice_section_target
from music_coach_ami.pipeline import run_coach_submit
from tests.claude_enrichment_fixtures import FAKE_KEY, make_settings

SAME = {"Intro": ["C", "G"], "Verse 1": ["C", "G", "Am", "F"], "Verse 2": ["C", "G", "Am", "F"], "Chorus": ["F", "G"]}
DIFFERENT = {"Intro": ["C", "G"], "Verse 1": ["C", "G", "Am", "F"], "Verse 2": ["Am", "F", "C", "G"], "Chorus": ["F", "G"]}
THREE_ONE_ODD = {"Verse 1": ["C", "G"], "Verse 2": ["C", "G"], "Verse 3": ["Am", "F"]}


# ---- resolver ---------------------------------------------------------------------------------------------------
def test_identical_numbered_sections_select_first_and_identify_it():
    res = resolve_chart_section("verse", chart_sections=SAME)
    assert res["ok"] and res["section"] == "Verse 1" and res["alternates"] == ["Verse 2"]
    assert res["same_progression_alternates"] is True
    assert "Verse 1" in res["resolution_note"] and "Verse 2" in res["resolution_note"]
    assert "same chords" in res["resolution_note"]


def test_three_identical_sections_are_all_named_in_the_note():
    sections = {"Verse 1": ["C"], "Verse 2": ["C"], "Verse 3": ["C"]}
    res = resolve_chart_section("verse", chart_sections=sections)
    assert res["ok"] and res["section"] == "Verse 1"
    assert "Verse 2 and Verse 3" in res["resolution_note"] and "have the same chords" in res["resolution_note"]


def test_differing_numbered_sections_are_ambiguous_and_not_chosen():
    res = resolve_chart_section("verse", chart_sections=DIFFERENT)
    assert res["ok"] is False and res["ambiguous"] is True
    assert res["section"] == "" and res["chords"] == [] and res["explicit"] is True
    assert res["candidates"] == ["Verse 1", "Verse 2"]
    assert "Verse 1 and Verse 2" in res["message"] and "Which one" in res["message"]


def test_one_odd_section_out_is_still_ambiguous():
    res = resolve_chart_section("verse", chart_sections=THREE_ONE_ODD)
    assert res["ambiguous"] is True and res["candidates"] == ["Verse 1", "Verse 2", "Verse 3"]


def test_exact_name_always_beats_numbered_variants_even_when_they_differ():
    sections = {"Verse": ["C", "G"], "Verse 1": ["Am"], "Verse 2": ["F"]}
    res = resolve_chart_section("verse", chart_sections=sections)
    assert res["ok"] and res["section"] == "Verse" and not res.get("ambiguous") and not res.get("alternates")


def test_naming_the_numbered_section_is_never_ambiguous():
    res = resolve_chart_section("verse 2", chart_sections=DIFFERENT)
    assert res["ok"] and res["section"] == "Verse 2" and not res.get("ambiguous")


def test_single_variant_and_chorus_prep_behaviour_is_unchanged():
    wonder = {"Chorus Prep / Bridge": ["Cadd9"], "Chorus": ["Em7"]}
    assert resolve_chart_section("chorus", chart_sections=wonder)["section"] == "Chorus"
    assert resolve_chart_section("verse", chart_sections={"Verse 1": ["C"]})["section"] == "Verse 1"


def test_missing_section_message_is_preserved():
    res = resolve_chart_section("bridge", chart_sections=SAME)
    assert res["ok"] is False and not res.get("ambiguous")
    assert "doesn't have a section labeled" in res["message"] and "Available sections" in res["message"]


def test_practice_target_passes_the_ambiguity_through():
    res = resolve_practice_section_target("How should I practice the Verse?", chart_sections=DIFFERENT)
    assert res["ok"] is False and res["ambiguous"] is True and res["section"] == ""
    ok = resolve_practice_section_target("How should I practice the Verse?", chart_sections=SAME)
    assert ok["ok"] and ok["section"] == "Verse 1"


def test_real_catalog_wonderwall_chorus_is_exact_and_verse_is_ambiguous_because_verse_3_differs():
    from song_catalog.catalog import _merge_records

    rec = next(r for r in _merge_records() if r["title"] == "Wonderwall")
    sections = {k: list(v) for k, v in rec["sections"].items()}
    assert resolve_chart_section("chorus", chart_sections=sections)["section"] == "Chorus"
    verse = resolve_chart_section("verse", chart_sections=sections)
    assert verse["ambiguous"] is True and verse["candidates"] == ["Verse 1", "Verse 2", "Verse 3"]
    assert resolve_chart_section("verse 3", chart_sections=sections)["section"] == "Verse 3"
    assert sections["Verse 1"] == sections["Verse 2"] != sections["Verse 3"]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("How should I practice the Verse 2 of this song?", "verse 2"),
        ("practice the chorus 3", "chorus 3"),
        ("work on the bridge 2 today", "bridge 2"),
        ("How should I practice the Verse of this song?", "verse"),
        ("practice the verse in 4/4", "verse"),
    ],
)
def test_numbered_section_names_in_the_question_are_extracted_exactly(question, expected):
    from music_coach_ami.musical_idea_knowledge import extract_requested_section

    assert extract_requested_section(question) == expected


def test_numbered_request_resolves_to_exactly_that_section():
    res = resolve_practice_section_target("How should I practice the Verse 2 of this song?", chart_sections=DIFFERENT)
    assert res["ok"] and res["section"] == "Verse 2" and not res.get("ambiguous")


# ---- end to end through the real AMI pipeline, mocked transport ---------------------------------------------------
class _Transport:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete(self, **kw):
        self.calls.append(kw)
        facts = json.loads(kw["user"].split("FACTS (verified from the active song chart):\n", 1)[1].split("\n\nEXISTING ANSWER", 1)[0])
        section, chords = next(iter(facts["chords_by_section"].items()))
        text = json.dumps(
            {
                "why_this_fits": "The {{section:%s}} moves {{chord:%s}} to {{chord:%s}}." % (section, chords[0], chords[1]),
                "guidance": [
                    "Drill {{chord:%s}} into {{chord:%s}} as a two-chord loop." % (chords[0], chords[1]),
                    "Join the pair back into the full {{section:%s}}." % section,
                ],
                "listen_for": [],
            }
        )
        usage = {"input_tokens": 1000, "output_tokens": 300, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        return TransportResult(text=text, usage=usage, request_id="req_fake", stop_reason="end_turn", model=kw["model"])


@pytest.fixture
def harness(tmp_path, monkeypatch):
    t = _Transport()
    monkeypatch.setattr(AnthropicTransport, "complete", lambda self, **kw: (_ for _ in ()).throw(AssertionError("LIVE API CALL")))
    monkeypatch.setenv(cu.LEDGER_ENV, str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr("anthropic_secrets_config.resolve_anthropic_api_key", lambda: (FAKE_KEY, object()))
    monkeypatch.setattr(ce, "AnthropicTransport", lambda key: t)
    monkeypatch.setattr(ce, "load_claude_settings", lambda: make_settings())
    return t


def _submit(question, sections, *, enrich=True):
    state = {"_ami_claude_dev_mode": True, "ami_claude_dev_enabled": enrich}
    ctx = {
        "instrument": "Flute",
        "level": "Intermediate",
        "focus": "Chord changes",
        "active_song": {"title": "Say", "key": "C", "default_key": "C"},
        "chart_sections": {k: list(v) for k, v in sections.items()},
        "chart_sections_key": "C",
        "bpm": 96,
        "practice_key_hint": "C",
    }
    _req, resp = run_coach_submit(question, state, ami_ctx=ctx)
    return resp


def test_ambiguous_section_asks_and_never_calls_claude(harness):
    resp = _submit("How should I practice the Verse of this song?", DIFFERENT)
    md = compose_coach_markdown(resp)
    assert "Which one do you want to practice?" in md and "Verse 1 and Verse 2" in md
    assert harness.calls == []
    assert resp.enrichment is None
    diag = resp.diagnostics
    assert diag["fallback_reason"] == "section_ambiguous" and diag["resolved_section"] == ""
    assert diag["ai_enrichment"]["reason"] == "section_ambiguous"
    assert "Loop **4–8 bars**" not in md and "practice **Verse 1** as the target" not in md


def test_identical_sections_use_first_say_so_and_enrich_once(harness):
    resp = _submit("How should I practice the Verse of this song?", SAME)
    md = compose_coach_markdown(resp)
    assert "practice **Verse 1** as the target" in md
    assert "Using **Verse 1**" in md and "Verse 2" in md and "same chords" in md
    assert len(harness.calls) == 1 and resp.enrichment is not None
    assert harness.calls[0]["user"].count('"target_section": "Verse 1"') == 1


def test_naming_the_exact_section_resolves_and_enriches(harness):
    resp = _submit("How should I practice the Verse 2 of this song?", DIFFERENT)
    md = compose_coach_markdown(resp)
    assert "Which one" not in md and len(harness.calls) == 1


def test_missing_section_behaviour_is_unchanged(harness):
    resp = _submit("How should I practice the Bridge of this song?", SAME)
    assert not resp.diagnostics.get("section_resolution", {}).get("ambiguous")
    assert resp.diagnostics.get("fallback_reason") != "section_ambiguous"
    assert "Which one" not in compose_coach_markdown(resp)


def test_deterministic_answer_for_identical_sections_is_unchanged_when_enrichment_is_off(harness):
    off = compose_coach_markdown(_submit("How should I practice the Verse of this song?", SAME, enrich=False))
    on = _submit("How should I practice the Verse of this song?", SAME, enrich=True)
    assert harness.calls and compose_coach_markdown(on).startswith(off)
    assert on.direct_answer in off
