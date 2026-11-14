"""Independent documented controls/pitches and real pipeline transition contracts."""
import copy,json
from pathlib import Path
import pytest
from music_coach_ami import fingering_data as data,fingering_view as view,fingering_instructor as fi,warmup_plan as wp
from tests.test_ami_sax_technique import setup,ask,no_api
from tests.test_ami_fingering_instructor import ready
from tests.test_abc_bar_accidentals import read_abc
O=json.loads(Path(__file__).with_name('fixtures').joinpath('yas280_stage_b_oracle.json').read_text())

@pytest.mark.parametrize('note',list(O['notes']))
def test_independent_chart_keys_octave_sources_and_pitch(note):
    r=data.record(note);o=O['notes'][note]
    assert (r['written_midi'],r['sounding_midi'])==(o['written'],o['sounding'])
    assert {k for k,v in r['key_states'].items() if v}==set(o['pressed'])
    assert not r['auxiliary_controls_pressed'] and not r['teacher_reviewed']
    assert r['model_id']=='yamaha-yas280' and r['verification']=='manufacturer/reference-supported'
    assert r['sources'][0]['sha256']==O['manual_sha256']
    assert r['sources'][2]['url'].endswith('fingering'+str(o['gif'])+'.gif')
    assert 'sax_bas_' in r['sources'][-1]['url'] and r['limitations']
    description=view.description(r)
    for k,label in data.KEYS:
        section=description.split('Release:')[0] if r['key_states'][k] else description.split('Release:')[1]
        assert label in section
    assert 'Octave thumb' in description

@pytest.mark.parametrize('note',list(O['notes']))
def test_lookup_real_written_octave_and_no_version(note):
    s=ready();h=copy.deepcopy(wp.history(s));r=ask(s,'Show me the fingering for '+note+'.')
    assert read_abc(r.notation_abc)==[O['notes'][note]['written']]
    assert wp.current(s) is None and wp.history(s)==h
    assert r.diagnostics['fingering_instruction']==[data.record(note)]

@pytest.mark.parametrize('letter,low,high', [('D',62,74),('E',64,76),('F',65,77),('G',67,79),('A',69,81)])
def test_octave_comparison_exact_pitch_and_only_documented_control_delta(letter,low,high):
    s=ready();h=copy.deepcopy(wp.history(s));r=ask(s,'Show me how to go from low '+letter+' to high '+letter+' on alto sax.')
    assert read_abc(r.notation_abc)==[low,high] and high-low==12
    assert data.changes(letter+'4',letter+'5')==['Octave thumb: press']
    assert '12 semitones' in r.direct_answer and 'Octave thumb: press' in r.direct_answer
    assert wp.current(s) is None and wp.history(s)==h
    assert fi.context(s)['notes']==[letter+'4',letter+'5']
    r=ask(s,"What's the difference between the two "+letter+' fingerings?')
    assert read_abc(r.notation_abc)==[low,high] and wp.history(s)==h


def test_transition_handoff_edits_and_exact_undo_redo():
    s=ready();ask(s,'Show me how to go from low G to high G on alto sax.')
    ask(s,'Give me a short exercise using these two notes.')
    a=copy.deepcopy(wp.current(s));assert a['items'][0]['written_midi']==[67,79]
    assert a['items'][0]['durations']==['half','half'] and a['items'][0]['sounding_midi']==[58,70]
    ask(s,'Make the transition slower.');b=copy.deepcopy(wp.current(s));assert b['items'][0]['written_midi']==[67,79] and b['spec']['bpm']==50
    ask(s,'Repeat the octave jump four times.');c=copy.deepcopy(wp.current(s));assert c['spec']['reps']==4 and c['items'][0]['written_midi']==[67,79]
    ask(s,'Make it descending.');d=copy.deepcopy(wp.current(s));assert d['items'][0]['written_midi']==[79,67] and d['spec']['reps']==4 and d['spec']['bpm']==50
    h=copy.deepcopy(wp.history(s));r=ask(s,'Explain which keys change.')
    assert 'Octave thumb: release' in r.direct_answer and wp.current(s)==d and wp.history(s)==h
    ask(s,'Undo.');assert wp.current(s)==c
    ask(s,'Redo.');assert wp.current(s)==d
    ask(s,'Give me a harder register-transition exercise.');hard=copy.deepcopy(wp.current(s))
    assert hard['items'][0]['written_midi']==[79,67,79,67] and hard['spec']['bpm']==50 and hard['spec']['reps']==4
    ask(s,'Make it easier.');assert wp.current(s)['items'][0]['written_midi']==[79,67] and wp.current(s)['items'][0]['durations']==['half','half']
    ask(s,'Undo.');assert wp.current(s)==hard


def test_lead_into_high_g_and_gradual_ladder_use_only_verified_records():
    s=ready();ask(s,'Give me an octave exercise using G.')
    ask(s,'Add a few notes leading into high G.');p=copy.deepcopy(wp.current(s))
    assert p['items'][0]['written_midi']==[67,76,77,79]
    h=copy.deepcopy(wp.history(s));r=ask(s,'Explain which keys change.')
    assert 'Right index: press' in r.direct_answer and 'Right middle: press' in r.direct_answer and wp.history(s)==h
    assert {r['id'] for r in r.diagnostics['fingering_instruction']}=={'G4','E5','F5','G5'}
    ask(s,'Start with low notes and gradually move higher.')
    assert wp.current(s)['items'][0]['written_midi']==[62,64,65,67,69,71,72,74]
    assert all(n in data.supported_notes() for n in wp.current(s)['items'][0]['written_notes'])
    assert read_abc(wp.current(s)['items'][0]['abc'])==wp.current(s)['items'][0]['written_midi']

