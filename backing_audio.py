"""Backing track synthesis and groove inference (no Streamlit UI)."""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np

from chord_subdivisions import (
    chord_at_beat as _sub_chord_at_beat,
    chord_at_pulse as _sub_chord_at_pulse,
    has_push as _sub_has_push,
    hit_underlying_chord as _sub_hit_underlying_chord,
    is_hit_token as _sub_is_hit_token,
    is_subdivided_bar as _sub_is_subdivided_bar,
    next_chord_at_beat as _sub_next_chord_at_beat,
    next_chord_at_pulse as _sub_next_chord_at_pulse,
    parse_subdivisions as _sub_parse_subdivisions,
    primary_chord as _sub_primary_chord,
)
from music_theory import NOTE_TO_MIDI, is_no_chord_token, normalize_root, split_chord

try:
    from practice_studio import song_groove_seed
except ImportError:

    def song_groove_seed(title: str, artist: str = "") -> int:
        return 0

try:
    from songs.meter import meter_timing, normalize_time_signature
except ImportError:

    def normalize_time_signature(time_signature: str) -> str:
        return str(time_signature or "4/4").strip() or "4/4"

    def meter_timing(bpm: int, time_signature: str):
        ts = normalize_time_signature(time_signature)
        num = int(ts.split("/")[0]) if "/" in ts else 4
        bpm = max(1, int(bpm))
        if ts == "6/8":
            bar_sec = 2 * (60.0 / bpm)
            pulse_sec = bar_sec / 6
            return type("T", (), {"pulses_per_bar": 6, "pulse_sec": pulse_sec, "bar_sec": bar_sec})()
        bar_sec = num * (60.0 / bpm)
        return type("T", (), {"pulses_per_bar": num, "pulse_sec": bar_sec / num, "bar_sec": bar_sec})()


__all__ = [
    "_chord_head",
    "_chord_bass",
    "chord_notes",
    "bass_note",
    "infer_groove_style",
    "synthesize_chords_to_numpy",
    "pcm16_wav_bytes_from_float",
    "generate_backing_track",
    "backing_bytes_to_float",
    "wav_bytes_from_float",
]


def _chord_head(chord: str) -> str:
    """First usable chord token (strip bars, slash bass, light annotations)."""
    if not chord:
        return ""
    token = str(chord).strip()
    token = token.replace("|", " ").split()[0] if token else ""
    token = token.split("/")[0]
    return token.replace("(", "").replace(")", "")


def _chord_bass(chord):
    primary = _sub_primary_chord(chord) or str(chord).strip()
    parts = primary.split("/", 1)
    return parts[1] if len(parts) == 2 and parts[1] else parts[0]


def _midi_for_root_symbol(symbol, fallback=60):
    root = split_chord(symbol)[0]
    return NOTE_TO_MIDI.get(root, NOTE_TO_MIDI.get(normalize_root(root), fallback))


def chord_notes(chord):

    head = _chord_head(chord)

    root, suffix = split_chord(head)

    base = NOTE_TO_MIDI.get(root, 60)
    base = NOTE_TO_MIDI.get(normalize_root(root), base)

    low = suffix.lower()

    if "m7b5" in low:
        intervals = [0,3,6,10]

    elif "dim7" in low:
        intervals = [0,3,6,9]

    elif "dim" in low:
        intervals = [0,3,6]

    elif "maj9" in low:
        intervals = [0,4,7,11,14]

    elif "maj7" in low:
        intervals = [0,4,7,11]

    elif "m9" in low:
        intervals = [0,3,7,10,14]

    elif "m7" in low:
        intervals = [0,3,7,10]

    elif "m" in low and "maj" not in low:
        intervals = [0,3,7]

    elif "13" in low:
        intervals = [0,4,7,10,14,21]

    elif "add9" in low:
        intervals = [0,4,7,14]

    elif "9" in low:
        intervals = [0,4,7,10,14]

    elif "6" in low:
        intervals = [0,4,7,9]

    elif "sus" in low:
        intervals = [0,5,7,10] if "7" in low else [0,5,7]

    elif "7" in low:
        intervals = [0,4,7,10]

    else:
        intervals = [0,4,7]

    if "b9" in low:
        intervals.append(13)
    elif "#9" in low:
        intervals.append(15)
    if "#11" in low:
        intervals.append(18)
    if "b13" in low:
        intervals.append(20)

    return [base+i for i in intervals]


def bass_note(chord):
    return _midi_for_root_symbol(_chord_bass(chord), 48)

def infer_groove_style(song_data, selected_style="Auto"):
    if selected_style != "Auto":
        return selected_style

    def safe_text(x):
        if x is None:
            return ""
        if isinstance(x, (list, tuple)):
            return " ".join(str(i) for i in x)
        if isinstance(x, dict):
            return " ".join(str(v) for v in x.values())
        return str(x)

    song_data = song_data or {}
    ext = song_data.get("extensions") or {}
    if ext.get("default_groove"):
        return str(ext["default_groove"])
    genre_name = safe_text(song_data.get("genre", ""))
    artist = safe_text(song_data.get("artist", ""))
    composer = safe_text(song_data.get("composer", ""))
    titleish = " ".join([
        safe_text(genre_name),
        safe_text(artist),
        safe_text(composer),
        safe_text(song_data.get("title", "")),
    ]).lower()
    if "ballad" in titleish:
        return "Ballad"
    if "jobim" in titleish or "bossa" in titleish or "samba" in titleish:
        return "Bossa nova"
    if genre_name == "Jazz":
        return "Jazz swing"
    if genre_name in ["Funk", "Soul"]:
        return "Funk groove"
    if genre_name == "Rock":
        return "Rock groove"
    if genre_name == "Jewish":
        return "Jewish groove"
    return "Pop groove"


@lru_cache(maxsize=256)
def _freq(midi_num):
    """Hz for a MIDI pitch. Cached because the synth hits roughly the
    same handful of voicing pitches thousands of times per generation."""
    return 440.0 * (2.0 ** ((midi_num - 69) / 12.0))


@lru_cache(maxsize=64)
def _attack_ramp(length: int) -> np.ndarray:
    """Cached fade-in ramp; the synth calls _add_tone with the same
    attack length many times per bar."""
    if length <= 0:
        return np.zeros(0, dtype=np.float64)
    return np.linspace(0.0, 1.0, length)


@lru_cache(maxsize=64)
def _release_ramp(length: int) -> np.ndarray:
    """Cached fade-out ramp (paired with _attack_ramp above)."""
    if length <= 0:
        return np.zeros(0, dtype=np.float64)
    return np.linspace(1.0, 0.02, length)


def _add_tone(audio, sr, start_sec, dur_sec, midi_num, volume, wave_type="sine"):
    start = int(start_sec * sr)
    if start >= len(audio) or dur_sec <= 0:
        return
    n = max(1, int(dur_sec * sr))
    end = min(len(audio), start + n)
    n = end - start
    # Build the time axis with arange (cheaper than np.linspace's extra
    # division work for tight loops).
    inv_sr = 1.0 / sr
    base_freq = _freq(midi_num)
    two_pi = 2.0 * np.pi
    phase = two_pi * base_freq * inv_sr * np.arange(n, dtype=np.float64)
    if wave_type == "bass":
        sig = np.sin(phase)
        sig += 0.35 * np.sin(phase * 2.0)
    elif wave_type == "organ":
        # +12 semitones = doubled frequency
        sig = np.sin(phase)
        sig += 0.25 * np.sin(phase * 2.0)
    else:
        sig = np.sin(phase)
    attack = max(1, int(0.01 * sr))
    release = max(1, int(min(0.08, dur_sec * 0.35) * sr))
    # In-place envelope shaping uses pre-cached ramp arrays so we skip
    # the np.ones allocation and the np.linspace calls that the original
    # version did on every single tone.
    a = min(attack, n)
    r = min(release, n)
    out = sig
    if a > 0:
        out[:a] *= _attack_ramp(a)
    if r > 0:
        out[-r:] *= _release_ramp(r)
    audio[start:end] += out * volume


def _add_noise_hit(audio, sr, start_sec, dur_sec, volume, seed=0):
    start = int(start_sec * sr)
    if start >= len(audio):
        return
    n = max(1, int(dur_sec * sr))
    end = min(len(audio), start + n)
    n = end - start
    rng = np.random.default_rng(seed)
    sig = rng.normal(0, 1, n)
    env = np.linspace(1, 0.01, n)
    audio[start:end] += sig * env * volume


