"""Source-backed Yamaha YTR-2330 valve/partial facts, separate from sax keys."""
import json
from pathlib import Path
from music_coach_ami import scale_pattern_harmony as sph

MODEL='yamaha-ytr2330'

def supported_notes():
    return tuple(r['id'] for r in _rows())

def _rows():
    return json.loads(Path(__file__).with_name('trumpet_fingering_records.json').read_text(encoding='utf-8'))

def record(note):
    r=next((v for v in _rows() if v['id']==note),None)
    if r is None:raise ValueError('Unsupported written trumpet note; no valve state is inferred.')
    from music_coach_ami.trumpet_technique import HARMONICS
    if r['model_id']!=MODEL or r['valve'] not in ('open','1','2') or r['partial'] not in (2,3,4):raise ValueError('Unverified model/partial')
    if HARMONICS[r['valve']][r['partial']]!=(r['written_name'],r['written_octave']):raise ValueError('Partial target differs from the source-backed record')
    if r['valve_states']!={str(i):r['valve']==str(i) for i in range(1,4)} or r['teacher_reviewed'] or r['physically_tested']:raise ValueError('Invalid source facts')
    written=sph.midi_of(r['written_name'],r['written_octave']);sounding=written-2
    name=sph.transpose_spelled(r['written_name'],-2)
    r.update(written_midi=written,sounding_midi=sounding,sounding_name=name,sounding_octave=sph.octave_for(name,sounding),offset=2)
    return r

def validate_record(value):
    expected=record(value['id'])
    if expected!=value:raise ValueError('Diagram data differs from registered source facts')
    return expected

def series(valve):
    return [record(v['id']) for v in _rows() if v['valve']==valve]
