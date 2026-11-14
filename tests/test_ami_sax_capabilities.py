"""Independent limits/projection, documentary scope and no-substitution contracts."""
import copy
from dataclasses import FrozenInstanceError, replace
import pytest
from music_coach_ami import sax_capabilities as cap, warmup_engine as we, warmup_plan as wp
from music_coach_ami.pipeline import run_coach_submit
from tests.test_ami_sax_technique import setup, ask, no_api
from tests.song_fixtures import song_session

EXPECTED = {'soprano': (2,(56,87)), 'alto': (9,(49,80)), 'tenor': (14,(44,75)), 'baritone': (21,(37,68))}
REQUESTS = ('Give me an altissimo G exercise.', 'Give me an overtone series from low B-flat.', 'Show me alternate fingerings for high F-sharp.')

@pytest.mark.parametrize('horn',cap.SAX)
def test_common_caps_exact_octave_projection_and_windows(horn):
    p=cap.profile(horn);offset,sounding=EXPECTED[horn]
    assert p.written_range==(58,89) and p.written_minus_sounding==offset and p.sounding_range==sounding
    assert dict(p.level_windows)=={'Beginner':(62,79),'Intermediate':(60,84),'Advanced':(58,89)}
    assert all(v is None for _,v in p.optional_hardware)
    with pytest.raises(FrozenInstanceError):p.written_range=(57,100)

@pytest.mark.parametrize('model',tuple(cap.MODELS))
def test_documentary_models_have_sources_and_do_not_expand_generation(model):
    m=cap.MODELS[model];before=we.make_player(m.instrument,'C')
    assert cap.model_scope(model,m.instrument)==m
    assert m.source_ids and all(i in cap.SOURCES for i in m.source_ids)
    assert all(cap.SOURCES[i].url.startswith('https://') for i in m.source_ids)
    assert all(cap.SOURCES[i].checked_on=='2026-11-13' for i in m.source_ids)
    assert 'unconfirmed' in m.revision
    assert we.make_player(m.instrument,'C')==before and cap.profile(m.instrument).written_range==(58,89)
    with pytest.raises(ValueError):cap.model_scope(model,'flute')


def test_unknown_is_not_false_or_a_hardware_upgrade():
    assert cap.MODELS['yamaha-yas26'].hardware('high_f_sharp') is None
    assert cap.MODELS['yamaha-yss875ex'].hardware('high_g') is None
    assert cap.MODELS['yamaha-yss875exhg'].hardware('high_g') is True
    assert cap.MODELS['yamaha-ybs62ii'].hardware('low_a') is True
    assert cap.MODELS['yamaha-ybs62ii'].keyed_low==57
    assert cap.MODELS['selmer-supreme-alto'].keyed_high==90
    with pytest.raises(ValueError):cap.model_scope('unspecified-alto','alto')
    with pytest.raises(ValueError):cap.profile('saxophone')
    with pytest.raises(TypeError):cap.MODELS['invented']='invented'


def target():
    return cap.StudyTarget('overtones','alto','yamaha-yas280',70,58,2,written_name='Bb',written_octave=4)


def evidence():
    # Synthetic completeness fixture, explicitly not a real instrument review.
    return cap.ReviewEvidence('yamaha-yas280','test specimen revision','test system','test setup',
        'https://example.invalid/review','test locator','test permission','test reviewer','2026-11-13',
        ('test prerequisite',),('response','intonation','transition_context'),
        ('written_sounding_octave','harmonic_relationship','notation','history_owner','browser_accessibility'))


def test_fundamental_partial_target_and_missing_review_are_distinct():
    t=target();r=cap.validation_requirements(t)
    assert t.fingered_fundamental==58 and t.written_target==70 and t.harmonic_partial==2
    assert not r.generation_supported and 'independent_reviewer' in r.missing and 'reviewed fingering reference' in r.missing
    assert 'fundamental within documented keyed bounds' in cap.validation_requirements(replace(t,fingered_fundamental=40)).missing
    assert 'matching written spelling and octave' in cap.validation_requirements(replace(t,written_octave=5)).missing

