"""Independent source transcription, real pitch reading and conversation contracts."""
import copy,json,re
from pathlib import Path
import pytest
from music_coach_ami import fingering_data as data,fingering_view as view,fingering_instructor as fi,warmup_plan as wp
from tests.test_ami_sax_technique import setup,ask,no_api
from tests.test_abc_bar_accidentals import read_abc
from tests.song_fixtures import song_session
ORACLE=json.loads(Path(__file__).with_name('fixtures').joinpath('yas280_basic_fingering_oracle.json').read_text())

def ready():
    s=setup();ask(s,'I play a Yamaha YAS-280.');return s

@pytest.mark.parametrize('note',('G4','A4','B4'))
def test_record_matches_independent_source_transcription_and_projection(note):
    r=data.record(note);o=ORACLE['notes'][note]
    assert r['written_midi']==o['written'] and r['sounding_midi']==o['sounding']
    assert {k for k,v in r['key_states'].items() if v}==set(o['pressed'])
    assert all(not r['key_states'][k] for k in ORACLE['released_common'])
    assert not r['auxiliary_controls_pressed'] and not r['teacher_reviewed']
    assert r['model']=='Yamaha YAS-280' and r['instrument']=='alto' and r['variant']=='basic'
    assert r['verification']=='manufacturer/reference-supported'
    assert r['sources'][0]['sha256'] and '335916' in r['sources'][0]['url']
    assert any('wfg.woodwind.org' in source['url'] for source in r['sources'])

@pytest.mark.parametrize('note',('G4','A4','B4'))
def test_original_svg_all_key_states_accessible_text_and_no_source_chart_copy(note):
    r=data.record(note);svg=view.svg(r)
    for key,value in r['key_states'].items():assert f'data-key="{key}" data-pressed="{str(value).lower()}"' in svg
    assert 'role="img"' in svg and '<desc' in svg and note in svg
    html=view.html([r]);assert 'tabindex="0"' in html and 'not independently teacher-reviewed' in html
    assert '<image' not in html and '.gif' not in html and 'base64' not in html
    r['key_states']['O']=True
    with pytest.raises(ValueError):view.svg(r)

@pytest.mark.parametrize('note',('G4','A4','B4'))
def test_native_abc_pitch_and_read_only_lookup(note):
    s=ready();before=copy.deepcopy(wp.history(s));r=ask(s,'Show me the fingering for '+note+'.')
    assert read_abc(r.notation_abc)==[ORACLE['notes'][note]['written']]
    assert wp.current(s) is None and wp.history(s)==before and r.diagnostics['fingering_lookup']
    assert note in r.direct_answer and r.diagnostics['fingering_instruction'][0]['id']==note

@pytest.mark.parametrize('q,note',[("What's the fingering for A?",'A4'),('Show me how to finger G.','G4'),('What keys do I press for B?','B4'),('show me the fingering for g','G4')])
def test_natural_language_documented_octave_default(q,note):
    s=ready();r=ask(s,q);assert fi.context(s)['note']==note and 'written octave 4' in r.direct_answer


def test_identify_model_before_note_and_never_interpret_article_a_as_a_note():
    s=setup();r=ask(s,"What's the fingering for A on alto saxophone?")
    assert 'Which saxophone model' in r.direct_answer and not fi.context(s) and wp.current(s) is None
    r=ask(s,'I play a Yamaha YAS-280.');assert fi.context(s)['note']=='' and not r.notation_abc

@pytest.mark.parametrize('q',['Show the fingering for C4.','Show the fingering for Bb4.','Show the fingering for A6.','Show the fingering for G6.','Show the fingering for concert A4.','Show the fingering for A on YAS-26.','Show the fingering for A on Selmer.','Show the fingering for A on modified YAS-280.','Show me the fingering for A on tenor saxophone.','Show me the fingering for G on flute.','Show me another fingering for A.'])
def test_unsupported_requests_preserve_note_exercise_and_history(q):
    s=ready();ask(s,'Show the fingering for A4.');ask(s,'Give me a short exercise using it.')
    c=fi.context(s);p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s));r=ask(s,q)
    assert fi.context(s)==c and wp.current(s)==p and wp.history(s)==h
    assert not r.diagnostics.get('fingering_lookup')


