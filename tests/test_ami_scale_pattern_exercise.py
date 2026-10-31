"""AMI M1d: scale patterns become structured, revisable exercises — in the right key, mode, harmony and pitch.

Covers: the Practice Key's mode, key-based versus chord-following patterns, charted split bars, exact written/concert pitch (octave
included) per instrument, the legacy outputs that must not move, the Blue Bossa conversation, and ownership isolation.
"""

from __future__ import annotations

import json
import pathlib
import re
from fractions import Fraction

import pytest

from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY as SAX_KEY
from music_coach_ami import conversation_state as cs
from music_coach_ami import exercise_scale_pattern as sp
from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.claude_client import AnthropicTransport
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_followup import last_exercise
from music_coach_ami.pipeline import run_coach_submit

GOLDEN = json.loads((pathlib.Path(__file__).parent / "fixtures" / "ami_scale_pattern_legacy_golden.json").read_text(encoding="utf-8"))

# The catalog's own Blue Bossa (Cm), one chord per bar
BOSSA_A = ["Cm7", "Cm7", "Fm7", "Fm7", "Dm7b5", "G7#5", "Cm7", "Cm7"]
BOSSA_B = ["Ebm7", "Ab7", "Dbmaj7", "Dbmaj7", "Dm7b5", "G7", "Cm7", "Cm7"]
ASK = "Give me an advanced scale pattern over Blue Bossa."
ASK_CHORDS = "Give me an advanced scale pattern over the chord changes of Blue Bossa."
_Q = re.compile(r"^Q:\S+=(\d+)", re.M)
SAXES = {"Alto": "Alto saxophone (Eb)", "Tenor": "Tenor saxophone (Bb)", "Soprano": "Soprano saxophone (Bb)", "Baritone": "Baritone saxophone (Eb)"}
# written minus sounding semitones, octave included
OFFSET = {"Flute": 0, "Alto": 9, "Tenor": 14, "Soprano": 2, "Trumpet": 2, "Clarinet": 2, "Piano": 0}


@pytest.fixture(autouse=True)
def _no_live_api(monkeypatch):
    monkeypatch.setattr(AnthropicTransport, "complete", lambda self, **kw: (_ for _ in ()).throw(AssertionError("LIVE API CALL")))


def ctx(instrument="Flute", level="Advanced", song="Blue Bossa", key="Cm", sections=None, meter=None, bpm=135):
    out = {"instrument": instrument, "level": level, "focus": "Improvisation", "display_key": key,
           "active_song": {"title": song, "key": key, "default_key": key},
           "chart_sections": {k: list(v) for k, v in (sections or {"Section A": BOSSA_A, "Section B": BOSSA_B}).items()},
           "chart_sections_key": key, "bpm": bpm}
    if meter:
        out["chart_meter"] = meter
    return out


def session(instrument="Flute", sax=None):
    s = {"_suite_auth_user_id": "u1", "_suite_active_workspace_id": "daniel", "instrument": instrument}
    if sax:
        s[SAX_KEY] = sax
    return s


def ask(s, q, **kw):
    return run_coach_submit(q, s, ami_ctx=ctx(**kw))[1]


def tempo(resp):
    m = _Q.search(resp.notation_abc or "")
    return int(m.group(1)) if m else 0


def start(q=ASK, instrument="Flute", sax=None, s=None, **kw):
    s = s if s is not None else session(instrument, sax)
    resp = ask(s, q, instrument=instrument, **kw)
    assert resp.diagnostics.get("generated_exercise_id"), (resp.diagnostics.get("scale_pattern_exercise_failed"), resp.direct_answer[:200])
    return s, resp


def exercise(resp):
    return resp.diagnostics["generated_exercise"]


# ================================================================ 1. the key and mode of the pattern
@pytest.mark.parametrize("token, tonic, tonality, source", [
    ("Cm", "C", "natural minor", "practice_key"), ("C", "C", "major", "practice_key"), ("G minor", "G", "natural minor", "practice_key"),
    ("Bb", "Bb", "major", "practice_key"), ("F#m", "F#", "natural minor", "practice_key"), ("Ebm", "Eb", "natural minor", "practice_key"),
    ("D major", "D", "major", "practice_key"),
])
def test_practice_key_scale_keeps_the_mode_of_the_token(token, tonic, tonality, source):
    ks = sph.practice_key_scale(token, "Am")
    assert (ks.tonic, ks.tonality, ks.source) == (tonic, tonality, source)


def test_the_songs_own_key_stands_in_only_when_there_is_no_practice_key_and_c_major_only_with_neither():
    assert sph.practice_key_scale("", "Dm") == sph.KeyScale("D", "natural minor", "song_original_key")
    assert sph.practice_key_scale("", "") == sph.KeyScale("C", "major", "default")


def test_a_c_minor_song_no_longer_gets_a_c_major_scale():
    _s, resp = start()
    ex = exercise(resp)
    assert (ex["tonic"], ex["mode"]) == ("C", "natural minor") and ex["context"]["concert_key"] == "Cm"
    assert set(ex["notes"]) == {"C", "D", "Eb", "F", "G", "Ab", "Bb"} and "K:Cm" in resp.notation_abc
    assert resp.diagnostics["scale_key"] == {"tonic": "C", "tonality": "natural minor", "source": "practice_key"}


