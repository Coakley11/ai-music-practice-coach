"""Trumpet technique: musical oracle, negative mutations and live-pipeline contracts."""
import copy
import pytest
from music_coach_ami import warmup_plan as wp, trumpet_technique as tt
from tests.test_ami_flexible_single import no_api, session, ask, row
from tests.trumpet_oracle import check


def start(s,q="Give me a beginner trumpet lip-slur exercise.",level="Intermediate",focus="Tone"):
    r=ask(s,q,level=level,instrument="Trumpet",focus=focus)
    assert not r.diagnostics.get("single_exercise_failed"),r.direct_answer
    p=wp.current(s);assert p and p["spec"]["trumpet"]
    assert check(p)==[],check(p)
    return p


def test_beginner_actual_open_c4_g4_two_note_slurs_without_routine():
    s=session();p=start(s)
    assert row(s)["written_midi"]==[60,67]*2
    assert row(s)["sounding_midi"]==[58,65]*2
    assert row(s)["partial_numbers"]==[2,3]*2
    assert not p["spec"]["routine"] and len(p["items"])==1
    assert "10-minute" not in row(s)["title"] and "(" in row(s)["abc"]
    assert s["instrument"]=="Flute"  # explicit trumpet wins without editing globals


@pytest.mark.parametrize("valve",["open","1","2"])
@pytest.mark.parametrize("level",["Beginner","Intermediate","Advanced"])
@pytest.mark.parametrize("direction",["ascending","descending"])
def test_audited_settings_levels_and_directions_against_frequency_oracle(valve,level,direction):
    s=session();start(s,f"Give me a {level} trumpet lip-slur exercise using {'open valves' if valve=='open' else 'valve '+valve}, {direction}.",level)
    assert wp.current(s)["spec"]["valve"]==valve


def test_exact_first_and_second_valve_lower_pairs():
    for valve,expected in [('1',[58,65]),('2',[59,66])]:
        s=session();start(s,f"Give me a beginner trumpet lip-slur exercise with valve {valve}.")
        assert row(s)["written_midi"]==expected*2


def test_advanced_finger_buster_is_genuine_partials_not_a_scale():
    s=session();p=start(s,"Give me an advanced trumpet lip-slur finger-buster.")
    assert set(row(s)["partial_numbers"])=={2,3,4,5,6,8}
    assert "sixteenth" in row(s)["durations"]
    assert max(row(s)["written_midi"])==84 and min(row(s)["written_midi"])==60
    assert any(abs(b-a)>=12 for a,b in zip(row(s)["written_midi"],row(s)["written_midi"][1:]))


@pytest.mark.parametrize("level",["Beginner","Intermediate","Advanced"])
def test_upper_register_preparation_is_three_level_bounded_stages(level):
    s=session();p=start(s,"Give me a trumpet warmup to improve my upper register.",level)
    assert p["spec"]["routine"] and len(row(s)["stages"])==3
    assert "Three short stages" in row(s)["how"][0]
    assert 7 not in row(s)["partial_numbers"]
    assert max(row(s)["written_midi"])<=dict(Beginner=74,Intermediate=79,Advanced=84)[level]


def test_requested_natural_revisions_keep_valid_fixed_valve_relationships():
    s=session();start(s,"Give me a trumpet flexibility exercise moving between harmonic partials.")
    original=copy.deepcopy(wp.current(s))
    for q in ["Move it lower.","Add another partial.","Now make it descending.","Use a different valve combination.","Make the rhythm more difficult."]:
        ask(s,q,level="Intermediate",instrument="Trumpet")
        assert check(wp.current(s))==[]
    p=copy.deepcopy(wp.current(s));hist=wp.history(s)
    assert p["spec"]["valve"]=="2"
    assert p["spec"]["direction"]=="descending"
    assert "eighth" in row(s)["durations"]
    r=ask(s,"Explain what this exercise is practicing.",level="Intermediate",instrument="Trumpet")
    assert "fixed tube length" in r.direct_answer
    assert wp.current(s)==p and wp.history(s)==hist
    ask(s,"Make it easier.",level="Intermediate",instrument="Trumpet")
    easy=copy.deepcopy(wp.current(s));assert easy["level"]=="Beginner" and check(easy)==[]
    ask(s,"Undo.",instrument="Trumpet");assert wp.current(s)==p
    ask(s,"Redo.",instrument="Trumpet");assert wp.current(s)==easy
    assert original["player"]["offset"]==easy["player"]["offset"]==2


def test_rhythm_harder_preserves_every_pitch_valve_and_level():
    s=session();p=start(s,"Give me a trumpet exercise using open valves.")
    pitches=row(s)["written_midi"][:];level=p["level"];valve=p["spec"]["valve"]
    ask(s,"Make the rhythm harder.",level="Intermediate",instrument="Trumpet")
    assert row(s)["written_midi"]==pitches
    assert wp.current(s)["level"]==level and wp.current(s)["spec"]["valve"]==valve
    assert "eighth" in row(s)["durations"] and check(wp.current(s))==[]


