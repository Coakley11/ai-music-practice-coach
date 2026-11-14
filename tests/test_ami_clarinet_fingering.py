"""Independent Boehm source facts, exact musical intervals and real AMI state contracts."""
import copy,json,xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from music_coach_ami import clarinet_fingering_data as data,clarinet_fingering_instructor as fi,clarinet_fingering_view as view,warmup_plan as wp,flexible_single as fs
from tests.test_ami_sax_technique import setup,ask,no_api
from tests.test_abc_bar_accidentals import read_abc
O=json.loads(Path(__file__).with_name('fixtures').joinpath('ycl255_fingering_oracle.json').read_text(encoding='utf-8'))
def ready():
 s=setup();r=ask(s,'I play a Yamaha YCL-255.');assert 'identified' in r.direct_answer;return s
def current(s):return copy.deepcopy(wp.current(s))
def history(s):return copy.deepcopy(wp.history(s))

@pytest.mark.parametrize('note',list(O['notes']))
def test_independent_source_holes_keys_little_finger_transposition_and_svg(note):
 r=data.record(note);o=O['notes'][note]
 assert (r['written_midi'],r['sounding_midi'])==(o['written'],o['sounding'])
 assert {k for k,v in r['holes'].items() if v}==set(o['covered'])
 assert {k for k,v in r['keys'].items() if v}==set(o['pressed'])
 assert r['model_id']==data.MODEL and r['system']=='Standard Boehm, 17 keys, 6 rings'
 assert not r['auxiliary_controls_pressed'] and not r['teacher_reviewed'] and not r['physically_tested']
 assert r['sources'][1]['sha256']==O['chart_sources'][o['chart']]['sha256']
 assert r['sources'][0]['sha256']==O['model_source']['sha256']
 root=ET.fromstring(view.svg(r));holes=[g for g in root.iter() if 'data-hole' in g.attrib];keys=[g for g in root.iter() if 'data-key' in g.attrib]
 assert len(holes)==7 and len(keys)==4
 for g in holes:assert g.attrib['data-covered']==str(g.attrib['data-hole'] in o['covered']).lower()
 for g in keys:assert g.attrib['data-pressed']==str(g.attrib['data-key'] in o['pressed']).lower()
 assert all(k in view.description(r) for k in ['Cover:','Open:','Press:','Release:'])

@pytest.mark.parametrize('note',list(O['notes']))
def test_real_lookup_staff_and_readonly_history_sidebar(note):
 s=ready();h=history(s);settings={k:copy.deepcopy(s.get(k)) for k in ['instrument','selected_transposing_instrument','display_key','level','focus']}
 r=ask(s,'Show the fingering for '+note+' on Bb clarinet.')
 assert read_abc(r.notation_abc)==[O['notes'][note]['written']]
 assert r.diagnostics['fingering_instruction']==[data.record(note)] and r.diagnostics['fingering_lookup']
 assert current(s) is None and history(s)==h and all(s.get(k)==v for k,v in settings.items())

@pytest.mark.parametrize('pair',O['pairs'])
def test_verified_twelfths_only_register_changes_and_actual_staff(pair):
 a,b=pair;assert data.record(b)['written_midi']-data.record(a)['written_midi']==19
 assert data.changes(a,b)==['Register key: press']
 s=ready();h=history(s);r=ask(s,'Show the fingerings from '+a+' to '+b+' on clarinet.')
 assert read_abc(r.notation_abc)==[O['notes'][n]['written'] for n in pair]
 assert '19 semitones' in r.direct_answer and 'Only the register key changes' in r.direct_answer
 assert history(s)==h and current(s) is None

@pytest.mark.parametrize('q,n',[("What's the fingering for low E?",'E3'),('How do I play B above the clarinet break?','B4'),("What's the fingering for high B?",'B4')])
def test_natural_register_questions_label_exact_written_candidate(q,n):
 s=ready();r=ask(s,q);assert read_abc(r.notation_abc)==[O['notes'][n]['written']]
 assert 'written '+n in r.direct_answer
 if 'high' in q:assert 'ambiguous' in r.direct_answer and 'numbered' in r.direct_answer

@pytest.mark.parametrize('q',['How do I use the register key?','Show me the difference between the low and high register fingerings.','How do I move from low E to B in the clarion register?'])
def test_register_explanation_and_candidate_pair_have_no_unwanted_exercise(q):
 s=ready();h=history(s);r=ask(s,q)
 assert read_abc(r.notation_abc)==[52,71] and '19 semitones' in r.direct_answer
 assert current(s) is None and history(s)==h

