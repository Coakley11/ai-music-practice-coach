"""Backing track synthesis and groove inference (no Streamlit UI)."""

from __future__ import annotations

import io
import wave
from functools import lru_cache
from typing import Any

import numpy as np

from chord_subdivisions import (
    chord_at_beat as _sub_chord_at_beat,
    chord_at_pulse as _sub_chord_at_pulse,
    has_push as _sub_has_push,
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
    notes = chord_notes(chord)
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


def _groove_time(bar_start, beat, beat_len, style, *, swing: float = 0.0):
    t = bar_start + beat * beat_len
    if swing and beat % 1:
        t = bar_start + (beat + swing) * beat_len
    elif style == "Jazz swing" and beat % 1:
        t = bar_start + (beat + 0.08) * beat_len
    elif style == "Funk groove" and beat % 1:
        t = bar_start + (beat - 0.02) * beat_len
    return t


def _scale_pattern_beats(beats: list[float], *, from_pulses: int, to_pulses: int) -> list[float]:
    if from_pulses <= 0 or to_pulses <= 0 or from_pulses == to_pulses:
        return list(beats)
    factor = to_pulses / from_pulses
    return [round(b * factor, 4) for b in beats]


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
):
    """Drum fill and lift between sections."""
    fill_anchor = max(0.0, pulses_per_bar - 0.8)
    fill_start = bar_start + fill_anchor * pulse_sec
    next_role = _section_role(next_event.get("section")) if next_event else "neutral"
    for i, off in enumerate([0.0, 0.5, 1.0, 1.5, 2.0, 2.5]):
        _add_noise_hit(
            audio,
            sr,
            fill_start + off * pulse_sec * 0.15,
            0.04,
            0.022 * intensity,
            seed=seed_base * 17 + i,
        )
    if next_role == "chorus":
        for t, freq in [(3.5, 200), (3.65, 260), (3.8, 330)]:
            pulse = min(float(pulses_per_bar) - 0.5, t)
            _add_tone(audio, sr, bar_start + pulse * pulse_sec, 0.06, freq, 0.04 * intensity, "bass")
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
    }
    if style == "Jazz swing":
        profile["swing"] = 0.11
        profile["ride_jazz"] = True
        profile["humanize_ms"] = 0.018
    elif style == "Bossa nova":
        profile["cross_stick"] = True
        profile["latin_relaxed"] = True
        profile["swing"] = 0.04
        profile["hat_soft"] = 0.72
        profile["humanize_ms"] = 0.015
    elif style == "Funk groove":
        profile["ghost_snare"] = True
        profile["comp_stab"] = True
        profile["kick_push"] = 1.12
    elif style == "Rock groove":
        profile["kick_push"] = 1.2
        profile["hat_soft"] = 0.9
    elif style == "Ballad":
        profile["hat_soft"] = 0.55
        profile["humanize_ms"] = 0.008

    if any(k in title for k in ("waiting on the world", "say", "john mayer")):
        profile["pop_soul"] = True
        profile["swing"] = max(profile["swing"], 0.03)
        profile["hat_soft"] = 0.82
        profile["humanize_ms"] = 0.014
    if "champions" in title or "queen" in title:
        profile["anthem_rock"] = True
        profile["kick_push"] = 1.28
    if "blue bossa" in title or "bossa" in title:
        profile["latin_relaxed"] = True
        profile["cross_stick"] = True
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
    if profile.get("pop_soul"):
        return _fit({
            "bass_beats": [0, 1.5, 2.5, 3.5],
            "comp_beats": [0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2.5],
            "comp_dur": 0.40,
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
    chord_list = event_cycle * max(1, int(loops))
    audio = np.zeros(int(sr * bar * len(chord_list)) + sr)
    song_profile = _song_backing_profile(song_title, song_artist, style, bpm=bpm)
    patterns = _style_patterns(style, song_profile, time_signature=timing.time_signature)
    groove_seed = song_groove_seed(song_title, song_artist) if song_title else 0
    swing_amt = float(song_profile.get("swing", 0.0))
    humanize = float(song_profile.get("humanize_ms", 0.012))
    kick_mul = float(song_profile.get("kick_push", 1.0))
    hat_mul = float(song_profile.get("hat_soft", 1.0))

    for idx, event in enumerate(chord_list):

        chord = event["chord"]
        next_event = chord_list[idx + 1] if idx + 1 < len(chord_list) else None
        next_chord = next_event["chord"] if next_event else None
        bar_start = idx * bar
        section_name = event.get("section", "Practice Loop")
        intensity = _section_intensity(section_name, style)
        role = _section_role(section_name)
        section_edge = _is_section_edge(event, next_event)
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
        notes = chord_notes(_sub_primary_chord(chord) if bar_is_subdivided else chord)
        bass_hits = patterns["bass_beats"]
        if groove_seed % 3 == 0 and role == "verse":
            bass_hits = bass_hits[: max(2, len(bass_hits) - 1)]
        comp_wave = _comp_wave_for_style(style, role)

        def _pulse_chord(b_pos: float) -> str:
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
            t_hit = _humanize_time(
                _groove_time(bar_start, b, pulse, style, swing=swing_amt),
                seed=idx * 41 + n + groove_seed,
                amount=humanize,
                beat_len=pulse,
            )
            _add_tone(
                audio,
                sr,
                t_hit,
                bass_dur,
                bass_pitch,
                _humanize_volume(0.11 * intensity, idx * 41 + n),
                "bass",
            )

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
            if song_profile.get("comp_stab"):
                dur *= 0.55
                comp_vol *= 1.2
            t_comp = _humanize_time(
                _groove_time(bar_start, b, pulse, style, swing=swing_amt),
                seed=idx * 53 + comp_idx,
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
                    _humanize_volume(comp_vol, idx + comp_idx + note),
                    comp_wave,
                )

        for b in patterns["hat_beats"]:
            hat_vol = (0.006 if style == "Ballad" else 0.010) * hat_mul
            if role == "chorus":
                hat_vol *= 1.28
            _add_noise_hit(
                audio,
                sr,
                _humanize_time(
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt),
                    seed=idx * 31 + int(b * 100),
                    amount=humanize * 0.5,
                    beat_len=pulse,
                ),
                0.028,
                hat_vol * intensity,
                seed=idx * 31 + int(b * 100) + (groove_seed % 997),
            )

        for b in patterns["snare_beats"]:
            snare_vol = 0.032 * intensity
            if song_profile.get("cross_stick"):
                snare_vol *= 0.65
            _add_noise_hit(
                audio,
                sr,
                _groove_time(bar_start, b, pulse, style, swing=swing_amt),
                0.055,
                _humanize_volume(snare_vol, idx * 67 + int(b * 100)),
                seed=idx * 67 + int(b * 100),
            )

        for b in patterns.get("ghost_snare", []):
            _add_noise_hit(
                audio,
                sr,
                _groove_time(bar_start, b, pulse, style, swing=swing_amt),
                0.025,
                0.010 * intensity,
                seed=idx * 71 + int(b * 50),
            )

        for b in patterns.get("cross_stick", []):
            _add_noise_hit(
                audio,
                sr,
                _groove_time(bar_start, b, pulse, style),
                0.040,
                0.014 * intensity,
                seed=idx * 73 + int(b * 40),
            )

        for b in patterns["kick_beats"]:
            _add_tone(
                audio,
                sr,
                _humanize_time(
                    bar_start + b * pulse,
                    seed=idx * 83 + int(b * 10),
                    amount=humanize * 0.35,
                    beat_len=pulse,
                ),
                0.07,
                36,
                _humanize_volume(0.070 * intensity * kick_mul, idx * 83),
                "bass",
            )

        if section_edge:
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
