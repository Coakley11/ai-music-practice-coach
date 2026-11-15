"""Independent ideal-partial, fingering-domain and development-gate contracts."""
import copy,json
from dataclasses import replace,FrozenInstanceError
from pathlib import Path
import pytest
from music_coach_ami import sax_overtone_pilot as pilot,sax_capabilities as cap,fingering_data as fd
from music_coach_ami.warmup_engine import WarmupUnavailable
from tests.test_abc_bar_accidentals import read_abc
from tests.test_ami_fingering_instructor import ready
from tests.test_ami_sax_technique import ask,no_api
from music_coach_ami import warmup_plan as wp
O=json.loads(Path(__file__).with_name('fixtures').joinpath('yas280_overtone_stage_f_oracle.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('i',[0,1])
def test_independent_partials_written_sounding_pitch_and_tuning(i):
 c=pilot.validate(pilot.CANDIDATES[i]);o=O['targets'][i]
 assert (c.partial,c.written_target,c.written_midi,c.sounding_target,c.sounding_midi,c.ideal_frequency_ratio)==(o['partial'],o['written_name'],o['written_midi'],o['sounding_name'],o['sounding_midi'],o['ideal_ratio'])
 assert c.written_midi-c.fingered_written_fundamental==o['semitones']
 assert c.ideal_cents_above_tempered_target==pytest.approx(o['ideal_cents_above_tempered'],abs=1e-9)
 assert c.written_midi-c.sounding_midi==9 and not c.teacher_reviewed and not c.physically_tested
 assert all(pilot.SOURCES[k].startswith('https://') for k in c.source_ids)

@pytest.mark.parametrize('c',pilot.CANDIDATES)
def test_fingered_fundamental_does_not_become_the_normal_target_fingering(c):
 r=pilot.fundamental_reference(c)
 assert r['id']=='D4' and {k for k,v in r['key_states'].items() if v}==set(O['fundamental']['pressed'])
 assert not r['key_states']['O'] and r['sounding_midi']==53
 assert fd.record(c.written_target)['key_states']['O'] # normal target uses a different fingering

@pytest.mark.parametrize('field,value',[('model_id','yamaha-yts62'),('partial',4),('partial',True),('written_midi',75),('written_midi',74.0),('sounding_midi',66),('fundamental_record','D5'),('teacher_reviewed',True),('physically_tested',True)])
def test_rejects_unregistered_or_falsely_validated_candidates(field,value):
 with pytest.raises(ValueError):pilot.validate(replace(pilot.CANDIDATES[0],**{field:value}))

@pytest.mark.parametrize('c',pilot.CANDIDATES)
def test_development_gate_stays_closed_without_physical_validation(c):
 before=cap.profile('alto');gate=pilot.review_gate(c)
 assert not gate.generation_supported and 'independent_reviewer' in gate.missing
 with pytest.raises(WarmupUnavailable,match='disabled'):pilot.specialized_exercise(c,cap.ReviewEvidence(model_id=pilot.MODEL,independent_reviewer='unverified submitted name'))
 assert cap.profile('alto')==before

def test_ordinary_preview_uses_existing_notation_timing_and_key_change_engine():
 p=pilot.ordinary_register_preview(pilot.MODEL,level='Intermediate');r=p['items'][0];o=O['ordinary_preview']
 assert r['written_midi']==o['written'] and r['sounding_midi']==o['sounding'] and r['durations']==o['durations']
 assert read_abc(r['abc'])==o['written'] and r['bpm']==60 and r['pass_seconds']==4 and p['total_seconds']==4
 assert fd.changes('D4','D5')==o['changed_controls']

@pytest.mark.parametrize('model,level,bpm',[('unknown','Intermediate',60),('yamaha-yas280','Expert',60),('yamaha-yas280','Advanced',0),('yamaha-yas280','Advanced',160)])
def test_no_model_level_or_tempo_substitution(model,level,bpm):
 with pytest.raises(ValueError):pilot.ordinary_register_preview(model,level=level,bpm=bpm)

@pytest.mark.parametrize('question',["How do I play altissimo G6 on alto sax?","What's the fingering for altissimo Bb6?","Give me an overtone exercise from D4.","Show me another alternate fingering."])
def test_existing_specialized_refusals_leave_exercise_and_history_exact(question,no_api):
 s=ready();ask(s,'Show me how to go from low D to high D on alto sax.');ask(s,'Give me a short exercise using these two notes.')
 plan=copy.deepcopy(wp.current(s));assert plan
 history=copy.deepcopy(wp.history(s));r=ask(s,question)
 assert r.diagnostics.get('specialized_generation_supported') is False
 assert wp.current(s)==plan and wp.history(s)==history

def test_documentary_records_are_immutable():
 with pytest.raises(FrozenInstanceError):pilot.CANDIDATES[0].partial=3
