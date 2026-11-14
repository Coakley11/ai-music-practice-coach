"""Independent flute source actions, native notes and real AMI state contracts."""
import copy,json,xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from music_coach_ami import flute_fingering_data as data,flute_fingering_instructor as fi,flute_fingering_view as view,warmup_plan as wp,flexible_single as fs,fingering_view,warmup_engine as we
from tests.test_ami_sax_technique import setup,ask,no_api
from tests.test_abc_bar_accidentals import read_abc
O=json.loads(Path(__file__).with_name('fixtures').joinpath('yfl222_fingering_oracle.json').read_text(encoding='utf-8'))
N={r['id']:r for r in O['notes']}
def ready():
 s=setup();assert 'identified' in ask(s,'I play a Yamaha YFL-222.').direct_answer;return s
def current(s):return copy.deepcopy(wp.current(s))
def history(s):return copy.deepcopy(wp.history(s))
def seed(s):return ask(s,'Give me an Intermediate flute octave exercise using E4 and E5.')

@pytest.mark.parametrize('note',list(N))
def test_independent_source_key_states_written_concert_and_original_diagram(note):
 r=data.record(note);n=N[note]
 assert (r['written_midi'],r['sounding_midi'],r['offset'])==(n['written_midi'],n['concert_midi'],0)
 assert {k for k,v in r['key_states'].items() if v}==set(n['pressed'])
 assert r['model_id']==data.MODEL and r['configuration']==data.CONFIGURATION
 assert not r['teacher_reviewed'] and not r['physically_tested']
 assert r['sources'][1]['sha256']==O['sources'][n['source_page']+'.html']['sha256']
 assert r['source_row']==n['source_row'] and r['key_states']['B_thumb'] and not r['key_states']['Bb_thumb']
 root=ET.fromstring(view.svg(r));controls=[g for g in root.iter() if 'data-key' in g.attrib];assert len(controls)==15
 for g in controls:
  pressed=g.attrib['data-key'] in n['pressed'];assert g.attrib['data-pressed']==str(pressed).lower()
  circle=next(x for x in g if x.tag.endswith('circle'));assert circle.attrib['fill']==('#174ea6' if pressed else 'white')
 assert 'Press:' in view.description(r) and 'Release:' in view.description(r) and 'no octave key' in view.description(r)
 assert 'ami-flute-diagram' in fingering_view.svg(r) and 'ami-flute-fingering' in fingering_view.html([r])

@pytest.mark.parametrize('note',list(N))
def test_real_lookup_actual_staff_readonly_and_sidebar_override(note):
 s=ready();before=copy.deepcopy(s);r=ask(s,'Show the fingering for '+note+' on flute.')
 assert read_abc(r.notation_abc)==[N[note]['written_midi']]
 assert r.diagnostics['fingering_instruction']==[data.record(note)] and r.diagnostics['fingering_lookup']
 assert current(s) is None and history(s)==history(before)
 for k in ['instrument','selected_transposing_instrument','display_key','level','focus']:assert s.get(k)==before.get(k)

@pytest.mark.parametrize('pair',O['pairs'])
def test_independently_verified_octaves_identical_actions_and_native_notes(pair):
 a,b=pair;assert N[b]['written_midi']-N[a]['written_midi']==12
 assert data.changes(a,b)==[] and data.record(a)['key_states']==data.record(b)['key_states']
 s=ready();h=history(s);r=ask(s,'Show the difference between '+a+' and '+b+' on flute.')
 assert read_abc(r.notation_abc)==[N[n]['written_midi'] for n in pair]
 assert '12 semitones' in r.direct_answer and 'identical selected key states' in r.direct_answer
 assert current(s) is None and history(s)==h

@pytest.mark.parametrize('q,ids',[("What's the fingering for E on flute?",['E4','E5']),('Show me how to play low E.',['E4']),('How do I play E in the higher octave?',['E5']),("What's the difference between low and high G?",['G4','G5']),('Show me the fingering for F5.',['F5']),('How do I move smoothly from E4 to E5?',['E4','E5']),('show the fingering for e4 on flute',['E4'])])
def test_practical_questions_actual_numbered_notes_no_unwanted_plan(q,ids):
 s=ready();r=ask(s,q);assert read_abc(r.notation_abc)==[N[n]['written_midi'] for n in ids];assert current(s) is None
 if q.startswith("What's the fingering for E") or 'higher octave' in q:assert 'ambiguous' in r.direct_answer

def test_contextual_higher_octave_and_last_readonly_note():
 s=ready();seed(s);p,h=current(s),history(s);ask(s,'Show the fingering for E4.');r=ask(s,'Show me the higher octave.');assert read_abc(r.notation_abc)==[76];assert current(s)==p and history(s)==h
 r=ask(s,'Explain which fingers are pressed.');assert read_abc(r.notation_abc)==[76];assert current(s)==p and history(s)==h

