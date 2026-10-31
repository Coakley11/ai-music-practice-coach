"""AMI M1c: one structured scale pattern, revised through conversation — intervals, chromatic approaches, rhythm, anticipation, difficulty.

The musical contract under test:

* every revision changes only what it names (a pitch change never moves the rhythm; a rhythm change never reorders the pitches),
* the chord timeline (split bars included) and the written/sounding relationship survive every revision,
* every chromatic approach note is a half step from the chord tone (key-based: tonic-chord tone) it resolves to,
* a harmonic anticipation is a deliberate, tagged note of the *next* chord an eighth early — syncopation alone never touches the harmony,
* difficulty is a deterministic walk through the recipe that keeps the player's interval shape,
* everything is reversible exactly (undo / redo), isolated per account and workspace, and needs no API call.
"""

from __future__ import annotations

import re
from fractions import Fraction

import pytest

from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY as SAX_KEY
from music_coach_ami import conversation_state as cs
from music_coach_ami import exercise_scale_pattern as sp
from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami import scale_pattern_recipe as rc
from music_coach_ami import scale_pattern_transforms as tr
from music_coach_ami.claude_client import AnthropicTransport
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.musical_idea_engine import MusicalEvent
from music_coach_ami.pipeline import run_coach_submit

BOSSA_A = ["Cm7", "Cm7", "Fm7", "Fm7", "Dm7b5", "G7#5", "Cm7", "Cm7"]
BOSSA_B = ["Ebm7", "Ab7", "Dbmaj7", "Dbmaj7", "Dm7b5", "G7", "Cm7", "Cm7"]
ASK = "Give me an advanced scale pattern over Blue Bossa."
ASK_CHORDS = "Give me an advanced scale pattern over the chord changes of Blue Bossa."
OFFSET = {"Flute": 0, "Alto": 9, "Tenor": 14, "Soprano": 2, "Trumpet": 2, "Clarinet": 2, "Piano": 0}
SAXES = {"Alto": "Alto saxophone (Eb)", "Tenor": "Tenor saxophone (Bb)", "Soprano": "Soprano saxophone (Bb)"}
F = Fraction


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


def session(instrument="Flute", sax=None, user="u1"):
    s = {"_suite_auth_user_id": user, "_suite_active_workspace_id": "daniel", "instrument": instrument}
    if sax:
        s[SAX_KEY] = sax
    return s


def ask(s, q, **kw):
    return run_coach_submit(q, s, ami_ctx=ctx(**kw))[1]


def start(q=ASK, instrument="Flute", sax=None, s=None, **kw):
    s = s if s is not None else session(instrument, sax)
    resp = ask(s, q, instrument=instrument, **kw)
    assert resp.diagnostics.get("generated_exercise_id"), (resp.diagnostics.get("scale_pattern_exercise_failed"), resp.direct_answer[:200])
    return s, resp


def exercise(resp):
    return resp.diagnostics["generated_exercise"]


def failed(resp):
    return bool(resp.diagnostics.get("exercise_followup_failed") or resp.diagnostics.get("exercise_revision_failed"))


def inst_kwargs(name):
    return {"instrument": {"Alto": "Alto Saxophone", "Tenor": "Tenor Saxophone", "Soprano": "Soprano Saxophone"}.get(name, name),
            "sax": SAXES.get(name)}


def begin(q, name="Flute", **kw):
    ik = inst_kwargs(name)
    s = session(ik["instrument"], ik["sax"])
    resp = ask(s, q, instrument=ik["instrument"], **kw)
    assert resp.diagnostics.get("generated_exercise_id"), (name, resp.diagnostics.get("scale_pattern_exercise_failed"))
    return s, resp, ik["instrument"]


# ---------------------------------------------------------------- reading an exercise back, independently of the builder


def wevents(ex):
    return ex["provenance"]["written_events"]


def dur(e):
    name = str(e["duration"]).lower().replace("rest_", "")
    return tr.BEATS[name]


def rest(e):
    return not str(e["spelled"] or "").strip() or str(e["duration"]).startswith("rest")


def pitched(ex):
    return [e for e in wevents(ex) if not rest(e)]


def per_bar(ex):
    return F(3) if ex["meter"] == "3/4" else F(4)


def midi_of_row(e):
    return sph.midi_of(e["spelled"], int(e["octave"]))


def pitch_order(ex):
    return list(ex["midi"])


def rhythm_sig(ex):
    return [(e["bar_index"], e["beat"], e["duration"]) for e in wevents(ex)]


def segments(ex):
    return ex["provenance"]["segments"]


def offset_of(ex):
    return ex["provenance"]["offset"]


def assert_sound(ex, *, chords=None):
    """The independent invariants every exercise this module produces must satisfy, recomputed from the stored data alone."""
    assert ex["validation"]["ok"], [c for c in ex["validation"]["checks"] if not c["ok"]]
    off = offset_of(ex)
    notes = pitched(ex)
    assert len(notes) == len(ex["midi"]) == len(ex["notes"])
    # written pitch is sounding pitch plus the one constant, octave included
    assert all(midi_of_row(w) - m == off for w, m in zip(notes, ex["midi"]))
    # every bar adds up exactly, and nothing crosses a bar line
    pb = per_bar(ex)
    totals: dict[int, Fraction] = {}
    for e in wevents(ex):
        assert F(str(e["beat"])).limit_denominator(8) + dur(e) <= pb
        totals[e["bar_index"]] = totals.get(e["bar_index"], F(0)) + dur(e)
    assert sorted(totals) == list(range(ex["bars"])) and all(t == pb for t in totals.values()), totals
    # onsets are contiguous
    cursor = F(0)
    for e in sorted(wevents(ex), key=lambda e: e["bar_index"] * pb + F(str(e["beat"])).limit_denominator(8)):
        assert e["bar_index"] * pb + F(str(e["beat"])).limit_denominator(8) == cursor
        cursor += dur(e)
    # the notation itself validates (bars, durations, rests), as the engine's own writer sees it
    from music_coach_ami.musical_idea_engine import composition_to_abc

    _abc, ndiag = composition_to_abc(sp.composition_of(sp.GeneratedExercise.from_dict(ex)), title="check", bpm=100)
    assert ndiag["notation_validation_ok"], ndiag["notation_validation_errors"]
    # approach notes: a half step from the note they resolve to, spelled sharp rising / flat falling, target a tone of the chord (or key)
    seq = [e for e in wevents(ex) if not rest(e)]
    for i, e in enumerate(seq):
        if e["tone_role"] in ("approach_below", "approach_above"):
            nxt = seq[i + 1]
            step = midi_of_row(nxt) - midi_of_row(e)
            assert step == (1 if e["tone_role"] == "approach_below" else -1)
            if e["tone_role"] == "approach_below":
                assert "b" not in e["spelled"][1:], e["spelled"]
            else:
                assert "#" not in e["spelled"], e["spelled"]
        if e["tone_role"] == "anticipation":
            nxt = next(x for x in seq[i + 1:] if not x["tone_role"].startswith("approach"))
            assert dur(e) == F(1, 2) and midi_of_row(nxt) == midi_of_row(e)
    return ex