def test_break_source_changes_register_stays_pressed_and_natural_sign():
 assert data.changes('Bb4','B4')==['Thumb hole: cover','Left index: cover','Left middle: cover','Left ring: cover','Right index: cover','Right middle: cover','Right ring: cover','Throat A key: release','Left little finger E/B: press']
 s=ready();h=history(s);r=ask(s,'Show the fingerings for Bb4 and B4 across the clarinet break.')
 assert read_abc(r.notation_abc)==[70,71] and '_B' in r.notation_abc and '=B' in r.notation_abc
 assert 'register key stays pressed' in r.direct_answer and 'one semitone' in r.direct_answer
 assert current(s) is None and history(s)==h

@pytest.mark.parametrize('pair',O['pairs'])
def test_pair_handoff_actual_music_repetition_descending_explain_and_exact_undo(pair):
 s=ready();ask(s,'Show the fingerings from '+pair[0]+' to '+pair[1]+'.');ask(s,'Give me a slow exercise moving between those notes.');a=current(s)
 expected=[O['notes'][n]['written'] for n in pair]
 assert a['spec']['clarinet_fingering'] and a['items'][0]['written_midi']==expected
 assert a['items'][0]['sounding_midi']==[n-2 for n in expected] and read_abc(a['items'][0]['abc'])==expected and 'z' in a['items'][0]['abc']
 ask(s,'Repeat the transition four times.');b=current(s);assert b['spec']['reps']==4
 ask(s,'Make it descending.');c=current(s);assert c['items'][0]['written_midi']==expected[::-1]
 h=history(s);r=ask(s,'Explain what my fingers are changing.');assert 'Register key: release' in r.direct_answer and current(s)==c and history(s)==h
 ask(s,'Undo.');assert current(s)==b
 ask(s,'Redo.');assert current(s)==c
 ask(s,'Make it easier.');assert current(s)['spec']['rhythm']=='half' and current(s)['spec']['bpm']==40
 ask(s,'Undo.');assert current(s)==c

def test_add_three_verified_pairs_then_refuse_and_restore_exact_versions():
 s=ready();ask(s,'Give me a slow exercise from E3 to B4.');a=current(s)
 ask(s,'Add another verified twelfth pair.');b=current(s);assert b['items'][0]['written_midi']==[52,71,53,72]
 ask(s,'Now add another verified twelfth pair.');c=current(s);assert c['items'][0]['written_midi']==[52,71,53,72,55,74]
 h=history(s);ask(s,'Add the next verified twelfth pair.');assert current(s)==c and history(s)==h
 ask(s,'Make it slower.');d=current(s);assert d['spec']['bpm']==40
 ask(s,'Make it easier.');assert current(s)['items'][0]['written_midi']==[52,71]
 ask(s,'Undo.');assert current(s)==d
 ask(s,'Undo.');assert current(s)==c

def test_break_handoff_is_semitone_recipe_and_descending_not_a_twelfth():
 s=ready();ask(s,'Give me a short register-break warmup.');a=current(s)
 assert a['items'][0]['written_midi']==[70,71] and a['spec']['clarinet_recipe']=={'kind':'break'}
 ask(s,'Make it descending.');b=current(s);assert b['items'][0]['written_midi']==[71,70]
 h=history(s);r=ask(s,'Explain what my fingers are changing.')
 assert 'Throat A key: press' in r.direct_answer and 'Thumb hole: open' in r.direct_answer and current(s)==b and history(s)==h
 ask(s,'Add another verified twelfth pair.');assert current(s)==b and history(s)==h
 ask(s,'Undo.');assert current(s)==a

@pytest.mark.parametrize('q',['Give me a Beginner exercise from E3 to B4.','Give me a Beginner exercise from F3 to C5.'])
def test_existing_beginner_window_not_silently_widened(q):
 s=ready();r=ask(s,q);assert current(s) is None and 'Intermediate' in r.direct_answer and 'Beginner' in r.direct_answer
 ask(s,'Give me a Beginner exercise from G3 to D5.');a=current(s);assert a['spec']['level']=='Beginner' and a['items'][0]['written_midi']==[55,74]
 h=history(s);ask(s,'Add another verified twelfth pair.');assert current(s)==a and history(s)==h

