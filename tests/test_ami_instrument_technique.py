"""Fixed musical expectations independent of technique recipe helpers."""
import copy
import pytest
from music_coach_ami import warmup_plan as wp, warmup_engine as we
from tests.test_ami_flexible_single import no_api, session, ask, row
from tests.test_abc_bar_accidentals import read_abc


def technique(s,q,level="Intermediate",instrument="Flute",focus="Tone"):
    r=ask(s,q,level=level,instrument=instrument,focus=focus)
    assert not r.diagnostics.get("single_exercise_failed"),r.direct_answer
    p=wp.current(s);assert p and p["spec"]["technique"]
    assert read_abc(p["items"][0]["abc"])==p["items"][0]["written_midi"]
    return p


def test_flute_low_d_octave_is_d4_d5_and_exact_concert_pitch():
    s=session();p=technique(s,"Give me octave jumps from low D to high D.")
    r=p["items"][0]
    assert r["written_midi"]==[62,74]*4
    assert r["written_notes"]==["D4","D5"]*4
    assert r["sounding_midi"]==r["written_midi"]
    assert p["player"]["offset"]==0


def test_clarinet_f_octave_is_not_a_twelfth_and_explicit_instrument_wins():
    s=session();before=copy.deepcopy(s)
    p=technique(s,"Give me a clarinet octave exercise from F to F.")
    r=p["items"][0]
    assert r["written_midi"]==[65,77]*4 and r["sounding_midi"]==[63,75]*4
    assert p["player"]["key"]=="clarinet" and p["player"]["offset"]==2
    assert s["instrument"]==before["instrument"]=="Flute"
    assert "12-semitone" in r["how"][0]


def test_twelfths_are_19_semitones_not_octaves():
    s=session();p=technique(s,"Give me a clarinet twelfth exercise.")
    r=p["items"][0]
    assert r["written_midi"]==[55,74]*4
    assert r["sounding_midi"]==[53,72]*4
    assert "19 semitones" in r["how"][0]


@pytest.mark.parametrize("level",we.LEVELS)
def test_real_break_fixed_bflat4_b4_even_when_practice_key_has_fsharp(level):
    s=session();s["instrument"]="Clarinet"
    p=technique(s,"Give me an exercise for crossing the register break.",level,instrument="Clarinet")
    r=p["items"][0]
    assert r["written_midi"]==[69,70,71,72]*4
    assert r["sounding_midi"]==[67,68,69,70]*4
    assert "_B" in r["abc"] and "B" in r["abc"]
    assert "semitone boundary" in r["how"][0]


@pytest.mark.parametrize("instrument,q",[("flute","Give me a difficult flute fingering exercise."),("clarinet","Give me a challenging clarinet fingering exercise.")])
def test_challenging_coordination_has_real_patterns_and_exact_offset(instrument,q):
    s=session();p=technique(s,q,level="Beginner")
    r=p["items"][0];notes=r["written_midi"]
    assert p["level"]=="Advanced" and p["player"]["key"]==instrument
    assert "sixteenth" in r["durations"] and len(notes)==16
    assert len(set(notes))>=5
    assert all(w-c==(0 if instrument=="flute" else 2) for w,c in zip(notes,r["sounding_midi"]))
    if instrument=="flute":assert max(abs(b-a) for a,b in zip(notes,notes[1:]))>=12
    else:assert any(a==70 and b==71 for a,b in zip(notes,notes[1:]))


@pytest.mark.parametrize("instrument",["flute","clarinet"])
@pytest.mark.parametrize("level",we.LEVELS)
def test_coordination_stays_strictly_inside_existing_level_profile(instrument,level):
    s=session();p=technique(s,f"Give me a {instrument} fingering exercise.",level)
    lo,hi=we.make_player(instrument,"C").window(level)
    assert all(lo<=m<=hi for m in p["items"][0]["written_midi"])
    if level=="Beginner":assert "sixteenth" not in p["items"][0]["durations"]


