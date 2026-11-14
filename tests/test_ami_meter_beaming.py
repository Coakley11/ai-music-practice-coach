"""Independent metrical expectations: only ABC separators may change."""
import copy,json,re
from pathlib import Path
from fractions import Fraction
import pytest
from music_coach_ami.scale_engine import _abc_beam_within_measure
from music_coach_ami import warmup_engine as we
from tests.test_abc_bar_accidentals import read_abc
CASES=json.loads(Path(__file__).with_name('fixtures').joinpath('ami_beaming_cases.json').read_text())
@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_exact_conventional_groups_and_whitespace_only_change(case):
 tokens=copy.deepcopy(case['tokens']);actual=_abc_beam_within_measure(tokens,case['meter'],'1/4')+' |'
 assert actual==case['expected'] and tokens==case['tokens']
 assert re.sub(r'\s+','',actual)==re.sub(r'\s+','',' '.join(tokens)+' |')
 old=f"X:1\nM:{case['meter']}\nL:1/4\nK:C\n"+' '.join(tokens)+' |'
 new=old[:old.rfind('\n')+1]+actual
 assert read_abc(old)==read_abc(new)

@pytest.mark.parametrize('tokens',[['(3:2:2C/2D/2E/2','F/2','G/2'],['C/2>','D/2'],['[unknown]','C/2']])
def test_explicit_tuplet_broken_or_unknown_groupings_are_preserved(tokens):
 assert _abc_beam_within_measure(tokens,'4/4','1/4')==' '.join(tokens)

def test_default_length_is_respected_without_changing_duration_tokens():
 assert _abc_beam_within_measure(list('CDEFGABc'),'4/4','1/8')=='CD EF GA Bc'
 assert _abc_beam_within_measure(list('CDEF'),'4/4','1/16')=='CDEF'
 assert _abc_beam_within_measure(list('CDEFGA'),'6/8','1/8')=='CDE FGA'

def test_slurred_canonical_warmup_events_remain_exact_while_beaming():
 notes=[we.Note(n,4,'sixteenth',slur=1) for n in 'CDEF']+[we.Note('',0,'half'),we.Note('',0,'quarter')]
 b=we.Built(notes,60,'Beam/slur invariant',[],[],{'window':[60,96]});events,_=we.to_events(notes);before=copy.deepcopy(events);before_notes=copy.deepcopy(b.notes)
 abc,diag=we.render(we.make_player('flute','C'),b,'C','major',title=b.title)
 assert b.notes==before_notes and events==before and read_abc(abc)==[60,62,64,65] and '(C/4D/4E/4F/4)' in abc
 assert all(e.duration=='sixteenth' and e.slur_group==1 for e in events[:4])