def _coerce_chord_events(chords_or_events):
    events = []
    for idx, item in enumerate(chords_or_events or []):
        if isinstance(item, dict):
            chord = item.get("chord", "")
            section = item.get("section", "Practice Loop")
            bar_in_section = int(item.get("bar_in_section", idx))
            section_bars = int(item.get("section_bars", len(chords_or_events) or 1))
        else:
            chord = item
            section = "Practice Loop"
            bar_in_section = idx
            section_bars = len(chords_or_events) or 1
        events.append({
            "chord": chord,
            "section": section,
            "bar_in_section": bar_in_section,
            "section_bars": max(1, section_bars),
        })
    return events


def _section_role(section_name):
    name = str(section_name or "").lower()
    if "chorus" in name and "pre" not in name:
        return "chorus"
    if "verse" in name or "main loop" in name:
        return "verse"
    if "pre" in name:
        return "pre"
    if "bridge" in name:
        return "bridge"
    if "intro" in name:
        return "intro"
    if "outro" in name or "ending" in name:
        return "outro"
    if "solo" in name:
        return "solo"
    return "neutral"


def _section_intensity(section_name, style):
    role = _section_role(section_name)
    base = {
        "intro": 0.68,
        "verse": 0.78,
        "pre": 0.95,
        "chorus": 1.18,
        "bridge": 1.02,
        "solo": 1.08,
        "outro": 0.82,
        "neutral": 0.92,
    }.get(role, 0.92)
    if style == "Ballad":
        base *= 0.78
    elif style in ["Rock groove", "Funk groove"] and role == "chorus":
        base *= 1.08
    return base


def _is_section_edge(event, next_event):
    return bool(next_event and next_event.get("section") != event.get("section"))


# ---------------------------------------------------------------------------
# Arrangement intelligence
#
# Up until now the synth treated every bar as standalone: ``role`` and
# ``intensity`` came from the section name and that was that. A real
# arrangement evolves *across* a song — the second chorus is bigger
# than the first, the bar after a bridge breakdown lifts back in,
# pre-choruses ramp into the drop, the outro fades out. The
# ``ArrangementContext`` is the small cache the synth builds once
# before the per-bar render loop so every per-bar decision (intensity
# multiplier, fill choice, anticipation, fade) can ask "where am I in
# the song?" rather than "what does my section name say?".
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArrangementContext:
    """Per-render arrangement memory.

    Attributes
    ----------
    chorus_index_for_event:
        For each event index, the 1-based chorus-pass number. ``0``
        for non-chorus bars. Lets the synth know "this is the second
        chorus" / "this is the final chorus".
    total_choruses:
        How many distinct chorus passes are in the rendered chord
        list. Used to identify the *final* chorus for a lift.
    section_phrase_pos:
        For each event, ``bar_in_section / max(1, section_bars - 1)``
        clamped to ``[0, 1]``. Drives phrase-level dynamic curves so
        the section gently builds toward its end.
    bridge_recovery:
        Set of event indices where the *previous* event's section had
        ``role == "bridge"`` and this bar does not. Used to drop a
        crash + lift on the breakdown-recovery downbeat.
    is_final_section_bar:
        True when this is the last bar of the song (used by outro
        fade and final-fill logic).
    is_song_last_bar:
        Convenience: integer index of the very last bar in the
        rendered chord list. Equal to ``len(chord_list) - 1``.
    final_chorus_first_bar:
        Integer index of the first bar of the final chorus, or
        ``None`` if there are no choruses. Lets the fill engine put a
        bigger transition fill into the final chorus.
    """

    chorus_index_for_event: tuple[int, ...] = field(default_factory=tuple)
    total_choruses: int = 0
    section_phrase_pos: tuple[float, ...] = field(default_factory=tuple)
    bridge_recovery: frozenset[int] = field(default_factory=frozenset)
    is_song_last_bar: int = 0
    final_chorus_first_bar: int | None = None

    def chorus_pass_at(self, idx: int) -> int:
        if 0 <= idx < len(self.chorus_index_for_event):
            return int(self.chorus_index_for_event[idx])
        return 0

    def is_final_chorus_event(self, idx: int) -> bool:
        return (
            self.total_choruses > 0
            and self.chorus_pass_at(idx) == self.total_choruses
        )

    def phrase_pos(self, idx: int) -> float:
        if 0 <= idx < len(self.section_phrase_pos):
            return float(self.section_phrase_pos[idx])
        return 0.0


def _build_arrangement_context(chord_list: list[dict]) -> ArrangementContext:
    """Pre-compute arrangement metadata for the rendered chord list."""
    if not chord_list:
        return ArrangementContext()

    # ------ Chorus pass numbering ------
    # Walk the events; every time we *enter* a new chorus section
    # (role == "chorus" and previous event was not in the same chorus
    # section) we increment the chorus counter. All bars inside that
    # section share the chorus index. Events that aren't chorus get
    # chorus_index = 0.
    chorus_index_for_event: list[int] = [0] * len(chord_list)
    chorus_pass = 0
    last_chorus_section: str | None = None
    final_chorus_first_bar: int | None = None
    for idx, event in enumerate(chord_list):
        section = str(event.get("section") or "")
        role = _section_role(section)
        if role == "chorus":
            if section != last_chorus_section:
                chorus_pass += 1
                last_chorus_section = section
            chorus_index_for_event[idx] = chorus_pass
        else:
            # Reset the "current chorus section" tracker so the next
            # chorus block (even one with the same name) counts as a
            # new pass. This is what makes "Chorus 1" → "Verse 2" →
            # "Chorus 1" still register as two distinct chorus passes.
            last_chorus_section = None
    total_choruses = chorus_pass
    if total_choruses > 0:
        for idx, pass_no in enumerate(chorus_index_for_event):
            if pass_no == total_choruses:
                final_chorus_first_bar = idx
                break

    # ------ Phrase position within section ------
    section_phrase_pos: list[float] = []
    for event in chord_list:
        bar_in_section = float(event.get("bar_in_section", 0) or 0)
        section_bars = max(1.0, float(event.get("section_bars", 1) or 1))
        denom = max(1.0, section_bars - 1.0)
        ratio = max(0.0, min(1.0, bar_in_section / denom))
        section_phrase_pos.append(ratio)

    # ------ Bridge recovery ------
    bridge_recovery: set[int] = set()
    for idx in range(1, len(chord_list)):
        prev_role = _section_role(chord_list[idx - 1].get("section") or "")
        cur_role = _section_role(chord_list[idx].get("section") or "")
        if prev_role == "bridge" and cur_role != "bridge":
            bridge_recovery.add(idx)

    return ArrangementContext(
        chorus_index_for_event=tuple(chorus_index_for_event),
        total_choruses=total_choruses,
        section_phrase_pos=tuple(section_phrase_pos),
        bridge_recovery=frozenset(bridge_recovery),
        is_song_last_bar=len(chord_list) - 1,
        final_chorus_first_bar=final_chorus_first_bar,
    )


def _arrangement_intensity_overlay(
    idx: int,
    role: str,
    arr_ctx: ArrangementContext,
) -> float:
    """Multiplier (~0.88..1.18) on top of base section intensity.

    Combines four "where am I in the arrangement?" signals:

    1. **Final chorus lift** — last chorus is +10% over earlier ones,
       so the climax actually feels like a climax.
    2. **Phrase position curve** — gentle build across the section
       (0.96 at bar 1 → 1.04 at last bar) so each section breathes.
       Slightly stronger curve for pre-choruses (0.92 → 1.06) which
       are *meant* to feel like a ramp into the drop.
    3. **Bridge recovery** — first bar after a bridge gets +8% so
       the breakdown→band-back feels intentional, not a continuation.
    4. **Repeated chorus growth** — every chorus pass after the first
       gains +3% (capped at +9%) so even non-final repeats feel
       slightly fuller than the first one.
    """
    mul = 1.0

    if role == "pre":
        # Stronger ramp on pre-choruses (they exist to lift).
        mul *= 0.92 + 0.14 * arr_ctx.phrase_pos(idx)
    else:
        # Subtle phrase-shape ramp for everything else: -4% at bar 1,
        # +4% at last bar of the section.
        mul *= 0.96 + 0.08 * arr_ctx.phrase_pos(idx)

    if role == "chorus":
        chorus_pass = arr_ctx.chorus_pass_at(idx)
        if chorus_pass > 1:
            growth = min(0.09, 0.03 * (chorus_pass - 1))
            mul *= 1.0 + growth
        if arr_ctx.is_final_chorus_event(idx):
            mul *= 1.10  # final chorus = climax

    if idx in arr_ctx.bridge_recovery:
        mul *= 1.08

    return mul


