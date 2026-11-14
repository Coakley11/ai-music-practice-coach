"""Bounded source-backed finger-control facts; no inferred fingerings or diagrams."""
from pathlib import Path
import json
from music_coach_ami import sax_capabilities as cap, scale_pattern_harmony as sph

KEYS = (('L1','Left index'),('L2','Left middle'),('L3','Left ring'),
        ('R1','Right index'),('R2','Right middle'),('R3','Right ring'),('O','Octave thumb'))


def record(note):
    raw=next((r for r in json.loads(Path(__file__).with_name('fingering_records.json').read_text(encoding='utf-8')) if r['id']==note),None)
    if raw is None: raise ValueError('Unsupported written note; no fingering is inferred.')
    cap.model_scope(raw['model_id'],raw['instrument'])
    p=cap.profile(raw['instrument']);written=sph.midi_of(raw['written_name'],raw['written_octave'])
    sounding=written-p.written_minus_sounding
    name=sph.transpose_spelled(raw['written_name'],-p.written_minus_sounding)
    raw.update(written_midi=written,sounding_midi=sounding,sounding_name=name,
        sounding_octave=sph.octave_for(name,sounding),offset=p.written_minus_sounding)
    if set(raw['key_states'])!={k for k,_ in KEYS} or raw['teacher_reviewed']:
        raise ValueError('Invalid source-backed pilot record')
    return raw


def validate_record(value):
    expected=record(value['id'])
    if value!=expected: raise ValueError('Diagram data does not match the registered source facts')
    return expected


def changes(a,b):
    x,y=record(a),record(b)
    return [f"{label}: {'press' if y['key_states'][key] else 'release'}" for key,label in KEYS
            if x['key_states'][key]!=y['key_states'][key]]


def supported_notes():
    return tuple(r['id'] for r in json.loads(Path(__file__).with_name('fingering_records.json').read_text(encoding='utf-8')))
