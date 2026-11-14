"""Independent manufacturer transcription, acoustic convention and real pipeline checks."""
import copy,json,xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from music_coach_ami import trumpet_fingering_data as data,trumpet_fingering_instructor as fi,trumpet_fingering_view as view,warmup_plan as wp,flexible_single as fs
from tests.test_ami_sax_technique import setup,ask,no_api
from tests.test_abc_bar_accidentals import read_abc
O=json.loads(Path(__file__).with_name('fixtures').joinpath('ytr2330_fingering_oracle.json').read_text(encoding='utf-8'))
CASES=[(valve,n) for valve,s in O['sets'].items() for n in s['notes']]

def ready():
    s=setup();r=ask(s,'I play a Yamaha YTR-2330.');assert 'identified' in r.direct_answer
    return s

def current(s):return copy.deepcopy(wp.current(s))
def history(s):return copy.deepcopy(wp.history(s))

@pytest.mark.parametrize('valve,n',CASES,ids=[v+'-'+n['id'] for v,n in CASES])
def test_independent_source_valve_partial_pitch_and_numbering(valve,n):
    r=data.record(n['id'])
    assert (r['written_midi'],r['sounding_midi'],r['partial'])==(n['written'],n['sounding'],n['partial'])
    assert r['valve_states']==O['valve_states'][valve] and r['valve']==valve
    assert r['normal_slot']==n['partial']-1
    assert r['written_midi']-r['fundamental_written_midi']=={2:12,3:19,4:24}[n['partial']]
    assert r['sources'][0]['sha256']==O['manual_sha256'] and r['sources'][1]['url']==O['harmonic_chart_urls'][valve]
    assert r['model_id']==data.MODEL and not r['teacher_reviewed'] and not r['physically_tested']
    assert 'theoretical' in r['partial_convention'] and 'not enabled' in r['partial_convention']
    root=ET.fromstring(view.svg(r));groups=[g for g in root.iter() if 'data-valve' in g.attrib]
    assert len(groups)==3 and root.attrib['data-partial']==str(n['partial'])
    for g in groups:assert g.attrib['data-pressed']==str(O['valve_states'][valve][g.attrib['data-valve']]).lower()
    assert 'Press:' in view.description(r) and 'Release:' in view.description(r)

@pytest.mark.parametrize('valve,n',CASES,ids=[v+'-'+n['id'] for v,n in CASES])
def test_actual_staff_and_readonly_lookup_without_sidebar_mutation(valve,n):
    s=ready();settings={k:copy.deepcopy(v) for k,v in s.items() if k in ('instrument','selected_transposing_instrument','practice_key','key','level','practice_focus','_suite_auth_user_id','_suite_active_workspace_id')};h=history(s)
    r=ask(s,'Show the fingering for '+n['id']+' on Bb trumpet.')
    assert read_abc(r.notation_abc)==[n['written']]
    assert r.diagnostics['fingering_instruction']==[data.record(n['id'])] and r.diagnostics['fingering_lookup']
    assert current(s) is None and history(s)==h
    assert all(s[k]==v for k,v in settings.items())

@pytest.mark.parametrize('q,expected',[("What's the fingering for C on B-flat trumpet?",[60,72]),("What valves do I press for G?",[67]),('Show me open-valve notes.',[60,67,72]),("What's the difference between playing low C and high C?",[60,72]),('How do I go from C to G without changing valves?',[60,72,67]),('Show me the notes of the open harmonic series.',[60,67,72]),('Show the fingering for Bb.',[58,70]),('Show the fingering for B.',[59,71])])
def test_conversational_questions_present_labelled_supported_possibilities(q,expected):
    s=ready();h=history(s);r=ask(s,q)
    assert read_abc(r.notation_abc)==expected,r.direct_answer
    assert 'written' in r.direct_answer and 'sounds' in r.direct_answer and 'Partial 1' in r.direct_answer
    assert current(s) is None and history(s)==h

@pytest.mark.parametrize('valve,expected',[('open',[60,67,72]),('1',[58,65,70]),('2',[59,66,71])])
def test_fixed_valve_handoff_next_partial_slurs_rests_and_exact_history(valve,expected):
    s=ready();ask(s,'Show the fingering for '+{'open':'C4','1':'Bb3','2':'B3'}[valve]+'.')
    ask(s,'Give me an exercise moving between those notes.');a=current(s)
    assert a['spec']['trumpet_fingering'] and a['spec']['valve']==valve
    assert a['items'][0]['written_midi']==expected[:2]
    assert a['items'][0]['sounding_midi']==[x-2 for x in expected[:2]]
    assert a['items'][0]['partial_numbers']==[2,3] and len(set(a['items'][0]['slur_groups']))==1
    assert '(' in a['items'][0]['abc'] and 'z' in a['items'][0]['abc']
    ask(s,'Now add the next supported partial.');b=current(s)
    assert b['items'][0]['written_midi']==expected and b['items'][0]['partial_numbers']==[2,3,4]
    assert read_abc(b['items'][0]['abc'])==expected
    h=history(s);ask(s,'Now add the next supported partial.');assert current(s)==b and history(s)==h
    ask(s,'Make it slower.');c=current(s);assert c['spec']['bpm']==40
    ask(s,'Repeat the pattern.');d=current(s);assert d['spec']['reps']==2
    h=history(s);r=ask(s,'Show me the valves for each note.');assert current(s)==d and history(s)==h
    assert [x['written_midi'] for x in r.diagnostics['fingering_instruction']]==expected
    r=ask(s,'Explain what changes when the valves stay the same.');assert 'tube length' in r.direct_answer and current(s)==d and history(s)==h
    ask(s,'Undo.');assert current(s)==c
    ask(s,'Redo.');assert current(s)==d
    ask(s,'Make it easier.');e=current(s);assert e['items'][0]['written_midi']==expected[:2] and e['spec']['bpm']==36
    ask(s,'Undo.');assert current(s)==d