def _bass_motion_pitch(chord, next_chord, style, slot_index, slot_count):
    notes = chord_notes(chord)
    root = bass_note(chord) - 12
    chord_root = notes[0] - 24
    third = notes[1] - 24 if len(notes) > 1 else chord_root + 4
    fifth = notes[2] - 24 if len(notes) > 2 else chord_root + 7

    if next_chord and slot_index == slot_count - 1:
        target = bass_note(next_chord) - 12
        return target - 1 if target >= root else target + 1

    if style == "Jazz swing":
        line = [root, third, fifth, root + 12]
    elif style == "Bossa nova":
        line = [root, fifth, root, fifth]
    elif style == "Funk groove":
        line = [root, root + 12, fifth, root, third, fifth]
    elif style == "Rock groove":
        line = [root, root, fifth, root + 12]
    elif style == "Ballad":
        line = [root, fifth]
    else:
        line = [root, fifth, root + 12, fifth]
    return int(line[slot_index % len(line)])


def _voicing_for_comp(chord, level, style, beat_index=0):
    """Style-aware comping voicing.

    Voicing strategy by style (subject to ``level`` thinning):

    * Jazz swing  — rootless 3-7-9 / 7-3-5 shells (what a jazz pianist
      actually plays under the bass).
    * Bossa nova  — stacked-thirds upper structure (no doubled root,
      preserves João Gilberto-style chord clarity).
    * Funk groove — punchy upper structures (drop the root, push the
      9th / 13th up so the comp sits *on top of* the bass instead of
      colliding with it).
    * Ballad      — open, wider spacing in the lower octave so
      sustained chords don't cloud the vocal.
    * Pop/Rock    — block voicing (close-position triad/seventh)
      which is what the previous implementation produced. Kept as
      the default to avoid surprising existing arrangements.
    """
    notes = chord_notes(chord)
    if not notes:
        return []
    style_key = (style or "").lower()

    # Helper: rotate so that ``rotation`` becomes the bottom note
    # (mod len). Used for inversion variation across beats.
    def _rotate(seq, rotation):
        if not seq:
            return seq
        rotation = rotation % len(seq)
        rotated = list(seq[rotation:]) + [n + 12 for n in seq[:rotation]]
        return rotated

    if "jazz" in style_key and len(notes) >= 3:
        # Rootless shell: drop the root, lean on 3rd/7th.
        # ``chord_notes`` returns root, 3, 5, (7), so notes[1] is the
        # 3rd and notes[3] is the 7th when present.
        third = notes[1]
        seventh = notes[3] if len(notes) >= 4 else notes[2]
        ninth = (notes[1] + 14) - notes[1]  # placeholder, recomputed below
        ninth = third + 14  # 9th = root + 14 semitones, expressed off the 3rd
        thirteenth = (notes[2] if len(notes) >= 3 else third) + 9
        # Alternate between two classic shells to add motion across
        # beats: A-form (3-5-7-9) and B-form (7-9-3-5).
        if beat_index % 2 == 0:
            voicing = [third, seventh, ninth]
        else:
            voicing = [seventh, ninth, third + 12]
        if level == "Advanced":
            voicing.append(thirteenth)

    elif "bossa" in style_key and len(notes) >= 3:
        # Stacked thirds, no doubled root; rotate gently per beat for
        # the João Gilberto/Tom Jobim "thumb-and-fingers" feel.
        upper = [n + 12 for n in notes[1:4]] if len(notes) >= 4 else [n + 12 for n in notes[1:3]]
        if level == "Beginner":
            upper = upper[:2]
        voicing = _rotate(upper, beat_index)

    elif "funk" in style_key and len(notes) >= 3:
        # Drop root, push the 9th + 13th up. Keeps the comp in the
        # mid/upper register so it sits cleanly above a busy bass.
        upper = [notes[1], notes[2]]
        if len(notes) >= 4:
            upper.append(notes[3])
        ninth = notes[1] + 14
        thirteenth = notes[2] + 9
        if level == "Beginner":
            voicing = [n + 12 for n in upper[:2]]
        elif level == "Advanced":
            voicing = [n + 12 for n in upper] + [ninth + 12, thirteenth + 12]
        else:
            voicing = [n + 12 for n in upper] + [ninth + 12]

    elif "ballad" in style_key and len(notes) >= 3:
        # Wider open voicing so sustained chords have air.
        voicing = [notes[0], notes[2]]
        if len(notes) >= 4:
            voicing.append(notes[3] + 12)
        voicing.append(notes[1] + 12)
        if level == "Beginner":
            voicing = voicing[:3]

    else:
        # Pop / Rock / unrecognised: previous block voicing,
        # preserved verbatim so existing arrangements stay stable.
        if level == "Advanced" and len(notes) > 4:
            voicing = [notes[0], notes[2], notes[3], notes[4]]
        elif level == "Beginner":
            voicing = notes[:3]
        else:
            voicing = notes[:4]
        if beat_index % 2 and len(voicing) >= 3:
            voicing = voicing[1:] + voicing[:1]

    octave = 12 if style != "Ballad" else 0
    return [n + octave for n in voicing]


def _groove_time(
    bar_start,
    beat,
    beat_len,
    style,
    *,
    swing: float = 0.0,
    pocket: float = 0.0,
):
    """Place a hit at ``bar_start + beat * beat_len`` with style feel.

    ``pocket`` is a per-style "where the band sits" offset in beats:

    * Negative -> ahead-of-the-beat / pushed (rock, funk).
    * Zero     -> tight quantized (modern pop).
    * Positive -> laid-back / behind-the-beat (R&B, neo-soul, hip-hop).

    Pocket only nudges off-beats so the kick/downbeat anchor doesn't
    drift — keeps the groove glued to the metronome while everything
    *around* the kick breathes.
    """
    t = bar_start + beat * beat_len
    is_offbeat = bool(beat % 1)
    if swing and is_offbeat:
        t = bar_start + (beat + swing) * beat_len
    elif style == "Jazz swing" and is_offbeat:
        t = bar_start + (beat + 0.08) * beat_len
    elif style == "Funk groove" and is_offbeat:
        t = bar_start + (beat - 0.02) * beat_len
    if pocket and is_offbeat:
        t = t + pocket * beat_len
    return t


def _outro_fade_envelope(
    idx: int,
    total_bars: int,
    fade_bars: int,
) -> float:
    """Linear taper across the last ``fade_bars`` bars of the song.

    Returns a multiplier in ``[0.0, 1.0]``: ``1.0`` for any bar more
    than ``fade_bars`` from the end, then a smooth linear fade down
    to a soft floor (0.10) on the very last bar so the final downbeat
    still has presence.
    """
    if fade_bars <= 0 or total_bars <= 0:
        return 1.0
    bars_left = max(0, total_bars - 1 - idx)
    if bars_left >= fade_bars:
        return 1.0
    progress = 1.0 - (bars_left / float(fade_bars))  # 0.0..1.0
    return max(0.10, 1.0 - 0.90 * progress)


def _scale_pattern_beats(beats: list[float], *, from_pulses: int, to_pulses: int) -> list[float]:
    if from_pulses <= 0 or to_pulses <= 0 or from_pulses == to_pulses:
        return list(beats)
    factor = to_pulses / from_pulses
    return [round(b * factor, 4) for b in beats]


def _add_cymbal_swell(
    audio,
    sr,
    fill_start,
    pulse_sec,
    pulses_per_bar,
    intensity,
    *,
    seed_base: int,
    duration_pulses: float = 1.5,
):
    """Cymbal/white-noise crescendo into a section drop.

    Stacks short hi-hat-style noise hits at increasing volumes so the
    listener hears a "shhhhhhhh" rising into the next downbeat. Used
    for chorus drops (especially the final chorus) and for
    breakdown→band-back recoveries.
    """
    swell_start = max(0.0, fill_start)
    swell_dur = max(0.4, float(duration_pulses)) * pulse_sec
    n_hits = max(8, int(duration_pulses * 12))
    for i in range(n_hits):
        progress = i / max(1, n_hits - 1)
        # Quadratic ramp so the swell *crests* into the downbeat.
        vol = 0.005 + 0.045 * (progress ** 1.6) * intensity
        t = swell_start + progress * swell_dur
        _add_noise_hit(
            audio,
            sr,
            t,
            0.045,
            vol,
            seed=seed_base * 23 + i,
        )


