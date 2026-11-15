"""Stage F documentary overtone pilot. No specialized user-facing solver.

Targets describe ideal harmonic relationships, not a verified response recipe.
The ordinary register preview reuses the existing key-changing octave engine.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import log2
from types import MappingProxyType
from music_coach_ami import sax_capabilities as cap, fingering_data as fd

MODEL = "yamaha-yas280"
SOURCES = MappingProxyType({
    "harmonics": "https://www.yamaha.com/en/musical_instrument_guide/saxophone/trivia/trivia008.html",
    "overblowing": "https://www.yamaha.com/en/musical_instrument_guide/saxophone/play/play002.html",
    "acoustics": "https://newt.phys.unsw.edu.au/jw/SaxTract.html",
    "model": "https://usa.yamaha.com/products/musical_instruments/winds/saxophones/yas-280/specs.html",
    "altissimo_candidates": "https://www.wfg.woodwind.org/sax/sax_alt_4.html",
})

@dataclass(frozen=True)
class OvertoneCandidate:
    model_id: str
    fundamental_record: str
    fingered_written_fundamental: int
    fingered_sounding_fundamental: int
    partial: int
    written_target: str
    written_midi: int
    sounding_target: str
    sounding_midi: int
    ideal_frequency_ratio: int
    source_ids: tuple[str, ...] = ("harmonics", "overblowing", "acoustics")
    teacher_reviewed: bool = False
    physically_tested: bool = False

    @property
    def ideal_cents_above_tempered_target(self):
        return 1200*log2(self.partial)-100*(self.written_midi-self.fingered_written_fundamental)

CANDIDATES = (
    OvertoneCandidate(MODEL,"D4",62,53,2,"D5",74,"F4",65,2),
    OvertoneCandidate(MODEL,"D4",62,53,3,"A5",81,"C5",72,3),
)

def validate(candidate):
    if any(type(getattr(candidate,k)) is not int for k in ("fingered_written_fundamental","fingered_sounding_fundamental","partial","written_midi","sounding_midi","ideal_frequency_ratio")):
        raise ValueError("Pitch/partial/ratio fields require integers, not coercion.")
    if candidate.teacher_reviewed is not False or candidate.physically_tested is not False:
        raise ValueError("No teacher or physical validation has occurred.")
    if candidate not in CANDIDATES:
        raise ValueError("Only the two documentary D4 fundamental candidates are registered.")
    cap.model_scope(candidate.model_id,"alto")
    fundamental=fd.record(candidate.fundamental_record)
    if (fundamental["written_midi"],fundamental["sounding_midi"]) != (candidate.fingered_written_fundamental,candidate.fingered_sounding_fundamental):
        raise ValueError("Fundamental must match its existing verified fingering record.")
    if type(candidate.partial) is not int or candidate.partial not in (2,3):
        raise ValueError("Unsupported partial.")
    target=fd.record(candidate.written_target)
    if candidate.written_midi != round(candidate.fingered_written_fundamental+12*log2(candidate.partial)) or candidate.ideal_frequency_ratio != candidate.partial:
        raise ValueError("Wrong ideal harmonic relationship.")
    if (target["written_midi"],target["sounding_midi"],target["sounding_name"]+str(target["sounding_octave"])) != (candidate.written_midi,candidate.sounding_midi,candidate.sounding_target):
        raise ValueError("Wrong written/sounding octave relationship.")
    lo,hi=cap.profile("alto").written_range
    if not lo<=candidate.fingered_written_fundamental<=candidate.written_midi<=hi:
        raise ValueError("Documentary normal-register targets must fit the existing range.")
    return candidate

def fundamental_reference(candidate):
    """Existing basic controls; never the ordinary target's fingering as an overtone recipe."""
    validate(candidate)
    return fd.record(candidate.fundamental_record)

def review_gate(candidate,review=None):
    validate(candidate)
    fundamental=fundamental_reference(candidate);source=fundamental["sources"][0]
    reference=cap.FingeringReference("d4-fundamental-reference-only",MODEL,"standard factory saxophone keywork",source["url"],source["locator"],"Fingering facts only; no source artwork reproduced")
    target=cap.StudyTarget("overtones","alto",MODEL,candidate.written_midi,candidate.fingered_written_fundamental,candidate.partial,reference,candidate.written_target[:-1],int(candidate.written_target[-1]))
    gate=cap.validation_requirements(target,review)
    return cap.ValidationGate(gate.missing+("overtone response on the identified specimen and setup",),False)

def specialized_exercise(candidate,review=None):
    """An explicit development gate. Metadata or Advanced level cannot enable it."""
    from music_coach_ami.warmup_engine import WarmupUnavailable
    gate=review_gate(candidate,review)
    raise WarmupUnavailable("Stage F specialized instruction is disabled: "+"; ".join(gate.missing))

def ordinary_register_preview(model_id,*,level,bpm=60):
    """One ordinary D4/D5 half-note bar. Octave thumb changes; NOT an overtone drill.

    Returns an uncommitted plan through the existing engine. No new route,
    exercise history, range window or physical performance claim is introduced.
    """
    if model_id!=MODEL:raise ValueError("Identify standard Yamaha YAS-280; no model substitution.")
    if type(bpm) is not int or not 36<=bpm<=100:raise ValueError("Choose an integer tempo from 36 to 100 BPM.")
    if level not in dict(cap.profile("alto").level_windows):raise ValueError("Choose an existing proficiency level.")
    from music_coach_ami.fingering_transitions import build
    spec={"single":True,"fingering":"D5","fingering_transition":{"pair":["D4","D5"],"pattern":"jump"},"family":"fingering","instrument":"alto","concert_key":"Eb","level":level,"register":"middle","direction":"ascending","rhythm":"half","bpm":bpm,"reps":1,"buster":False,"articulation":"","quality":"major","count":2}
    return build(spec)
