"""Concert vs written pitch labelling and coaching-brief variety for Claude enrichment. Offline only."""

from __future__ import annotations

import dataclasses
import json
import os
from unittest import mock

import pytest

from instrument_transposition import written_key_for_type
from music_coach_ami.claude_brief import ANGLES, build_brief
from music_coach_ami.claude_enrichment import SYSTEM_PROMPT, maybe_enrich_song_coaching
from music_coach_ami.claude_facts import PROMPT_VERSION, build_fact_sheet
from music_coach_ami.claude_pitch import build_pitch_reference, pitch_note
from music_coach_ami.claude_validate import validate_enrichment
from music_coach_ami.composer import _enrichment_markdown
from tests.claude_enrichment_fixtures import FakeTransport, make_req, make_resp, make_settings


def _req(instrument: str, *, level: str = "Intermediate", focus: str = "Chord changes", session_ref=None, chart=None):
    base = make_req(chart=chart)
    extra = dict(base.context.extra)
    if session_ref is not None:
        extra["session_ref"] = session_ref
    ctx = dataclasses.replace(base.context, instrument=instrument, level=level, practice_focus=focus, extra=extra)
    return dataclasses.replace(base, context=ctx)


def _facts(instrument: str, **kw):
    f, reason = build_fact_sheet(_req(instrument, **kw), make_resp())
    assert reason == "ok" and f is not None
    return f


# ---- written pitch is deterministic and comes from instrument_transposition ----------------------------------


@pytest.mark.parametrize(
    ("instrument", "concert", "written"),
    [
        ("Alto Saxophone", "C", "A"),
        ("Alto Saxophone", "G", "E"),
        ("Alto Saxophone", "F", "D"),
        ("Alto Saxophone", "Bb", "G"),
        ("Tenor Saxophone", "C", "D"),
        ("Tenor Saxophone", "G", "A"),
        ("Tenor Saxophone", "F", "G"),
        ("Soprano Saxophone", "C", "D"),
        ("Soprano Saxophone", "Bb", "C"),
        ("Baritone Saxophone", "C", "A"),
        ("Trumpet", "C", "D"),
        ("Clarinet", "F", "G"),
    ],
)
def test_written_keys_match_existing_transposition_logic(instrument, concert, written):
    ref = build_pitch_reference(instrument, {}, keys=(concert,), chords=("Dm7",))
    assert ref.status == "verified"
    assert ref.written_key(concert) == written
    assert ref.written_key(concert) == written_key_for_type(concert, ref.transposing_type)


def test_written_chords_are_deterministic_transpositions():
    ref = build_pitch_reference("Alto Saxophone", {}, keys=("C",), chords=("Dm7", "G7", "Cmaj7", "Cm"))
    assert dict(ref.chord_pairs) == {"Dm7": "Bm7", "G7": "E7", "Cmaj7": "Amaj7", "Cm": "Am"}
    tenor = build_pitch_reference("Tenor Saxophone", {}, keys=("C",), chords=("Dm7", "G7"))
    assert dict(tenor.chord_pairs) == {"Dm7": "Em7", "G7": "A7"}


@pytest.mark.parametrize("instrument", ["Flute", "Guitar", "Voice", "Piano", "Violin"])
def test_non_transposing_instruments_are_concert_controls(instrument):
    ref = build_pitch_reference(instrument, {}, keys=("C",), chords=("Dm7",))
    assert ref.status == "concert" and not ref.transposing
    assert pitch_note(ref, ["C"], ["Dm7"]) == ""


def test_generic_saxophone_without_a_type_pick_is_unverified_not_guessed():
    ref = build_pitch_reference("Saxophone", {}, keys=("C",), chords=("Dm7",))
    assert ref.status == "unverified" and ref.key_pairs == () and ref.chord_pairs == ()
    note = pitch_note(ref, ["C"], ["Dm7"])
    assert "concert pitch" in note and "could not be verified" in note and "=" not in note


def test_generic_saxophone_with_session_pick_is_verified():
    ref = build_pitch_reference(
        "Saxophone", {"selected_transposing_instrument": "Tenor saxophone (Bb)"}, keys=("C",), chords=()
    )
    assert ref.status == "verified" and ref.written_key("C") == "D"


def test_octave_relationship_is_stated_for_tenor_and_baritone_only():
    alto = build_pitch_reference("Alto Saxophone", {}, keys=("C",), chords=())
    tenor = build_pitch_reference("Tenor Saxophone", {}, keys=("C",), chords=())
    bari = build_pitch_reference("Baritone Saxophone", {}, keys=("C",), chords=())
    assert alto.relation == "a major sixth above" and "octave" not in alto.relation
    assert "octave" in tenor.relation and "octave" in bari.relation