@pytest.mark.parametrize('q',['Show the fingering for C6.','Show the fingering for A4.','Show valve 3.','Show valves 1+2.','Show valves 1 and 2.','Show the first and second valves.','Show partial 1.','Show partial 5.','Give me a pedal-tone exercise.','Give me specialized embouchure instruction.','Show an alternate fingering.','Show the fingering for G on C trumpet.','Show the fingering for G on YTR-8335.','Use sixteenth notes.','Make it higher.','Use concert G.','Repeat the pattern 13 times.'])
def test_unsupported_requests_preserve_plan_history_and_lookup(q):
    s=ready();ask(s,'Give me a trumpet lip-slur exercise.');p=current(s);h=history(s);ctx=fi.context(s)
    ask(s,q);assert current(s)==p and history(s)==h and fi.context(s)==ctx

@pytest.mark.parametrize('q',["I do not play a YTR-2330.","I don't have a YTR-2330.",'How do I know if my trumpet is a YTR-2330?'])
def test_no_model_inference_from_negation_or_question(q):
    s=setup();ask(s,q);assert not fi.context(s) and current(s) is None

def test_explicit_trumpet_model_needed_with_alto_sidebar():
    s=setup();r=ask(s,'Show the fingering for C4 on Bb trumpet.')
    assert 'Which trumpet model' in r.direct_answer and not fi.context(s) and current(s) is None
    r=ask(s,'Show the fingering for G4 on Yamaha YTR-2330 Bb trumpet.')
    assert read_abc(r.notation_abc)==[67] and s['instrument']=='Saxophone'

def test_ambiguous_high_c_is_not_silently_assigned_c5():
    s=ready();r=ask(s,'Show the fingering for high C.')
    assert read_abc(r.notation_abc)==[60,72] and 'not assumed to mean C5' in r.direct_answer

def test_fixed_valves_does_not_imply_open_and_mixed_setting_handoff_refuses():
    s=ready();r=ask(s,'Show F4 and Bb4 without changing valves.')
    assert read_abc(r.notation_abc)==[65,70] and {x['valve'] for x in r.diagnostics['fingering_instruction']}=={'1'}
    ask(s,'Give me an exercise moving between those notes.');assert current(s)['items'][0]['written_midi']==[65,70]
    p=current(s);h=history(s);ask(s,'Show C4 and B3 fingerings.');ask(s,'Give me an exercise moving between those notes.')
    assert current(s)==p and history(s)==h

def test_c_to_g_start_and_gap_disclosed_in_c_octave_handoff():
    s=ready();ask(s,'Show the fingering for C.');ask(s,'Give me an exercise moving between those notes.')
    assert current(s)['items'][0]['written_midi']==[60,67,72]
    ask(s,'Start with C and move up to G.');assert current(s)['items'][0]['written_midi']==[60,67]

def test_existing_sax_plan_history_and_last_lookup_owner_are_preserved():
    s=setup();ask(s,'I play a Yamaha YAS-280.');ask(s,'Give me an octave exercise using G.');old=current(s)
    ask(s,'I play a Yamaha YTR-2330.');ask(s,'Show the fingering for C4.');h=history(s);assert current(s)==old
    ask(s,'Give me an exercise moving between those notes.');new=current(s)
    ask(s,'Undo.');assert current(s)==old and not fi.context(s)
    ask(s,'Redo.');assert current(s)==new and fi.context(s)['model']==data.MODEL
    ask(s,'Show the fingering for A4 on Yamaha YAS-280.');assert not fi.context(s)
    ask(s,'Give me a short exercise using it.');assert current(s)['spec'].get('fingering')=='A4'

@pytest.mark.parametrize('owner',['_suite_auth_user_id','_suite_active_workspace_id'])
def test_account_workspace_isolation(owner):
    s=ready();ask(s,'Give me a trumpet lip-slur exercise.');s[owner]='different'
    r=ask(s,'Show the fingering for C4 on Bb trumpet.')
    assert current(s) is None and not fi.context(s) and 'model' in r.direct_answer

@pytest.mark.parametrize('change',[{'partial_count':4},{'start':1,'partial_count':3},{'trumpet_model':'other'},{'valve':'3'},{'style':'tongued'},{'concert_key':'C'}])
def test_unverified_builder_mutations_cannot_reach_commit(change):
    s=ready();ask(s,'Give me a trumpet lip-slur exercise.');p=current(s);spec=copy.deepcopy(p['spec']);spec.update(change)
    with pytest.raises((ValueError,KeyError)):fs.build(spec)
    assert current(s)==p

def test_diagram_rejects_tampering_and_shared_renderer_dispatches():
    from music_coach_ami.fingering_view import html,svg
    r=data.record('G4');assert svg(r)==view.svg(r) and html([r])==view.html([r])
    r['valve_states']['1']=True
    with pytest.raises(ValueError):view.svg(r)