def _add_section_transition_fill(
    audio,
    sr,
    bar_start,
    pulse_sec,
    pulses_per_bar,
    style,
    role,
    next_event,
    intensity,
    *,
    seed_base: int,
    next_intensity: float = 1.0,
    is_into_final_chorus: bool = False,
):
    """Drum fill and lift between sections.

    The fill complexity scales with how *big* the section we're going
    into is. A tom roll into the final chorus is a different beast
    from a soft brush-fill into a verse, so we ramp:

    * Number of fill hits scales with ``next_intensity``.
    * Cymbal swell is added for chorus drops (and is bigger for the
      final chorus or anthem-rock songs).
    * Bridge transitions still get the long organ tone.
    """
    fill_anchor = max(0.0, pulses_per_bar - 0.8)
    fill_start = bar_start + fill_anchor * pulse_sec
    next_role = _section_role(next_event.get("section")) if next_event else "neutral"

    # Number of fill hits scales with the *target* section intensity.
    base_hits = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    # Final chorus / chorus drops get a denser tom-style roll.
    drop_into_chorus = next_role == "chorus"
    if drop_into_chorus or is_into_final_chorus:
        base_hits = [0.0, 0.33, 0.66, 1.0, 1.33, 1.66, 2.0, 2.33, 2.66]
    fill_volume = 0.022 * intensity * max(0.6, min(1.4, next_intensity))
    for i, off in enumerate(base_hits):
        _add_noise_hit(
            audio,
            sr,
            fill_start + off * pulse_sec * 0.15,
            0.04,
            fill_volume,
            seed=seed_base * 17 + i,
        )

    # Cymbal swell into chorus drops. The swell is louder and longer
    # for the final chorus / anthem songs, giving the climax its
    # dramatic "lift".
    if drop_into_chorus:
        swell_intensity = intensity * (1.4 if is_into_final_chorus else 1.0)
        swell_start = bar_start + max(0.0, pulses_per_bar - 1.6) * pulse_sec
        _add_cymbal_swell(
            audio,
            sr,
            swell_start,
            pulse_sec,
            pulses_per_bar,
            swell_intensity,
            seed_base=seed_base,
            duration_pulses=1.8 if is_into_final_chorus else 1.2,
        )
        for t, freq in [(3.5, 200), (3.65, 260), (3.8, 330)]:
            pulse = min(float(pulses_per_bar) - 0.5, t)
            _add_tone(
                audio,
                sr,
                bar_start + pulse * pulse_sec,
                0.06,
                freq,
                0.04 * intensity * (1.20 if is_into_final_chorus else 1.0),
                "bass",
            )
    elif next_role == "bridge":
        _add_tone(
            audio,
            sr,
            bar_start + min(float(pulses_per_bar) - 0.6, 3.4) * pulse_sec,
            0.12,
            90,
            0.05 * intensity,
            "organ",
        )
    if role == "intro":
        _add_noise_hit(audio, sr, bar_start + 0.1 * pulse_sec, 0.08, 0.012 * intensity, seed=seed_base * 3)


def _add_breakdown_recovery_crash(
    audio,
    sr,
    bar_start,
    pulse_sec,
    intensity,
    *,
    seed_base: int,
):
    """Crash + sub-tone on the downbeat following a bridge breakdown.

    Real bands punctuate the "we're back!" moment with a cymbal crash
    and a deep low-end hit. This adds both on the very first
    downbeat after the bridge ends so the recovery actually lands.
    """
    # The crash itself: short, bright noise burst.
    _add_noise_hit(
        audio,
        sr,
        bar_start,
        0.18,
        0.060 * intensity,
        seed=seed_base * 41,
    )
    # Sub-tone underneath the crash.
    _add_tone(audio, sr, bar_start, 0.15, 36, 0.085 * intensity, "bass")


def _comp_wave_for_style(style: str, role: str) -> str:
    if style == "Ballad":
        return "organ"
    if style == "Rock groove" and role == "chorus":
        return "sine"
    return "organ"


def _song_backing_profile(
    song_title: str,
    song_artist: str,
    style: str,
    *,
    bpm: int = 100,
) -> dict[str, Any]:
    """Song-aware groove character (energy, swing, anthem, soul-pop, etc.)."""
    title = f"{song_title} {song_artist}".lower()
    profile: dict[str, Any] = {
        "swing": 0.0,
        "humanize_ms": 0.012,
        "ghost_snare": False,
        "cross_stick": False,
        "ride_jazz": False,
        "pop_soul": False,
        "anthem_rock": False,
        "latin_relaxed": False,
        "kick_push": 1.0,
        "hat_soft": 1.0,
        "comp_stab": False,
        "riff_driven": False,
        "groove_based": False,
        "acoustic_unplugged": False,
        "vocal_ballad": False,
        "broadway_gospel": False,
        "disney_cinematic": False,
        "piano_centric": False,
        "jazz_ballad": False,
        # ---- Arrangement-level character (new) ----
        # ``pocket_offset`` is in *beats* and applied to off-beats by
        # ``_groove_time``. Negative = pushed/ahead, positive =
        # laid-back. Tight modern pop sits at 0.
        "pocket_offset": 0.0,
        # ``hat_open_ands`` = play an *open* hi-hat (longer noise
        # tail) on the listed off-beat positions. Funk/disco/pop
        # idioms put it on the "and of 4"; rock uses it sparser.
        "hat_open_ands": [],
        # ``outro_fade_bars`` lets a song request a programmed fade
        # on the very last N bars of the rendered chord list. When
        # 0 (default) the synth ends cold on the last downbeat,
        # which is the previous behaviour.
        "outro_fade_bars": 0,
    }
    if style == "Jazz swing":
        profile["swing"] = 0.11
        profile["ride_jazz"] = True
        profile["humanize_ms"] = 0.018
        # Jazz sits squarely in the pocket — drummers ride a hair
        # behind to swing the eighth-notes, but kick + bass stay
        # right on the beat. Net: tiny laid-back nudge.
        profile["pocket_offset"] = 0.012
    elif style == "Bossa nova":
        profile["cross_stick"] = True
        profile["latin_relaxed"] = True
        profile["swing"] = 0.04
        profile["hat_soft"] = 0.72
        profile["humanize_ms"] = 0.015
        profile["pocket_offset"] = 0.018
    elif style == "Funk groove":
        profile["ghost_snare"] = True
        profile["comp_stab"] = True
        profile["kick_push"] = 1.12
        # Funk pushes the off-beats slightly ahead — that's the
        # "in the pocket but on top" feel. Open hat on "and of 4"
        # is the genre signature.
        profile["pocket_offset"] = -0.015
        profile["hat_open_ands"] = [3.5]
    elif style == "Rock groove":
        profile["kick_push"] = 1.2
        profile["hat_soft"] = 0.9
        profile["pocket_offset"] = -0.008
    elif style == "Ballad":
        profile["hat_soft"] = 0.55
        profile["humanize_ms"] = 0.008
        # Ballads breathe back of the beat — sets up the romantic feel.
        profile["pocket_offset"] = 0.020
    elif style in ("Jewish groove", "Klezmer groove"):
        profile["swing"] = 0.06
        profile["comp_stab"] = True
        profile["humanize_ms"] = 0.014
        profile["hat_soft"] = 0.85
        profile["pocket_offset"] = 0.010
    elif style == "Jewish hora":
        profile["swing"] = 0.04
        profile["comp_stab"] = True
        profile["humanize_ms"] = 0.012
        profile["hat_soft"] = 0.9
        profile["pocket_offset"] = 0.006
    elif style == "Jewish ballad":
        profile["hat_soft"] = 0.5
        profile["humanize_ms"] = 0.010
        profile["pocket_offset"] = 0.018
    elif style in ("Pop groove", "Pop"):
        # Modern pop = tight, quantized, on the grid.
        profile["pocket_offset"] = 0.0
        profile["hat_open_ands"] = [3.5]

    if any(k in title for k in ("waiting on the world", "say", "john mayer")):
        profile["pop_soul"] = True
        profile["swing"] = max(profile["swing"], 0.03)
        profile["hat_soft"] = 0.82
        profile["humanize_ms"] = 0.014
        profile["pocket_offset"] = max(profile["pocket_offset"], 0.012)
    if "champions" in title or "queen" in title:
        profile["anthem_rock"] = True
        profile["kick_push"] = 1.28
    if "come together" in title:
        profile["riff_driven"] = True
        profile["comp_stab"] = True
        profile["ghost_snare"] = True
        profile["kick_push"] = 1.18
        profile["hat_soft"] = 0.88
        profile["humanize_ms"] = 0.014
        profile["pocket_offset"] = 0.016
        profile["outro_fade_bars"] = 4
    if "autumn leaves" in title:
        profile["cross_stick"] = True
        profile["hat_soft"] = min(profile["hat_soft"], 0.48)
        profile["humanize_ms"] = min(profile["humanize_ms"], 0.009)
        profile["pocket_offset"] = max(profile["pocket_offset"], 0.022)
        if style == "Jazz swing":
            profile["ride_jazz"] = True
            profile["swing"] = max(profile["swing"], 0.07)
    if "all the things" in title or "things you are" in title:
        profile["jazz_ballad"] = True
        profile["cross_stick"] = True
        profile["hat_soft"] = min(profile["hat_soft"], 0.48)
        profile["humanize_ms"] = max(profile["humanize_ms"], 0.009)
        profile["pocket_offset"] = max(profile["pocket_offset"], 0.022)
        if style == "Jazz swing":
            profile["ride_jazz"] = True
            profile["swing"] = max(profile["swing"], 0.10)
        elif style == "Bossa nova":
            profile["latin_relaxed"] = True
            profile["swing"] = max(profile["swing"], 0.04)
    if any(
        k in title
        for k in ("attention", "treasure", "uptown funk", "get lucky", "charlie puth")
    ):
        profile["groove_based"] = True
        profile["comp_stab"] = True
        profile["ghost_snare"] = True
        profile["kick_push"] = max(profile["kick_push"], 1.14)
        profile["hat_soft"] = min(profile["hat_soft"], 0.92)
        profile["pocket_offset"] = min(profile["pocket_offset"], -0.012)
        profile["humanize_ms"] = max(profile["humanize_ms"], 0.011)
    if "blue bossa" in title or "bossa" in title:
        profile["latin_relaxed"] = True
        profile["cross_stick"] = True
    if "take on me" in title and ("unplugged" in title or "mtv" in title):
        profile["acoustic_unplugged"] = True
        profile["hat_soft"] = min(profile["hat_soft"], 0.38)
        profile["humanize_ms"] = max(profile["humanize_ms"], 0.010)
        profile["pocket_offset"] = max(profile["pocket_offset"], 0.018)
        profile["outro_fade_bars"] = 8
    if "want it that way" in title or "backstreet" in title:
        profile["vocal_ballad"] = True
        profile["hat_soft"] = min(profile["hat_soft"], 0.52)
        profile["humanize_ms"] = max(profile["humanize_ms"], 0.009)
        profile["pocket_offset"] = max(profile["pocket_offset"], 0.014)
    if any(
        k in title
        for k in ("won't say", "wont say", "in love", "hercules", "muses", "megara")
    ):
        profile["broadway_gospel"] = True
        profile["vocal_ballad"] = True
        profile["cross_stick"] = True
        profile["hat_soft"] = min(profile["hat_soft"], 0.44)
        profile["humanize_ms"] = max(profile["humanize_ms"], 0.011)
        profile["pocket_offset"] = max(profile["pocket_offset"], 0.016)
    if any(
        k in title
        for k in (
            "how far",
            "moana",
            "let it go",
            "part of your world",
            "reflection",
        )
    ):
        profile["disney_cinematic"] = True
        profile["vocal_ballad"] = True
        profile["cross_stick"] = True
        profile["hat_soft"] = min(profile["hat_soft"], 0.40)
        profile["humanize_ms"] = max(profile["humanize_ms"], 0.010)
        profile["pocket_offset"] = max(profile["pocket_offset"], 0.020)
        profile["outro_fade_bars"] = 5
    if "vienna" in title or (
        "joel" in title and any(k in title for k in ("piano man", "new york state"))
    ):
        profile["piano_centric"] = True
        profile["vocal_ballad"] = True
        profile["cross_stick"] = True
        profile["hat_soft"] = min(profile["hat_soft"], 0.46)
        profile["humanize_ms"] = max(profile["humanize_ms"], 0.009)
        profile["pocket_offset"] = max(profile["pocket_offset"], 0.022)
        profile["outro_fade_bars"] = 4
    if "take the a train" in title or "ellington" in title:
        profile["ride_jazz"] = True
        profile["swing"] = 0.12
    if bpm >= 120 and profile["anthem_rock"]:
        profile["kick_push"] *= 1.05
    return profile