@pytest.mark.parametrize('q',['Show the fingering for B5.','Show the fingering for low C.','Show the fingering for high E.','Show the fingering for low E5.','Show alternate fingerings.','Show altissimo fingerings.','Show the fingering for G3 on Albert clarinet.','Show the fingering for G3 on Oehler clarinet.','Show the fingering for G3 on bass clarinet.','Show the fingering for G3 on Eb clarinet.','Show the fingering for G3 on clarinet in A.','Show the fingering for G3 on YCL-450.','Show the fingering for concert E3.','Give me an ordinary octave fingering exercise.','Use sixteenth notes.','Make it higher.','Transpose it up.','Repeat the transition 13 times.','Give me an embouchure method.'])
def test_unsupported_preserves_scores_history_and_context_with_clarinet_limits(q):
 s=ready();ask(s,'Give me a slow exercise from E3 to B4.');a=current(s);h=history(s);ctx=fi.context(s)
 r=ask(s,q);assert current(s)==a and history(s)==h and fi.context(s)==ctx
 assert 'YCL-255' in r.direct_answer and 'saxophone engine' not in r.direct_answer

@pytest.mark.parametrize('q',["I do not play a Yamaha YCL-255.","I don't have a YCL-255.",'How do I know if my clarinet is a YCL-255?'])
def test_no_model_confirmation_from_negation_or_model_question(q):
 s=setup();ask(s,q);assert not fi.context(s) and current(s) is None

def test_explicit_clarinet_overrides_alto_sidebar_but_requires_model():
 s=setup();r=ask(s,'Show the fingering for E3 on Bb clarinet.');assert 'Which clarinet model' in r.direct_answer and current(s) is None
 r=ask(s,'Show the fingering for E3 on Yamaha YCL-255 Bb clarinet.')
 assert read_abc(r.notation_abc)==[52] and s['instrument']=='Saxophone' and fi.context(s)['model']==data.MODEL

def test_old_sax_and_trumpet_owners_history_and_lookup_contexts():
 s=setup();ask(s,'I play a Yamaha YAS-280.');ask(s,'Give me an octave exercise using G.');old=current(s)
 ask(s,'I play a Yamaha YCL-255.');ask(s,'Show the fingering for E3.');assert current(s)==old
 ask(s,'Give me a slow exercise moving between those notes.');new=current(s)
 ask(s,'Undo.');assert current(s)==old and not fi.context(s)
 ask(s,'Redo.');assert current(s)==new and fi.context(s)['model']==data.MODEL
 ask(s,'Show the fingering for G4 on Yamaha YTR-2330 Bb trumpet.');assert not fi.context(s)
 ask(s,'Give me an exercise moving between those notes.');assert current(s)['spec'].get('trumpet_fingering')
 ask(s,'Show the fingering for G5 on Yamaha YAS-280.');assert not fi.context(s)

@pytest.mark.parametrize('owner',['_suite_auth_user_id','_suite_active_workspace_id'])
def test_account_workspace_isolation(owner):
 s=ready();ask(s,'Give me a slow exercise from E3 to B4.');s[owner]='different'
 r=ask(s,'Show the fingering for E3 on clarinet.');assert current(s) is None and not fi.context(s) and 'model' in r.direct_answer

@pytest.mark.parametrize('change',[{'concert_key':'C'},{'instrument':'alto'},{'clarinet_model':'other'},{'rhythm':'sixteenth'},{'clarinet_recipe':{'kind':'octave','pairs':[0]}},{'clarinet_recipe':{'kind':'twelfth','pairs':[3]}},{'level':'Beginner'}])
def test_builder_mutations_cannot_escape_source_or_level(change):
 s=ready();ask(s,'Give me a slow exercise from E3 to B4.');a=current(s);spec=copy.deepcopy(a['spec']);spec.update(change)
 with pytest.raises((ValueError,KeyError)):fs.build(spec)
 assert current(s)==a

def test_tamper_rejected_shared_renderer_dispatch_and_other_models_distinct():
 from music_coach_ami.fingering_view import svg,html
 r=data.record('B4');assert svg(r)==view.svg(r) and html([r])==view.html([r])
 r['holes']['T']=False
 with pytest.raises(ValueError):view.svg(r)

def test_last_readonly_note_wins_except_explicit_stored_exercise_explanation():
 s=ready();ask(s,'Give me a slow exercise from E3 to B4.');a=current(s);h=history(s)
 ask(s,'Show the fingering for D5.');r=ask(s,'Explain which fingers are pressed.')
 assert read_abc(r.notation_abc)==[74] and current(s)==a and history(s)==h
 r=ask(s,'Explain the finger changes in the exercise.');assert r.diagnostics['fingering_instruction'][0]['id']=='E3' and current(s)==a and history(s)==h