@pytest.mark.parametrize('q',['Give me an octave exercise using E.','Give me a slow exercise that goes between the two registers.','Give me an exercise to improve octave transitions.','Alternate between E4 and E5.'])
def test_contextual_handoffs_remain_single_verified_exercises(q):
 s=ready();ask(s,'Show the fingerings for E4 and E5.');r=ask(s,q);p=current(s)
 assert p['spec']['flute_fingering'] and len(p['items'])==1 and p['items'][0]['written_midi']==[64,76]
 assert p['items'][0]['sounding_midi']==[64,76] and 'lip slurs' in r.direct_answer and 'not trumpet' in r.direct_answer
 assert read_abc(p['items'][0]['abc'])==[64,76]

def test_actual_revisions_readonly_exact_undo_redo_and_alternation():
 s=ready();seed(s);base=current(s)
 ask(s,'Repeat it four times.');assert current(s)['spec']['reps']==4
 ask(s,'Make it slower.');slow=current(s);assert slow['spec']['bpm']==40
 ask(s,'Now make it descending.');desc=current(s);assert desc['items'][0]['written_midi']==[76,64]
 h=history(s);ask(s,'Explain which fingers change.');assert current(s)==desc and history(s)==h
 ask(s,'Undo.');assert current(s)==slow
 ask(s,'Redo.');assert current(s)==desc
 ask(s,'Make it more challenging.');hard=current(s);assert hard['spec']['rhythm']=='quarter' and hard['spec']['bpm']==48 and hard['items'][0]['written_midi']==[76,64]
 ask(s,'Make it easier.');assert current(s)['spec']['rhythm']=='half' and current(s)['spec']['bpm']==40
 ask(s,'Alternate between F4 and F5.');assert current(s)['items'][0]['written_midi']==[77,65]

def test_all_three_short_warmup_and_add_only_verified_pair():
 s=ready();r=ask(s,'Give me a short Intermediate flute warmup with all three verified octave pairs.');p=current(s)
 assert p['spec']['single'] and len(p['items'])==1 and p['items'][0]['written_midi']==[64,76,65,77,67,79]
 assert set(p['items'][0]['written_notes'])==set(N)
 seed(s);ask(s,'Add another verified octave pair.');assert current(s)['items'][0]['written_midi']==[64,76,65,77]
 ask(s,'Add another verified octave pair.');p,h=current(s),history(s);ask(s,'Add another verified octave pair.');assert current(s)==p and history(s)==h

@pytest.mark.parametrize('q',["Show the fingering for C4.",'Show the fingering for E6.','Show low E5 fingerings.','Show fingerings on a Yamaha YFL-212.','Show fingerings on YFL-222H.','Show the fingering for E4 on bass flute.','Show the fingering for E4 on piccolo.','Show alternate fingerings.','Show flute altissimo fingerings.','Use a B footjoint for these fingerings.','Show open-hole flute fingerings.','Use modified keywork.','Transpose this flute exercise.','Give me a sixteenth-note exercise between E4 and E5.','Teach a circular breathing method.','Give me trumpet-style lip slurs for flute.'])
def test_unsupported_requests_preserve_actual_plan_and_history(q):
 s=ready();seed(s);p,h=current(s),history(s);r=ask(s,q)
 assert current(s)==p and history(s)==h
 assert not r.diagnostics.get('fingering_lookup') and any(cue in r.direct_answer.lower() for cue in ['unsupported','outside','conflict','verified'])

@pytest.mark.parametrize('q',['Give me a Beginner flute octave exercise using E4 and E5.','Give me a Beginner flute octave exercise using F4 and F5.','Give me a Beginner flute warmup with all three verified octave pairs.'])
def test_existing_beginner_window_never_widened(q):
 s=ready();seed(s);p,h=current(s),history(s);r=ask(s,q);assert 'Intermediate' in r.direct_answer and current(s)==p and history(s)==h

def test_beginner_supported_pair_and_harder_keep_existing_range():
 s=ready();ask(s,'Give me a Beginner flute octave exercise using G4 and G5.');p=current(s);assert p['items'][0]['written_midi']==[67,79]
 ask(s,'Make it more challenging.');assert current(s)['level']=='Beginner' and current(s)['items'][0]['written_midi']==[67,79]
 p,h=current(s),history(s);r=ask(s,'Add another verified octave pair.');assert 'Intermediate' in r.direct_answer and current(s)==p and history(s)==h