def _humanize_time(
    t_sec: float,
    *,
    seed: int,
    amount: float,
    beat_len: float,
) -> float:
    if amount <= 0:
        return t_sec
    rng = np.random.default_rng(seed)
    jitter = float(rng.uniform(-amount, amount)) * beat_len
    return max(0.0, t_sec + jitter)


def _humanize_volume(base: float, seed: int) -> float:
    rng = np.random.default_rng(seed % 999983)
    return base * float(rng.uniform(0.88, 1.12))


def _style_patterns(style, profile: dict | None = None, *, time_signature: str = "4/4"):
    profile = profile or {}
    timing = meter_timing(100, time_signature)
    pulses = timing.pulses_per_bar
    base_pulses = 4

    def _fit(pattern: dict[str, Any]) -> dict[str, Any]:
        out = dict(pattern)
        for key in (
            "bass_beats",
            "comp_beats",
            "hat_beats",
            "snare_beats",
            "kick_beats",
            "ghost_snare",
            "cross_stick",
        ):
            if key in out:
                out[key] = _scale_pattern_beats(out[key], from_pulses=base_pulses, to_pulses=pulses)
        return out

    if time_signature == "6/8" and style in ("Jewish groove", "Jewish hora"):
        return {
            "bass_beats": [0, 3],
            "comp_beats": [0, 1.5, 3, 4.5],
            "hat_beats": [0, 1, 2, 3, 4, 5],
            "snare_beats": [2, 5],
            "kick_beats": [0, 3],
            "comp_dur": 0.34,
        }
    if time_signature == "6/8" and style == "Ballad":
        return {
            "bass_beats": [0, 3],
            "comp_beats": [0, 2, 3, 5],
            "hat_beats": [0, 1, 2, 3, 4, 5],
            "snare_beats": [3],
            "kick_beats": [0],
            "comp_dur": 0.55,
        }
    if time_signature == "6/8":
        return {
            "bass_beats": [0, 3],
            "comp_beats": [0, 1.5, 3, 4.5],
            "hat_beats": [0, 1, 2, 3, 4, 5],
            "snare_beats": [3],
            "kick_beats": [0, 3],
            "comp_dur": 0.38,
        }
    if time_signature == "12/8":
        return {
            "bass_beats": [0, 3, 6, 9],
            "comp_beats": [0, 2, 3, 5, 6, 8, 9, 11],
            "hat_beats": list(range(12)),
            "snare_beats": [3, 9],
            "kick_beats": [0, 6],
            "comp_dur": 0.34,
        }

    if style == "Jazz swing":
        hat = [0, 1.5, 2, 3.5] if profile.get("ride_jazz") else [0, 1.65, 2, 3.65]
        return _fit({
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [1.0, 2.5, 3.5],
            "hat_beats": hat,
            "snare_beats": [1.0, 2.0, 3.0],
            "kick_beats": [0, 2],
            "ghost_snare": [1.5, 2.5],
            "comp_dur": 0.42,
        })
    if style == "Bossa nova":
        return _fit({
            "bass_beats": [0, 1.5, 2, 3.5],
            "comp_beats": [0.0, 1.25, 2.5, 3.25],
            "hat_beats": [0, 0.5, 1.5, 2, 2.5, 3.5],
            "snare_beats": [1.5, 3.5],
            "kick_beats": [0, 2],
            "cross_stick": [1.0, 3.0],
            "comp_dur": 0.30,
        })
    if style == "Funk groove":
        return _fit({
            "bass_beats": [0, 0.75, 1.5, 2, 2.75, 3.5],
            "comp_beats": [0.5, 1.75, 2.5, 3.25],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "ghost_snare": [0.5, 1.5, 2.5, 3.5],
            "kick_beats": [0, 1.5, 2.75],
            "comp_dur": 0.20,
        })
    if style == "Rock groove":
        return _fit({
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [0, 1, 2, 3],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 1.5, 2, 3.5],
            "ghost_snare": [2.5],
            "comp_dur": 0.48,
        })
    if style == "Ballad":
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5, 3.5],
            "hat_beats": [0, 1, 2, 3],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "comp_dur": 0.95,
        })
    if style == "Jewish ballad":
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "comp_dur": 1.05,
        })
    if style in ("Jewish groove", "Klezmer groove"):
        return _fit({
            "bass_beats": [0, 1.5, 2, 3],
            "comp_beats": [0, 0.75, 1.5, 2.25, 3],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 2.5, 3.0],
            "kick_beats": [0, 2],
            "comp_dur": 0.32,
        })
    if profile.get("pop_soul"):
        return _fit({
            "bass_beats": [0, 1.5, 2.5, 3.5],
            "comp_beats": [0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2.5],
            "comp_dur": 0.40,
        })
    if profile.get("riff_driven"):
        return _fit({
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [0, 2],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "ghost_snare": [1.5, 3.5],
            "comp_dur": 0.26,
        })
    if profile.get("groove_based"):
        return _fit({
            "bass_beats": [0, 0.75, 1.5, 2, 2.75, 3.5],
            "comp_beats": [0.5, 1.25, 2.5, 3.25],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "ghost_snare": [0.5, 1.5, 2.5, 3.5],
            "kick_beats": [0, 1.5, 2.75],
            "comp_dur": 0.18,
        })
    if profile.get("acoustic_unplugged"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "cross_stick": [1.0],
            "comp_dur": 0.78,
        })
    if profile.get("vocal_ballad"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 3.5],
            "hat_beats": [0, 1, 2, 3],
            "snare_beats": [3.0],
            "kick_beats": [0, 2.5],
            "comp_dur": 0.62,
        })
    if profile.get("broadway_gospel"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "cross_stick": [1.0],
            "comp_dur": 0.52,
        })
    if profile.get("disney_cinematic"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5],
            "hat_beats": [0, 2],
            "snare_beats": [],
            "kick_beats": [0],
            "cross_stick": [2.0],
            "comp_dur": 0.88,
        })
    if profile.get("piano_centric"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "cross_stick": [1.0],
            "comp_dur": 0.82,
        })
    return _fit({
        "bass_beats": [0, 2],
        "comp_beats": [0, 1.5, 2.5, 3.5],
        "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
        "snare_beats": [1.0, 3.0],
        "kick_beats": [0, 2.5],
        "comp_dur": 0.36,
    })