def concert_chord_notes(ex, i):
    return ex["chords"][ex["chord_assignment"][i]]


# ================================================================ 1. understanding the request
@pytest.mark.parametrize("q, op", [
    ("Change it to fourths", ("shape", "fourths")), ("Change this pattern to thirds.", ("shape", "thirds")),
    ("Make it a pattern in fourths", ("shape", "fourths")), ("Keep the same rhythm but use fourths", ("shape", "fourths")),
    ("Use fifths", ("shape", "fifths")), ("Make it stepwise", ("shape", "scalar")), ("Can you change it to thirds please", ("shape", "thirds")),
    ("Use a mix of thirds and fourths", ("shape", "mixed")),
    ("Make the intervals wider", ("wider", "")), ("Give me a more advanced interval pattern", ("interval_advance", "")),
    ("Make the intervals narrower", ("narrower", "")), ("Simplify the notes without changing the tempo", ("simplify_notes", "")),
    ("Add chromatic approaches", ("approach", "both")), ("Approach the chord tones from below", ("approach", "below")),
    ("Approach the chord tones from above", ("approach", "above")), ("Make the line more chromatic", ("approach_more", "")),
    ("Add more advanced jazz vocabulary", ("approach_more", "")), ("Remove the chromatic approaches", ("approach_off", "")),
    ("Make the rhythm more syncopated", ("sync_more", "")), ("Use more offbeats", ("sync_more", "")),
    ("Make it more rhythmically advanced", ("sync_more", "")), ("Add some rhythmic displacement", ("displace", "on")),
    ("Keep the same notes but change the rhythm", ("new_rhythm", "")), ("Straighten the rhythm", ("sync_less", "")),
    ("Add anticipations of the next chord", ("anticipate", "on")), ("Remove the anticipations", ("anticipate", "off")),
])
def test_requests_are_understood(q, op):
    change = rc.parse_pattern_change(q)
    assert change is not None and op in change.ops and not change.unsupported, (q, change)


@pytest.mark.parametrize("q", [
    "Give me an advanced scale pattern over Blue Bossa.", "Give me a pattern in fourths", "Why do we use chromatic approaches?",
    "What are fourths?", "Explain syncopation", "Make it slower", "Undo that", "Redo", "Add accents", "Give me another one",
    "Show me a scale pattern over the chord changes", "Tell me about anticipations",
])
def test_new_requests_questions_and_other_revisions_are_not_mistaken_for_pattern_changes(q):
    assert rc.parse_pattern_change(q) is None


def test_a_request_can_name_several_changes_in_the_order_given():
    change = rc.parse_pattern_change("Make a pattern in thirds with chromatic approaches")
    assert change.ops == (("shape", "thirds"), ("approach", "both"))


def test_unsupported_intervals_are_named_not_guessed():
    change = rc.parse_pattern_change("Change it to sixths")
    assert change.unsupported == ("sixths, sevenths or octaves",) and not change.ops


# ================================================================ 2. the recipe and its difficulty walk
def test_the_first_steps_of_the_walk_are_exactly_the_m1d_ladder():
    r, labels = rc.Recipe(level="beginner", subdivision="quarter"), []
    labels.append(r.label())
    for _ in range(4):
        r = rc.advance(r)[0]
        labels.append(r.label())
    assert labels == ["Beginner", "Intermediate", "Advanced", "Advanced+", "Advanced++"]


@pytest.mark.parametrize("shape", ["scalar", "thirds", "fourths", "fifths", "mixed"])
def test_every_step_up_is_harder_every_step_down_is_easier_and_the_shape_is_kept(shape):
    r = rc.Recipe(level="beginner", subdivision="quarter", shape=shape)
    scores, cur = [r.score()], r
    while (got := rc.advance(cur)) is not None:
        cur = got[0]
        scores.append(cur.score())
        assert cur.shape == shape, "difficulty must not replace the interval shape the player chose"
    assert scores == sorted(set(scores)) and len(scores) >= 9
    down = [cur.score()]
    while (got := rc.ease(cur)) is not None:
        cur = got[0]
        down.append(cur.score())
        assert cur.shape in (shape, *rc.WIDTH_ORDER)
    assert down == sorted(set(down), reverse=True)


def test_advancing_never_skips_back_to_a_simple_scale_once_fourths_are_chosen():
    r = rc.Recipe(shape="fourths")
    while (got := rc.advance(r)) is not None:
        r = got[0]
        assert r.shape == "fourths" and r.cell().startswith("fourths")


def test_widening_walks_scale_steps_thirds_fourths_fifths_and_stops():
    r, seen = rc.Recipe(), []
    while (got := rc.widen(r)) is not None:
        r = got[0]
        seen.append((r.shape, r.tier))
    assert [s for s, _ in seen][-1] == "fifths" and ("thirds", 0) in seen and ("fourths", 0) in seen
    assert rc.widen(r) is None


def test_the_recipe_round_trips_through_its_stored_form():
    r = rc.Recipe(level="advanced", subdivision="sixteenth", shape="fourths", tier=2, approach="below", approach_density=2, syncopation=2,
                  displaced=True, anticipation=True)
    assert rc.Recipe.from_dict(r.to_dict()) == r