@pytest.mark.parametrize("key, song, tonic, mode, scale", [
    ("Gm", "Autumn Leaves", "G", "natural minor", {"G", "A", "Bb", "C", "D", "Eb", "F"}),
    ("C", "Some Major Song", "C", "major", {"C", "D", "E", "F", "G", "A", "B"}),
    ("Bb", "Another Major Song", "Bb", "major", {"Bb", "C", "D", "Eb", "F", "G", "A"}),
    ("F#m", "A Sharp-Key Song", "F#", "natural minor", {"F#", "G#", "A", "B", "C#", "D", "E"}),
])
def test_major_and_minor_practice_keys_set_the_scale(key, song, tonic, mode, scale):
    _s, resp = start(song=song, key=key, sections={"A": ["Cm7", "F7"]})
    ex = exercise(resp)
    assert (ex["tonic"], ex["mode"]) == (tonic, mode) and set(ex["notes"]) == scale
    assert ex["context"]["concert_key"] == key


def test_a_practice_key_transposed_away_from_the_songs_key_keeps_its_own_mode():
    _s, resp = start(key="Gm", song="Blue Bossa")                  # Blue Bossa is Cm; the player practises it in Gm
    assert exercise(resp)["tonic"] == "G" and exercise(resp)["mode"] == "natural minor"


def test_an_explicitly_requested_scale_still_wins_over_the_practice_key():
    _s, resp = start("Give me a D dorian scale pattern over Blue Bossa.")
    ex = exercise(resp)
    assert (ex["tonic"], ex["mode"]) == ("D", "dorian") and ex["context"]["concert_key"] == "D" and ex["context"]["key_source"] == "explicit_request"
    assert set(ex["notes"]) == {"D", "E", "F", "G", "A", "B", "C"}


def test_a_requested_mode_without_a_tonic_takes_the_practice_keys_tonic():
    _s, resp = start("Give me a dorian scale pattern over Blue Bossa.")
    assert (exercise(resp)["tonic"], exercise(resp)["mode"]) == ("C", "dorian")


def test_a_named_key_without_a_mode_is_the_legacy_major_scale():
    _s, resp = start("Give me a 4-bar scale pattern in G.")
    assert (exercise(resp)["tonic"], exercise(resp)["mode"]) == ("G", "major")


@pytest.mark.parametrize("instrument", ["Flute", "Violin", "Guitar", "Voice"])
@pytest.mark.parametrize("level", ["Beginner", "Advanced"])
@pytest.mark.parametrize("question", ["Give me a C major scale pattern", "Give me a 2-bar G major scale pattern in thirds", "Give me an Eb harmonic minor scale pattern"])
def test_explicit_scale_patterns_are_byte_identical_to_the_legacy_output(instrument, level, question):
    gold = GOLDEN[f"{instrument}|{level}|{question}"]
    resp = ask(session(instrument), question, instrument=instrument, level=level, bpm=120, sections={"Section A": ["Cm7", "Cm7", "Fm7", "Fm7"]})
    assert resp.notation_abc == gold["abc"] and resp.practice_steps[: len(gold["steps"])] == gold["steps"]
    assert resp.direct_answer.startswith(gold["direct"])


def test_intentional_change_a_tonic_named_before_the_mode_is_now_honoured():
    """Legacy parsed "a D dorian pattern" as a mode with no tonic and played C dorian (the golden file records it). It is now D dorian."""
    legacy = GOLDEN["Flute|Beginner|Give me a D dorian scale pattern"]["abc"]
    assert "K:Bb" in legacy                                                       # C dorian's signature: the legacy result
    resp = ask(session(), "Give me a D dorian scale pattern", instrument="Flute", level="Beginner", bpm=120, sections={"Section A": ["Cm7", "Cm7", "Fm7", "Fm7"]})
    assert "K:C" in resp.notation_abc and exercise(resp)["tonic"] == "D" and exercise(resp)["mode"] == "dorian"
    assert set(exercise(resp)["notes"]) == {"D", "E", "F", "G", "A", "B", "C"}


@pytest.mark.parametrize("question, tonic, mode", [("give me an eb mixolydian line", "Eb", "mixolydian"), ("give me a c lydian pattern", "C", "lydian"),
                                                  ("give me a dorian scale pattern", "", "dorian"), ("a minor scale pattern", "A", "natural minor")])
def test_scale_words_parse_tonic_and_mode(question, tonic, mode):
    from music_coach_ami.musical_idea_request import _parse_tonality_and_key

    assert _parse_tonality_and_key(question) == (tonic, mode)       # a lone "a" before a mode word is the article, not the note


# ================================================================ 2. key-based versus chord-following
def test_the_default_is_key_based_and_says_so_without_claiming_chords():
    _s, resp = start()
    ex = exercise(resp)
    assert ex["provenance"]["kind"] == "key_based" and ex["chords"] == [] and ex["chord"] == "" and not any(ex["chord_roles"])
    assert "key-based" in resp.direct_answer.lower() and "does not follow the chord changes" in resp.direct_answer
    assert '"Cm7"' not in resp.notation_abc and "no chord" in ex["provenance"]["harmony"]
    assert resp.diagnostics["scale_pattern_kind"] == "key_based"