def synthesize_chords_to_numpy(
    chords,
    bpm=100,
    loops=1,
    sr=44100,
    *,
    style="Pop groove",
    level="Intermediate",
    song_title: str = "",
    song_artist: str = "",
    time_signature: str = "4/4",
):

    timing = meter_timing(bpm, time_signature)
    pulse = timing.pulse_sec
    bar = timing.bar_sec
    pulses_per_bar = timing.pulses_per_bar
    event_cycle = _coerce_chord_events(chords)
    cycle_len = max(1, len(event_cycle))
    chord_list = event_cycle * max(1, int(loops))
    audio = np.zeros(int(sr * bar * len(chord_list)) + sr)
    song_profile = _song_backing_profile(song_title, song_artist, style, bpm=bpm)
    patterns = _style_patterns(style, song_profile, time_signature=timing.time_signature)
    groove_seed = song_groove_seed(song_title, song_artist) if song_title else 0
    swing_amt = float(song_profile.get("swing", 0.0))
    humanize = float(song_profile.get("humanize_ms", 0.012))
    kick_mul = float(song_profile.get("kick_push", 1.0))
    hat_mul = float(song_profile.get("hat_soft", 1.0))
    pocket_offset = float(song_profile.get("pocket_offset", 0.0))
    hat_open_ands = list(song_profile.get("hat_open_ands", []))
    outro_fade_bars = int(song_profile.get("outro_fade_bars", 0) or 0)

    # Pre-compute arrangement memory (chorus passes, phrase positions,
    # bridge-recovery bars) so per-bar decisions know "where am I in
    # the song?" rather than relying on section name alone.
    arr_ctx = _build_arrangement_context(chord_list)
    total_song_bars = len(chord_list)

    for idx, event in enumerate(chord_list):

        chord = event["chord"]
        next_event = chord_list[idx + 1] if idx + 1 < len(chord_list) else None
        next_chord = next_event["chord"] if next_event else None
        bar_start = idx * bar
        section_name = event.get("section", "Practice Loop")
        base_intensity = _section_intensity(section_name, style)
        role = _section_role(section_name)
        # Arrangement-aware overlay: pre-chorus ramp, final chorus
        # lift, phrase-position curve, bridge recovery.
        arrangement_mul = _arrangement_intensity_overlay(idx, role, arr_ctx)
        # Outro fade: only the last ``outro_fade_bars`` taper down.
        fade_mul = _outro_fade_envelope(idx, total_song_bars, outro_fade_bars)
        intensity = base_intensity * arrangement_mul * fade_mul
        if song_profile.get("groove_based") and role == "bridge":
            intensity *= 0.82
        if song_profile.get("vocal_ballad") and role == "verse":
            intensity *= 0.88
        if song_profile.get("vocal_ballad") and role in ("pre", "bridge"):
            intensity *= 1.05
        if song_profile.get("broadway_gospel") and "ensemble" in str(section_name).lower():
            intensity *= 1.12
        if song_profile.get("disney_cinematic") and role == "pre":
            intensity *= 1.06
        if song_profile.get("disney_cinematic") and (
            "final" in str(section_name).lower()
            or "ending" in str(section_name).lower()
            or "key change" in str(section_name).lower()
        ):
            intensity *= 1.14
        if song_profile.get("piano_centric") and role == "verse":
            intensity *= 0.86
        if song_profile.get("piano_centric") and (
            "final" in str(section_name).lower() or role == "chorus"
        ):
            intensity *= 1.08
        section_edge = _is_section_edge(event, next_event)
        is_breakdown_recovery = idx in arr_ctx.bridge_recovery
        is_final_chorus_bar = arr_ctx.is_final_chorus_event(idx)
        # Loop pass index — used to seed humanization so loop 2 of a
        # repeated section is *slightly* different from loop 1
        # (different micro-timing + velocity jitter). Keeps the take
        # from sounding like a copy-paste while staying deterministic
        # for a given (song, settings) input.
        loop_pass = idx // cycle_len
        loop_seed = loop_pass * 9173 + groove_seed * 31
        # For subdivided bars, ``chord`` is e.g. ``"Fmaj7|Am7|C/D"`` (equal
        # subdivisions) or ``"C:2|G:2"`` / ``"C:3.5|D:0.5p"`` (weighted /
        # pushed). The per-pulse chord lookup goes through
        # ``chord_at_beat`` so weighted durations and push markers are
        # honoured exactly - ``chord_notes(_sub_primary_chord(chord))``
        # only seeds the head chord for any non-pulse-aware fallback uses.
        bar_is_subdivided = _sub_is_subdivided_bar(chord)
        # ``N.C.`` (no chord / tacet) bars: harmony instruments lay
        # out so the breakdown stays stark. Drums/percussion still
        # carry the groove via the kick/snare/hat blocks below.
        bar_is_no_chord = (
            False if bar_is_subdivided else is_no_chord_token(chord)
        )
        # ``Bm.hit`` rhythmic-hit / stop-time bar: the band stings
        # the chord on beat 1, then the rest of the bar lays out so
        # the gap reads as a band-stab rather than a tame bar of
        # comping. Solo bars also get one snare crack on beat 1.
        bar_is_hit = (
            False if bar_is_subdivided else _sub_is_hit_token(chord)
        )
        # Bridge dropout: when the bridge starts on a tacet bar we
        # pull the kit back even further than a plain N.C. (no hat,
        # no full snare — just kick + cross-stick) so the breakdown
        # has real space. Re-engages automatically on the next bar
        # that has chords.
        bar_is_bridge_dropout = bar_is_no_chord and role == "bridge"
        # Resolve the *sounding* chord for hit bars: ``"Bm.hit"`` ->
        # ``"Bm"`` so chord_notes/voicing/bass calls all agree.
        sounding_chord = (
            _sub_hit_underlying_chord(chord) if bar_is_hit else chord
        )
        notes = chord_notes(
            _sub_primary_chord(chord) if bar_is_subdivided else sounding_chord
        )
        bass_hits = patterns["bass_beats"]
        if groove_seed % 3 == 0 and role == "verse":
            bass_hits = bass_hits[: max(2, len(bass_hits) - 1)]
        comp_wave = _comp_wave_for_style(style, role)

        def _pulse_chord(b_pos: float) -> str:
            if bar_is_hit:
                return sounding_chord
            if not bar_is_subdivided:
                return chord
            return _sub_chord_at_beat(chord, b_pos, beats_per_bar=pulses_per_bar)

        def _pulse_next_chord(b_pos: float) -> str | None:
            if not bar_is_subdivided:
                return next_chord
            return _sub_next_chord_at_beat(
                chord,
                b_pos,
                beats_per_bar=pulses_per_bar,
                fallback_next_bar_chord=next_chord,
            )

        # ----- Bass line ----------------------------------------------
        # Hit bars play exactly one short, accented attack on beat 1
        # (the "stab"); the rest of the bar lays out so the gap reads
        # as a stop-time break.
        if bar_is_hit and not bar_is_no_chord:
            stab_pitch = _bass_motion_pitch(
                sounding_chord, next_chord, style, 0, max(1, len(bass_hits))
            )
            t_stab = _humanize_time(
                bar_start,
                seed=idx * 41 + groove_seed + loop_seed,
                amount=humanize * 0.5,
                beat_len=pulse,
            )
            _add_tone(
                audio,
                sr,
                t_stab,
                pulse * 0.40,
                stab_pitch,
                _humanize_volume(0.16 * intensity, idx * 41 + loop_seed),
                "bass",
            )
        else:
            for n, b in enumerate(bass_hits):
                if bar_is_no_chord:
                    break  # tacet — bass lays out for the whole bar
                pulse_chord = _pulse_chord(b)
                pulse_next = _pulse_next_chord(b)
                if is_no_chord_token(pulse_chord):
                    continue  # bar contains an N.C. sub-segment
                bass_pitch = _bass_motion_pitch(pulse_chord, pulse_next, style, n, len(bass_hits))
                bass_dur = pulse * (0.72 if style in ["Ballad", "Jazz swing"] else 0.50)
                if style == "Funk groove":
                    bass_dur = pulse * 0.32
                elif song_profile.get("pop_soul"):
                    bass_dur = pulse * 0.55
                elif song_profile.get("riff_driven"):
                    bass_dur = pulse * 0.42
                elif song_profile.get("groove_based"):
                    bass_dur = pulse * 0.36
                t_hit = _humanize_time(
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    seed=idx * 41 + n + groove_seed + loop_seed,
                    amount=humanize,
                    beat_len=pulse,
                )
                _add_tone(
                    audio,
                    sr,
                    t_hit,
                    bass_dur,
                    bass_pitch,
                    _humanize_volume(
                        (
                            0.16
                            if song_profile.get("riff_driven")
                            else 0.15
                            if song_profile.get("groove_based")
                            else 0.11
                        )
                        * intensity,
                        idx * 41 + n + loop_seed,
                    ),
                    "bass",
                )

        # ----- Chord comping -------------------------------------------
        if bar_is_hit and not bar_is_no_chord:
            # Single chord stab on beat 1, brighter and shorter than
            # a normal comping hit — the punctuation that makes a
            # hit bar sound like a band stop.
            stab_voicing = _voicing_for_comp(sounding_chord, level, style, 0)
            stab_dur = pulse * 0.32
            stab_vol = 0.034 * intensity
            t_stab = _humanize_time(
                bar_start,
                seed=idx * 53 + loop_seed,
                amount=humanize * 0.4,
                beat_len=pulse,
            )
            for note in stab_voicing:
                _add_tone(
                    audio,
                    sr,
                    t_stab,
                    stab_dur,
                    note,
                    _humanize_volume(stab_vol, idx + note + loop_seed),
                    comp_wave,
                )
        else:
            for comp_idx, b in enumerate(patterns["comp_beats"]):
                if bar_is_no_chord:
                    break  # tacet — chord comping lays out for the whole bar
                if is_no_chord_token(_pulse_chord(b)):
                    continue  # bar contains an N.C. sub-segment
                if role == "verse" and comp_idx % 3 == 2 and not song_profile.get("anthem_rock"):
                    continue
                if role == "intro" and comp_idx > 1:
                    continue
                dur = pulse * patterns.get("comp_dur", 0.45)
                if role == "chorus":
                    dur *= 1.18 if song_profile.get("anthem_rock") else 1.15
                elif role == "bridge":
                    dur *= 0.95
                elif song_profile.get("latin_relaxed"):
                    dur *= 0.88
                voicing = _voicing_for_comp(_pulse_chord(b), level, style, comp_idx)
                comp_vol = 0.022 * intensity
                if role == "verse":
                    comp_vol *= 0.72
                elif role == "chorus":
                    comp_vol *= 1.14 if song_profile.get("anthem_rock") else 1.12
                if song_profile.get("riff_driven"):
                    head = _sub_primary_chord(_pulse_chord(b)).split("/")[0]
                    if head.startswith("Dm"):
                        comp_vol *= 0.28
                    elif is_no_chord_token(_pulse_chord(b)):
                        comp_vol = 0.0
                    else:
                        comp_vol *= 0.65
                if song_profile.get("groove_based"):
                    comp_vol *= 0.52
                    dur *= 0.62
                if song_profile.get("acoustic_unplugged"):
                    comp_vol *= 0.68 if role == "verse" else 0.88 if role == "chorus" else 0.78
                    dur *= 1.05 if role == "chorus" else 0.92
                if song_profile.get("vocal_ballad"):
                    comp_vol *= 0.55 if role == "verse" else 0.72
                    if role == "chorus":
                        comp_vol *= 1.08
                if song_profile.get("broadway_gospel"):
                    comp_vol *= 0.50 if role == "verse" else 0.65
                    if role == "pre":
                        comp_vol *= 0.78
                    if role == "chorus" or "ensemble" in str(section_name).lower():
                        comp_vol *= 1.10
                    dur *= 0.95
                if song_profile.get("disney_cinematic"):
                    comp_vol *= 0.48 if role == "verse" else 0.62
                    if role == "pre":
                        comp_vol *= 0.75
                    if role == "chorus":
                        comp_vol *= 0.85
                    if "final" in str(section_name).lower() or "ending" in str(section_name).lower():
                        comp_vol *= 1.05
                    dur *= 1.08
                if song_profile.get("piano_centric"):
                    comp_vol *= 0.58 if role == "verse" else 0.78
                    if role == "chorus" or "final" in str(section_name).lower():
                        comp_vol *= 1.06
                    dur *= 1.12
                if song_profile.get("comp_stab"):
                    dur *= 0.55
                    comp_vol *= 1.2
                t_comp = _humanize_time(
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    seed=idx * 53 + comp_idx + loop_seed,
                    amount=humanize * 0.7,
                    beat_len=pulse,
                )
                for note in voicing:
                    _add_tone(
                        audio,
                        sr,
                        t_comp,
                        dur,
                        note,
                        _humanize_volume(comp_vol, idx + comp_idx + note + loop_seed),
                        comp_wave,
                    )

        # Hit / stop-time bars: drums lay out for the bar except for
        # one snare crack on beat 1 to punctuate the band-stab. The
        # kick + percussion blocks below are skipped via
        # ``bar_drums_silent``.
        bar_drums_silent = bar_is_hit
        if bar_is_hit:
            _add_noise_hit(
                audio,
                sr,
                bar_start,
                0.060,
                0.040 * intensity,
                seed=idx * 67 + loop_seed,
            )

        # Bridge dropout: when the bridge starts on a tacet bar drop
        # the kit to kick + cross-stick only so the breakdown breathes.
        # The flag controls hat/snare/ghost suppression below.
        bar_bridge_breakdown = bar_is_bridge_dropout

        if not bar_drums_silent and not bar_bridge_breakdown:
            for b in patterns["hat_beats"]:
                hat_vol = (0.006 if style == "Ballad" else 0.010) * hat_mul
                if role == "chorus":
                    hat_vol *= 1.28
                # Open hi-hat: longer noise tail on style-defined
                # off-beats (e.g. the "and of 4" in funk/disco/pop).
                # We detect the open-hat by approximate match because
                # the pattern beats may have been rescaled to an odd
                # meter via ``_scale_pattern_beats``.
                is_open_hat = any(abs(b - oa) < 0.06 for oa in hat_open_ands)
                hat_dur = 0.090 if is_open_hat else 0.028
                hat_vol_local = hat_vol
                if is_open_hat:
                    hat_vol_local *= 1.35
                _add_noise_hit(
                    audio,
                    sr,
                    _humanize_time(
                        _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                        seed=idx * 31 + int(b * 100) + loop_seed,
                        amount=humanize * 0.5,
                        beat_len=pulse,
                    ),
                    hat_dur,
                    hat_vol_local * intensity,
                    seed=idx * 31 + int(b * 100) + (groove_seed % 997) + loop_seed,
                )

        if not bar_drums_silent and not bar_bridge_breakdown:
            for b in patterns["snare_beats"]:
                snare_vol = 0.032 * intensity
                if song_profile.get("cross_stick"):
                    snare_vol *= 0.65
                _add_noise_hit(
                    audio,
                    sr,
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    0.055,
                    _humanize_volume(snare_vol, idx * 67 + int(b * 100) + loop_seed),
                    seed=idx * 67 + int(b * 100) + loop_seed,
                )

        if not bar_drums_silent and not bar_bridge_breakdown:
            for b in patterns.get("ghost_snare", []):
                _add_noise_hit(
                    audio,
                    sr,
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    0.025,
                    0.010 * intensity,
                    seed=idx * 71 + int(b * 50) + loop_seed,
                )

        # Cross-stick keeps its 2/4 colouring even on a bridge
        # dropout — that's the only piece of the kit that stays so
        # the listener still has a pulse reference to count against.
        if not bar_drums_silent:
            cross_beats = patterns.get("cross_stick", [])
            if bar_bridge_breakdown and not cross_beats:
                # Bridge bar without baked-in cross-stick gets a soft
                # 2 & 4 click so the dropout still has a pulse.
                cross_beats = [b for b in (1.0, 3.0) if b < pulses_per_bar]
            for b in cross_beats:
                _add_noise_hit(
                    audio,
                    sr,
                    _groove_time(bar_start, b, pulse, style),
                    0.040,
                    0.014 * intensity * (0.85 if bar_bridge_breakdown else 1.0),
                    seed=idx * 73 + int(b * 40) + loop_seed,
                )

        if not bar_drums_silent:
            kick_beats = patterns["kick_beats"]
            if bar_bridge_breakdown:
                # Pull kicks down to just beat 1 (and beat 3 in 4/4)
                # so the bridge breakdown reads as dropout, not as a
                # full bar of drums under N.C.
                kick_beats = [b for b in kick_beats if b in (0.0, 2.0)]
            kick_vol_mul = 0.78 if bar_bridge_breakdown else 1.0
            for b in kick_beats:
                _add_tone(
                    audio,
                    sr,
                    _humanize_time(
                        bar_start + b * pulse,
                        seed=idx * 83 + int(b * 10) + loop_seed,
                        amount=humanize * 0.35,
                        beat_len=pulse,
                    ),
                    0.07,
                    36,
                    _humanize_volume(
                        0.070 * intensity * kick_mul * kick_vol_mul, idx * 83 + loop_seed
                    ),
                    "bass",
                )

        # ----- Mid-bar bass anticipation pickup -------------------
        # On the "and of 4" (last off-beat of the bar) play a short
        # chromatic-approach note toward the next bar's chord root.
        # This is the classic "walk-up into the change" that bass
        # players add to glue the bar line. Only fires when:
        #   * the next bar exists and has a *different* root,
        #   * the current bar isn't tacet/hit/subdivided (those have
        #     their own logic),
        #   * the style is one where this groove fits (skip Ballad
        #     which prefers held notes).
        try:
            if (
                next_chord
                and not bar_is_no_chord
                and not bar_is_hit
                and not bar_is_subdivided
                and style not in ("Ballad",)
            ):
                cur_root = bass_note(sounding_chord)
                # ``next_chord`` may itself be a hit/tacet/subdivided
                # token; resolve to a sounding chord head before
                # asking for its root.
                if _sub_is_hit_token(next_chord):
                    nxt_head = _sub_hit_underlying_chord(next_chord)
                elif _sub_is_subdivided_bar(next_chord):
                    nxt_head = _sub_primary_chord(next_chord)
                elif is_no_chord_token(next_chord):
                    nxt_head = None
                else:
                    nxt_head = next_chord
                if nxt_head:
                    nxt_root = bass_note(nxt_head)
                    if (cur_root % 12) != (nxt_root % 12):
                        # Half-step chromatic approach toward the
                        # target root, in the bass register.
                        target = nxt_root - 12
                        approach_pitch = (
                            target - 1 if target >= cur_root - 12 else target + 1
                        )
                        pickup_b = max(0.0, pulses_per_bar - 0.5)
                        t_pickup = _humanize_time(
                            _groove_time(
                                bar_start, pickup_b, pulse, style,
                                swing=swing_amt, pocket=pocket_offset,
                            ),
                            seed=idx * 113 + loop_seed,
                            amount=humanize * 0.6,
                            beat_len=pulse,
                        )
                        # Volume scales gently so the pickup doesn't
                        # eclipse the downbeat that follows.
                        _add_tone(
                            audio,
                            sr,
                            t_pickup,
                            pulse * 0.30,
                            approach_pitch,
                            _humanize_volume(
                                0.055 * intensity, idx * 113 + loop_seed
                            ),
                            "bass",
                        )
        except Exception:
            # Pickup is purely decorative — never let an unexpected
            # chord-token form (e.g. a custom non-standard symbol)
            # break the synth. Silently skip and continue.
            pass

        # Breakdown recovery: first downbeat after a bridge gets a
        # crash + sub-tone so the band-back-in moment lands. We do
        # this *before* the section-edge fill check so the crash
        # sits cleanly under any pickup that follows.
        if is_breakdown_recovery and not bar_is_no_chord:
            _add_breakdown_recovery_crash(
                audio,
                sr,
                bar_start,
                pulse,
                intensity,
                seed_base=idx,
            )

        if section_edge:
            # Estimate the *next* section's intensity so the fill
            # engine can size the roll appropriately (bigger fill
            # before a chorus, more so for the final chorus).
            next_section_name = next_event.get("section") if next_event else ""
            next_role_for_fill = _section_role(next_section_name)
            next_arr_mul = _arrangement_intensity_overlay(idx + 1, next_role_for_fill, arr_ctx)
            next_intensity_estimate = (
                _section_intensity(next_section_name, style) * next_arr_mul
            )
            into_final_chorus = (
                next_role_for_fill == "chorus"
                and arr_ctx.is_final_chorus_event(idx + 1)
            )
            _add_section_transition_fill(
                audio,
                sr,
                bar_start,
                pulse,
                pulses_per_bar,
                style,
                role,
                next_event,
                intensity,
                seed_base=idx,
                next_intensity=next_intensity_estimate,
                is_into_final_chorus=into_final_chorus,
            )
            tail = max(0.0, pulses_per_bar - 0.45)
            tail_chord = _pulse_chord(tail)
            tail_next = next_chord if not bar_is_subdivided else (
                _sub_primary_chord(next_chord) if next_chord else None
            )
            # Skip the pickup bass note if this bar (or its tail
            # segment) is tacet — N.C. bars shouldn't suddenly fire a
            # bass attack just because a section ends.
            if not bar_is_no_chord and not is_no_chord_token(tail_chord):
                approach = _bass_motion_pitch(tail_chord, tail_next, style, len(bass_hits) - 1, len(bass_hits))
                _add_tone(audio, sr, bar_start + tail * pulse, pulse * 0.25, approach, 0.075 * intensity, "bass")
            _add_noise_hit(
                audio,
                sr,
                bar_start + (tail + 0.2) * pulse,
                0.050,
                0.018 * intensity,
                seed=idx * 101,
            )
            if (
                not bar_is_no_chord
                and next_event
                and _section_role(next_event.get("section")) == "chorus"
            ):
                _add_tone(audio, sr, bar_start + (tail + 0.33) * pulse, 0.09, 48, 0.055, "bass")

        # Pushed-chord anticipations: when a sub-chord inside this bar is
        # marked with ``push`` (e.g. ``"C:3.5|D:0.5p"``) the synth bass
        # / comp grid above won't fire on the off-beat, so we add a
        # single extra attack a half-beat *before* its written start
        # time to give the chord change an audible anticipation.
        if bar_is_subdivided:
            push_subs = _sub_parse_subdivisions(chord, beats_per_bar=pulses_per_bar)
            if any(s.push for s in push_subs):
                beat_cursor = 0.0
                for sub in push_subs:
                    if sub.push and beat_cursor > 0:
                        push_b = max(0.0, beat_cursor - 0.5)
                        push_pitch = _bass_motion_pitch(
                            sub.chord, None, style, 0, 1
                        )
                        _add_tone(
                            audio,
                            sr,
                            bar_start + push_b * pulse,
                            pulse * 0.42,
                            push_pitch,
                            0.085 * intensity,
                            "bass",
                        )
                        push_voicing = _voicing_for_comp(sub.chord, level, style, 0)
                        for _push_note in push_voicing:
                            _add_tone(
                                audio,
                                sr,
                                bar_start + push_b * pulse,
                                pulse * 0.55,
                                _push_note,
                                0.020 * intensity,
                                comp_wave,
                            )
                    beat_cursor += float(sub.weight)

    audio = np.tanh(audio)
    audio = audio / (np.max(np.abs(audio)) + 1e-9) * 0.86
    return audio, sr