def test_ordinary_clarinet_octave_and_scale_owners_survive_identified_model():
 s=ready();ask(s,'Give me a slow exercise from E3 to B4.')
 ask(s,'Give me a beginner clarinet octave exercise.');p=current(s)
 assert p['player']['key']=='clarinet' and not p['spec'].get('clarinet_fingering')
 notes=p['items'][0]['written_midi'];assert all(b-a==12 for a,b in zip(notes[::2],notes[1::2]))
 ask(s,'Give me a beginner clarinet major scale.');p=current(s)
 assert p['player']['key']=='clarinet' and not p['spec'].get('clarinet_fingering')


@pytest.mark.parametrize('q',['I play a Yamaha YCL-450.','My clarinet is a YCL-450.','I use a YCL-450.','I play an Albert clarinet.','I play a bass clarinet.'])
def test_changed_model_identity_retracts_supported_model_but_preserves_clarinet_scope(q):
 s=ready();ask(s,'Give me a slow exercise from E3 to B4.');a=current(s);h=history(s)
 r=ask(s,q);assert 'outside' in r.direct_answer and current(s)==a and history(s)==h
 assert not fi.context(s).get('model') and fi.context(s)['instrument']=='clarinet'
 r=ask(s,'Show the fingering for E3.');assert 'Which clarinet model' in r.direct_answer
 assert current(s)==a and history(s)==h
 ask(s,'I play a Yamaha YCL-255.');r=ask(s,'Show the fingering for E3.')
 assert read_abc(r.notation_abc)==[52] and current(s)==a and history(s)==h


@pytest.mark.parametrize('q',['Give me a beginner clarinet scale exercise in C.','Give me a clarinet arpeggio exercise in F.','Give me a warmup in C.','Give me a jazz exercise in Bb.','Give me an exercise over F7 chords.'])
def test_generic_keyed_music_retains_its_owner_after_clarinet_identification(q):
 s=ready();ask(s,'Show the fingering for E3.');ctx=fi.context(s);h=history(s)
 assert fi.handle(q,s,{'instrument':'Saxophone','level':'Intermediate','display_key':'C'}) is None
 assert fi.context(s)==ctx and history(s)==h

def test_actual_keyed_clarinet_scale_and_arpeggio_keep_existing_engines():
 s=ready();ask(s,'Give me a slow exercise from E3 to B4.');old=current(s)
 ask(s,'Give me a beginner clarinet scale exercise in C.');scale=current(s)
 assert scale['player']['key']=='clarinet' and not scale['spec'].get('clarinet_fingering') and scale['player']['concert_key']=='C'
 r=ask(s,'Give me a beginner clarinet arpeggio exercise in F.');assert current(s)==scale and 'complete octave does not fit' in r.direct_answer
 ask(s,'Give me an Advanced clarinet arpeggio exercise in F.');arpeggio=current(s)
 assert arpeggio['player']['key']=='clarinet' and not arpeggio['spec'].get('clarinet_fingering') and arpeggio['player']['concert_key']=='F'
 ask(s,'Make it slower.');slow=current(s);assert slow['spec']['bpm']<arpeggio['spec']['bpm'] and slow['player']['concert_key']=='F'
 ask(s,'Undo.');assert current(s)==arpeggio
 ask(s,'Redo.');assert current(s)==slow


@pytest.mark.parametrize('q',['Give me a beginner bass fingering exercise.','Give me a guitar fingering exercise.','Give me a trombone fingering exercise.','Give me a beginner piano finger exercise.'])
def test_explicit_other_instruments_use_the_shared_instrument_parser(q):
 s=ready();ask(s,'Show the fingering for E3.');ctx=fi.context(s);h=history(s)
 assert fi.handle(q,s,{'instrument':'Saxophone','level':'Intermediate','display_key':'C'}) is None
 assert fi.context(s)==ctx and history(s)==h

def test_bare_bass_fingering_request_reaches_bass_and_tab_after_clarinet_lookup():
 from tests.bass_oracle import check
 s=ready();ask(s,'Show the fingering for E3.');r=ask(s,'Give me a beginner bass fingering exercise.');p=current(s)
 assert p['player']['key']=='bass' and p['spec'].get('bass') and not p['spec'].get('clarinet_fingering')
 assert check(p)==[] and r.diagnostics.get('bass_tab_sections')
