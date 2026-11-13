"""Documentary capabilities and future-study gates; never expands generation.

Range/offset/level values are read from existing AMI engines. Published keywork
is not a reviewed fingering, a player's facility or permission to generate a study.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from types import MappingProxyType
from music_coach_ami import warmup_engine as we, scale_pattern_harmony as sph

SAX = ('soprano', 'alto', 'tenor', 'baritone')
SPECIALIZED = ('overtones', 'altissimo', 'alternate_fingerings', 'advanced_register')

@dataclass(frozen=True)
class SourceReference:
    id: str
    url: str
    title: str
    checked_on: str
    evidence: str
    status: str

SOURCES = MappingProxyType({r['id']: SourceReference(**r) for r in
    json.loads(Path(__file__).with_name('sax_capability_sources.json').read_text(encoding='utf-8'))})

@dataclass(frozen=True)
class ModelScope:
    id: str
    instrument: str
    maker: str
    model: str
    region: str
    revision: str
    source_ids: tuple[str, ...]
    hardware_claims: tuple[tuple[str, bool], ...]
    keyed_low: int | None = None
    keyed_high: int | None = None

    def hardware(self, feature: str) -> bool | None:
        """None means unknown; missing keys are never inferred absent/present."""
        return dict(self.hardware_claims).get(feature)

# Documentary snapshots only. Exact specimen/revision matching remains mandatory.
_REV = 'Published listing checked 2026-11-13; specimen revision unconfirmed'
MODELS = MappingProxyType({m.id: m for m in (
    ModelScope('yamaha-yss875ex', 'soprano', 'Yamaha', 'YSS-875EX', 'US', _REV,
        ('yamaha-yss',), (('front_f', True), ('high_f_sharp', True)), keyed_high=90),
    ModelScope('yamaha-yss875exhg', 'soprano', 'Yamaha', 'YSS-875EXHG', 'US', _REV,
        ('yamaha-yss',), (('front_f', True), ('high_f_sharp', True), ('high_g', True)), keyed_high=91),
    ModelScope('yamaha-yas26', 'alto', 'Yamaha', 'YAS-26', 'US', _REV,
        ('yamaha-yas26',), (('front_f', True),)),
    ModelScope('yamaha-yas280', 'alto', 'Yamaha', 'YAS-280', 'US', _REV,
        ('yamaha-yas280',), (('front_f', True), ('high_f_sharp', True)), keyed_high=90),
    ModelScope('selmer-supreme-alto', 'alto', 'Henri SELMER Paris', 'Supreme alto', 'International', _REV,
        ('selmer-supreme',), (('high_f_sharp', True),), keyed_low=58, keyed_high=90),
    ModelScope('yamaha-yts62', 'tenor', 'Yamaha', 'YTS-62', 'Japan', _REV,
        ('yamaha-yts62',), (('front_f', True), ('high_f_sharp', True)), keyed_high=90),
    ModelScope('yamaha-ybs62ii', 'baritone', 'Yamaha', 'YBS-62II', 'US archived model', _REV,
        ('yamaha-ybs62ii',), (('front_f', True), ('high_f_sharp', True), ('low_a', True)), keyed_low=57, keyed_high=90),
)})

@dataclass(frozen=True)
class SaxProfile:
    instrument: str
    notation: str
    written_range: tuple[int, int]
    written_minus_sounding: int
    sounding_range: tuple[int, int]
    level_windows: tuple[tuple[str, tuple[int, int]], ...]
    clef: str
    octave_convention: str = 'Scientific pitch: C4 = MIDI 60'
    optional_hardware: tuple[tuple[str, None], ...] = (
        ('front_f', None), ('high_f_sharp', None), ('high_g', None), ('low_a', None))


def profile(instrument: str) -> SaxProfile:
    if instrument not in SAX:
        raise ValueError('Choose soprano, alto, tenor or baritone; no assumed subtype.')
    p = we.make_player(instrument, 'C')
    return SaxProfile(instrument, p.notation, (p.play_low, p.play_high), p.offset,
        (p.play_low-p.offset, p.play_high-p.offset),
        tuple((level, p.window(level)) for level in we.LEVELS), p.clef)


def model_scope(model_id: str, instrument: str) -> ModelScope:
    """Read metadata, never activate it or change any exercise profile."""
    m = MODELS.get(model_id)
    if m is None or m.instrument != instrument:
        raise ValueError('Unknown or mismatched model; keep the common generation profile.')
    return m

@dataclass(frozen=True)
class FingeringReference:
    """Future source reference only: no fingering/key combinations are supplied."""
    variant_id: str
    model_id: str
    instrument_system: str
    source_url: str
    locator: str
    permission: str

@dataclass(frozen=True)
class StudyTarget:
    technique: str
    instrument: str
    model_id: str
    written_target: int
    fingered_fundamental: int | None = None
    harmonic_partial: int | None = None
    fingering: FingeringReference | None = None
    written_name: str = ''
    written_octave: int | None = None

@dataclass(frozen=True)
class ReviewEvidence:
    model_id: str = ''
    specimen_revision: str = ''
    instrument_system: str = ''
    setup: str = ''
    primary_reference: str = ''
    locator: str = ''
    permission: str = ''
    independent_reviewer: str = ''
    reviewed_on: str = ''
    prerequisites: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()
    independent_checks: tuple[str, ...] = ()

@dataclass(frozen=True)
class ValidationGate:
    missing: tuple[str, ...]
    generation_supported: bool = False


def validation_requirements(target: StudyTarget, review: ReviewEvidence | None = None) -> ValidationGate:
    """Assess completeness, not truth or authorization. No metadata enables an engine."""
    missing = []
    if target.technique not in SPECIALIZED: missing.append('recognized specialized technique')
    if target.instrument not in SAX: missing.append('verified saxophone subtype')
    try: m = model_scope(target.model_id, target.instrument)
    except ValueError: m = None; missing.append('matched documentary model scope')
    if type(target.written_target) is not int or not 0 <= target.written_target <= 127:
        missing.append('explicit valid written target and octave')
    try:
        if type(target.written_octave) is not int or sph.midi_of(target.written_name, target.written_octave) != target.written_target:
            missing.append('matching written spelling and octave')
    except (ValueError, TypeError, IndexError): missing.append('matching written spelling and octave')
    if target.technique == 'overtones':
        if type(target.fingered_fundamental) is not int or not 0 <= target.fingered_fundamental <= 127:
            missing.append('distinct fingered fundamental')
        if type(target.harmonic_partial) is not int or target.harmonic_partial < 2:
            missing.append('intended harmonic partial >= 2')
        if m is not None and type(target.fingered_fundamental) is int:
            lo, hi = profile(target.instrument).written_range
            if not (m.keyed_low if m.keyed_low is not None else lo) <= target.fingered_fundamental <= (m.keyed_high if m.keyed_high is not None else hi):
                missing.append('fundamental within documented keyed bounds')
    r = review or ReviewEvidence()
    for field in ('specimen_revision','instrument_system','setup','primary_reference','locator','permission','independent_reviewer'):
        if not getattr(r, field).strip(): missing.append(field)
    if r.model_id != target.model_id or not r.model_id: missing.append('review matched to model')
    if not r.primary_reference.startswith('https://'): missing.append('traceable primary source URL')
    try: date.fromisoformat(r.reviewed_on)
    except (ValueError, TypeError): missing.append('valid review date')
    if not r.prerequisites: missing.append('expert-reviewed prerequisites')
    for field in ('response','intonation','transition_context'):
        if field not in r.observations: missing.append(field+' observations')
    for field in ('written_sounding_octave','harmonic_relationship','notation','history_owner','browser_accessibility'):
        if field not in r.independent_checks: missing.append(field+' validation')
    f = target.fingering
    if target.technique in SPECIALIZED:
        if f is None: missing.append('reviewed fingering reference')
        elif (f.model_id != target.model_id or f.instrument_system != r.instrument_system or
              not f.variant_id or not f.source_url.startswith('https://') or not f.locator or not f.permission):
            missing.append('matched licensed fingering reference')
    # Even a complete submitted record is not expert validation or an implemented solver.
    missing.append('separately approved and independently verified specialized engine')
    return ValidationGate(tuple(missing))
