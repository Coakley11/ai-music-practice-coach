"""Verified basic YCL-255 finger actions, with holes distinct from keys."""
import json
from pathlib import Path
from music_coach_ami import scale_pattern_harmony as sph
MODEL='yamaha-ycl255'
HOLES=(('T','Thumb hole'),('L1','Left index'),('L2','Left middle'),('L3','Left ring'),('R1','Right index'),('R2','Right middle'),('R3','Right ring'))
KEYS=(('Register','Register key'),('A','Throat A key'),('L_EB','Left little finger E/B'),('R_FC','Right little finger F/C'))
PAIRS=(('E3','B4'),('F3','C5'),('G3','D5'))
BREAK=('Bb4','B4')
def _rows():return json.loads(Path(__file__).with_name('clarinet_fingering_records.json').read_text(encoding='utf-8'))
def supported_notes():return tuple(r['id'] for r in _rows())
def record(note):
    r=next((r for r in _rows() if r['id']==note),None)
    if r is None:raise ValueError('Unsupported written clarinet note; no fingering is inferred')
    if r['model_id']!=MODEL or r['system']!='Standard Boehm, 17 keys, 6 rings' or set(r['holes'])!={k for k,_ in HOLES} or set(r['keys'])!={k for k,_ in KEYS}:raise ValueError('Invalid model or control schema')
    if any(type(v) is not bool for v in list(r['holes'].values())+list(r['keys'].values())) or r['auxiliary_controls_pressed'] or r['teacher_reviewed'] or r['physically_tested']:raise ValueError('Invalid verification/control facts')
    written=sph.midi_of(r['written_name'],r['written_octave']);sounding=written-2;name=sph.transpose_spelled(r['written_name'],-2)
    r.update(written_midi=written,sounding_midi=sounding,sounding_name=name,sounding_octave=sph.octave_for(name,sounding),offset=2)
    return r

def validate_record(value):
    r=record(value['id'])
    if value!=r:raise ValueError('Diagram differs from the registered source facts')
    return r

def changes(a,b):
    x,y=record(a),record(b);out=[]
    for k,label in HOLES:
        if x['holes'][k]!=y['holes'][k]:out.append(label+': '+('cover' if y['holes'][k] else 'open'))
    for k,label in KEYS:
        if x['keys'][k]!=y['keys'][k]:out.append(label+': '+('press' if y['keys'][k] else 'release'))
    return out

def groups(recipe,direction='ascending'):
    if recipe.get('kind')=='break':pairs=[BREAK]
    elif recipe.get('kind')=='twelfth':
        indices=recipe.get('pairs',[])
        if not indices or len(indices)!=len(set(indices)) or any(type(i) is not int or not 0<=i<3 for i in indices):raise ValueError('Choose one to three verified twelfth pairs')
        pairs=[PAIRS[i] for i in indices]
    else:raise ValueError('Only verified twelfth or register-break recipes are enabled')
    for a,b in pairs:
        expected=1 if recipe['kind']=='break' else 19
        if record(b)['written_midi']-record(a)['written_midi']!=expected:raise ValueError('Source interval does not match recipe')
    if direction=='descending':return [tuple(reversed(pair)) for pair in reversed(pairs)]
    if direction!='ascending':raise ValueError('Choose ascending or descending')
    return pairs