def test_natural_revisions_preserve_musical_identity_and_exact_history():
    s=session();p=technique(s,"Give me octave jumps from low D to high D.")
    original=copy.deepcopy(p)
    ask(s,"Make it higher.",level="Intermediate")
    higher=copy.deepcopy(wp.current(s));assert row(s)["written_midi"]==[74,86]*4
    ask(s,"Make it slower.",level="Intermediate")
    assert row(s)["written_midi"]==higher["items"][0]["written_midi"]
    assert row(s)["bpm"]<higher["items"][0]["bpm"]
    ask(s,"Now descend.",level="Intermediate")
    assert row(s)["written_midi"]==[86,74]*4
    ask(s,"Give me fewer notes.",level="Intermediate")
    assert row(s)["written_midi"]==[86,74]*3
    before=copy.deepcopy(wp.current(s));hist=wp.history(s)
    r=ask(s,"Explain what this exercise develops.",level="Intermediate")
    assert "Develop accurate octave placement" in r.direct_answer
    assert wp.current(s)==before and wp.history(s)==hist
    ask(s,"Keep the notes but change the articulation.",level="Intermediate")
    after=copy.deepcopy(wp.current(s))
    assert row(s)["written_midi"]==before["items"][0]["written_midi"]
    assert row(s)["durations"]==before["items"][0]["durations"]
    assert wp.current(s)["spec"]["articulation"]=="staccato"
    ask(s,"Undo.",level="Intermediate");assert wp.current(s)==before
    ask(s,"Redo.",level="Intermediate");assert wp.current(s)==after
    assert original["player"]==after["player"]


def test_wider_flute_interval_is_disclosed_as_two_octaves():
    s=session();technique(s,"Give me octave jumps from low D to high D.")
    r=ask(s,"Use wider intervals.",level="Intermediate")
    assert row(s)["written_midi"]==[62,86]*4
    assert "Two-octave" in r.direct_answer


def test_wider_clarinet_octave_becomes_explicitly_named_twelfth():
    s=session();technique(s,"Give me a clarinet octave exercise from F to F.")
    r=ask(s,"Use wider intervals.",level="Intermediate")
    assert row(s)["written_midi"]==[65,84]*4
    assert "perfect twelfths" in r.direct_answer


def test_break_higher_and_wider_keeps_actual_boundary_and_harder_changes_rhythm():
    s=session();s["instrument"]="Clarinet"
    technique(s,"Give me an exercise for crossing the register break.",instrument="Clarinet")
    for q in ["Make it higher.","Use wider intervals.","Make it harder."]:
        ask(s,q,level="Intermediate",instrument="Clarinet")
        notes=row(s)["written_midi"]
        assert any(a==70 and b==71 for a,b in zip(notes,notes[1:]))
    assert wp.current(s)["level"]=="Advanced"
    assert "eighth" in row(s)["durations"]


@pytest.mark.parametrize("q",["Make it lower.","Use flute alternate fingerings.","Make it 5 minutes."])
def test_invalid_revision_preserves_complete_snapshot(q):
    s=session();technique(s,"Give me octave jumps from low D to high D.")
    before=copy.deepcopy(wp.current(s));hist=wp.history(s)
    r=ask(s,q,level="Intermediate")
    assert r and wp.current(s)==before and wp.history(s)==hist


def test_beginner_f_octave_refuses_instead_of_expanding_window():
    s=session();r=ask(s,"Give me a clarinet octave exercise from F to F.")
    assert not r.notation_abc and wp.current(s) is None
    assert "55-76" in r.direct_answer


@pytest.mark.parametrize("field,value",[("_suite_auth_user_id","other"),("_suite_active_workspace_id","other")])
def test_new_technique_does_not_leak_across_owner_change(field,value):
    s=session();technique(s,"Give me a clarinet octave exercise from F to F.")
    s[field]=value
    r=ask(s,"Explain what this exercise develops.",level="Intermediate")
    assert wp.current(s) is None
    assert not (r and "F4, F5" in r.direct_answer)