@pytest.mark.parametrize('partial',[None,0,1,-2,2.5,True])
def test_invalid_partial_never_becomes_a_note_sequence(partial):
    r=cap.validation_requirements(replace(target(),harmonic_partial=partial))
    assert 'intended harmonic partial >= 2' in r.missing and not r.generation_supported


def test_complete_submitted_metadata_cannot_enable_unimplemented_engine():
    f=cap.FingeringReference('test variant','yamaha-yas280','test system','https://example.invalid/fingering','test locator','test permission')
    t=replace(target(),fingering=f)
    r=cap.validation_requirements(t,evidence())
    assert r.missing==('separately approved and independently verified specialized engine',)
    assert not r.generation_supported
    r=cap.validation_requirements(replace(t,fingering=replace(f,model_id='yamaha-yts62')),evidence())
    assert 'matched licensed fingering reference' in r.missing
    assert 'review matched to model' in cap.validation_requirements(t,replace(evidence(),model_id='yamaha-yts62')).missing

@pytest.mark.parametrize('horn',cap.SAX)
@pytest.mark.parametrize('question',REQUESTS)
def test_fresh_specialized_requests_are_explicit_without_substitution(horn,question):
    s=setup();q=question.rstrip('.')+' for '+horn+' saxophone.'
    r=ask(s,q)
    assert wp.current(s) is None and not r.notation_abc
    assert r.diagnostics['specialized_generation_supported'] is False
    assert 'not supported' in r.direct_answer and 'ordinary' in r.direct_answer

@pytest.mark.parametrize('question',REQUESTS)
def test_specialized_requests_preserve_exact_selected_jazz_plan_and_history(question):
    s=song_session('Blue Bossa');ask(s,'Give me a ten-minute alto sax jazz improvisation warmup over Blue Bossa.')
    ask(s,'Make the second exercise harder.');p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s))
    settings={k:copy.deepcopy(s.get(k)) for k in ('instrument','level','focus','display_key','concert_key','backing_track_bpm')}
    r=ask(s,question)
    assert wp.current(s)==p and wp.history(s)==h
    assert all(s.get(k)==v for k,v in settings.items())
    assert 'existing exercise' in r.direct_answer and r.diagnostics['single_exercise_failed']=='unsupported_sax'
    ask(s,'Undo.');assert wp.current(s)!=p
    ask(s,'Redo.');assert wp.current(s)==p

@pytest.mark.parametrize('owner',['_suite_auth_user_id','_suite_active_workspace_id'])
def test_specialized_refusal_never_reveals_previous_owner_score(owner):
    s=setup();ask(s,'Give me an alto sax exercise in thirds.');s[owner]='different'
    r=ask(s,REQUESTS[0]);assert wp.current(s) is None and not r.notation_abc


def test_other_instrument_partial_owner_is_preserved():
    s=setup();r=run_coach_submit('Give me a beginner trumpet lip-slur exercise.',s,ami_ctx={'instrument':'Trumpet','level':'Beginner','display_key':'C'})[1]
    assert wp.current(s)['spec']['trumpet'] and wp.current(s)['items'][0]['written_midi']==[60,67]*2
    assert 'specialized_generation_supported' not in r.diagnostics


@pytest.mark.parametrize('question',REQUESTS)
def test_legacy_single_score_refusal_preserves_its_own_response_contract(question):
    s=setup();ask(s,'Give me an alto sax exercise in thirds.')
    p=copy.deepcopy(wp.current(s));h=copy.deepcopy(wp.history(s));r=ask(s,question)
    assert p['spec']['single'] and wp.current(s)==p and wp.history(s)==h
    assert r.notation_abc==p['items'][0]['abc'] and r.diagnostics['single_exercise_failed']=='unsupported_sax'


def test_unspecified_saxophone_subtype_is_not_presented_as_a_verified_alto():
    from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
    s=setup();s.pop(SELECTED_TRANSPOSING_INSTRUMENT_KEY,None)
    r=ask(s,'Give me a saxophone altissimo exercise.')
    assert wp.current(s) is None and 'Choose soprano, alto, tenor or baritone' in r.direct_answer
    assert 'ordinary alto' not in r.direct_answer