def test_claude_is_never_handed_written_values():
    facts = _facts("Alto Saxophone")
    blob = json.loads(facts.facts_json())
    assert blob["pitch_reference"] == {
        "names_are": "concert pitch",
        "instrument_transposes": True,
        "app_adds_written_pitch_labels": True,
    }
    assert facts.pitch_ref.written_key("C") == "A"
    assert "written_key" not in facts.facts_json() and "Bm7" not in facts.facts_json()


# ---- validator / rendering ------------------------------------------------------------------------------------

PAYLOAD_WITH_KEY = {
    "why_this_fits": "The {{section:Verse}} sits in {{key:C}} and moves {{chord:Dm7}} to {{chord:G7}}.",
    "guidance": ["Drill {{chord:Dm7}} to {{chord:G7}} as a two-chord loop.", "Join it back to {{chord:Cmaj7}}."],
    "listen_for": [],
}


def test_alto_key_is_labelled_concert_and_written_label_is_added_by_code():
    res = validate_enrichment(PAYLOAD_WITH_KEY, _facts("Alto Saxophone"))
    assert res.ok, res.violations
    assert "**C** (concert)" in res.enrichment.why
    note = res.enrichment.pitch_note
    assert "Alto Saxophone" in note and "a major sixth above sounding pitch" in note
    assert "C concert = A written" in note
    assert "Dm7 → Bm7" in note and "G7 → E7" in note and "Cmaj7 → Amaj7" in note
    assert res.enrichment.as_dict()["pitch_note"] == note


def test_tenor_note_states_octave_relationship():
    res = validate_enrichment(PAYLOAD_WITH_KEY, _facts("Tenor Saxophone"))
    assert res.ok
    assert "major second plus an octave above" in res.enrichment.pitch_note
    assert "C concert = D written" in res.enrichment.pitch_note


def test_flute_control_has_no_concert_label_and_no_pitch_note():
    res = validate_enrichment(PAYLOAD_WITH_KEY, _facts("Flute"))
    assert res.ok
    assert "**C**" in res.enrichment.why and "(concert)" not in res.enrichment.why
    assert res.enrichment.pitch_note == ""
    assert "pitch_note" not in res.enrichment.as_dict()


def test_only_chords_actually_used_appear_in_the_written_list():
    res = validate_enrichment(
        {
            "why_this_fits": "Work {{chord:Dm7}} in the {{section:Verse}}.",
            "guidance": ["Loop {{chord:Dm7}}.", "Take it slowly."],
            "listen_for": [],
        },
        _facts("Alto Saxophone"),
    )
    assert res.ok and "Dm7 → Bm7" in res.enrichment.pitch_note and "G7 →" not in res.enrichment.pitch_note


@pytest.mark.parametrize(
    "text",
    [
        "In written pitch you read this a sixth higher.",
        "Transpose it up a step first.",
        "Play it an octave lower.",
        "This is concert pitch for you.",
        "Use the capo on the second fret.",
        "Mind the enharmonic spelling.",
    ],
)
@pytest.mark.parametrize("instrument", ["Alto Saxophone", "Flute"])
def test_claude_pitch_claims_are_rejected(text, instrument):
    res = validate_enrichment(
        {"why_this_fits": "Work the {{section:Verse}}.", "guidance": [text, "Loop it slowly."], "listen_for": []},
        _facts(instrument),
    )
    assert not res.ok
    assert any(v.startswith("unsupported_pitch_claim:") for v in res.violations)


def test_written_key_marker_is_not_accepted():
    res = validate_enrichment(
        {"why_this_fits": "Written key {{key:A}} here.", "guidance": ["Loop slowly.", "Count aloud."], "listen_for": []},
        _facts("Alto Saxophone"),
    )
    assert not res.ok and "key_not_in_facts:A" in res.violations


def test_composer_renders_pitch_note_last_and_labels_it():
    res = validate_enrichment(PAYLOAD_WITH_KEY, _facts("Alto Saxophone"))
    md = _enrichment_markdown(res.enrichment.as_dict())
    assert md[-1].startswith("*Chord and key names in this note are concert pitch")
    assert _enrichment_markdown({"why": "x", "guidance": ["a"]})[-1] == "- a"


def test_deterministic_answer_unchanged_for_alto_with_enrichment_on_off_and_failing():
    def run(settings, transport):
        resp = make_resp()
        before = (resp.direct_answer, list(resp.practice_steps), resp.suggested_next_action)
        state = {"_ami_claude_dev_mode": True, "ami_claude_dev_enabled": True}
        out = maybe_enrich_song_coaching(
            _req("Alto Saxophone"),
            resp,
            state,
            transport_factory=transport.factory() if transport else None,
            settings=settings,
        )
        assert (out.direct_answer, list(out.practice_steps), out.suggested_next_action) == before
        return out

    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-FAKEKEY-do-not-use-0000000000"}):
        on = run(make_settings(), FakeTransport(payload=PAYLOAD_WITH_KEY))
        assert on.enrichment and "pitch_note" in on.enrichment
        failed = run(make_settings(), FakeTransport(text="not json"))
        assert failed.enrichment is None
    off = run(make_settings(master_enabled=False), None)
    assert off.enrichment is None