def test_existing_requested_flute_tones_and_tone_warmup_and_beginner_clarinet():
    s=session();r=ask(s,"Give me three low-register long tones.",level="Intermediate")
    assert len(row(s)["written_midi"])==3 and max(row(s)["written_midi"])<=74
    r=ask(s,"Give me a tone warmup for intermediate flute.")
    p=wp.current(s);assert p["level"]=="Intermediate" and not p["spec"].get("single")
    assert set(p["spec"]["families"])=={"long_tones","scale"}
    ask(s,"Give me a beginner clarinet warmup.")
    p=wp.current(s);assert p["player"]["key"]=="clarinet" and p["level"]=="Beginner"


def test_articulation_focus_used_but_explicit_request_and_level_win():
    s=session();p=technique(s,"Give me a flute fingering exercise.",level="Beginner",focus="Articulation")
    assert p["spec"]["articulation"]=="staccato" and p["level"]=="Beginner"
    p=technique(s,"Give me a difficult flute fingering exercise with tenuto.",level="Beginner",focus="Articulation")
    assert p["level"]=="Advanced" and p["spec"]["articulation"]=="tenuto"


def test_wrong_instrument_does_not_silently_become_clarinet():
    s=session();r=ask(s,"Give me an exercise for crossing the register break.")
    assert not r.notation_abc and wp.current(s) is None and s["instrument"]=="Flute"


def test_counted_low_tones_does_not_depend_on_default_count():
    s=session();ask(s,"Give me five low-register long tones.",level="Intermediate")
    assert len(row(s)["written_midi"])==5


def test_harder_tone_focused_octave_changes_actual_tempo_without_changing_notes():
    s=session();p=technique(s,"Give me octave jumps from low D to high D.")
    notes=p["items"][0]["written_midi"][:];bpm=p["items"][0]["bpm"]
    ask(s,"Make it harder.",level="Intermediate")
    assert row(s)["written_midi"]==notes and row(s)["bpm"]>bpm


@pytest.mark.parametrize("kind,span",[("octaves",13),("twelfths",12)])
def test_invalid_interval_metadata_is_rejected(kind,span):
    from music_coach_ami import instrument_technique as it
    s=session();p=technique(s,"Give me a clarinet octave exercise from F to F.")
    spec=copy.deepcopy(p["spec"]);spec.update(technique=kind,span=span)
    with pytest.raises(we.WarmupUnavailable):it.build(spec)


def test_twelfth_endpoint_is_not_silently_ignored():
    s=session();r=ask(s,"Give me a clarinet twelfth exercise from F to G.",level="Intermediate")
    assert not r.notation_abc and wp.current(s) is None


def test_generic_beginner_clarinet_octave_fits_without_relabeling_f_octave():
    s=session();p=technique(s,"Give me a clarinet octave exercise.",level="Beginner")
    assert p["items"][0]["written_midi"]==[55,67]*4


def test_lowercase_endpoint_names_are_read_instead_of_defaulted():
    s=session();p=technique(s,"give me a clarinet octave exercise from g to g.")
    assert p["items"][0]["written_midi"]==[67,79]*4


@pytest.mark.parametrize("q",["Give me a clarinet octave exercise from F to H.","Give me a flute octave exercise from Z to Z."])
def test_malformed_endpoints_are_not_silently_defaulted(q):
    s=session();r=ask(s,q,level="Intermediate")
    assert not r.notation_abc and wp.current(s) is None
    assert "endpoint" in r.direct_answer


def test_fresh_descending_octave_request_is_not_silently_ascending():
    s=session();p=technique(s,"Give me descending flute octave jumps from low D to high D.")
    assert p["items"][0]["written_midi"]==[74,62]*4
