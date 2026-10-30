"""Schema and factual-grounding validation of Claude enrichment payloads."""

from __future__ import annotations

import copy

import pytest

from music_coach_ami.claude_facts import build_fact_sheet
from music_coach_ami.claude_validate import validate_enrichment
from tests.claude_enrichment_fixtures import GOOD_PAYLOAD, make_req, make_resp


@pytest.fixture()
def facts():
    f, reason = build_fact_sheet(make_req(), make_resp())
    assert reason == "ok" and f is not None
    return f


def _payload(**overrides):
    p = copy.deepcopy(GOOD_PAYLOAD)
    p.update(overrides)
    return p


def test_valid_payload_accepted_and_markers_rendered(facts):
    res = validate_enrichment(GOOD_PAYLOAD, facts)
    assert res.ok, res.violations
    assert "**Dm7**" in res.enrichment.why and "**Verse**" in res.enrichment.why
    assert "75 BPM" in res.enrichment.guidance[1]
    assert "{{" not in "".join(res.enrichment.guidance)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Practice {{chord:Fm7}} slowly.", "chord_not_in_facts:Fm7"),
        ("Practice Gmaj7 slowly.", "unmarked_musical_token:Gmaj7"),
        ("Practice Bb7 slowly.", "unmarked_musical_token:Bb7"),
        ("Stay in {{key:Eb}} here.", "key_not_in_facts:Eb"),
        ("Jump to the {{section:Bridge}}.", "section_not_in_facts:Bridge"),
        ("Try {{bpm:140}} BPM.", "bpm_not_in_facts:140"),
        ("Try 140 BPM today.", "bpm_not_in_facts:140"),
        ("Land on F first.", "unmarked_musical_token:F"),
        ("Play it in B flat.", "unmarked_note_name"),
        ("Use a Dorian sound here.", "unsupported_theory:dorian"),
        ("Use the blues scale here.", "unsupported_theory:blues scale"),
        ("The song modulates up a step.", "unsupported_claim:modulates"),
        ("Match the original recording.", "unsupported_claim:recording"),
        ("Work on bar 5 first.", "unsupported_bar_reference"),
        ("See https://example.com now.", "format:url"),
        ("Use **bold** text.", "format:emphasis"),
        ("Open the {{chord:Dm7 now.", "malformed_marker"),
    ],
)
def test_unsupported_content_is_rejected(facts, text, code):
    res = validate_enrichment(_payload(guidance=[text, "Loop it slowly with a metronome."]), facts)
    assert not res.ok
    assert code in res.violations
    assert res.enrichment is None


def test_article_a_and_ordinary_words_are_not_flagged(facts):
    res = validate_enrichment(
        _payload(guidance=["A slow loop helps. Add a click and Be patient.", "Check Dynamics and Clean endings."]),
        facts,
    )
    assert res.ok, res.violations


def test_bpm_from_existing_answer_and_chart_tempo_allowed(facts):
    assert set(facts.allowed_bpm) == {75, 100}
    res = validate_enrichment(_payload(guidance=["Start near {{bpm:100}} later.", "Use {{bpm:75}} first."]), facts)
    assert res.ok, res.violations


def test_chord_with_pipe_in_chart_is_split_into_allowed_tokens():
    f, _ = build_fact_sheet(make_req(), make_resp(section="Chorus"))
    assert {"Am7", "D7", "G7", "Cmaj7"} <= set(f.allowed_chords())


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("G:3.5", ["G"]),
        ("C:0.5p", ["C"]),
        ("G:3.5 C:0.5p", ["G", "C"]),
        ("Dm7|G7", ["Dm7", "G7"]),
        ("Cmaj7:4 Cmaj7:4", ["Cmaj7"]),
        ("N.C.", []),
        ("-", []),
        ("Bb7/D:2", ["Bb7/D"]),
        ("", []),
    ],
)
def test_beat_annotated_chart_tokens_become_bare_chords(entry, expected):
    from music_coach_ami.claude_facts import split_chord_entry

    assert split_chord_entry(entry) == expected


def test_facts_from_beat_annotated_chart_contain_only_real_chords():
    chart = {
        "chart_available": True,
        "sections_in_practice_key": True,
        "chart_sections": {"Chorus 1": ["G:3.5", "C:0.5p", "C:4", "Em7:4", "D:4", "D:2"]},
        "practice_key": "G",
        "original_key": "G",
        "bpm": 82,
    }
    f, reason = build_fact_sheet(make_req(chart=chart), make_resp(section="Chorus 1"))
    assert reason == "ok"
    assert f.sections[0][1] == ("G", "C", "Em7", "D")
    import json

    assert json.loads(f.facts_json())["chords_by_section"] == {"Chorus 1": ["G", "C", "Em7", "D"]}
    assert validate_enrichment(
        {"why_this_fits": "{{chord:G}} to {{chord:C}} drives the {{section:Chorus 1}}.",
         "guidance": ["Loop {{chord:Em7}} to {{chord:D}}.", "Count the change aloud."], "listen_for": []},
        f,
    ).ok
    assert not validate_enrichment(
        {"why_this_fits": "{{chord:G:3.5}} drives it.", "guidance": ["Loop it slowly.", "Count aloud."], "listen_for": []},
        f,
    ).ok


@pytest.mark.parametrize(
    "bad",
    [
        "not an object",
        {"guidance": ["a", "b"], "why_this_fits": "ok", "listen_for": [], "extra": 1},
        {"why_this_fits": "", "guidance": ["a b", "c d"], "listen_for": []},
        {"why_this_fits": "ok", "guidance": ["only one"], "listen_for": []},
        {"why_this_fits": "ok", "guidance": ["a", "b", "c", "d", "e"], "listen_for": []},
        {"why_this_fits": "ok", "guidance": ["a", 7], "listen_for": []},
        {"why_this_fits": "ok", "guidance": ["a", "b"], "listen_for": ["1", "2", "3", "4"]},
        {"why_this_fits": "x" * 400, "guidance": ["a", "b"], "listen_for": []},
        {"why_this_fits": "ok", "guidance": ["x" * 300, "b"], "listen_for": []},
    ],
)
def test_schema_violations_rejected(facts, bad):
    res = validate_enrichment(bad, facts)
    assert not res.ok
    assert any(v.startswith("schema:") for v in res.violations)