@pytest.mark.parametrize('q',['Give me an octave exercise using A.','Give me an exercise to practice switching the octave key.'])
def test_direct_natural_language_handoff(q):
    s=ready();ask(s,q);p=wp.current(s);assert p and p['items'][0]['written_midi'][-1]-p['items'][0]['written_midi'][0]==12
    assert all(n in data.supported_notes() for n in p['items'][0]['written_notes'])

@pytest.mark.parametrize('q',['Show the fingering for Bb4.','Show the fingering for B5.','Show the fingering for C.','Compare the fingerings for G4 and A5.','Show the fingering for low G5.','Show the fingering for high B.','Show the fingering for concert G4.','Show the fingering for G on YAS-26.','Give me an altissimo fingering exercise.','Give me an overtone fingering exercise.','Show an alternate fingering for G5.'])
def test_negative_requests_preserve_pair_plan_history_and_context(q):
    s=ready();ask(s,'Give me an octave exercise using G.')
    p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s));c=fi.context(s);ask(s,q)
    assert wp.current(s)==p and wp.history(s)==h and fi.context(s)==c

@pytest.mark.parametrize('q',['Use sixteenth notes.','Make it higher.','Change it to tenor saxophone.','Use concert F.','Add a few notes leading into high A.'])
def test_unavailable_edits_preserve_exact_stored_transition(q):
    s=ready();ask(s,'Give me an octave exercise using A.')
    p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s));ask(s,q)
    assert wp.current(s)==p and wp.history(s)==h

@pytest.mark.parametrize('owner',['_suite_auth_user_id','_suite_active_workspace_id'])
def test_pair_context_owner_isolation(owner):
    s=ready();ask(s,'Give me an octave exercise using G.');s[owner]='other'
    r=ask(s,'Give me a short exercise using these two notes.')
    assert not fi.context(s) and wp.current(s) is None and 'model' in r.direct_answer


def test_sidebar_and_read_only_pair_after_different_stored_exercise():
    s=ready();ask(s,'Give me an octave exercise using A.');p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s))
    ask(s,'Show me how to go from low G to high G.');s['instrument']='Flute'
    r=ask(s,'Can you show these two notes on the staff?');assert read_abc(r.notation_abc)==[67,79] and wp.current(s)==p and wp.history(s)==h
    r=ask(s,'Explain which keys change in the exercise.');assert {x['id'] for x in r.diagnostics['fingering_instruction']}=={'A4','A5'} and wp.current(s)==p and wp.history(s)==h


def test_octave_pair_does_not_get_confused_with_different_note_or_thumb_toggle_only():
    from music_coach_ami import fingering_transitions as ft
    s=ready();ask(s,'Give me an octave exercise using G.');spec=copy.deepcopy(wp.current(s)['spec']);spec['fingering_transition']['pair']=['C5','D5']
    with pytest.raises(ValueError):ft.build(spec)
    assert data.changes('C5','D5')!=['Octave thumb: press']

@pytest.mark.parametrize('note',list(O['notes']))
def test_new_single_note_exercise_preserves_written_octave_and_exact_history(note):
    s=ready();ask(s,'Show the fingering for '+note+'.');ask(s,'Give me a short exercise using it.')
    p=copy.deepcopy(wp.current(s));assert p['items'][0]['written_midi']==[O['notes'][note]['written']]*4
    assert read_abc(p['items'][0]['abc'])==p['items'][0]['written_midi']
    ask(s,'Make the exercise slower.');slow=copy.deepcopy(wp.current(s));assert slow['items'][0]['written_midi']==p['items'][0]['written_midi']
    ask(s,'Undo.');assert wp.current(s)==p
    ask(s,'Redo.');assert wp.current(s)==slow


def test_pair_handoff_undo_redo_restores_ordinary_warmup_exactly():
    s=setup();ask(s,'Give me a warmup.');old=copy.deepcopy(wp.current(s))
    ask(s,'Give me an octave exercise using G on Yamaha YAS-280.');new=copy.deepcopy(wp.current(s))
    ask(s,'Undo.');assert wp.current(s)==old
    ask(s,'Redo.');assert wp.current(s)==new and fi.context(s)['notes']==['G4','G5']


def test_two_explicit_fingering_notes_resolve_to_read_only_octave_comparison():
    s=ready();h=copy.deepcopy(wp.history(s));r=ask(s,'Show the fingerings for E4 and E5.')
    assert read_abc(r.notation_abc)==[64,76] and wp.history(s)==h and wp.current(s) is None

@pytest.mark.parametrize('q',['Give me an alto sax exercise in octaves.','Give me something to improve my register transitions.','Make me a five-minute alto sax register transitions warmup.'])
def test_unbound_generic_sax_technique_retains_existing_owner(q):
    s=setup();r=ask(s,q);p=wp.current(s)
    assert p and p['spec'].get('sax') and not p['spec'].get('fingering')
    assert not fi.context(s)