# ================================================================ 3. the transforms, on a known line
def line(unit="eighth", bars=2, meter="4/4", chord="Cm7", start_midi=72, names=("C", "D", "Eb", "F", "G", "Ab", "Bb", "C")):
    """A straight ascending line of unit-length notes over one chord (default: C natural minor from C5)."""
    pb = tr.per_bar_of(meter)
    step = tr.BEATS[unit]
    semis = [0, 2, 3, 5, 7, 8, 10, 12]
    out, onset, i = [], F(0), 0
    while onset < pb * bars:
        spelled, midi = names[i % 8], start_midi + semis[i % 8]
        bar = int(onset // pb)
        out.append(MusicalEvent(spelled=spelled, octave=sph.octave_for(spelled, midi), duration=unit, bar_index=bar, beat=float(onset - pb * bar),
                                scale_degree=(i % 7) + 1, pitch_class=sph.pc_of(spelled), chord=chord, role="pattern", domain="concert",
                                tone_role="chord_tone"))
        onset += step
        i += 1
    return out


def midis(events):
    return [sph.midi_of(e.spelled, int(e.octave)) for e in events if not tr.is_rest(e)]


def total(events, pb):
    return sum((tr.dur_of(e) for e in events), F(0))


def test_syncopation_with_eighths_keeps_every_pitch_in_order_and_every_bar_whole():
    evs = line("eighth", bars=2)
    for level in (1, 2):
        out, dropped = tr.retime(evs, per_bar=F(4), pieces=[(F(0), F(4)), (F(4), F(4))], level=level, displaced=False)
        assert dropped == 0 and midis(out) == midis(evs) and total(out, F(4)) == F(8)
        assert tr.verify(out, per_bar=F(4), bars=2, is_target=lambda e: True, chord_pcs=None) == []
    full, _ = tr.retime(evs, per_bar=F(4), pieces=[(F(0), F(4)), (F(4), F(4))], level=2, displaced=False)
    # a held note starts on an offbeat in every two-beat group
    held = [(tr.onset_of(e, F(4)) % 1, tr.dur_of(e)) for e in full if tr.dur_of(e) >= 1]
    assert len(held) == 4 and all(o == F(1, 2) for o, _ in held)


def test_light_syncopation_touches_every_other_group_full_touches_all():
    evs = line("eighth", bars=1)
    light, _ = tr.retime(evs, per_bar=F(4), pieces=[(F(0), F(4))], level=1, displaced=False)
    full, _ = tr.retime(evs, per_bar=F(4), pieces=[(F(0), F(4))], level=2, displaced=False)
    assert sum(1 for e in light if tr.dur_of(e) == F(1)) == 1 and sum(1 for e in full if tr.dur_of(e) == F(1)) == 2


def test_syncopation_at_sixteenth_speed_is_refused_rather_than_dropping_notes():
    evs = line("sixteenth", bars=1)
    for level, displaced in ((1, False), (2, False), (0, True), (2, True)):
        with pytest.raises(tr.TransformUnavailable, match="sixteenth"):
            tr.retime(evs, per_bar=F(4), pieces=[(F(0), F(4))], level=level, displaced=displaced)


def test_quarter_note_patterns_are_not_syncopated_silently():
    with pytest.raises(tr.TransformUnavailable, match="eighth notes or faster"):
        tr.retime(line("quarter", bars=1), per_bar=F(4), pieces=[(F(0), F(4))], level=1, displaced=False)


def test_displacement_starts_late_with_a_rest_and_keeps_every_note():
    evs = line("eighth", bars=1)
    out, dropped = tr.retime(evs, per_bar=F(4), pieces=[(F(0), F(4))], level=0, displaced=True)
    assert tr.is_rest(out[0]) and tr.dur_of(out[0]) == F(1, 2) and dropped == 0
    assert midis(out) == midis(evs) and total(out, F(4)) == F(4)                 # same pitches, same order, same bar length
    assert [tr.dur_of(e) for e in out if not tr.is_rest(e)][-2:] == [F(1, 4), F(1, 4)]    # made room with a sixteenth-note pick-up at the end


def test_displacement_in_three_four_and_in_short_chord_segments_keeps_the_bars_whole():
    evs = line("eighth", bars=2, meter="3/4")
    out, dropped = tr.retime(evs, per_bar=F(3), pieces=[(F(0), F(3)), (F(3), F(3))], level=1, displaced=True)
    assert total(out, F(3)) == F(6) and dropped == 0 and midis(out) == midis(evs) and tr.verify(out, per_bar=F(3), bars=2, is_target=lambda e: True, chord_pcs=None) == []


def test_chromatic_approaches_are_half_steps_to_chord_tones_on_strong_beats_only():
    evs = line("eighth", bars=2)
    core = {0, 3, 7, 10}      # Cm7
    out, applied = tr.add_approaches(evs, per_bar=F(4), mode="both", density=1, is_target=lambda e: sph.pc_of(e.spelled) in core,
                                     segment_starts={F(0), F(4)}, bounds=(40, 100))
    assert applied and len(out) == len(evs)
    for a in applied:
        app, tgt = out[a["index"]], out[a["target_index"]]
        assert a["target_index"] == a["index"] + 1 and abs(sph.midi_of(app.spelled, app.octave) - sph.midi_of(tgt.spelled, tgt.octave)) == 1
        assert sph.pc_of(tgt.spelled) in core and (tr.onset_of(tgt, F(4)) % 2 == 0)
        assert app.tone_role == (tr.APPROACH_BELOW if sph.midi_of(app.spelled, app.octave) < sph.midi_of(tgt.spelled, tgt.octave) else tr.APPROACH_ABOVE)
    # durations and the number of notes are untouched: only pitches moved
    assert [e.duration for e in out] == [e.duration for e in evs]


def test_the_player_can_choose_the_side_of_the_approach():
    evs = line("eighth", bars=2)
    for mode, role in (("below", tr.APPROACH_BELOW), ("above", tr.APPROACH_ABOVE)):
        out, applied = tr.add_approaches(evs, per_bar=F(4), mode=mode, density=2, is_target=lambda e: sph.pc_of(e.spelled) in {0, 3, 7, 10},
                                         segment_starts={F(0), F(4)}, bounds=(40, 100))
        assert applied and {out[a["index"]].tone_role for a in applied} == {role}


def test_an_approach_that_would_leave_the_instrument_range_is_not_placed():
    evs = line("eighth", bars=2)
    out, applied = tr.add_approaches(evs, per_bar=F(4), mode="both", density=2, is_target=lambda e: True, segment_starts={F(0)}, bounds=(72, 72))
    assert applied == [] and out == evs


def test_approach_spelling_is_sharp_rising_and_flat_falling():
    for pc in range(12):
        midi = 60 + pc
        up = tr._neighbour(midi, True)
        down = tr._neighbour(midi, False)
        assert up[2] == midi - 1 and down[2] == midi + 1
        assert "b" not in up[0][1:] and "#" not in down[0]


def test_anticipation_plays_the_next_chords_first_note_an_eighth_early_and_nothing_else_moves():
    a = line("eighth", bars=1, chord="Cm7")
    b = [MusicalEvent(**{**e.__dict__, "bar_index": 1}) for e in line("eighth", bars=1, chord="Fm7", start_midi=77,
                                                                           names=("F", "G", "Ab", "Bb", "C", "Db", "Eb", "F"))]
    evs = a + b
    out, records = tr.anticipate(evs, per_bar=F(4), boundaries=[(F(4), "Cm7", "Fm7")])
    assert len(out) == len(evs) and records[0]["replaced"] == 1
    ant = [e for e in out if e.tone_role == tr.ANTICIPATION]
    assert len(ant) == 1 and ant[0].chord == "Cm7" and tr.onset_of(ant[0], F(4)) == F(7, 2)
    first_f = next(e for e in out if e.chord == "Fm7" and e.tone_role != tr.ANTICIPATION)
    assert sph.midi_of(ant[0].spelled, ant[0].octave) == sph.midi_of(first_f.spelled, first_f.octave)
    assert tr.verify(out, per_bar=F(4), bars=2, is_target=lambda e: True, chord_pcs=lambda c: {5, 8, 0, 3}) == []
    # everything but that one eighth is exactly as before
    assert [e for e in out if e.tone_role != tr.ANTICIPATION] == [e for e in evs if tr.onset_of(e, F(4)) != F(7, 2)]


def test_anticipation_on_a_mid_bar_change_uses_the_and_of_two():
    a = line("eighth", bars=1, chord="Cm7")
    # chord changes on beat 3 of bar 1
    evs = [MusicalEvent(**{**e.__dict__, "chord": "Fm7" if tr.onset_of(e, F(4)) >= 2 else "Cm7"}) for e in a]
    out, _ = tr.anticipate(evs, per_bar=F(4), boundaries=[(F(2), "Cm7", "Fm7")])
    ant = next(e for e in out if e.tone_role == tr.ANTICIPATION)
    assert tr.onset_of(ant, F(4)) == F(3, 2)


def test_verify_catches_a_broken_line():
    evs = line("eighth", bars=1)
    broken = evs[:-1]
    assert tr.verify(broken, per_bar=F(4), bars=1, is_target=lambda e: True, chord_pcs=None)
    bad = list(evs)
    bad[2] = MusicalEvent(**{**bad[2].__dict__, "tone_role": tr.APPROACH_BELOW})      # a tagged approach that is not a half step from the next note
    assert any("half_step" in e for e in tr.verify(bad, per_bar=F(4), bars=1, is_target=lambda e: True, chord_pcs=None))


# ================================================================ 4. the conversation
CONVERSATION = ["Change it to fourths", "Make it more advanced", "Add chromatic approaches", "Make the rhythm more syncopated", "Add accents"]


@pytest.mark.parametrize("q0", [ASK, ASK_CHORDS])
def test_the_complete_blue_bossa_conversation_works_and_undo_redo_are_exact(q0):
    s, first = start(q0)
    versions = [(first.notation_abc, exercise(first))]
    for q in CONVERSATION:
        resp = ask(s, q)
        assert not failed(resp), (q, resp.direct_answer[:200])
        ex = assert_sound(exercise(resp))
        assert ex["context"]["song_title"] == "Blue Bossa" and ex["context"]["concert_key"] == "Cm" and ex["tempo_bpm"] == 135
        assert re.search(r"^Q:\S+=135", resp.notation_abc, re.M)
        versions.append((resp.notation_abc, ex))
    # fourths survived "more advanced"; the later layers are all there
    rec = sp.recipe_of(sp.GeneratedExercise.from_dict(versions[-1][1]))
    assert rec.shape == "fourths" and rec.tier == 1 and rec.has_chromatic() and rec.syncopation == 1
    assert versions[-1][1]["accents"] and any(versions[-1][1]["accents"])
    # undo walks back through exactly the versions that were shown, byte for byte
    for abc, ex in reversed(versions[:-1]):
        back = ask(s, "Undo that")
        assert back.notation_abc == abc and exercise(back) == ex
    assert "Nothing to undo" in ask(s, "Undo that").direct_answer
    for abc, ex in versions[1:]:
        fwd = ask(s, "Redo")
        assert fwd.notation_abc == abc and exercise(fwd) == ex
    assert "Nothing to redo" in ask(s, "Redo").direct_answer
    assert cs.history(s)["versions"] == len(versions)


def test_fourths_are_real_diatonic_fourths_in_the_chords_scale():
    s, _ = start(ASK_CHORDS)
    ex = exercise(ask(s, "Change it to fourths"))
    scales = {g["chord"]: [sph.pc_of(n) for n in g["scale_notes"]] for g in segments(ex)}
    # within each chord segment, the first two notes of every cell are the scale degrees four apart
    by_seg: dict[str, list[int]] = {}
    for m, ci in zip(ex["midi"], ex["chord_assignment"]):
        by_seg.setdefault(ex["chords"][ci], []).append(m % 12)
    for chord, pcs in by_seg.items():
        order = scales[chord]
        for a, b in zip(pcs[0::2], pcs[1::2]):
            assert (order.index(b) - order.index(a)) % 7 == 3, (chord, a, b)


def test_thirds_in_a_key_based_pattern_are_diatonic_thirds_of_the_practice_keys_scale():
    s, _ = start(ASK)
    ex = exercise(ask(s, "Change it to thirds"))
    scale = [sph.pc_of(n) for n in ["C", "D", "Eb", "F", "G", "Ab", "Bb"]]
    pcs = [m % 12 for m in ex["midi"]]
    assert set(pcs) <= set(scale)
    assert all((scale.index(b) - scale.index(a)) % 7 == 2 for a, b in zip(pcs[0::2], pcs[1::2]))


def test_a_pitch_change_leaves_the_rhythm_alone_and_a_rhythm_change_leaves_the_pitch_order_alone():
    for q0 in (ASK, ASK_CHORDS):
        s, first = start(q0)
        base = exercise(first)
        for q in ("Change it to fourths", "Add chromatic approaches", "Make the intervals wider", "Simplify the notes"):
            ex = exercise(ask(s, q))
            assert rhythm_sig(ex) == rhythm_sig(base), q
        s, first = start(q0)
        base_midi = pitch_order(exercise(first))
        for q in ("Make the rhythm more syncopated", "Make the rhythm more syncopated"):
            ex = exercise(ask(s, q))
            assert pitch_order(ex) == base_midi, q          # eighth notes: nothing is dropped, nothing reordered
            assert segments(ex) == segments(exercise(first))
        straight = ask(s, "Straighten the rhythm")
        assert pitch_order(exercise(straight)) == base_midi and rhythm_sig(exercise(straight)) != rhythm_sig(exercise(ask(s, "Make the rhythm more syncopated")))


def test_syncopation_never_changes_the_harmony_but_anticipation_does_exactly_what_it_says():
    s, first = start(ASK_CHORDS)
    base = exercise(first)
    syn = exercise(ask(s, "Make the rhythm more syncopated"))
    assert segments(syn) == segments(base) and [c for c in syn["chord_assignment"]] == [c for c in base["chord_assignment"]]
    assert not any(e["tone_role"] == "anticipation" for e in wevents(syn))
    ant = ask(s, "Add anticipations of the next chord")
    assert not failed(ant)
    ex = assert_sound(exercise(ant))
    tagged = [e for e in wevents(ex) if e["tone_role"] == "anticipation"]
    changes = sum(1 for a, b in zip(segments(base), segments(base)[1:]) if a["chord"] != b["chord"])
    assert len(tagged) == changes == 4                       # Cm7>Fm7, Fm7>Dm7b5, Dm7b5>G7#5, G7#5>Cm7
    assert segments(ex) == segments(base)                    # the charted chord timeline is untouched
    assert "eighth note early" in " ".join(ant.practice_steps) and "Anticipations" in " ".join(ant.practice_steps)
    # each anticipated note is a tone of the chord that follows, played an eighth early
    for e in tagged:
        assert e["beat"] % 1 == 0.5 and e["duration"] == "eighth"


def test_anticipation_follows_a_split_bar_and_a_mid_bar_change():
    sections = {"Section A": ["Dm7|G7", "Cmaj7", "Dm7b5|G7", "Cm7"]}
    s, first = start(ASK_CHORDS, sections=sections)
    ex0 = exercise(first)
    assert [(g["bar"], g["beat"], g["chord"]) for g in segments(ex0)][:3] == [(1, "1", "Dm7"), (1, "3", "G7"), (2, "1", "Cmaj7")]
    ex = assert_sound(exercise(ask(s, "Add anticipations of the next chord", sections=sections)))
    ants = [(e["bar_index"], e["beat"]) for e in wevents(ex) if e["tone_role"] == "anticipation"]
    assert (0, 1.5) in ants and (0, 3.5) in ants              # the and of 2 before the beat-3 change; the and of 4 before bar 2


def test_a_key_based_pattern_refuses_anticipation_and_says_how_to_get_one():
    s, first = start(ASK)
    before = dict(s[AMI_LAST_EXERCISE_KEY])
    resp = ask(s, "Add anticipations of the next chord")
    assert failed(resp) and "no chord changes to anticipate" in resp.direct_answer and "over the chord changes" in resp.direct_answer
    assert s[AMI_LAST_EXERCISE_KEY] == before and cs.history(s)["versions"] == 1


def test_key_based_approaches_target_the_keys_tonic_triad_and_say_they_do_not_follow_chords():
    s, _ = start(ASK)
    resp = ask(s, "Add chromatic approaches")
    ex = assert_sound(exercise(resp))
    text = " ".join(resp.practice_steps)
    assert "tonic-triad" in text and "doesn't follow the chord changes" in text
    seq = [e for e in wevents(ex) if not rest(e)]
    for i, e in enumerate(seq):
        if e["tone_role"].startswith("approach"):
            assert seq[i + 1]["scale_degree"] in (1, 3, 5)


def test_chord_following_approaches_resolve_to_chord_tones_including_across_a_chord_change():
    s, _ = start(ASK_CHORDS)
    ex = assert_sound(exercise(ask(s, "Add chromatic approaches")))
    seq = [e for e in wevents(ex) if not rest(e)]
    crossing = 0
    for i, e in enumerate(seq):
        if e["tone_role"].startswith("approach"):
            tgt = seq[i + 1]
            assert sph.pc_of(tgt["spelled"]) in sp.core_tones(tgt["chord"])
            if tgt["chord"] != e["chord"]:
                crossing += 1
    assert any(e["tone_role"].startswith("approach") for e in seq) and crossing >= 2


def test_approach_direction_requests_are_honoured():
    for word, role in (("below", "approach_below"), ("above", "approach_above")):
        s, _ = start(ASK_CHORDS)
        ex = exercise(ask(s, f"Approach the chord tones from {word}"))
        roles = {e["tone_role"] for e in wevents(ex) if e["tone_role"].startswith("approach")}
        assert roles == {role}


def test_more_chromatic_adds_approaches_and_the_limit_is_stated():
    s, _ = start(ASK_CHORDS)
    one = exercise(ask(s, "Add chromatic approaches"))
    two = exercise(ask(s, "Make the line more chromatic"))
    count = lambda ex: sum(1 for e in wevents(ex) if e["tone_role"].startswith("approach"))   # noqa: E731
    assert count(two) > count(one)
    last = ask(s, "Make the line more chromatic")
    assert failed(last) and "as chromatic as I build" in last.direct_answer


def test_removing_the_approaches_restores_the_pitches_exactly():
    s, first = start(ASK_CHORDS)
    ask(s, "Add chromatic approaches")
    off = ask(s, "Remove the chromatic approaches")
    assert exercise(off)["midi"] == exercise(first)["midi"] and exercise(off)["notes"] == exercise(first)["notes"]


def test_jazz_vocabulary_is_answered_with_what_is_actually_added():
    s, _ = start(ASK_CHORDS)
    resp = ask(s, "Add more advanced jazz vocabulary")
    assert not failed(resp) and "jazz vocabulary I can add so far" in resp.direct_answer
    assert any(e["tone_role"].startswith("approach") for e in wevents(exercise(resp)))


def test_difficulty_up_adds_something_musical_and_keeps_the_chosen_shape():
    s, _ = start(ASK_CHORDS)
    ask(s, "Change it to fourths")
    seen = []
    while True:
        resp = ask(s, "Make it more advanced")
        if failed(resp):
            break
        seen.append(sp.recipe_of(sp.GeneratedExercise.from_dict(exercise(resp))))
        assert seen[-1].shape == "fourths"
    assert [r.score() for r in seen] == sorted({r.score() for r in seen}) and "already the hardest" in resp.direct_answer
    assert any(r.has_chromatic() for r in seen)
    assert not any(r.syncopation or r.displaced for r in seen)      # by then the line is in sixteenths, where a rhythm shift would cost notes


def test_simplify_the_notes_undoes_pitch_complexity_in_order_and_keeps_the_tempo():
    s, _ = start(ASK_CHORDS)
    ask(s, "Change it to fourths")
    ask(s, "Add chromatic approaches")
    r1 = ask(s, "Simplify the notes without changing the tempo")
    assert not any(e["tone_role"].startswith("approach") for e in wevents(exercise(r1))) and exercise(r1)["tempo_bpm"] == 135
    r2 = ask(s, "Simplify the notes")
    assert sp.recipe_of(sp.GeneratedExercise.from_dict(exercise(r2))).shape == "thirds"
    ask(s, "Simplify the notes")
    last = ask(s, "Simplify the notes")
    assert failed(last) and "already as simple" in last.direct_answer


def test_wider_intervals_walk_up_and_stop_at_fifths():
    s, _ = start(ASK)
    shapes = []
    for _ in range(8):
        r = ask(s, "Make the intervals wider")
        if failed(r):
            assert "widest" in r.direct_answer
            break
        shapes.append(sp.recipe_of(sp.GeneratedExercise.from_dict(exercise(r))).shape)
    assert shapes[0] == "thirds" and shapes[-1] == "fifths" and "fourths" in shapes


# ================================================================ 5. tempo, accents and every other conversation step keep working
def test_tempo_changes_and_accents_work_between_pattern_changes_and_survive_them():
    s, _ = start(ASK_CHORDS)
    ask(s, "Change it to fourths")
    slow = ask(s, "Make it slower")
    assert exercise(slow)["tempo_bpm"] == 121
    acc = ask(s, "Accent the downbeats")
    assert sum(exercise(acc)["accents"]) == 8
    more = ask(s, "Add chromatic approaches")
    ex = exercise(more)
    assert ex["tempo_bpm"] == 121 and re.search(r"^Q:\S+=121", more.notation_abc, re.M)
    assert sum(ex["accents"]) == 8, "accents follow the notes through a pitch revision"
    both = ask(s, "Make the rhythm more syncopated and add accents on the guide tones")
    assert not failed(both) and ex["tempo_bpm"] == 121


def test_a_bare_accents_request_inside_a_pattern_change_is_disclosed():
    s, _ = start(ASK_CHORDS)
    resp = ask(s, "Add chromatic approaches and accents")
    assert not failed(resp) and "accented the downbeats" in resp.direct_answer and any(exercise(resp)["accents"])


# ================================================================ 6. instruments, written pitch and register
@pytest.mark.parametrize("name", ["Flute", "Alto", "Tenor", "Soprano", "Trumpet", "Clarinet", "Piano"])
@pytest.mark.parametrize("q0", [ASK, ASK_CHORDS])
def test_every_structured_instrument_keeps_exact_written_pitch_through_every_kind_of_revision(name, q0):
    s, first, inst = begin(q0, name)
    assert offset_of(exercise(first)) == OFFSET[name]
    follows = exercise(first)["provenance"]["kind"] == "chord_following"
    for q in CONVERSATION + ["Make the rhythm more syncopated", "Add some rhythmic displacement"] + (
            ["Add anticipations of the next chord"] if follows else []):
        resp = ask(s, q, instrument=inst)
        assert not failed(resp), (name, q, resp.direct_answer[:240])
        ex = assert_sound(exercise(resp))
        assert offset_of(ex) == OFFSET[name]
        lo, hi = sph.playable_written_range(ex["context"]["notation_instrument"] or ex["context"]["instrument"]) or (0, 200)
        assert all(lo <= midi_of_row(e) <= hi for e in pitched(ex)), (name, q)


@pytest.mark.parametrize("name", ["Alto", "Tenor", "Flute"])
def test_written_chord_labels_and_key_are_the_instruments_after_a_revision(name):
    s, first, inst = begin(ASK_CHORDS, name)
    resp = ask(s, "Change it to fourths", instrument=inst)
    ex = exercise(resp)
    written_chords = [e["chord"] for e in wevents(ex) if e["chord"]]
    first_written = [e["chord"] for e in wevents(exercise(first)) if e["chord"]]
    assert written_chords == first_written                         # the same written chord labels as the first answer
    assert ex["context"]["written_key"] == exercise(first)["context"]["written_key"]


def test_alto_approach_notes_are_written_idiomatically():
    s, _, inst = begin(ASK_CHORDS, "Alto")
    ex = exercise(ask(s, "Add chromatic approaches", instrument=inst))
    apps = [e for e in wevents(ex) if e["tone_role"].startswith("approach")]
    assert apps and all(("#" in e["spelled"]) == (e["tone_role"] == "approach_below") or len(e["spelled"]) == 1 for e in apps)


# ================================================================ 7. other progressions
@pytest.mark.parametrize("song, key, sections", [
    ("ii-V-I", "C", {"Section A": ["Dm7", "G7", "Cmaj7", "Cmaj7"]}),
    ("Autumn Leaves", "Gm", {"Section A": ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7", "Gm7", "Gm7"]}),
    ("Split Bars", "C", {"Section A": ["Dm7|G7", "Cmaj7", "Am7|D7", "Gmaj7"]}),
    ("Uneven Split", "Cm", {"Section A": ["Cm7:3|Fm7:1", "Dm7b5:2|G7:2", "Cm7", "Cm7"]}),
])
def test_other_progressions_stay_correct_under_every_revision(song, key, sections):
    s, first = start(f"Give me an advanced scale pattern over the chord changes of {song}.", song=song, key=key, sections=sections)
    base = exercise(first)
    for q in ["Change it to fourths", "Add chromatic approaches", "Make the rhythm more syncopated", "Add some rhythmic displacement",
              "Add anticipations of the next chord"]:
        resp = ask(s, q, song=song, key=key, sections=sections)
        assert not failed(resp), (song, q, resp.direct_answer[:240])
        ex = assert_sound(exercise(resp))
        assert segments(ex) == segments(base), (song, q)


def test_three_four_chord_following_patterns_revise_correctly():
    sections = {"Section A": ["Cm7", "Fm7", "G7", "Cm7"]}
    s, first = start(ASK_CHORDS, meter="3/4", sections=sections)
    assert exercise(first)["meter"] == "3/4"
    for q in ["Change it to thirds", "Add chromatic approaches", "Make the rhythm more syncopated", "Add anticipations of the next chord"]:
        resp = ask(s, q, meter="3/4", sections=sections)
        assert not failed(resp), (q, resp.direct_answer[:200])
        assert_sound(exercise(resp))


# ================================================================ 8. honest limits
def test_beginner_patterns_stay_plain_and_syncopation_asks_for_more_density_first():
    s, first = start(ASK_CHORDS, level="Beginner")
    ex = exercise(first)
    if sp.recipe_of(sp.GeneratedExercise.from_dict(ex)).subdivision == "quarter":
        resp = ask(s, "Make the rhythm more syncopated", level="Beginner")
        assert failed(resp) and "eighth notes or faster" in resp.direct_answer and "nothing was changed" in resp.direct_answer.lower()
        assert cs.history(s)["versions"] == 1


@pytest.mark.parametrize("q", ["Change it to sixths", "Add chromatic approaches and slurs", "Make it more syncopated and add a crescendo",
                               "Add triplets", "Use fourths for alto saxophone"])
def test_unsupported_requests_are_named_and_change_nothing(q):
    s, _ = start(ASK_CHORDS)
    before = dict(s[AMI_LAST_EXERCISE_KEY])
    n = cs.history(s)["versions"]
    resp = ask(s, q)
    assert failed(resp) and "haven't changed" in resp.direct_answer
    assert s[AMI_LAST_EXERCISE_KEY] == before and cs.history(s)["versions"] == n


def test_repeating_a_change_that_is_already_applied_says_so_and_adds_no_version():
    s, _ = start(ASK_CHORDS)
    ask(s, "Change it to fourths")
    n = cs.history(s)["versions"]
    again = ask(s, "Change it to fourths")
    assert failed(again) and "already in diatonic fourths" in again.direct_answer and cs.history(s)["versions"] == n


def test_nothing_to_revise_without_a_working_exercise():
    s = session()
    for q in ("Change it to fourths", "Make the rhythm more syncopated"):
        resp = ask(s, q)
        assert "no exercise from this conversation" in resp.direct_answer.lower() and not resp.notation_abc


def test_a_revision_never_touches_the_practice_key_or_other_app_state():
    s, _ = start(ASK_CHORDS)
    before = {k: v for k, v in s.items() if not k.startswith(("_ami_", "_music_"))}
    for q in CONVERSATION:
        ask(s, q)
    assert {k: v for k, v in s.items() if not k.startswith(("_ami_", "_music_"))} == before


# ================================================================ 9. ownership and a changed song
def test_another_account_cannot_revise_or_undo_someones_pattern():
    s, first = start(ASK_CHORDS)
    ask(s, "Change it to fourths")
    s["_suite_auth_user_id"] = "u2"                      # same browser session, a different account signs in
    for q in ("Change it to thirds", "Add chromatic approaches", "Undo that"):
        resp = ask(s, q)
        assert ("no exercise from this conversation" in resp.direct_answer.lower() or "no generated exercise" in resp.direct_answer.lower()) and not resp.notation_abc
    s["_suite_auth_user_id"] = "u1"
    assert "no exercise from this conversation" in ask(s, "Change it to thirds").direct_answer.lower()    # u1's state was purged on the switch


def test_a_pattern_made_for_another_song_is_not_silently_revised():
    s, _ = start(ASK_CHORDS)
    for q in ("Change it to fourths", "Add chromatic approaches", "Add anticipations of the next chord", "Make the rhythm more syncopated"):
        resp = ask(s, q, song="Autumn Leaves", key="Gm", sections={"Section A": ["Cm7", "F7", "Bbmaj7", "Ebmaj7"]})
        assert "Blue Bossa" in resp.direct_answer and "haven't changed it" in resp.direct_answer
    assert cs.history(s)["versions"] == 1


# ================================================================ 10. M1d behaviour that must not move
def test_a_plain_pattern_is_exactly_what_m1d_produced_and_has_no_m1c_text():
    s, first = start(ASK_CHORDS)
    ex = exercise(first)
    assert sp.recipe_of(sp.GeneratedExercise.from_dict(ex)) == rc.Recipe(level="advanced", subdivision="eighth")
    text = " ".join(first.practice_steps)
    assert "Chromatic approaches" not in text and "Anticipations" not in text and "Rhythm —" not in text
    assert ex["provenance"]["m1c"] == {} and "no chromatic approach notes are added" in text


def test_harder_then_easier_returns_to_the_same_notes_for_both_kinds():
    for q0 in (ASK, ASK_CHORDS):
        s, first = start(q0)
        h = ask(s, "Make it harder")
        e = ask(s, "Make it easier")
        assert exercise(e)["notes"] == exercise(first)["notes"] and exercise(e)["midi"] == exercise(first)["midi"]
        assert exercise(h)["notes"] != exercise(first)["notes"]


def test_a_non_scale_pattern_exercise_keeps_the_old_answers_for_these_requests():
    s = session()
    ask(s, "Give me a guide-tone exercise over Blue Bossa", instrument="Flute")
    if AMI_LAST_EXERCISE_KEY in s:
        resp = ask(s, "Change the pattern to fourths")
        assert failed(resp) and "unchanged" in resp.direct_answer


# ================================================================ 11. randomized conversations: whatever is asked, the result is sound or refused unchanged
_PHRASES = [
    "Change it to thirds", "Change it to fourths", "Use fifths", "Make the intervals wider", "Make the intervals narrower", "Simplify the notes",
    "Add chromatic approaches", "Approach the chord tones from below", "Approach the chord tones from above", "Make the line more chromatic",
    "Remove the chromatic approaches", "Make the rhythm more syncopated", "Straighten the rhythm", "Add some rhythmic displacement",
    "Keep the same notes but change the rhythm", "Add anticipations of the next chord", "Remove the anticipations", "Make it more advanced",
    "Make it easier", "Make it slower", "Accent the downbeats", "Give me a more advanced interval pattern",
]
_SWEEP = [
    ("Flute", ASK_CHORDS, None), ("Alto", ASK_CHORDS, None), ("Tenor", ASK_CHORDS, None), ("Flute", ASK, None), ("Alto", ASK, None),
    ("Trumpet", ASK_CHORDS, None), ("Clarinet", ASK_CHORDS, None), ("Soprano", ASK, None),
]


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("name, q0, _x", _SWEEP)
def test_random_conversations_never_produce_an_unsound_exercise_and_undo_everything(name, q0, _x, seed):
    import random

    rng = random.Random(f"{name}-{q0}-{seed}")
    s, first, inst = begin(q0, name)
    shown = [(first.notation_abc, exercise(first))]
    for _ in range(9):
        q = rng.choice(_PHRASES)
        before = (dict(s[AMI_LAST_EXERCISE_KEY]), cs.history(s)["versions"])
        resp = ask(s, q, instrument=inst)
        if failed(resp):
            assert (s[AMI_LAST_EXERCISE_KEY], cs.history(s)["versions"]) == before, (q, "a refusal must change nothing")
            continue
        ex = exercise(resp)
        assert_sound(ex)
        assert re.search(r"^Q:\S+=\d+", resp.notation_abc, re.M)
        if cs.history(s)["versions"] > before[1] or ex != shown[-1][1]:
            shown.append((resp.notation_abc, ex))
    # walk all the way back and forward again, exactly
    for abc, ex in reversed(shown[:-1]):
        back = ask(s, "Undo that", instrument=inst)
        assert not failed(back) and exercise(back)["id"] == ex["id"] and back.notation_abc == abc
    for abc, ex in shown[1:]:
        fwd = ask(s, "Redo", instrument=inst)
        assert not failed(fwd) and exercise(fwd)["id"] == ex["id"] and fwd.notation_abc == abc


# ================================================================ 12. the duplicate-send guard must not swallow a repeated revision
def test_repeating_undo_or_a_pattern_request_is_a_new_request_each_time_for_the_duplicate_send_guard():
    from music_coach_ami.exercise_context import exercise_authority_signature

    s, _ = start(ASK_CHORDS)
    for q in ("Make the rhythm more syncopated", "Add chromatic approaches", "Change it to fourths"):
        ask(s, q)
    sigs = []
    for _ in range(3):
        sigs.append(exercise_authority_signature(s, "Undo that"))
        ask(s, "Undo that")
    assert len(set(sigs)) == 3, sigs
    redo = [exercise_authority_signature(s, "Redo")]
    ask(s, "Redo")
    redo.append(exercise_authority_signature(s, "Redo"))
    assert redo[0] != redo[1]
    assert exercise_authority_signature(s, "Make it slower") != exercise_authority_signature(s, "What is a ii-V-I?")


# ================================================================ 13. rhythm-only keeps every note; pitch-only keeps the rhythm (final acceptance)
RHYTHM_ONLY = ["Keep the same notes but make the rhythm more syncopated.", "Add some rhythmic displacement", "Straighten the rhythm",
               "Keep the same notes but change the rhythm", "Use more offbeats"]


def bar_totals(ex):
    out = {}
    for e in wevents(ex):
        out[e["bar_index"]] = out.get(e["bar_index"], F(0)) + dur(e)
    return out


def pitches_only(ex):
    return [(e["spelled"], int(e["octave"])) for e in wevents(ex) if not rest(e)]


def rhythm_only_signature(ex):
    return [(dur(e), rest(e)) for e in wevents(ex)]


@pytest.mark.parametrize("name", ["Flute", "Alto", "Tenor", "Soprano", "Trumpet", "Clarinet", "Piano"])
@pytest.mark.parametrize("ask_", [ASK, ASK_CHORDS])
def test_rhythm_only_requests_keep_every_pitch_in_order_and_every_bar_whole(name, ask_):
    s, first, inst = begin(ask_, name)
    for starting in ("", "Add chromatic approaches"):
        if starting:
            ask(s, starting, instrument=inst)
        for q in RHYTHM_ONLY:
            current = cs.current_version(s)["exercise"]
            resp = ask(s, q, instrument=inst)
            if failed(resp):
                assert any(t in resp.direct_answer.lower() for t in ("nothing was changed", "unchanged")), (q, resp.direct_answer[:200])
                assert cs.current_version(s)["exercise"]["id"] == current["id"]
                continue
            ex = exercise(resp)
            assert pitches_only(ex) == pitches_only(current), (name, q)
            assert ex["midi"] == current["midi"], (name, q)
            assert set(bar_totals(ex).values()) == {per_bar(ex)} and len(bar_totals(ex)) == ex["bars"], (name, q, bar_totals(ex))
            assert ex["provenance"]["layers"]["anticipations"] == 0           # syncopation alone never touches the harmony


@pytest.mark.parametrize("ask_", [ASK, ASK_CHORDS])
def test_the_note_preserving_syncopation_phrase_changes_only_the_durations(ask_):
    s, first = start(ask_)
    base = exercise(first)
    resp = ask(s, "Keep the same notes but make the rhythm more syncopated.")
    ex = exercise(resp)
    assert not failed(resp) and pitches_only(ex) == pitches_only(base) and rhythm_only_signature(ex) != rhythm_only_signature(base)
    assert [e["chord"] for e in wevents(ex) if e["chord"]] == [e["chord"] for e in wevents(base) if e["chord"]]


@pytest.mark.parametrize("ask_", [ASK, ASK_CHORDS])
def test_a_sixteenth_note_pattern_cannot_be_syncopated_without_losing_notes_so_it_says_so_and_changes_nothing(ask_):
    s, _ = start(ask_)
    for _ in range(2):
        ask(s, "Make it harder")                      # Advanced+, Advanced++ (sixteenth notes)
    current = cs.current_version(s)["exercise"]
    assert current["provenance"]["recipe"]["subdivision"] == "sixteenth"
    versions = cs.history(s)["versions"]
    for q in ("Make the rhythm more syncopated", "Add some rhythmic displacement"):
        resp = ask(s, q)
        assert failed(resp) and "sixteenth" in resp.direct_answer and "nothing was changed" in resp.direct_answer.lower(), resp.direct_answer[:240]
    assert cs.history(s)["versions"] == versions and cs.current_version(s)["exercise"]["id"] == current["id"]


@pytest.mark.parametrize("name", ["Flute", "Alto", "Tenor"])
@pytest.mark.parametrize("ask_", [ASK, ASK_CHORDS])
def test_pitch_only_requests_keep_the_rhythm_exactly(name, ask_):
    s, first, inst = begin(ask_, name)
    ask(s, "Make the rhythm more syncopated", instrument=inst)
    rhythm = rhythm_only_signature(cs.current_version(s)["exercise"])
    for q in ("Change it to fourths", "Change it to thirds", "Make the intervals wider", "Add chromatic approaches", "Remove the chromatic approaches",
              "Use a mix of thirds and fourths", "Simplify the notes"):
        resp = ask(s, q, instrument=inst)
        if failed(resp):
            continue
        ex = exercise(resp)
        assert rhythm_only_signature(ex) == rhythm, (name, q)
        assert set(bar_totals(ex).values()) == {per_bar(ex)}


def test_harmonic_anticipation_appears_only_when_asked_for_and_leaves_with_the_undo():
    s, first = start(ASK_CHORDS)
    seen = [exercise(first)]
    for q in ("Change it to fourths", "Add chromatic approaches", "Make the rhythm more syncopated", "Add some rhythmic displacement",
              "Add accents", "Make it slower", "Change it to thirds", "Straighten the rhythm"):
        resp = ask(s, q)
        if not failed(resp):
            seen.append(exercise(resp))
    assert len(seen) > 5
    for ex in seen:
        assert not any(e["tone_role"] == "anticipation" for e in wevents(ex)), ex["id"]
        assert ex["provenance"]["recipe"]["anticipation"] is False
    asked = exercise(ask(s, "Add anticipations of the next chord"))
    assert any(e["tone_role"] == "anticipation" for e in wevents(asked))
    back = exercise(ask(s, "Undo that"))
    assert back["id"] == seen[-1]["id"] and not any(e["tone_role"] == "anticipation" for e in wevents(back))


def test_changing_the_rhythm_after_anticipations_keeps_every_note_or_is_refused_with_the_reason():
    s, _ = start(ASK_CHORDS)
    ask(s, "Add anticipations of the next chord")
    refused = 0
    for q in ("Make the rhythm more syncopated", "Make the rhythm more syncopated", "Add some rhythmic displacement", "Straighten the rhythm"):
        current = cs.current_version(s)["exercise"]
        resp = ask(s, q)
        after = cs.current_version(s)["exercise"]
        if failed(resp):
            refused += 1
            assert after["id"] == current["id"] and "unchanged" in resp.direct_answer.lower() or "Nothing was changed" in resp.direct_answer
        else:
            assert pitches_only(after) == pitches_only(current), q            # an accepted rhythm change never swaps a note
            assert any(e["tone_role"] == "anticipation" for e in wevents(after))
    assert refused >= 1                                                      # the full syncopation / displacement cannot keep the anticipated notes
    assert not failed(ask(s, "Remove the anticipations"))


def test_the_revision_contract_catches_a_pitch_line_presented_as_rhythm_only():
    import dataclasses

    s, first = start(ASK_CHORDS)
    parent = sp.GeneratedExercise.from_dict(exercise(first))
    old = sp.recipe_of(parent)
    sync = dataclasses.replace(old, syncopation=2)
    child, _why = sp.regenerate(parent, sync)
    assert child is not None and sp.revision_contract(parent, child, old, sync) == ""
    other, _why = sp.regenerate(parent, dataclasses.replace(old, shape="fourths"))
    assert other is not None
    assert "keep all of your notes" in sp.revision_contract(parent, other, old, sync)           # different pitches claimed as a rhythm-only change
    synced = sp.GeneratedExercise.from_dict(child.to_dict())
    assert "moved the rhythm" in sp.revision_contract(parent, synced, old, dataclasses.replace(old, shape="fourths"))     # a new rhythm claimed as pitch-only


@pytest.mark.parametrize("ask_", [ASK, ASK_CHORDS])
def test_undo_and_redo_restore_every_rhythm_and_pitch_revision_exactly(ask_):
    s, first = start(ask_)
    shown = [(first.notation_abc, exercise(first))]
    for q in ("Change it to fourths", "Make the rhythm more syncopated", "Add chromatic approaches", "Add some rhythmic displacement", "Add accents"):
        resp = ask(s, q)
        assert not failed(resp), (q, resp.direct_answer[:200])
        shown.append((resp.notation_abc, exercise(resp)))
    for abc, ex in reversed(shown[:-1]):
        back = ask(s, "Undo that")
        assert exercise(back)["id"] == ex["id"] and back.notation_abc == abc
        assert pitches_only(exercise(back)) == pitches_only(ex) and rhythm_only_signature(exercise(back)) == rhythm_only_signature(ex)
    for abc, ex in shown[1:]:
        fwd = ask(s, "Redo")
        assert exercise(fwd)["id"] == ex["id"] and fwd.notation_abc == abc