@pytest.mark.parametrize("question", [ASK_CHORDS, "Give me a scale pattern that follows the chords of Blue Bossa", "Give me a scale pattern for each chord in Blue Bossa",
                                      "Give me a chord-following scale pattern over Blue Bossa"])
def test_asking_for_the_chords_gives_a_chord_following_pattern(question):
    _s, resp = start(question)
    ex = exercise(resp)
    assert ex["provenance"]["kind"] == "chord_following" and ex["chords"] == ["Cm7", "Fm7", "Dm7b5", "G7#5"]
    assert '"Cm7"' in resp.notation_abc and '"G7#5"' in resp.notation_abc
    assert "key-based" not in resp.direct_answer.lower()
    assert resp.diagnostics["scale_pattern_kind"] == "chord_following"


def test_blue_bossa_scales_are_chosen_by_each_chord_and_every_chord_tone_is_inside_them():
    _s, resp = start(ASK_CHORDS)
    segs = exercise(resp)["provenance"]["segments"]
    assert [(g["chord"], g["scale"]) for g in segs if g["bar"] in (1, 3, 5, 6)] == [("Cm7", "C aeolian"), ("Fm7", "F dorian"), ("Dm7b5", "D locrian"), ("G7#5", "G altered")]
    for g in segs:
        assert g["why"] and len(g["scale_notes"]) == 7


def test_the_answer_explains_why_each_scale_was_chosen():
    _s, resp = start(ASK_CHORDS)
    text = " ".join(resp.practice_steps)
    assert "Scales by chord" in text and "G altered" in text and "Practice Key's own mode" in text and "no chromatic approach notes" in text


def test_every_note_belongs_to_its_chords_scale_and_chord_tones_are_marked():
    _s, resp = start(ASK_CHORDS)
    ex = exercise(resp)
    scales = {g["chord"]: {sph.pc_of(n) for n in g["scale_notes"]} for g in ex["provenance"]["segments"]}
    for midi, ci in zip(ex["midi"], ex["chord_assignment"]):
        assert midi % 12 in scales[ex["chords"][ci]]
    assert {"R", "3", "5"} <= set(ex["chord_roles"]) and len(ex["provenance"]["written_events"]) == len(ex["notes"])


def test_the_pattern_changes_scale_exactly_where_the_chord_changes():
    _s, resp = start(ASK_CHORDS)
    ex = exercise(resp)
    first_of_chord: dict[tuple[int, str], float] = {}
    for e in ex["provenance"]["written_events"]:
        first_of_chord.setdefault((e["bar_index"], e["chord"]), e["beat"])
    assert [first_of_chord[(b, c)] for b, c in ((0, "Cm7"), (2, "Fm7"), (4, "Dm7b5"), (5, "G7#5"))] == [0, 0, 0, 0]
    assert all(g["beat"] == "1" for g in ex["provenance"]["segments"])


def test_section_b_follows_its_own_chords():
    _s, resp = start("Give me an advanced scale pattern over the chord changes of Section B of Blue Bossa.")
    ex = exercise(resp)
    assert ex["chords"] == ["Ebm7", "Ab7", "Dbmaj7", "Dm7b5", "G7", "Cm7"] and ex["context"]["section"] == "Section B"
    got = {g["chord"]: g["scale"] for g in ex["provenance"]["segments"]}
    assert got == {"Ebm7": "Eb dorian", "Ab7": "Ab mixolydian", "Dbmaj7": "Db ionian", "Dm7b5": "D locrian", "G7": "G mixolydian b6", "Cm7": "C aeolian"}


def test_a_major_song_ii_v_i_gets_major_key_scales():
    _s, resp = start(ASK_CHORDS.replace("Blue Bossa", "this song"), song="ii V I", key="C", sections={"A": ["Dm7", "G7", "Cmaj7", "Am7"]})
    got = [(g["chord"], g["scale"]) for g in exercise(resp)["provenance"]["segments"]]
    assert got == [("Dm7", "D dorian"), ("G7", "G mixolydian"), ("Cmaj7", "C ionian"), ("Am7", "A aeolian")]
    assert exercise(resp)["mode"] == "major"