def test_explicit_alto_model_overrides_sidebar_flute_without_writing_globals():
    s=setup();s['instrument']='Flute';before=copy.deepcopy(s)
    r=ask(s,'Show me the fingering for A4 on Yamaha YAS-280 alto saxophone.')
    assert r.diagnostics['fingering_instruction'][0]['id']=='A4' and s['instrument']==before['instrument']


def test_sidebar_tenor_is_not_silently_substituted_with_remembered_alto():
    from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
    s=ready();s[SELECTED_TRANSPOSING_INSTRUMENT_KEY]='Tenor saxophone (Bb)'
    r=ask(s,'Show me the fingering for A.');assert 'only' in r.direct_answer and not r.diagnostics.get('fingering_lookup')


def test_followups_read_only_existing_jazz_plan_and_owner_context():
    s=song_session('Blue Bossa');ask(s,'Give me a ten-minute alto sax jazz improvisation warmup over Blue Bossa.')
    p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s))
    ask(s,'Show me the fingering for G4 on Yamaha YAS-280.')
    for q in ('Can you explain which keys are pressed?','Can you show me that note on the staff?'):
        r=ask(s,q);assert read_abc(r.notation_abc)==[67] and wp.current(s)==p and wp.history(s)==h


def test_target_handoff_slowing_and_exact_history():
    s=ready();ask(s,'Show the fingering for A4.');ask(s,'Give me a short exercise using it.')
    p=copy.deepcopy(wp.current(s));assert p['items'][0]['written_midi']==[69]*4 and p['items'][0]['sounding_midi']==[60]*4
    ask(s,'Make the exercise slower.');slow=copy.deepcopy(wp.current(s));assert slow['items'][0]['written_midi']==[69]*4 and slow['items'][0]['bpm']<p['items'][0]['bpm']
    ask(s,'Undo.');assert wp.current(s)==p
    ask(s,'Redo.');assert wp.current(s)==slow


def test_verified_lead_in_descending_key_changes_and_easier_use_actual_notes():
    s=ready();ask(s,'Show the fingering for B4.');ask(s,'Show me a couple of notes leading up to it.')
    a=copy.deepcopy(wp.current(s));assert a['items'][0]['written_midi']==[67,69,71,71]
    ask(s,'Now make it descending.');b=copy.deepcopy(wp.current(s));assert b['items'][0]['written_midi']==[71,71,69,67]
    h=copy.deepcopy(wp.history(s));r=ask(s,'Explain what keys I need to change.')
    assert 'Left middle: press' in r.direct_answer and 'Left ring: press' in r.direct_answer
    assert wp.current(s)==b and wp.history(s)==h
    ask(s,'Make it easier.');assert wp.current(s)['items'][0]['written_midi']==[71,71]
    ask(s,'Undo.');assert wp.current(s)==b


def test_handoff_to_and_from_existing_warmup_history_uses_shared_version_owner():
    s=setup();ask(s,'Give me a warmup.');old=copy.deepcopy(wp.current(s))
    ask(s,'Show the fingering for A4 on Yamaha YAS-280.');ask(s,'Give me a short exercise using it.');new=copy.deepcopy(wp.current(s))
    ask(s,'Undo.');assert wp.current(s)==old
    ask(s,'Redo.');assert wp.current(s)==new

@pytest.mark.parametrize('owner',['_suite_auth_user_id','_suite_active_workspace_id'])
def test_account_workspace_clears_fingering_and_exercise_context(owner):
    s=ready();ask(s,'Show the fingering for A4.');ask(s,'Give me a short exercise using it.');s[owner]='other'
    r=ask(s,'Show the fingering for A.');assert not fi.context(s) and wp.current(s) is None and 'model' in r.direct_answer