@pytest.mark.parametrize('q',['I play a Yamaha YFL-212.','I play a YFL-222H.','I use a YFL-222 with split E mechanism.','I do not play a Yamaha YFL-222.'])
def test_unknown_or_conflicting_identity_retracts_model_with_flute_scope(q):
 s=ready();seed(s);p,h=current(s),history(s);ask(s,q);assert not fi.context(s)['model'];r=ask(s,'Show the fingering for E4.');assert 'Which flute model' in r.direct_answer and current(s)==p and history(s)==h
 ask(s,'I play a Yamaha YFL-222.');assert fi.context(s)['model']==data.MODEL

def test_model_question_does_not_confirm_and_explicit_configuration_is_accepted():
 s=setup();r=ask(s,'Does the Yamaha YFL-222 have a split-E mechanism?');assert 'no split-E' in r.direct_answer and not fi.context(s).get('model')
 r=ask(s,'I play a Yamaha YFL-222 concert C flute, covered keys, offset G, C footjoint, no split E.');assert 'identified' in r.direct_answer and fi.context(s)['model']==data.MODEL

def test_model_required_and_no_sidebar_assumption():
 s=setup();r=ask(s,'Show the fingering for E4 on flute.');assert 'Which flute model' in r.direct_answer and current(s) is None

@pytest.mark.parametrize('identity,query,flag',[('I play a Yamaha YAS-280.','Show the fingering for G5 on Yamaha YAS-280.','_ami_conv_fingering'),('I play a Yamaha YTR-2330.','Show the fingering for G4 on Yamaha YTR-2330.','_ami_conv_trumpet_fingering'),('I play a Yamaha YCL-255.','Show the fingering for B4 on Yamaha YCL-255.','_ami_conv_clarinet_fingering')])
def test_readonly_instrument_handoffs_clear_flute_context(identity,query,flag):
 s=ready();seed(s);p,h=current(s),history(s);ask(s,query);assert not fi.context(s) and s.get(flag) and current(s)==p and history(s)==h
 ask(s,'Show the fingering for E4 on Yamaha YFL-222 flute.');assert fi.context(s)['model']==data.MODEL and not s.get(flag)

@pytest.mark.parametrize('key,value',[('_suite_auth_user_id','other@example.com'),('_suite_active_workspace_id','other-workspace')])
def test_account_workspace_isolation(key,value):
 s=ready();seed(s);s[key]=value;assert not fi.context(s) and current(s) is None

@pytest.mark.parametrize('q',['Give me a flute scale exercise in F.','Give me a flute arpeggio exercise in C.','Give me a flute jazz exercise in Bb.','Give me a warmup in C.','Give me an exercise over F7.','Give me a beginner bass fingering exercise.','Give me a guitar exercise.','Give me a trombone fingering exercise.'])
def test_existing_generic_and_instrument_owners_receive_request(q):
 s=ready();seed(s);assert fi.handle(q,s) is None

def test_actual_ordinary_scale_and_bass_tab_still_work():
 s=ready();seed(s);r=ask(s,'Give me an Intermediate flute scale exercise in G.');assert current(s)['player']['key']=='flute' and not current(s)['spec'].get('flute_fingering')
 r=ask(s,'Give me a beginner bass fingering exercise.');assert current(s)['player']['key']=='bass' and r.diagnostics.get('bass_tab_sections')

@pytest.mark.parametrize('field,value',[('flute_model','other'),('instrument','alto'),('concert_key','Bb'),('rhythm','sixteenth'),('bpm',120),('reps',13)])
def test_direct_builder_rejects_unverified_substitution(field,value):
 s=ready();seed(s);spec=copy.deepcopy(current(s)['spec']);spec[field]=value
 with pytest.raises((ValueError,we.WarmupUnavailable)):fs.build(spec)

def test_tampered_diagram_and_recipe_cannot_create_unverified_fingerings():
 r=data.record('E4');r['key_states']['R3']=True
 with pytest.raises(ValueError):view.svg(r)
 for recipe in [{'kind':'octave','pairs':[3]},{'kind':'octave','pairs':[0,0]},{'kind':'twelfth','pairs':[0]}]:
  with pytest.raises(ValueError):data.groups(recipe)

def test_ordinary_F_scale_range_refusal_matches_unbound_existing_owner():
 q='Give me an Intermediate flute scale exercise in F.'
 fresh=setup();a=ask(fresh,q)
 s=ready();seed(s);p,h=current(s),history(s);b=ask(s,q)
 assert 'complete octave does not fit' in a.direct_answer and a.direct_answer==b.direct_answer and current(s)==p and history(s)==h

def test_low_and_high_same_note_does_not_substitute_other_named_pitches():
 s=ready();r=ask(s,'Show the difference between low E and high E on flute.');assert read_abc(r.notation_abc)==[64,76]
 r=ask(s,'Show the difference between low E and high G on flute.');assert read_abc(r.notation_abc)==[64,79] and '15 semitones' in r.direct_answer