def test_autumn_leaves_in_g_minor():
    sec = {"A": ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7", "Gm", "Gm"]}
    _s, resp = start(ASK_CHORDS.replace("Blue Bossa", "Autumn Leaves"), song="Autumn Leaves", key="Gm", sections=sec)
    got = {g["chord"]: g["scale"] for g in exercise(resp)["provenance"]["segments"]}
    assert got == {"Cm7": "C dorian", "F7": "F mixolydian", "Bbmaj7": "Bb ionian", "Ebmaj7": "Eb ionian", "Am7b5": "A locrian", "D7": "D mixolydian b6", "Gm": "G aeolian"}
    assert (exercise(resp)["tonic"], exercise(resp)["mode"]) == ("G", "natural minor")


# ---- split bars and several chords per measure
SPLIT = ["Cm7", "Dm7b5|G7", "C:2|G:2", "C:3.5|D:0.5p"]


def test_split_bars_keep_their_beats_and_the_chord_changes_mid_bar():
    _s, resp = start(ASK_CHORDS.replace("Blue Bossa", "this song"), song="Split", key="Cm", sections={"A": SPLIT})
    ex = exercise(resp)
    segs = [(g["bar"], g["beat"], g["beats"], g["chord"]) for g in ex["provenance"]["segments"]]
    assert segs == [(1, "1", "4", "Cm7"), (2, "1", "2", "Dm7b5"), (2, "3", "2", "G7"), (3, "1", "2", "C"), (3, "3", "2", "G"), (4, "1", "3.5", "C"), (4, "4.5", "0.5", "D")]
    assert ex["bars"] == 4 and '"Dm7b5"' in resp.notation_abc and '"G7"' in resp.notation_abc
    bar2 = [e for e in ex["provenance"]["written_events"] if e["bar_index"] == 1]
    assert [e["chord"] for e in bar2] == ["Dm7b5"] * 4 + ["G7"] * 4 and bar2[4]["beat"] == 2.0
    assert sum(Fraction(r["dur"]) for r in ex["rhythm_events"]) == 16 and ex["validation"]["ok"]


def test_the_flattened_chord_list_is_not_mistaken_for_one_chord_per_bar():
    _s, resp = start(ASK_CHORDS.replace("Blue Bossa", "this song"), song="Split", key="Cm", sections={"A": SPLIT})
    assert exercise(resp)["bars"] == 4            # the coach's chord list has 7 names; the chart has 4 bars


def test_a_three_four_chord_following_pattern_fills_each_bar():
    _s, resp = start(ASK_CHORDS.replace("Blue Bossa", "this song"), song="Waltz", key="Cm", sections={"A": ["Cm7", "Fm7|G7"]}, meter="3/4")
    ex = exercise(resp)
    assert ex["meter"] == "3/4" and sum(Fraction(r["dur"]) for r in ex["rhythm_events"]) == 3 * ex["bars"]


# ---- harmony that cannot be followed is explained, not invented
@pytest.mark.parametrize("sections, why", [
    ({"A": ["Cm7", "Bdim7", "Cm7", "Cm7"]}, "diminished chords aren't supported yet"),
    ({"A": ["Cm7", "G7#9", "Cm7", "Cm7"]}, "none of the scales I know"),
])
def test_unsupported_chords_are_named_and_a_key_based_pattern_is_given_instead(sections, why):
    _s, resp = start(ASK_CHORDS.replace("Blue Bossa", "this song"), song="Odd", key="Cm", sections=sections)
    assert why in resp.direct_answer and "key-based pattern instead" in resp.direct_answer
    assert exercise(resp)["provenance"]["kind"] == "key_based" and resp.diagnostics["chord_following_unavailable"]


def test_no_chords_means_no_chord_following_and_it_says_so():
    resp = run_coach_submit("Give me an advanced scale pattern over the chord changes.", session(),
                            ami_ctx={"instrument": "Flute", "level": "Advanced", "display_key": "Cm", "bpm": 120})[1]
    assert "I don't have this song's chords" in resp.direct_answer and resp.diagnostics.get("scale_pattern_kind") == "key_based"


def test_an_unverifiable_instrument_is_not_chord_followed():
    resp = ask(session("Guitar"), ASK_CHORDS, instrument="Guitar")
    assert "can't verify the written pitch for Guitar" in resp.direct_answer and not resp.diagnostics.get("generated_exercise_id")


# ================================================================ 3. exact pitch, octave included
@pytest.mark.parametrize("kind_q", [ASK, ASK_CHORDS], ids=["key_based", "chord_following"])
@pytest.mark.parametrize("name, instrument, sax", [("Flute", "Flute", None), ("Alto", "Saxophone", SAXES["Alto"]), ("Tenor", "Saxophone", SAXES["Tenor"]),
                                                    ("Soprano", "Saxophone", SAXES["Soprano"]), ("Trumpet", "Trumpet", None),
                                                    ("Clarinet", "Clarinet", None), ("Piano", "Piano", None)])
def test_written_is_concert_plus_one_exact_offset_octave_included(kind_q, name, instrument, sax):
    _s, resp = start(kind_q, instrument=instrument, sax=sax)
    ex = exercise(resp)
    shifts = {w - c for c, w in zip(ex["midi"], ex["written"]["midi"])}
    assert shifts == {OFFSET[name]}, (name, shifts)
    assert ex["provenance"]["offset"] == OFFSET[name] and ex["validation"]["ok"]
    assert any(c["name"] == "written_equals_concert_plus_offset" and c["ok"] for c in ex["validation"]["checks"])


@pytest.mark.parametrize("name, instrument, sax, low, high", [("Alto", "Saxophone", SAXES["Alto"], 58, 89), ("Tenor", "Saxophone", SAXES["Tenor"], 58, 89),
                                                              ("Soprano", "Saxophone", SAXES["Soprano"], 58, 89), ("Trumpet", "Trumpet", None, 54, 84),
                                                              ("Clarinet", "Clarinet", None, 52, 96), ("Flute", "Flute", None, 60, 96)])
@pytest.mark.parametrize("kind_q", [ASK, ASK_CHORDS], ids=["key_based", "chord_following"])
@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
def test_written_notes_are_inside_what_the_instrument_can_play_and_the_app_window(name, instrument, sax, low, high, kind_q, level):
    _s, resp = start(kind_q, instrument=instrument, sax=sax, level=level)
    ex = exercise(resp)
    written = ex["written"]["midi"]
    assert min(written) >= low and max(written) <= high
    from music_coach_ami.notation_profile import notation_profile_for_instrument

    profile = notation_profile_for_instrument(ex["context"]["notation_instrument"])
    assert min(written) >= profile.midi_low - 2 and max(written) <= profile.midi_high + 2


@pytest.mark.parametrize("name", ["Tenor", "Soprano"])
def test_tenor_and_soprano_use_their_own_notation_profiles_not_the_alto_window(name):
    _s, resp = start(instrument="Saxophone", sax=SAXES[name])
    assert resp.diagnostics["notation_instrument"] == f"{name} Saxophone"
    assert exercise(resp)["context"]["notation_instrument"] == f"{name} Saxophone"


def test_written_key_follows_the_instrument_transposition():
    for sax, wkey in ((SAXES["Alto"], "Am"), (SAXES["Tenor"], "Dm"), (SAXES["Soprano"], "Dm")):
        _s, resp = start(instrument="Saxophone", sax=sax)
        assert exercise(resp)["written"]["key"] == wkey and f"K:{wkey}" in resp.notation_abc
    _s, resp = start(instrument="Trumpet")
    assert exercise(resp)["written"]["key"] == "Dm"


def test_the_concert_and_written_scale_spellings_agree_with_the_keys():
    _s, resp = start(instrument="Saxophone", sax=SAXES["Alto"])
    ex = exercise(resp)
    assert set(ex["notes"]) == {"C", "D", "Eb", "F", "G", "Ab", "Bb"} and set(ex["written"]["notes"]) == {"A", "B", "C", "D", "E", "F", "G"}


@pytest.mark.parametrize("instrument", ["Violin", "Guitar", "Voice"])
def test_instruments_whose_pitch_projection_cannot_be_verified_keep_the_legacy_answer_and_say_so(instrument):
    s = session(instrument)
    resp = ask(s, ASK, instrument=instrument)
    assert resp.notation_abc and not resp.diagnostics.get("generated_exercise_id")
    assert "can't verify the written pitch and range" in resp.direct_answer and AMI_LAST_EXERCISE_KEY not in s
    assert "no exercise from this conversation" in ask(s, "Make it slower", instrument=instrument).direct_answer.lower()


def test_baritone_sax_is_not_structured_because_its_app_window_and_real_written_range_barely_overlap():
    s = session("Saxophone", SAXES["Baritone"])
    resp = ask(s, ASK, instrument="Saxophone")
    assert resp.notation_abc and not resp.diagnostics.get("generated_exercise_id") and "can't verify the written pitch" in resp.direct_answer


def test_an_explicit_sax_label_that_contradicts_the_selected_type_is_not_structured():
    s = session("Tenor Saxophone")                      # the app's selected type is still its default (alto)
    resp = ask(s, ASK, instrument="Tenor Saxophone")
    assert not resp.diagnostics.get("generated_exercise_id")


def test_piano_scale_patterns_are_written_for_the_right_hand_treble_staff():
    _s, resp = start(instrument="Piano")
    assert "clef=treble" in resp.notation_abc and "clef=bass" not in resp.notation_abc
    ex = exercise(resp)
    assert min(ex["written"]["midi"]) >= 60 and ex["validation"]["ok"]
    assert resp.diagnostics.get("notation_validation_ok", True)


def test_flute_output_is_unchanged_by_the_exact_transposition():
    _s, resp = start(instrument="Flute")
    ex = exercise(resp)
    assert ex["midi"] == ex["written"]["midi"] and ex["provenance"]["offset"] == 0


def test_exact_transposition_helpers():
    assert sph.exact_offset("Alto Saxophone", 9) == 9 and sph.exact_offset("Tenor Saxophone", 2) == 14 and sph.exact_offset("Baritone Saxophone", 9) == 21
    assert sph.exact_offset("Tenor Saxophone", 9) is None            # the app's own transposition disagrees: not verified
    assert sph.exact_offset("Violin", 0) is None and sph.exact_offset("", 0) is None
    assert sph.transpose_spelled("C", 9) == "A" and sph.transpose_spelled("Eb", 9) == "C" and sph.transpose_spelled("F#", 9) == "D#"
    assert sph.octave_for("A", 69) == 4


# ================================================================ 4. conversion fidelity
@pytest.mark.parametrize("kind_q", [ASK, ASK_CHORDS, "Give me a beginner scale pattern over Blue Bossa", "Give me a dorian scale pattern over Blue Bossa"])
@pytest.mark.parametrize("name, instrument, sax", [("Flute", "Flute", None), ("Alto", "Saxophone", SAXES["Alto"]), ("Tenor", "Saxophone", SAXES["Tenor"]),
                                                    ("Soprano", "Saxophone", SAXES["Soprano"]), ("Trumpet", "Trumpet", None), ("Clarinet", "Clarinet", None)])
def test_rerendering_the_stored_exercise_reproduces_the_original_notation_exactly(kind_q, name, instrument, sax):
    s, resp = start(kind_q, instrument=instrument, sax=sax)
    abc, _ = sp.render(last_exercise(s), bpm=tempo(resp))
    assert abc == resp.notation_abc


def test_the_structured_exercise_does_not_change_the_notation_the_player_gets(monkeypatch):
    _s1, with_adapter = start()
    monkeypatch.setattr(sp, "build_exercise", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("adapter off")))
    without = ask(session(), ASK)
    assert "scale_pattern_exercise_failed" in without.diagnostics and not without.diagnostics.get("generated_exercise_id")
    assert without.notation_abc == with_adapter.notation_abc and without.practice_steps == with_adapter.practice_steps


