"""Source-bounded YFL-222 C-foot finger actions, separate from linked pad states."""
import copy,json
from pathlib import Path
from music_coach_ami import scale_pattern_harmony as sph
MODEL='yamaha-yfl222-c-foot'
CONFIGURATION='Yamaha YFL-222 concert C flute; covered keys; offset G; C footjoint; no split-E mechanism'
KEYS=(('B_thumb','B-natural thumb'),('Bb_thumb','Bb thumb'),('L1','LH index (C)'),('L2','LH middle (A)'),('L3','LH ring (G)'),('G_sharp','LH G# pinky'),('R1','RH index (F)'),('R2','RH middle (E)'),('R3','RH ring (D)'),('Eb','RH Eb pinky'),('Bb_trill','Bb trill'),('D_trill','D trill'),('Eb_trill','D# trill'),('low_C_sharp','Low C# pinky'),('low_C','Low C pinky'))
PAIRS=(('E4','E5'),('F4','F5'),('G4','G5'))

def supported_notes():return tuple(r['id'] for r in _rows())
def _rows():return json.loads(Path(__file__).with_name('flute_fingering_records.json').read_text(encoding='utf-8'))
def record(note):
    r=next((r for r in _rows() if r['id']==note),None)
    if r is None:raise ValueError('That exact flute note/octave has no verified fingering in this pilot')
    if r['model_id']!=MODEL or r['configuration']!=CONFIGURATION or set(r['key_states'])!={k for k,_ in KEYS} or any(type(v) is not bool for v in r['key_states'].values()) or r['teacher_reviewed'] or r['physically_tested']:raise ValueError('Invalid model, keywork or verification state')
    m=sph.midi_of(r['written_name'],r['written_octave']);r.update(written_midi=m,sounding_midi=m,sounding_name=r['written_name'],sounding_octave=r['written_octave'],offset=0)
    return r

def validate_record(value):
    r=record(value['id'])
    if value!=r:raise ValueError('Displayed fingering differs from the registered source facts')
    return r

def changes(a,b):
    x,y=record(a),record(b)
    return [label+(': press' if y['key_states'][k] else ': release') for k,label in KEYS if x['key_states'][k]!=y['key_states'][k]]

def groups(recipe,direction='ascending'):
    indices=recipe.get('pairs')
    if recipe.get('kind')!='octave' or not isinstance(indices,list) or not indices or any(type(i) is not int or i not in range(3) for i in indices) or len(indices)!=len(set(indices)) or direction not in ('ascending','descending'):raise ValueError('Choose only the three verified octave pairs')
    result=[list(PAIRS[i]) for i in indices]
    if direction=='descending':result=[list(reversed(p)) for p in reversed(result)]
    return result