@pytest.mark.parametrize('q',['Show me a couple of notes leading up to it.','Now make it descending.','Make it higher.','Use sixteenth notes.'])
def test_unavailable_revisions_do_not_replace_target_or_history(q):
    s=ready();ask(s,'Show the fingering for A4.');ask(s,'Give me a short exercise using it.')
    p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s));ask(s,q)
    assert wp.current(s)==p and wp.history(s)==h


@pytest.mark.parametrize('q',["I do not play a Yamaha YAS-280.","I don't have a YAS-280.",'How do I know if my sax is a YAS-280?'])
def test_negation_or_model_identification_question_does_not_confirm_a_model(q):
    s=setup();r=ask(s,q);assert not fi.context(s) and wp.current(s) is None


def test_practice_followups_bind_stored_note_despite_sidebar_instrument_change():
    s=ready();ask(s,'Show the fingering for B4.');ask(s,'Show me a couple of notes leading up to it.')
    s['instrument']='Flute';ask(s,'Make it easier.')
    assert wp.current(s)['items'][0]['written_midi']==[71,71]
    assert wp.current(s)['player']['key']=='alto' and s['instrument']=='Flute'
    r=ask(s,'Can you show me that note on the staff?');assert read_abc(r.notation_abc)==[71]


def test_ordinary_other_instrument_fingering_exercises_keep_existing_owners():
    s=ready();r=ask(s,'Give me a difficult flute fingering exercise.')
    assert wp.current(s)['player']['key']=='flute' and not wp.current(s)['spec'].get('fingering')


def test_original_svg_is_standalone_valid_and_source_facts_remain_data_driven():
    import xml.etree.ElementTree as ET
    root=ET.fromstring(view.svg(data.record('A4')))
    assert root.tag=='{http://www.w3.org/2000/svg}svg'
    assert len([g for g in root.iter() if 'data-key' in g.attrib])==7


def test_retracting_confirmed_model_clears_lookup_only_and_requires_reconfirmation():
    s=ready();ask(s,'Show the fingering for A4.');ask(s,'Give me a short exercise using it.')
    p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s))
    ask(s,"I do not play a Yamaha YAS-280.")
    assert not fi.context(s) and wp.current(s)==p and wp.history(s)==h
    r=ask(s,'Show the fingering for A.');assert 'Which saxophone model' in r.direct_answer
    assert not fi.context(s) and wp.current(s)==p and wp.history(s)==h


def test_last_readonly_note_wins_over_a_different_stored_exercise_target():
    s=ready();ask(s,'Show the fingering for A4.');ask(s,'Give me a short exercise using it.')
    p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s))
    ask(s,'Show the fingering for B4.');r=ask(s,'Can you explain which keys are pressed?')
    assert read_abc(r.notation_abc)==[71] and r.diagnostics['fingering_instruction'][0]['id']=='B4'
    assert wp.current(s)==p and wp.history(s)==h and fi.context(s)['note']=='B4'
    r=ask(s,'Explain which keys change in the exercise.')
    assert r.diagnostics['fingering_instruction'][0]['id']=='A4' and fi.context(s)['note']=='A4'
    assert wp.current(s)==p and wp.history(s)==h


def test_ordinary_navigation_reruns_and_clears_unrelated_fingering_metadata():
    from tests.test_ami_warmup_nav import _fresh,_card_from,_press
    s,r=_fresh();p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s))
    card=_card_from(r);card['fingering_instruction']=[data.record('A4')]
    _,updated=_press(s,card,'Next exercise')
    assert updated['fingering_instruction']==[] and wp.current(s)==p
    assert wp.history(s)['versions']==h['versions'] and wp.history(s)['can_undo']==h['can_undo']