# ---- coaching brief ---------------------------------------------------------------------------------------------


def _brief(**kw):
    base = dict(
        song_title="Song",
        section="Verse",
        instrument="Flute",
        level="Intermediate",
        practice_focus="Chord changes",
        chords=("C", "G"),
    )
    base.update(kw)
    return build_brief(**base)


def test_brief_is_deterministic():
    assert _brief() == _brief()


def test_prompt_version_bumped_and_brief_in_facts():
    assert PROMPT_VERSION == "song-enrich-v2"
    blob = json.loads(_facts("Flute").facts_json())
    assert blob["coaching_brief"]["angle_ids"] and blob["coaching_brief"]["level_scope"]["items"]


def test_brief_depends_on_instrument_and_level():
    flute, guitar, voice = _brief(instrument="Flute"), _brief(instrument="Guitar"), _brief(instrument="Voice")
    assert len({tuple(b["instrument_cues"]) for b in (flute, guitar, voice)}) == 3
    assert any(w in " ".join(flute["instrument_cues"]).lower() for w in ("breath", "air", "finger"))
    assert any(w in " ".join(guitar["instrument_cues"]).lower() for w in ("fret", "strum", "pick"))
    assert any(w in " ".join(voice["instrument_cues"]).lower() for w in ("breath", "vowel", "pitch"))
    assert _brief(level="Beginner")["level_scope"]["items"] == "2"
    assert _brief(level="Advanced")["level_scope"]["items"] == "3 to 4"


def test_brief_focus_selects_a_different_angle_pool():
    rhythm = {a for i in range(30) for a in _brief(practice_focus="Rhythm", song_title=f"S{i}")["angle_ids"]}
    pitch = {a for i in range(30) for a in _brief(practice_focus="Pitch", song_title=f"S{i}")["angle_ids"]}
    assert "rhythm_placement" in rhythm and "rhythm_placement" not in pitch
    assert "listen_first" in pitch


def test_angles_vary_across_exercises():
    sections = [
        ("Verse", ("C", "G")),
        ("Chorus", ("Am", "F")),
        ("Bridge", ("Dm7", "G7")),
        ("Intro", ("C",)),
        ("Outro", ("F", "C")),
        ("A1", ("Am7", "Dm7", "G7")),
    ]
    ids = {tuple(_brief(section=s, chords=c)["angle_ids"]) for s, c in sections}
    assert len(ids) >= 3


def test_primary_and_secondary_angles_differ_and_exist():
    for focus in ("Chord changes", "Rhythm", "Pitch", "Improvisation", "", "Tone"):
        for sec in ("Verse", "Chorus", "Bridge"):
            b = _brief(practice_focus=focus, section=sec)
            assert len(set(b["angle_ids"])) == 2 and all(a in ANGLES for a in b["angle_ids"])


def test_tempo_and_recording_advice_are_gated_by_angle():
    seen = set()
    for focus in ("Chord changes", "Rhythm", "Pitch", "Improvisation"):
        for i in range(40):
            b = _brief(practice_focus=focus, song_title=f"S{i}", chords=("C", f"D{i}"))
            assert b["may_mention_tempo"] == ("tempo_ladder" in b["angle_ids"])
            assert b["may_suggest_recording"] == ("self_check" in b["angle_ids"])
            seen.add((b["may_mention_tempo"], b["may_suggest_recording"]))
    assert (False, False) in seen and (True, False) in seen


def test_most_exercises_get_no_default_tempo_or_recording_advice():
    off = n = 0
    for focus in ("Chord changes", "Rhythm", "Pitch", "Improvisation"):
        for i in range(30):
            b = _brief(practice_focus=focus, song_title=f"T{i}", chords=(f"C{i}", "G"))
            n += 1
            off += not (b["may_mention_tempo"] or b["may_suggest_recording"])
    assert off / n > 0.5


def test_system_prompt_enforces_brief_and_pitch_rules():
    for needle in (
        "coaching_brief",
        "may_mention_tempo",
        "may_suggest_recording",
        "CONCERT pitch",
        "Never mention written pitch",
    ):
        assert needle in SYSTEM_PROMPT


def test_fingerprint_changes_with_instrument_and_level():
    fps = {
        f.fingerprint("claude-sonnet-5-5")
        for f in (_facts("Flute"), _facts("Guitar"), _facts("Flute", level="Beginner"))
    }
    assert len(fps) == 3


def test_enrichment_sources_use_american_spelling():
    """origin/dev enforces American spelling across music_coach_ami; the Claude modules must not reintroduce British forms."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "music_coach_ami"
    pattern = re.compile(r"[Pp]ractis(?:e|ed|es|ing)\b|recognisable|colours the")
    offenders = [p.name for p in root.glob("claude_*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
    assert all("ractise" not in text for text in ANGLES.values())