def test_an_adapter_failure_leaves_the_legacy_answer_and_no_stale_exercise(monkeypatch):
    s, _first = start()
    monkeypatch.setattr(sp, "build_exercise", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    resp = ask(s, "Give me a beginner scale pattern")
    assert resp.notation_abc and "scale_pattern_exercise_failed" in resp.diagnostics and AMI_LAST_EXERCISE_KEY not in s
    assert "no exercise from this conversation" in ask(s, "Make it slower").direct_answer.lower()


def test_concert_midi_matches_the_notes_and_every_event_has_a_duration():
    _s, resp = start(ASK_CHORDS)
    ex = exercise(resp)
    pcs = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    for note, midi in zip(ex["notes"], ex["midi"]):
        acc = note[1:].count("#") - note[1:].count("b")
        assert midi % 12 == (pcs[note[0]] + acc) % 12
    assert [e["n"] for e in ex["rhythm_events"] if not e["rest"]] == list(range(len(ex["notes"])))
    assert sum(Fraction(e["dur"]) for e in ex["rhythm_events"]) == 4 * ex["bars"]


@pytest.mark.parametrize("level, unit_beats", [("Beginner", Fraction(1)), ("Advanced", Fraction(1, 2))])
def test_levels_change_the_rhythm_the_way_the_engine_does(level, unit_beats):
    _s, resp = start("Give me a scale pattern over Blue Bossa.", level=level)
    assert {Fraction(e["dur"]) for e in exercise(resp)["rhythm_events"]} == {unit_beats}
    _s, resp = start("Give me a scale pattern over the chord changes of Blue Bossa.", level=level)
    assert {Fraction(e["dur"]) for e in exercise(resp)["rhythm_events"]} == {unit_beats}


def test_intermediate_is_a_valid_exercise_for_both_kinds():
    for q in (ASK, ASK_CHORDS):
        assert exercise(start(q, level="Intermediate")[1])["validation"]["ok"]


# ================================================================ 5. the Blue Bossa conversation (both kinds)
@pytest.mark.parametrize("question", [ASK, ASK_CHORDS], ids=["key_based", "chord_following"])
def test_blue_bossa_conversation_keeps_one_exercise_through_every_step(question):
    s, first = start(question)
    base = exercise(first)
    slower = ask(s, "Make it slower")
    assert tempo(slower) == 121 and exercise(slower)["notes"] == base["notes"] and exercise(slower)["rhythm_events"] == base["rhythm_events"]
    assert _Q.sub("Q:X", slower.notation_abc) == _Q.sub("Q:X", first.notation_abc)
    harder = ask(s, "Make it harder")
    h = exercise(harder)
    assert harder.diagnostics["followup_kind"] == "harder" and tempo(harder) == 121 and h["validation"]["ok"]
    assert (h["tonic"], h["mode"], h["context"]["concert_key"], h["context"]["song_title"]) == (base["tonic"], base["mode"], base["context"]["concert_key"], "Blue Bossa")
    assert h["provenance"]["kind"] == base["provenance"]["kind"] and h["chords"] == base["chords"]
    assert h["transform"]["level_from"] == "Advanced" and h["transform"]["level_to"] == "Advanced+" and h["midi"] != base["midi"]
    accents = ask(s, "Add accents")
    a = exercise(accents)
    assert a["notes"] == h["notes"] and a["midi"] == h["midi"] and a["rhythm_events"] == h["rhythm_events"] and a["chords"] == h["chords"]
    assert a["chord_assignment"] == h["chord_assignment"] and any(a["accents"]) and not all(a["accents"])
    assert "!>!" in accents.notation_abc and tempo(accents) == 121
    undone = ask(s, "Undo that")
    assert exercise(undone) == exercise(harder) and undone.notation_abc == harder.notation_abc and "!>!" not in undone.notation_abc
    redone = ask(s, "Redo")
    assert redone.notation_abc == accents.notation_abc and exercise(redone) == exercise(accents)
    assert last_exercise(s).context.concert_key == "Cm" and last_exercise(s).context.instrument == "Flute"


@pytest.mark.parametrize("question", [ASK, ASK_CHORDS], ids=["key_based", "chord_following"])
@pytest.mark.parametrize("name, instrument, sax", [("Alto", "Saxophone", SAXES["Alto"]), ("Tenor", "Saxophone", SAXES["Tenor"]), ("Trumpet", "Trumpet", None)])
def test_the_conversation_keeps_exact_transposition_for_transposing_instruments(question, name, instrument, sax):
    s, first = start(question, instrument=instrument, sax=sax)
    for q in ("Make it slower", "Make it harder", "Add accents", "Undo that", "Redo", "Make it easier"):
        resp = ask(s, q, instrument=instrument)
        ex = exercise(resp)
        assert {w - c for c, w in zip(ex["midi"], ex["written"]["midi"])} == {exercise(first)["provenance"]["offset"]}, q
        assert ex["validation"]["ok"] and ex["context"]["instrument"] == instrument, q


def test_undo_returns_the_exact_original_pattern_after_every_kind_of_change():
    for question in (ASK, ASK_CHORDS):
        s, first = start(question)
        for q in ("Make it slower", "Make it harder", "Add accents"):
            ask(s, q)
        for _ in range(3):
            last = ask(s, "Undo that")
        assert last.notation_abc == first.notation_abc and exercise(last) == exercise(first)


def test_the_difficulty_ladder_goes_both_ways_for_both_kinds_and_stops_at_the_ends():
    for question in (ASK, ASK_CHORDS):
        s, _ = start(question)
        for want in ("Advanced+", "Advanced++"):
            assert exercise(ask(s, "Make it harder"))["transform"]["level_to"] == want
        top = ask(s, "Make it harder")
        assert "already the hardest" in top.direct_answer and top.diagnostics["exercise_followup_failed"]
        for want in ("Advanced+", "Advanced", "Intermediate", "Beginner"):
            assert exercise(ask(s, "Make it easier"))["transform"]["level_to"] == want
        assert "already the easiest" in ask(s, "Make it easier").direct_answer


def test_a_chord_following_pattern_keeps_its_chords_scales_and_timeline_through_difficulty_changes():
    s, first = start(ASK_CHORDS)
    base = exercise(first)["provenance"]["segments"]
    scales = {g["chord"]: {sph.pc_of(n) for n in g["scale_notes"]} for g in base}
    for q in ("Make it harder", "Make it harder", "Make it easier", "Make it easier", "Make it easier"):
        ex = exercise(ask(s, q))
        assert ex["provenance"]["segments"] == base and ex["validation"]["ok"]
        assert all(m % 12 in scales[ex["chords"][ci]] for m, ci in zip(ex["midi"], ex["chord_assignment"]))


def test_chord_roles_make_chord_tone_accents_possible_on_a_chord_following_pattern():
    s, _ = start(ASK_CHORDS)
    resp = ask(s, "Accent the chord tones")
    ex = exercise(resp)
    assert not resp.diagnostics.get("exercise_followup_failed") and any(ex["accents"])
    assert all(r for r, a in zip(ex["chord_roles"], ex["accents"]) if a)


def test_key_based_patterns_refuse_chord_role_targets_and_say_what_to_ask_instead():
    s, _ = start()
    t = ask(s, "Add accents to the guide tones")
    assert t.diagnostics["exercise_followup_failed"] and "chord roles" in t.direct_answer and "over the chord changes" in t.direct_answer


def test_accents_with_a_named_target_and_dynamics_are_handled_honestly():
    s, first = start()
    r = ask(s, "Accent every second note")
    assert not r.diagnostics.get("exercise_followup_failed") and sum(exercise(r)["accents"]) == len(exercise(first)["notes"]) // 2
    d = ask(s, "Add a crescendo")
    assert d.diagnostics["exercise_followup_failed"] and "Dynamics" in d.direct_answer


@pytest.mark.parametrize("q", ["Give me another one", "Move it up a step", "Keep the notes but change the rhythm", "Keep the rhythm but change the notes",
                               "Add some chromatic approaches", "Change the pattern to fourths"])
def test_unsupported_followups_get_a_clear_answer_and_leave_the_exercise_alone(q):
    s, _ = start()
    before = dict(s[AMI_LAST_EXERCISE_KEY])
    r = ask(s, q)
    assert "unchanged" in r.direct_answer and (r.diagnostics.get("exercise_followup_failed") or r.diagnostics.get("exercise_revision_failed"))
    assert s[AMI_LAST_EXERCISE_KEY] == before and cs.history(s)["versions"] == 1


def test_the_list_of_what_can_change_is_specific_to_scale_patterns():
    s, _ = start()
    msg = " ".join(ask(s, "Change the pattern to fourths").practice_steps)
    assert "harder or easier" in msg and "accents" in msg and "moving or sequencing" not in msg and "new notes" not in msg


# ================================================================ 6. ownership and stale context
def test_practice_key_and_other_app_state_are_never_written():
    s, _ = start(ASK_CHORDS)
    before = {k: v for k, v in s.items() if not k.startswith(("_ami_", "_music_"))}
    for q in ("Make it slower", "Make it harder", "Add accents", "Undo that", "Redo"):
        ask(s, q)
    assert {k: v for k, v in s.items() if not k.startswith(("_ami_", "_music_"))} == before


def test_a_song_change_cannot_reuse_the_exercise():
    s, _ = start(ASK_CHORDS)
    for q in ("Make it slower", "Make it harder", "Undo that"):
        r = ask(s, q, song="Autumn Leaves")
        assert "built for **Blue Bossa**" in r.direct_answer and r.diagnostics["exercise_revision_failure_reason"] == "song_changed"
    assert cs.history(s)["versions"] == 1 and cs.working_tempo(s) == 135
    assert tempo(ask(s, "Make it slower")) == 121


def test_a_new_request_on_the_new_song_is_not_blocked_and_carries_that_songs_key():
    s, _ = start()
    r = ask(s, ASK.replace("Blue Bossa", "Autumn Leaves"), song="Autumn Leaves", key="Gm", sections={"A": ["Cm7", "F7"]})
    assert exercise(r)["context"]["song_title"] == "Autumn Leaves" and exercise(r)["tonic"] == "G" and exercise(r)["mode"] == "natural minor"


def test_account_and_workspace_isolation_for_scale_pattern_exercises():
    s, _ = start(ASK_CHORDS)
    s["_suite_auth_user_id"] = "u2"
    assert "no exercise from this conversation" in ask(s, "Make it slower").direct_answer.lower()
    s2, _ = start()
    s2["_suite_active_workspace_id"] = "ariel"
    assert "no exercise from this conversation" in ask(s2, "Undo that").direct_answer.lower()


def test_no_billable_call_is_made_by_any_scale_pattern_revision():
    s, _ = start(ASK_CHORDS)
    for q in ("Make it slower", "Make it harder", "Add accents", "Undo that", "Redo", "Make it easier"):
        ask(s, q)            # the autouse fixture raises on any live API call


def test_six_eight_tempo_marking_is_swapped_correctly():
    from music_coach_ami import exercise_revision as er

    assert er._swap_tempo("X:1\nQ:3/8=96\nK:C", 80) == "X:1\nQ:3/8=80\nK:C"
    assert cs.tempo_of_abc("X:1\nQ:3/8=96\nK:C") == 96


# ================================================================ 7. the harmony module itself
@pytest.mark.parametrize("chord, kind", [("Cm7", "aeolian"), ("Fm7", "dorian"), ("Dm7b5", "locrian"), ("G7", "mixolydian b6"), ("G7#5", "altered"), ("G7b9", "phrygian dominant"),
                                         ("B7alt", "altered"), ("Cm6", "dorian"), ("G13", "mixolydian"), ("Ab7", "mixolydian"), ("Dbmaj7", "ionian"), ("Cm(maj7)", "melodic minor"),
                                         ("G7sus4", "mixolydian"), ("Bb7#11", "lydian dominant"), ("CM7", "ionian"), ("C/E", "ionian")])
def test_chord_scales_in_c_minor_and_each_holds_every_chord_tone(chord, kind):
    scale = sph.chord_scale_for(chord, sph.practice_key_scale("Cm"))
    assert scale.kind == kind and set(sph.chord_tone_roles(chord)) <= {sph.pc_of(n) for n in scale.notes}


@pytest.mark.parametrize("chord, kind", [("Dm7", "dorian"), ("Em7", "phrygian"), ("Am7", "aeolian"), ("G7", "mixolydian"), ("Cmaj7", "ionian"), ("E7", "mixolydian"), ("A7b9", "phrygian dominant")])
def test_chord_scales_in_c_major(chord, kind):
    assert sph.chord_scale_for(chord, sph.practice_key_scale("C")).kind == kind


@pytest.mark.parametrize("chord", ["Bdim7", "G7#9"])
def test_chords_that_cannot_be_given_a_verified_scale_raise_with_a_reason(chord):
    with pytest.raises(ValueError) as exc:
        sph.chord_scale_for(chord, sph.practice_key_scale("Cm"))
    assert chord in str(exc.value)


def test_scale_spelling_agrees_with_the_engines_own_spelling_for_the_modes_it_knows():
    from music_coach_ami.musical_idea_engine import authoritative_scale_degrees

    for root in ("C", "G", "Bb", "F#", "Eb", "A"):
        for kind, name in (("ionian", "major"), ("dorian", "dorian"), ("mixolydian", "mixolydian"), ("lydian", "lydian"), ("aeolian", "natural minor"), ("locrian", "locrian")):
            try:
                mine = sph.spell_scale(root, kind)
            except ValueError:
                continue                                  # needs a double accidental: refused here by design
            assert mine == authoritative_scale_degrees(root, name), (root, kind)


def test_chord_tone_roles_include_alterations():
    assert sph.chord_tone_roles("G7#5") == {7: "R", 11: "3", 3: "5", 5: "7"} and sph.chord_tone_roles("G7b9")[8] == "9"
    assert sph.chord_tone_roles("Dm7b5") == {2: "R", 5: "3", 8: "5", 0: "7"}


def test_timeline_segments_reject_slots_whose_beats_do_not_add_up():
    with pytest.raises(ValueError):
        sph.timeline_segments(["C:3|G:3"], 1)
    with pytest.raises(ValueError):
        sph.timeline_segments([], 4)


def test_wants_chord_following_phrases():
    yes = ["over the chord changes", "scale pattern for each chord", "that follows the chords", "chord-following pattern", "over the progression", "through the changes"]
    no = ["advanced scale pattern over Blue Bossa", "scale pattern over Cm7", "a scale pattern in thirds", "scale pattern in G"]
    assert all(sph.wants_chord_following(q) for q in yes) and not any(sph.wants_chord_following(q) for q in no)


@pytest.mark.parametrize("question", ["Give me an A minor pentatonic pattern.", "Give me a pentatonic pattern in thirds", "Give me a blues scale pattern"])
def test_pentatonic_and_blues_patterns_stay_on_the_legacy_path_that_dev_pins(question):
    s = session("Piano")
    resp = ask(s, question, instrument="Piano", sections={"A": ["Am7", "D7"]}, key="Am")
    assert resp.notation_abc and not resp.diagnostics.get("generated_exercise_id") and AMI_LAST_EXERCISE_KEY not in s
    assert "scale_pattern_exercise_failed" not in resp.diagnostics and "can't verify" not in resp.direct_answer