def test_slur_and_articulation_changes_keep_notes_and_are_honestly_labelled():
    s=session();start(s,"Give me an advanced trumpet lip-slur finger-buster.")
    before=row(s)["written_midi"][:]
    r=ask(s,"Use staccato.",instrument="Trumpet")
    assert row(s)["written_midi"]==before and check(wp.current(s))==[]
    assert "tongued" in r.direct_answer and "lip-slur finger-buster" not in row(s)["title"]
    explain=ask(s,"Explain what this exercise is practicing.",instrument="Trumpet")
    assert "no lip-slur markings" in explain.direct_answer
    ask(s,"Use slur two.",instrument="Trumpet");assert check(wp.current(s))==[]
    assert row(s)["written_midi"]==before


@pytest.mark.parametrize("q",["Use valve 3.","Use valves 1 and 2.","Add partial 7.","Use pedal tones.","Make it 10 minutes.","Make it higher."])
def test_invalid_revision_preserves_complete_snapshot(q):
    s=session();start(s,"Give me an advanced trumpet lip-slur finger-buster.")
    p=copy.deepcopy(wp.current(s));h=wp.history(s)
    r=ask(s,q,instrument="Trumpet")
    assert r and wp.current(s)==p and wp.history(s)==h


@pytest.mark.parametrize("q",["Give me a C trumpet lip-slur exercise.","Give me a trumpet lip-slur exercise using valves 1 and 2.","Give me trumpet pedal lip slurs."])
def test_unsupported_type_and_valves_are_not_substituted(q):
    s=session();r=ask(s,q,instrument="Trumpet")
    assert not r.notation_abc and wp.current(s) is None


@pytest.mark.parametrize("field,value",[("_suite_auth_user_id","b"),("_suite_active_workspace_id","two")])
def test_account_and_workspace_scope(field,value):
    s=session();start(s);s[field]=value
    r=ask(s,"Explain what this exercise is practicing.",instrument="Trumpet")
    assert wp.current(s) is None
    assert not (r and "fixed tube length" in r.direct_answer)


def test_plain_full_warmup_and_other_instruments_keep_existing_routes():
    s=session();ask(s,"Give me a beginner trumpet warmup.",instrument="Trumpet")
    assert not wp.current(s)["spec"].get("single")
    ask(s,"Give me high-register flute exercises.",level="Advanced")
    assert wp.current(s)["player"]["key"]=="flute" and not wp.current(s)["spec"].get("trumpet")


@pytest.mark.parametrize("mutation",['note','valve','offset','slur','range'])
def test_independent_validator_catches_musical_mutations(mutation):
    s=session();p=copy.deepcopy(start(s))
    if mutation=='note':p['items'][0]['written_midi'][0]+=1
    if mutation=='valve':p['spec']['valve']='2'
    if mutation=='offset':p['items'][0]['sounding_midi'][0]+=1
    if mutation=='slur':p['items'][0]['abc']=p['items'][0]['abc'].replace('(','').replace(')','')
    if mutation=='range':p['items'][0]['written_midi'][0]=84
    assert check(p)


def test_descending_revision_reverses_actual_nonpalindromic_notes():
    s=session();start(s,"Give me a trumpet exercise using open valves.")
    before=row(s)["written_midi"][:]
    assert before==[67,72,76]*2
    ask(s,"Now make it descending.",level="Intermediate",instrument="Trumpet")
    assert row(s)["written_midi"]==[76,72,67]*2 and row(s)["written_midi"]!=before
    assert check(wp.current(s))==[]


def test_beginner_middle_register_uses_g4_c5_without_expanding_window():
    s=session();start(s,"Give me a beginner middle-register trumpet flexibility exercise.")
    assert row(s)["written_midi"]==[67,72]*2


def test_warmup_lower_revision_changes_final_stage_and_preserves_fixed_valve():
    s=session();p=start(s,"Give me a trumpet warmup to improve my upper register.")
    before=row(s)["written_midi"][:];valve=p["spec"]["valve"]
    ask(s,"Move it lower.",level="Intermediate",instrument="Trumpet")
    assert row(s)["written_midi"]!=before
    assert wp.current(s)["spec"]["valve"]==valve and check(wp.current(s))==[]


def test_hyphenated_open_valve_request_does_not_fall_through_to_generic_scale():
    s=session();start(s,"Give me a trumpet exercise using open-valve partials.")
    assert wp.current(s)["spec"]["valve"]=="open"
    assert row(s)["written_midi"]==[67,72,76]*2
