"""Phase 3B — Custom tools + Arrangement Assistant Focus bias."""

from __future__ import annotations

from creative_lab_text import creativity_arrangement_text
from custom_progression_lab import generate_exercises_markdown
from practice_focus_custom import (
    arrangement_focus_recommendations,
    custom_focus_exercise_blocks,
    detect_explicit_custom_intent,
)
from practice_studio import _section_exercise


_PROGRESSION = ["G", "D", "Em", "C"]
_SECTIONS = {
    "Verse": [{"chord": "G", "bars": 1}, {"chord": "D", "bars": 1}, {"chord": "Em", "bars": 1}, {"chord": "C", "bars": 1}],
}


def _custom_md(instrument: str, focus: str, *, user_request: str = "") -> str:
    return generate_exercises_markdown(
        sections=_SECTIONS,
        instrument=instrument,
        level="Intermediate",
        focus=focus,
        key_center="G",
        groove_style="Pop",
        time_signature="4/4",
        bpm=100,
        user_request=user_request,
    )


def test_guitar_strumming_timing_harmony_custom_differ():
    strum = _custom_md("Guitar", "Strumming")
    timing = _custom_md("Guitar", "Timing")
    harmony = _custom_md("Guitar", "Harmony")
    assert "Practice Focus drills" in strum
    assert "continuous" in strum.lower() or "strumming" in strum.lower() or "hand motion" in strum.lower()
    assert "metronome" in timing.lower() or "subdivision" in timing.lower()
    assert "chord tone" in harmony.lower() or "guide-tone" in harmony.lower() or "guide tone" in harmony.lower()
    assert strum != timing != harmony
    assert "Strumming" in strum and "Timing" in timing and "Harmony" in harmony


def test_sax_tone_articulation_phrasing_custom_differ():
    tone = _custom_md("Saxophone", "Tone")
    artic = _custom_md("Saxophone", "Articulation")
    phrase = _custom_md("Saxophone", "Phrasing")
    assert "long tone" in tone.lower() or "register" in tone.lower()
    assert "tongu" in artic.lower() or "slur" in artic.lower() or "articulation" in artic.lower()
    assert "phrase" in phrase.lower() or "space" in phrase.lower() or "question" in phrase.lower()
    assert tone != artic != phrase


def test_explicit_chord_tone_request_precedes_strumming_focus():
    md = _custom_md(
        "Guitar",
        "Strumming",
        user_request="Give me a chord-tone exercise over G-D-Em-C.",
    )
    assert "Primary task (your request)" in md
    assert "chord-tone" in md.lower() or "chord tone" in md.lower()
    assert detect_explicit_custom_intent("Give me a chord-tone exercise") == "chord_tones"
    # Focus may add optional note but must not replace the primary ask.
    assert "Primary task" in md
    payload = custom_focus_exercise_blocks(
        "Guitar",
        "Strumming",
        chords=_PROGRESSION,
        user_request="Give me a chord-tone exercise over G-D-Em-C.",
    )
    assert payload["explicit_intent"] == "chord_tones"
    assert any("Primary task" in d for d in payload["drills"])


def test_same_rerun_focus_change_changes_custom_payload():
    a = custom_focus_exercise_blocks("Guitar", "Strumming", chords=_PROGRESSION)
    b = custom_focus_exercise_blocks("Guitar", "Harmony", chords=_PROGRESSION)
    assert a["category"] != b["category"]
    assert a["drills"] != b["drills"]
    assert "\n".join(a["drills"]) != "\n".join(b["drills"])


def test_unknown_focus_safe_generic():
    payload = custom_focus_exercise_blocks(
        "Piano",
        "My Weird Custom Focus XYZ",
        chords=_PROGRESSION,
    )
    assert payload["focus"]  # exact-ish label preserved via profile
    assert payload["drills"]
    md = _custom_md("Piano", "My Weird Custom Focus XYZ")
    assert "Practice Focus drills" in md
    assert "My Weird Custom Focus XYZ" in md or payload["drills"]


def test_arrangement_assistant_focus_bias_advisory_only():
    ctx = {
        "song": "Demo",
        "instrument": "Guitar",
        "level": "Intermediate",
        "focus": "Harmony",
        "genre": "Pop",
        "sections": {"Verse": ["G", "D", "Em", "C"]},
        "chart_key": "G",
        "display_key": "G",
        "key": "G",
    }
    harm = creativity_arrangement_text(ctx, "Pop Rock", "Verse")
    ctx_m = {**ctx, "focus": "Melody"}
    mel = creativity_arrangement_text(ctx_m, "Pop Rock", "Verse")
    ctx_t = {**ctx, "focus": "Timing"}
    tim = creativity_arrangement_text(ctx_t, "Pop Rock", "Verse")
    ctx_p = {**ctx, "focus": "Phrasing"}
    phr = creativity_arrangement_text(ctx_p, "Pop Rock", "Verse")

    assert "Practice Focus suggestions (advisory only)" in harm
    assert "do not rewrite" in harm.lower() or "advisory" in harm.lower()
    assert harm != mel
    assert mel != tim
    assert tim != phr
    # Underlying section chords still described — arrangement not rewritten.
    assert "Verse" in harm and "Verse" in mel
    assert arrangement_focus_recommendations("Guitar", "Harmony")[0] != (
        arrangement_focus_recommendations("Guitar", "Melody")[0]
    )


def test_section_exercise_uses_focus_lines():
    strum = _section_exercise("Verse", _PROGRESSION, "Guitar", "Intermediate", "Strumming", "Pop")
    tone = _section_exercise("Verse", _PROGRESSION, "Saxophone", "Intermediate", "Tone", "Pop")
    assert strum != tone
    assert "Groove drill" in strum


def test_instrument_compat_consumed_via_policy_not_local_table():
    # Sax + Strumming falls back in policy; Custom must still return usable drills.
    payload = custom_focus_exercise_blocks("Saxophone", "Strumming", chords=_PROGRESSION)
    assert payload["drills"]
    assert payload["category"]  # resolved category from central policy