def pcm16_wav_bytes_from_float(audio, sr=44100):

    out = io.BytesIO()

    with wave.open(out, "wb") as wf:

        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)

        wf.writeframes(
            (audio * 32767)
            .astype(np.int16)
            .tobytes()
        )

    out.seek(0)

    return out.getvalue()


def generate_backing_track(
    chords,
    bpm=100,
    loops=1,
    style="Pop groove",
    level="Intermediate",
    song_title: str = "",
    song_artist: str = "",
    time_signature: str = "4/4",
):

    audio, sr = synthesize_chords_to_numpy(
        chords,
        bpm=bpm,
        loops=loops,
        style=style,
        level=level,
        song_title=song_title,
        song_artist=song_artist,
        time_signature=time_signature,
    )
    return pcm16_wav_bytes_from_float(audio, sr)


def backing_bytes_to_float(
    chords,
    bpm=100,
    style="Pop groove",
    level="Intermediate",
    time_signature: str = "4/4",
):

    y, _sr = synthesize_chords_to_numpy(
        chords,
        bpm=bpm,
        loops=1,
        style=style,
        level=level,
        time_signature=time_signature,
    )
    return y


def wav_bytes_from_float(audio, sr=44100):

    return pcm16_wav_bytes_from_float(audio, sr)
