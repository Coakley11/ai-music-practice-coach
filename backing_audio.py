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

import backing_arrangement_profiles as _arr_profiles
import backing_groove_profiles as _groove_profiles
import backing_keys_voice as _kv

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


# Chord-suffix spellings that the quality matching below would otherwise misread
# (ø7 / °7 / -7 / Δ7 as dominant, M7 as minor 7, min7 as a triad, aug without its #5 ...).
# Case-sensitive, applied before lower-casing; longest first.
_SUFFIX_ALIASES = (
    ("mMaj7", "mmaj7"), ("m(maj7)", "mmaj7"), ("mM7", "mmaj7"), ("min(maj7)", "mmaj7"),
    ("ø7", "m7b5"), ("ø", "m7b5"), ("m7(b5)", "m7b5"), ("-7b5", "m7b5"),
    ("°7", "dim7"), ("o7", "dim7"), ("°", "dim"),
    ("Δ7", "maj7"), ("Δ", "maj7"), ("M7", "maj7"), ("ma7", "maj7"), ("Maj7", "maj7"),
    ("min7", "m7"), ("mi7", "m7"), ("-7", "m7"), ("min", "m"), ("mi", "m"),
    ("7+5", "7#5"), ("7aug", "7#5"), ("aug7", "7#5"), ("+7", "7#5"),
    ("6/9", "69"),
)


def _canonical_suffix(suffix: str) -> str:
    s = str(suffix or "")
    for alias, canon in _SUFFIX_ALIASES:
        if s.startswith(alias):
            s = canon + s[len(alias):]
            break
    if s in ("o",):
        s = "dim"
    if s in ("+", "aug") or s.startswith("aug") and "7" not in s:
        s = "aug"
    if s.startswith("-") and not s.startswith("-7"):
        s = "m" + s[1:]
    return s


def chord_notes(chord):

    head = _chord_head(chord)

    root, suffix = split_chord(head)

    base = NOTE_TO_MIDI.get(root, 60)
    base = NOTE_TO_MIDI.get(normalize_root(root), base)

    low = _canonical_suffix(suffix).lower()

    altered_ninth = "b9" in low or "#9" in low
    if "mmaj7" in low:
        intervals = [0,3,7,11]

    elif "alt" in low:
        # Altered dominant: 3, #5, b7, b9, #9 (slots stay root / 3rd / 5th / 7th / extensions).
        intervals = [0,4,8,10,13,15]

    elif "m7b5" in low:
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

    elif low.startswith("m6"):
        intervals = [0,3,7,9]

    elif "m" in low and "maj" not in low:
        intervals = [0,3,7]

    elif low.startswith("7#5"):
        intervals = [0,4,8,10]

    elif low.startswith("aug"):
        intervals = [0,4,8]

    elif low.startswith("69"):
        intervals = [0,4,7,9,14]

    elif "13" in low and "b13" not in low:
        intervals = [0,4,7,10,14,21]

    elif "add9" in low:
        intervals = [0,4,7,14]

    elif "9" in low and not altered_ninth:
        intervals = [0,4,7,10,14]

    elif "6" in low:
        intervals = [0,4,7,9]

    elif "sus" in low:
        intervals = [0,5,7,10] if "7" in low else [0,5,7]

    elif "7" in low:
        intervals = [0,4,7,10]

    else:
        intervals = [0,4,7]

    # An explicit b5 / #5 replaces the perfect fifth (7b5, 9b5, maj7#5 ...); m7b5, dim, aug,
    # 7#5 and alt already spell theirs.
    if 7 in intervals:
        if "b5" in low:
            intervals[intervals.index(7)] = 6
        elif "#5" in low or "+5" in low:
            intervals[intervals.index(7)] = 8

    if "alt" in low:
        pass  # already spelled
    elif "b9" in low:
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
    if "blues" in titleish:
        return "Blues groove"
    if genre_name == "Jazz":
        return "Jazz swing"
    if genre_name == "Blues":
        return "Blues groove"
    if genre_name in ["Funk", "Soul"]:
        return "Funk groove"
    if genre_name == "Rock":
        return "Rock groove"
    if genre_name == "Jewish Traditional":
        return "Jewish ballad"
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
        # Round bass with a gentle pluck: the 2nd harmonic and level settle after the attack.
        t = np.arange(n, dtype=np.float64) * inv_sr
        sig = np.sin(phase) + 0.35 * np.sin(phase * 2.0) * (0.5 + 0.5 * np.exp(-t * 4.0))
        sig *= 0.8 + 0.2 * np.exp(-t * 2.5)
    elif wave_type == "bass_upright":
        # Plucked upright for long legato notes: same tone as "bass", but the note keeps
        # decaying after the pluck instead of holding level like an organ.
        t = np.arange(n, dtype=np.float64) * inv_sr
        sig = np.sin(phase) + 0.4 * np.sin(phase * 2.0) * (0.45 + 0.55 * np.exp(-t * 5.0))
        sig *= 0.42 + 0.58 * np.exp(-t * 2.2)
    elif wave_type == "piano":
        # Piano-like comping voice: decaying harmonics (upper ones fade faster) and a second,
        # slightly detuned string, so chords bloom and decay instead of holding like a test tone.
        t = np.arange(n, dtype=np.float64) * inv_sr
        detune = 2.0 ** (0.7 / 1200.0)
        sig = np.zeros(n, dtype=np.float64)
        for k, amp in ((1, 1.0), (2, 0.30), (3, 0.10), (4, 0.04)):
            decay = np.exp(-t * (1.6 + 2.2 * (k - 1)))
            sig += amp * decay * (np.sin(phase * k) + 0.6 * np.sin(phase * k * detune)) / 1.6
        sig *= 0.80
    elif wave_type == "drive":
        # Rock rhythm guitar: harmonic-rich (saw-like) tone, softly clipped.
        sig = np.zeros(n, dtype=np.float64)
        for k in range(1, 11):
            sig += np.sin(phase * k) / k
        sig = np.tanh(1.8 * sig) * 0.75
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


def _add_noise_hit(audio, sr, start_sec, dur_sec, volume, seed=0, *, tone: float = 0.0):
    start = int(start_sec * sr)
    if start >= len(audio):
        return
    n = max(1, int(dur_sec * sr))
    end = min(len(audio), start + n)
    n = end - start
    rng = np.random.default_rng(seed)
    sig = rng.normal(0, 1, n)
    # ``tone`` mixes a bright ping into the noise (for ride/hat colour):
    # 0.0 = pure noise (snare/closed hat), 1.0 = strong pitched shimmer.
    if tone > 0.0:
        two_pi = 2.0 * np.pi
        t = np.arange(n, dtype=np.float64) / sr
        ping = np.sin(two_pi * 3200.0 * t) + 0.5 * np.sin(two_pi * 5400.0 * t)
        sig = (1.0 - tone) * sig + tone * ping
    env = np.linspace(1, 0.01, n)
    audio[start:end] += sig * env * volume


def _add_kick(audio, sr, start_sec, volume, *, punch: float = 1.0, seed: int = 0):
    """Style-aware kick: pitch-swept sine body + short click transient.

    ``punch`` scales the click transient and pitch drop so rock/funk kicks
    read harder than a pop/ballad thump.
    """
    start = int(start_sec * sr)
    if start >= len(audio) or volume <= 0:
        return
    dur = 0.11 + 0.03 * punch
    n = max(1, int(dur * sr))
    end = min(len(audio), start + n)
    n = end - start
    t = np.arange(n, dtype=np.float64) / sr
    # Pitch sweep from ~110Hz down to ~45Hz — harder punch drops faster.
    f_start = 90.0 + 40.0 * punch
    f_end = 45.0
    k = 22.0 + 14.0 * punch
    freq = f_end + (f_start - f_end) * np.exp(-k * t)
    phase = 2.0 * np.pi * np.cumsum(freq) / sr
    body = np.sin(phase)
    env = np.exp(-t * (26.0 + 8.0 * punch))
    sig = body * env
    # Click transient for attack definition.
    click_n = max(1, int(0.006 * sr))
    click_n = min(click_n, n)
    rng = np.random.default_rng(seed)
    click = rng.normal(0, 1, click_n) * np.linspace(1.0, 0.0, click_n)
    sig[:click_n] += click * 0.5 * punch
    audio[start:end] += sig * volume


def _add_snare(audio, sr, start_sec, volume, *, crack: float = 1.0, seed: int = 0):
    """Style-aware snare: noise burst + tonal shell. ``crack`` = brightness."""
    start = int(start_sec * sr)
    if start >= len(audio) or volume <= 0:
        return
    dur = 0.06 + 0.02 * crack
    n = max(1, int(dur * sr))
    end = min(len(audio), start + n)
    n = end - start
    t = np.arange(n, dtype=np.float64) / sr
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n)
    # Tonal shell around 180-220Hz gives the snare a body/pitch.
    shell = np.sin(2.0 * np.pi * (190.0 + 30.0 * crack) * t)
    mix = (0.72 + 0.15 * crack) * noise + (0.28 - 0.1 * crack) * shell
    env = np.exp(-t * (34.0 - 8.0 * crack))
    audio[start:end] += mix * env * volume


def _add_ride(audio, sr, start_sec, volume, seed=0):
    """Jazz ride cymbal: pitched shimmer with a long, sizzling tail."""
    start = int(start_sec * sr)
    if start >= len(audio) or volume <= 0:
        return
    dur = 0.32
    n = max(1, int(dur * sr))
    end = min(len(audio), start + n)
    n = end - start
    t = np.arange(n, dtype=np.float64) / sr
    two_pi = 2.0 * np.pi
    # Inharmonic partials = metallic cymbal ping.
    ping = (
        np.sin(two_pi * 2400.0 * t)
        + 0.6 * np.sin(two_pi * 3700.0 * t)
        + 0.3 * np.sin(two_pi * 5600.0 * t)
    )
    rng = np.random.default_rng(seed)
    # Wash, not hiss: the sizzle is low-passed (~6 kHz) like a dark jazz ride.
    from scipy.signal import lfilter

    alpha = 1.0 - np.exp(-2.0 * np.pi * 6000.0 / sr)
    sizzle = lfilter([alpha], [1.0, alpha - 1.0], rng.normal(0, 1, n)) * 0.75
    env = np.exp(-t * 11.0)
    audio[start:end] += (ping * 0.6 + sizzle) * env * volume


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
    elif style == "Blues groove":
        base *= 0.94
    elif style in ("Rock groove", "Funk groove") and role == "chorus":
        base *= 1.08
    return base


def _style_drum_character(style: str) -> dict[str, Any]:
    """Per-style kit voicing — exaggerated for obvious identity (Phase 2C)."""
    base: dict[str, Any] = {
        "kick_punch": 1.0,
        "snare_crack": 1.0,
        "hat_tone": 0.0,
        "hat_vol_mul": 1.0,
        "snare_vol_mul": 1.0,
        "kick_vol_mul": 1.0,
        "use_ride": False,
        "ride_vol_mul": 1.0,
        "cross_stick_vol_mul": 1.0,
        "suppress_snare": False,
        "suppress_hats": False,
        "ghost_vol_mul": 1.0,
    }
    if style == "Rock groove":
        base.update(
            kick_punch=1.85,
            snare_crack=1.55,
            snare_vol_mul=1.65,
            kick_vol_mul=1.55,
            hat_vol_mul=1.2,
            ghost_vol_mul=1.4,
        )
    elif style == "Funk groove":
        base.update(
            kick_punch=1.45,
            snare_crack=1.35,
            hat_tone=0.2,
            hat_vol_mul=1.2,
            snare_vol_mul=1.15,
            ghost_vol_mul=1.6,
        )
    elif style == "Jazz swing":
        base.update(
            kick_punch=0.45,
            snare_crack=0.45,
            snare_vol_mul=0.35,
            kick_vol_mul=0.45,
            use_ride=True,
            ride_vol_mul=5.5,
            suppress_snare=True,
        )
    elif style == "Bossa nova":
        base.update(
            kick_punch=0.55,
            snare_crack=0.4,
            hat_vol_mul=0.0,
            cross_stick_vol_mul=2.8,
            kick_vol_mul=0.55,
            suppress_snare=True,
            suppress_hats=True,
        )
    elif style == "Blues groove":
        base.update(
            kick_punch=0.95,
            snare_crack=0.9,
            hat_tone=0.12,
            use_ride=True,
            ride_vol_mul=3.2,
            hat_vol_mul=0.85,
            ghost_vol_mul=1.3,
        )
    elif style in ("Pop groove", "Pop"):
        base.update(kick_punch=0.95, snare_crack=0.92, hat_vol_mul=0.9, snare_vol_mul=0.88)
    return base


def _style_arrangement_character(style: str) -> dict[str, float]:
    """Per-style bass/comp level and duration — arrangement feel, not timbre only."""
    base = {"bass_vol_mul": 1.0, "comp_vol_mul": 1.0, "bass_dur_mul": 1.0}
    if style in ("Pop groove", "Pop"):
        base.update(bass_vol_mul=0.82, comp_vol_mul=0.72, bass_dur_mul=0.55)
    elif style == "Rock groove":
        base.update(bass_vol_mul=1.35, comp_vol_mul=1.45, bass_dur_mul=0.38)
    elif style == "Jazz swing":
        base.update(bass_vol_mul=1.25, comp_vol_mul=0.50, bass_dur_mul=0.82)
    elif style == "Bossa nova":
        base.update(bass_vol_mul=1.1, comp_vol_mul=0.78, bass_dur_mul=0.62)
    elif style == "Funk groove":
        base.update(bass_vol_mul=1.2, comp_vol_mul=1.55, bass_dur_mul=0.22)
    elif style == "Blues groove":
        base.update(bass_vol_mul=1.15, comp_vol_mul=1.12, bass_dur_mul=0.68)
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


BASS_ROOT_LOW = 36  # C2: bass roots sit in C2 .. B2 and the line climbs from there (upright / electric bass)


def _bass_register(midi_num, near=None):
    """Pitch class of ``midi_num`` in the bass register (C2 .. B2), or the octave nearest ``near``."""
    m = BASS_ROOT_LOW + ((int(midi_num) - BASS_ROOT_LOW) % 12)
    if near is not None:
        while m - near > 6:
            m -= 12
        while near - m > 6:
            m += 12
    return m


def _bass_motion_pitch(chord, next_chord, style, slot_index, slot_count, *, beat=None, pulses_per_bar=None):
    notes = chord_notes(chord)
    root = _bass_register(bass_note(chord))
    # The chord's own root in the bass octave (equal to ``root`` unless a slash bass), so the
    # 3rd / 5th sit next to the root instead of an octave below it (no C#3 -> E2 -> G2 leaps).
    chord_root = root - ((root - notes[0]) % 12)
    third = chord_root + (notes[1] - notes[0]) if len(notes) > 1 else chord_root + 4
    fifth = chord_root + (notes[2] - notes[0]) if len(notes) > 2 else chord_root + 7

    # A half-step approach belongs on the last beat before the change; on an earlier hit
    # (beat 3 of a two-hit bar) it would sustain a non-chord tone under the current chord.
    on_last_beat = beat is None or pulses_per_bar is None or float(beat) >= float(pulses_per_bar) - 1.0
    # Dev: only where the last hit is a short one (>= 4 hits a bar); in a two-hit bar the approach
    # note would sustain under the current chord for half the bar.
    if next_chord and slot_index == slot_count - 1 and slot_count >= 4 and on_last_beat:
        # Approach the octave the next downbeat is actually played in (roots sit in C2 .. B2):
        # aiming near this bar's root put the approach an 11th away from the note it leads to.
        target = _bass_register(bass_note(next_chord))
        if target % 12 == root % 12:
            # Same root next bar: walk to the 5th (below, when the line is already up high).
            return fifth - 12 if (root - BASS_ROOT_LOW) >= 7 else fifth
        return target - 1 if target > root else target + 1

    if style == "Jazz swing":
        # Walking quarters (the approach into the next chord is the last-beat rule above).
        # From a low root walk up (root, 3rd, 5th, chromatic step); from a high root walk down
        # (root, b7 / 6th below, 5th below, chromatic step) so the line stays in the bass range.
        if (root - BASS_ROOT_LOW) >= 7:
            low7 = chord_root + ((notes[3] - notes[0]) if len(notes) >= 4 else 10) - 12
            low5 = fifth - 12
            line = [root, low7, low5, low5 - 1 if slot_index % 2 else low5 + 1]
        else:
            chrom = fifth - 1 if slot_index % 2 else third + 1
            line = [root, third, fifth, chrom]
    elif style == "Bossa nova":
        line = [root, fifth, root + 7, fifth, root, root + 7]
    elif style == "Funk groove":
        chrom_up = root + 1
        line = [root, chrom_up, root, fifth, root + 12, third, fifth, chrom_up]
    elif style == "Rock groove":
        line = [root, root, fifth, fifth, root + 12, root, fifth, root + 12]
    elif style == "Blues groove":
        flat7 = fifth - 2
        line = [root, fifth, flat7, root, root + 12, fifth, flat7]
    elif style == "Ballad":
        line = [root, fifth]
    elif style in ("Pop groove", "Pop"):
        line = [root, fifth]
    else:
        line = [root, fifth, root + 12, fifth]
    return int(line[slot_index % len(line)])


# Bossa nova bass (upright / acoustic bass guitar) lives in E1 .. C3 and is voice-led: each
# note takes the octave nearest the previous one, pulled gently back toward C2.
BOSSA_BASS_LOW = 28
BOSSA_BASS_HIGH = 48
_BOSSA_BASS_CENTER = 36


def _bass_fifth_interval(chord) -> int:
    """Semitones from the root to the fifth the chord actually has: b5, #5 or a perfect 5th."""
    low = _canonical_suffix(split_chord(_chord_head(chord))[1]).lower()
    if "alt" in low or "#5" in low or "+5" in low or low.startswith("aug"):
        return 8
    if "b5" in low or "dim" in low:
        return 6
    return 7


def _bossa_bass_pcs(chord) -> tuple[int, int]:
    """Pitch classes for (beat 1, beat 3) of a chord.

    Beat 1 is the written bass, so an inversion starts on its slash note. Beat 3 is the
    chord's own fifth in root position; with the 3rd in the bass it is the fifth, with the
    fifth in the bass it is the root, and over a 7th or a pedal (non-chord) bass it stays
    on the written note so the line the chart asks for is not covered up.
    """
    notes = chord_notes(chord)
    root = notes[0] % 12
    bass = bass_note(chord) % 12
    fifth = (root + _bass_fifth_interval(chord)) % 12
    if bass == root:
        return bass, fifth
    third = notes[1] % 12 if len(notes) > 1 else (root + 4) % 12
    if bass == third:
        return bass, fifth
    if bass == fifth:
        return bass, root
    return bass, bass


def _bossa_bass_pitch(pc, near, toward_pc=None) -> int:
    """``pc`` in E1 .. C3, in the octave nearest ``near`` (C2 when there is no previous note).

    ``toward_pc`` (the next chord's bass) also counts, so beat 3 does not drop to the low
    fifth only to leap a 9th up into the next bar.
    """
    ref = _BOSSA_BASS_CENTER if near is None else near
    cands = [m for m in range(BOSSA_BASS_LOW, BOSSA_BASS_HIGH + 1) if m % 12 == pc % 12]
    ahead = [m for m in range(BOSSA_BASS_LOW, BOSSA_BASS_HIGH + 1) if toward_pc is not None and m % 12 == toward_pc % 12]

    def cost(m):
        step_on = 0.5 * min(abs(a - m) for a in ahead) if ahead else 0.0
        return (abs(m - ref) + 0.35 * abs(m - _BOSSA_BASS_CENTER) + step_on, m)

    return min(cands, key=cost)


def _bossa_bass_approach(target, prev, kind, chord) -> int:
    """A short note on the last eighth that leads into ``target`` (the next downbeat)."""
    if kind == "chromatic":
        options = [target - 1, target + 1]
    elif kind == "fifth":
        options = [target + 7, target - 5]
    else:
        # Step into a held chord: its 7th below (b7 on dominant / minor chords), or the 9th.
        notes = chord_notes(chord)
        minorish = len(notes) > 1 and (notes[1] - notes[0]) == 3
        flat7 = len(notes) > 3 and (notes[3] - notes[0]) == 10
        options = [target - (2 if minorish or flat7 else 1), target + 2]
    options = [m for m in options if BOSSA_BASS_LOW <= m <= BOSSA_BASS_HIGH] or [target]
    return min(options, key=lambda m: (abs(m - prev), m))


def _bossa_next_head(next_chord) -> str | None:
    """First sounding chord of the next bar, or None when it is tacet or a stop-time hit."""
    if not next_chord or _sub_is_hit_token(next_chord) or is_no_chord_token(next_chord):
        return None
    subs = _sub_parse_subdivisions(next_chord)
    head = subs[0].chord if subs else ""
    return None if not head or is_no_chord_token(head) else head


def _bossa_bass_bar(chord, next_chord, pulses_per_bar, state, rng, *, density=1.0, phrase_end=False):
    """One bar of bossa nova bass as ``(beat, beats, midi, accent)`` notes.

    Two-feel anchored on 1 and 3 (written bass, then its fifth), with the surdo pickups on
    the "and" of 2 (anticipating beat 3) and the "and" of 4 (anticipating the next bar, or a
    chromatic / fifth / scale-step approach into it). The pickups come and go with
    ``density`` and ``rng`` so bars are not copies of each other. Every chord change in a
    subdivided bar gets its own bass note on the beat it starts. ``state`` carries the
    previous note and the planned next downbeat across bars, so approaches land on the
    octave that is actually played.
    """
    segs = _sub_parse_subdivisions(chord, beats_per_bar=pulses_per_bar)
    p_mid = min(0.95, 0.25 + 0.6 * density)
    p_end = min(0.95, 0.35 + 0.6 * density)
    hits: list[list] = []
    rests: list[float] = []
    cursor = 0.0
    for i, seg in enumerate(segs):
        start, end = cursor, cursor + float(seg.weight)
        cursor = end
        if is_no_chord_token(seg.chord):
            state["planned"] = None
            rests.append(start)
            continue
        pushed = False
        if i + 1 < len(segs):
            nxt = None if is_no_chord_token(segs[i + 1].chord) else segs[i + 1].chord
            pushed = bool(segs[i + 1].push)
        else:
            nxt = _bossa_next_head(next_chord)
        bass_pc, alt_pc = _bossa_bass_pcs(seg.chord)
        planned = state.get("planned")
        down = planned if planned is not None and planned % 12 == bass_pc else _bossa_bass_pitch(bass_pc, state.get("prev"))
        state["planned"] = None
        hits.append([start, down, 1.0])
        last = down
        if end - start >= 3.0:
            three = _bossa_bass_pitch(alt_pc, down, _bossa_bass_pcs(nxt)[0] if nxt is not None else None)
            if rng.random() < p_mid:
                hits.append([start + 1.5, three, 0.72])
            hits.append([start + 2.0, three, 0.9])
            last = three
        if nxt is not None and end - start >= 1.5:
            nxt_pc = _bossa_bass_pcs(nxt)[0]
            target = _bossa_bass_pitch(nxt_pc, last)
            state["planned"] = target
            p = max(p_end, 0.9) if phrase_end and i == len(segs) - 1 else p_end
            if pushed or rng.random() < p:
                pick = rng.random()
                if pushed:
                    kind = "anticipate"  # lands with the comp's push attack
                elif nxt_pc == bass_pc:
                    kind = "step" if pick < 0.3 else "anticipate"
                elif pick < 0.55:
                    kind = "anticipate"
                elif pick < 0.85:
                    kind = "chromatic"
                else:
                    kind = "fifth"
                pitch = target if kind == "anticipate" else _bossa_bass_approach(target, last, kind, nxt)
                hits.append([end - 0.5, pitch, 0.7])
                last = pitch
        state["prev"] = last
    hits.sort(key=lambda h: h[0])
    notes = []
    for j, (beat, midi, accent) in enumerate(hits):
        until = hits[j + 1][0] if j + 1 < len(hits) else float(pulses_per_bar)
        until = min([until] + [r for r in rests if r > beat])
        notes.append((beat, until - beat, int(midi), accent))
    return notes


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
        root = notes[0]
        half_dim = (notes[1] - root) == 3 and len(notes) >= 3 and (notes[2] - root) == 6
        # Extensions are counted from the root: 9th = root + 14 (the 11th, root + 17, on a
        # half-diminished chord, whose natural 9th is not diatonic); 13th = root + 21, only
        # on dominant / major chords.
        ninth = root + (17 if half_dim else 14)
        thirteenth = root + 21 if (notes[1] - root) == 4 else None
        # Alternate between two classic shells to add motion across
        # beats: A-form (3-5-7-9) and B-form (7-9-3-5).
        if beat_index % 2 == 0:
            voicing = [third, seventh, ninth]
        else:
            voicing = [seventh, ninth, third + 12]
        if level == "Advanced" and thirteenth is not None:
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
        ninth = notes[0] + 14
        thirteenth = notes[0] + 21
        if level == "Beginner":
            voicing = [n + 12 for n in upper[:2]]
        elif level == "Advanced":
            voicing = [n + 12 for n in upper] + [ninth + 12, thirteenth + 12]
        else:
            voicing = [n + 12 for n in upper] + [ninth + 12]

    elif "rock" in style_key and len(notes) >= 3:
        # Driving piano rock voicing: root, fifth and octave with the third on
        # top -- a bare power chord left a piano unable to say major or minor.
        voicing = [notes[0], notes[2], notes[1] + 12]
        if level != "Beginner":
            voicing.append(notes[0] + 12)
        if beat_index % 2 and len(notes) >= 4:
            voicing.append(notes[3])

    elif "blues" in style_key and len(notes) >= 3:
        seventh = notes[3] if len(notes) >= 4 else notes[2]
        if beat_index % 2 == 0:
            voicing = [notes[0], notes[1], seventh]
        else:
            voicing = [notes[1], seventh, notes[1] + 12]
        if level == "Advanced":
            voicing.append(notes[0] + 12)

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


COMP_REGISTER = (52, 79)  # E3 .. G5: piano comping range, clear of the bass and the soloist


def _voice_lead(voicing, prev, *, lo=COMP_REGISTER[0], hi=COMP_REGISTER[1]):
    """Same chord tones and shape, moved to the inversion / octave nearest the previous hit.

    Candidates are the voicing transposed by octaves and its inversions (bottom note up an
    octave); the one inside ``[lo, hi]`` with the least total movement from ``prev`` wins (with
    no ``prev``, the one centred in the band). Pitch classes never change.
    """
    if not voicing:
        return voicing
    base = sorted(int(n) for n in voicing)
    shapes = [base]
    cur = list(base)
    for _ in range(len(base) - 1):
        cur = sorted(cur[1:] + [cur[0] + 12])
        shapes.append(cur)
    cands = []
    for shape in shapes:
        for k in range(-4, 5):
            c = [n + 12 * k for n in shape]
            if c[0] >= lo and c[-1] <= hi:
                cands.append(c)
    if not cands:
        return voicing
    if prev:
        p = sorted(prev)

        def cost(c):
            n = min(len(c), len(p))
            return sum(abs(a - b) for a, b in zip(c[:n], p[:n])) + abs(c[-1] - p[-1]) * 0.5
    else:
        mid = (lo + hi) / 2.0

        def cost(c):
            return abs(sum(c) / len(c) - mid)
    return min(cands, key=cost)


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
        # Blues gets extra shuffle push on off-beats.
        swing_amt = swing * (1.35 if style == "Blues groove" else 1.0)
        t = bar_start + (beat + swing_amt) * beat_len
    elif style == "Jazz swing" and is_offbeat:
        t = bar_start + (beat + 0.12) * beat_len
    elif style == "Funk groove" and is_offbeat:
        t = bar_start + (beat - 0.03) * beat_len
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


def _add_groove_fill(
    audio,
    sr,
    bar_start,
    pulse_sec,
    pulses_per_bar,
    fill_type,
    intensity,
    *,
    seed_base: int,
    light: bool = False,
):
    """The groove profile's own fill on the last beat of a bar.

    ``light`` is the shorter phrase-end version (inside a section); the full
    fill closes a section. Seeded per bar, so a song plays the same fills on
    every render.
    """
    last = float(pulses_per_bar) - 1.0
    if fill_type == "pickup":
        hits = [(last + 0.5, 0.7), (last + 0.75, 1.0)] if not light else [(last + 0.75, 0.8)]
        for i, (beat, vel) in enumerate(hits):
            _add_snare(audio, sr, bar_start + beat * pulse_sec, 0.030 * vel * intensity, crack=1.1, seed=seed_base * 19 + i)
    elif fill_type == "snare_roll":
        steps = [0.0, 0.25, 0.5, 0.75] if not light else [0.5, 0.75]
        for i, off in enumerate(steps):
            vel = 0.45 + 0.55 * (i + 1) / len(steps)
            _add_snare(audio, sr, bar_start + (last + off) * pulse_sec, 0.034 * vel * intensity, crack=0.95, seed=seed_base * 29 + i)
    elif fill_type == "tom_run":
        toms = [(0.0, 50), (0.25, 47), (0.5, 43), (0.75, 40)] if not light else [(0.5, 45), (0.75, 40)]
        _add_snare(audio, sr, bar_start + last * pulse_sec, 0.030 * intensity, crack=1.2, seed=seed_base * 31)
        for i, (off, midi) in enumerate(toms):
            _add_tone(audio, sr, bar_start + (last + off) * pulse_sec, pulse_sec * 0.3, midi, 0.06 * intensity, "sine")
            _add_noise_hit(audio, sr, bar_start + (last + off) * pulse_sec, 0.05, 0.012 * intensity, seed=seed_base * 37 + i, tone=0.35)
    elif fill_type == "swell" and not light:
        _add_cymbal_swell(
            audio, sr, bar_start + max(0.0, float(pulses_per_bar) - 1.6) * pulse_sec, pulse_sec,
            pulses_per_bar, intensity * 0.8, seed_base=seed_base, duration_pulses=1.4,
        )


def _add_crash(audio, sr, start_sec, intensity, *, seed: int):
    """Crash cymbal on a section downbeat."""
    _add_noise_hit(audio, sr, start_sec, 0.45, 0.034 * intensity, seed=seed * 43, tone=0.15)


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


def _comp_wave_for_style(style: str, role: str, song_profile: dict | None = None) -> str:
    profile = song_profile or {}
    hinted = str(profile.get("comp_wave") or "").strip()
    if hinted in ("organ", "sine", "piano", "drive"):
        return hinted
    # Piano is the accompaniment voice; a song profile can still ask for organ.
    return "piano"


# Piano comp level (RMS) relative to the rhythm section, by style: piano-led
# ballads and pop up front, comping under the groove in funk and jazz.
_KEYS_BALANCE: dict[str, float] = {
    "Ballad": 0.75,
    "Jewish ballad": 0.75,
    "Pop groove": 0.6,
    "Pop": 0.6,
    "Bossa nova": 0.55,
    "Rock groove": 0.5,
    "Blues groove": 0.5,
    "Funk groove": 0.45,
    "Jazz swing": 0.4,
}

# Pre-mix bus levels of the last render (diagnostics / balance tests).
LAST_MIX_STATS: dict[str, float] = {}

# Loudness of the piano comp relative to the old sustained organ voice: a struck
# note decays, so it needs more headroom to carry the same harmony.
_PIANO_GAIN = 2.6


def _add_comp_chord(
    keys_bus,
    sr,
    t_start,
    dur,
    voicing,
    base_vol,
    wave,
    *,
    beat: float,
    seed: int,
    pulses_per_bar: int,
    roll: bool = False,
):
    """Sound one comp chord on the keys bus.

    Piano: one velocity per hit from the beat (downbeat strongest, off-beats
    lighter, small deterministic variation), the top voice slightly louder than
    the inner voices, and an optional gentle roll for sustained ballad chords.
    Other voices keep the original per-note humanized sine/organ tone.
    """
    if not voicing:
        return
    if wave != "piano":
        for note in voicing:
            _add_tone(keys_bus, sr, t_start, dur, note, _humanize_volume(base_vol, seed + note), wave)
        return
    vel = _kv.hit_velocity(beat, seed=seed, pulses_per_bar=pulses_per_bar)
    gains = _kv.voice_gains(voicing)
    loud = base_vol * _PIANO_GAIN * (vel / 0.72)
    order = sorted(range(len(voicing)), key=lambda i: voicing[i])
    for rank, i in enumerate(order):
        offset = rank * 0.016 if roll else 0.0
        _kv.add_piano_note(keys_bus, sr, t_start + offset, max(0.03, dur - offset), voicing[i], loud * gains[i], vel)


def _song_backing_profile(
    song_title: str,
    song_artist: str,
    style: str,
    *,
    bpm: int = 100,
) -> dict[str, Any]:
    """Song-aware groove character (energy, swing, anthem, soul-pop, etc.).

    The per-song rules live as data in ``backing_arrangement_profiles``.
    """
    return _arr_profiles.song_arrangement_profile(song_title, song_artist, style, bpm=bpm)


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

    try:
        from backing_style_recipes import style_pattern_for_recipe, style_recipe_id

        _recipe_styles = {
            "Pop groove", "Pop", "Rock groove", "Jazz swing",
            "Bossa nova", "Funk groove", "Blues groove",
        }
        if style in _recipe_styles:
            pat = style_pattern_for_recipe(style_recipe_id(style), pulses=pulses if pulses in (4, 12) else 4)
            if pulses == base_pulses:
                return pat
            return _fit(pat)
    except ImportError:
        pass

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
    if not profile.get("style_locked") and profile.get("pop_soul"):
        return _fit({
            "bass_beats": [0, 1.5, 2.5, 3.5],
            "comp_beats": [0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2.5],
            "comp_dur": 0.40,
        })
    if not profile.get("style_locked") and profile.get("riff_driven"):
        return _fit({
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [0, 2],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "ghost_snare": [1.5, 3.5],
            "comp_dur": 0.26,
        })
    if not profile.get("style_locked") and profile.get("groove_based"):
        return _fit({
            "bass_beats": [0, 0.75, 1.5, 2, 2.75, 3.5],
            "comp_beats": [0.5, 1.25, 2.5, 3.25],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "ghost_snare": [0.5, 1.5, 2.5, 3.5],
            "kick_beats": [0, 1.5, 2.75],
            "comp_dur": 0.18,
        })
    if not profile.get("style_locked") and profile.get("acoustic_unplugged"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "cross_stick": [1.0],
            "comp_dur": 0.78,
        })
    if not profile.get("style_locked") and profile.get("vocal_ballad"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 3.5],
            "hat_beats": [0, 1, 2, 3],
            "snare_beats": [3.0],
            "kick_beats": [0, 2.5],
            "comp_dur": 0.62,
        })
    if not profile.get("style_locked") and profile.get("broadway_gospel"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "cross_stick": [1.0],
            "comp_dur": 0.52,
        })
    if not profile.get("style_locked") and profile.get("disney_cinematic"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5],
            "hat_beats": [0, 2],
            "snare_beats": [],
            "kick_beats": [0],
            "cross_stick": [2.0],
            "comp_dur": 0.88,
        })
    if not profile.get("style_locked") and profile.get("piano_centric"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "cross_stick": [1.0],
            "comp_dur": 0.82,
        })
    if not profile.get("style_locked") and profile.get("alt_rock_ballad"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 2, 2.5, 3.5],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2.5],
            "comp_dur": 0.52,
        })
    if not profile.get("style_locked") and profile.get("jewish_traditional"):
        return _fit({
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "cross_stick": [1.0],
            "comp_dur": 1.05,
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
    musical_profile=None,
    layers=None,
    strings: bool = False,
):
    """Render the backing track.

    ``strings`` adds the optional string section (arrangement setting).
    ``layers`` (diagnostics / tests) limits the mix to some of ``"rhythm"``
    (bass + drums), ``"keys"`` (piano comp) and ``"strings"``; ``None``
    renders every layer that is switched on.
    """

    timing = meter_timing(bpm, time_signature)
    pulse = timing.pulse_sec
    bar = timing.bar_sec
    pulses_per_bar = timing.pulses_per_bar
    event_cycle = _coerce_chord_events(chords)
    cycle_len = max(1, len(event_cycle))
    chord_list = event_cycle * max(1, int(loops))
    audio = np.zeros(int(sr * bar * len(chord_list)) + sr)
    keys_bus = np.zeros_like(audio)
    prev_comp: list[int] | None = None
    strings_bus = np.zeros_like(audio) if strings else None
    prev_strings: list[int] | None = None
    synth_style = style
    if musical_profile is not None:
        synth_style = musical_profile.canonical_style() or style
    song_profile = _song_backing_profile(song_title, song_artist, synth_style, bpm=bpm)
    if str(style or "").strip().lower() not in ("", "auto"):
        song_profile["style_locked"] = True
    patterns = _style_patterns(synth_style, song_profile, time_signature=timing.time_signature)
    if musical_profile is not None:
        try:
            from backing_style_recipes import apply_profile_to_synthesis

            song_profile, patterns = apply_profile_to_synthesis(
                style=synth_style,
                song_profile=song_profile,
                patterns=patterns,
                profile=musical_profile,
            )
        except ImportError:
            pass
    style = synth_style
    # The song's groove profile (drums / bass / comp rhythm per section role).
    # Song tweaks keep their values; the groove fills in what they left alone.
    groove = _groove_profiles.resolve_groove_profile(
        synth_style,
        song_profile_id=_arr_profiles.song_groove_profile_id(song_title, song_artist),
        time_signature=timing.time_signature,
    )
    if groove is not None:
        for _gk, _gv in groove.flags.items():
            if song_profile.get(_gk) == _arr_profiles.DEFAULT_PROFILE.get(_gk):
                song_profile[_gk] = _gv
    groove_seed = song_groove_seed(song_title, song_artist) if song_title else 0
    swing_amt = float(song_profile.get("swing", 0.0))
    if style == "Bossa nova":
        # Bossa nova is straight 8ths: song tweaks and feel text must not swing it.
        swing_amt = 0.0
    humanize = float(song_profile.get("humanize_ms", 0.012))
    kick_mul = float(song_profile.get("kick_push", 1.0))
    hat_mul = float(song_profile.get("hat_soft", 1.0))
    pocket_offset = float(song_profile.get("pocket_offset", 0.0))
    hat_open_ands = list(song_profile.get("hat_open_ands", []))
    outro_fade_bars = int(song_profile.get("outro_fade_bars", 0) or 0)
    drum_char = _style_drum_character(style)
    arr_char = _style_arrangement_character(style)
    bass_density = float(song_profile.get("bass_density", 1.0)) * float(song_profile.get("density_mul", 1.0))
    bossa_bass_state: dict[str, Any] = {"prev": None, "planned": None}

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
        # Song-specific section lifts (arrangement profile data).
        intensity = _arr_profiles.apply_section_lifts(song_profile, role, section_name, intensity)
        if groove is not None:
            intensity *= groove.dynamics(role)
            bar_patterns = groove.bar_grid(patterns, role, bpm=int(bpm))
        else:
            bar_patterns = patterns
        if song_profile.get("alt_rock_ballad") and role == "verse":
            intensity *= 0.90
        if song_profile.get("alt_rock_ballad") and role == "chorus":
            intensity *= 1.08
        if song_profile.get("alt_rock_ballad") and any(
            k in str(section_name).lower()
            for k in ("build", "instrumental", "ending", "final chorus")
        ):
            intensity *= 1.12
        section_edge = _is_section_edge(event, next_event)
        is_breakdown_recovery = idx in arr_ctx.bridge_recovery
        is_final_chorus_bar = arr_ctx.is_final_chorus_event(idx)
        if song_profile.get("alt_rock_ballad") and is_final_chorus_bar:
            intensity *= 1.06
        if song_profile.get("jewish_traditional") and role == "verse":
            intensity *= 0.88
        if song_profile.get("jewish_traditional") and "instrumental" in str(section_name).lower():
            intensity *= 0.94
        if song_profile.get("jewish_traditional") and (
            "verse 4" in str(section_name).lower() or "outro" in str(section_name).lower()
        ):
            intensity *= 1.04
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
        bass_hits = bar_patterns["bass_beats"]
        if groove_seed % 3 == 0 and role == "verse":
            bass_hits = bass_hits[: max(2, len(bass_hits) - 1)]
        comp_wave = _comp_wave_for_style(style, role, song_profile)

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
        elif style == "Bossa nova" and not bar_is_no_chord:
            bossa_notes = _bossa_bass_bar(
                chord,
                next_chord,
                pulses_per_bar,
                bossa_bass_state,
                np.random.default_rng(idx * 7919 + groove_seed * 131 + loop_seed),
                density=bass_density * (0.85 if role == "verse" else 1.0),
                phrase_end=section_edge or int(event.get("bar_in_section", 0) or 0) % 4 == 3,
            )
            bass_vol = 0.11 * intensity * arr_char["bass_vol_mul"]
            for n, (b, beats, bass_pitch, accent) in enumerate(bossa_notes):
                t_hit = _humanize_time(
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    seed=idx * 41 + n + groove_seed + loop_seed,
                    amount=humanize * 0.6,
                    beat_len=pulse,
                )
                # Legato: each note rings into the next one, minus a small breath.
                _add_tone(
                    audio,
                    sr,
                    t_hit,
                    max(0.05, beats * pulse - min(0.03, 0.08 * pulse)),
                    bass_pitch,
                    _humanize_volume(bass_vol * accent, idx * 41 + n + loop_seed),
                    "bass_upright",
                )
        else:
            hit_beats = list(bass_hits)
            seg_starts = [0.0]
            if bar_is_subdivided:
                # A chord that starts between two hits gets its own bass note on the beat it
                # starts (pushed chords already get an anticipation attack below).
                _subs = _sub_parse_subdivisions(chord, beats_per_bar=pulses_per_bar)
                seg_starts = [sum(float(s.weight) for s in _subs[:i]) for i in range(len(_subs))]
                hit_beats = sorted(set(hit_beats) | {
                    s for s, sub in zip(seg_starts, _subs)
                    if not sub.push and all(abs(s - h) > 0.01 for h in hit_beats)
                })
            sounded_segs: set[int] = set()
            for n, b in enumerate(hit_beats):
                if bar_is_no_chord:
                    break  # tacet — bass lays out for the whole bar
                pulse_chord = _pulse_chord(b)
                pulse_next = _pulse_next_chord(b)
                if is_no_chord_token(pulse_chord):
                    continue  # bar contains an N.C. sub-segment
                bass_pitch = _bass_motion_pitch(pulse_chord, pulse_next, style, n, len(hit_beats),
                                                beat=b, pulses_per_bar=pulses_per_bar)
                if bar_is_subdivided:
                    seg_i = sum(1 for s in seg_starts if s <= b + 0.01) - 1
                    if seg_i not in sounded_segs:
                        # The first note of each chord in the bar is that chord's bass (slash note).
                        sounded_segs.add(seg_i)
                        bass_pitch = _bass_register(bass_note(pulse_chord))
                bass_dur = pulse * (0.72 if style in ["Ballad", "Jazz swing"] else 0.50)
                bass_dur *= arr_char["bass_dur_mul"]
                if style == "Funk groove":
                    bass_dur = pulse * 0.18
                elif style == "Blues groove":
                    bass_dur = pulse * 0.62
                elif style == "Rock groove":
                    bass_dur = pulse * 0.36
                elif style in ("Pop groove", "Pop"):
                    bass_dur = pulse * 0.48
                elif style == "Bossa nova":
                    bass_dur = pulse * 0.58
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
                        * intensity
                        * arr_char["bass_vol_mul"],
                        idx * 41 + n + loop_seed,
                    ),
                    "bass",
                )

        # ----- Chord comping -------------------------------------------
        if bar_is_hit and not bar_is_no_chord:
            # Single chord stab on beat 1, brighter and shorter than
            # a normal comping hit — the punctuation that makes a
            # hit bar sound like a band stop.
            stab_voicing = _kv.lead_voicing(_voicing_for_comp(sounding_chord, level, style, 0), prev_comp)
            prev_comp = stab_voicing or prev_comp
            stab_dur = pulse * 0.32
            stab_vol = 0.034 * intensity
            t_stab = _humanize_time(
                bar_start,
                seed=idx * 53 + loop_seed,
                amount=humanize * 0.4,
                beat_len=pulse,
            )
            _add_comp_chord(
                keys_bus, sr, t_stab, stab_dur, stab_voicing, stab_vol, comp_wave,
                beat=0, seed=idx * 53 + loop_seed, pulses_per_bar=pulses_per_bar,
            )
        else:
            for comp_idx, b in enumerate(bar_patterns["comp_beats"]):
                if bar_is_no_chord:
                    break  # tacet — chord comping lays out for the whole bar
                if is_no_chord_token(_pulse_chord(b)):
                    continue  # bar contains an N.C. sub-segment
                if role == "verse" and comp_idx % 3 == 2 and not song_profile.get("anthem_rock"):
                    continue
                if role == "intro" and comp_idx > 1:
                    continue
                dur = pulse * bar_patterns.get("comp_dur", 0.45)
                if role == "chorus":
                    dur *= 1.18 if song_profile.get("anthem_rock") else 1.15
                elif role == "bridge":
                    dur *= 0.95
                elif song_profile.get("latin_relaxed"):
                    dur *= 0.88
                # Voice-led into the comp register: nearest inversion / octave to
                # the previous chord, above the bass and below the lead.
                voicing = _kv.lead_voicing(_voicing_for_comp(_pulse_chord(b), level, style, comp_idx), prev_comp)
                prev_comp = voicing or prev_comp
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
                if song_profile.get("alt_rock_ballad"):
                    comp_vol *= 0.72 if role == "verse" else 0.92
                    if role == "chorus":
                        comp_vol *= 1.06
                    if any(
                        k in str(section_name).lower()
                        for k in ("build", "instrumental", "ending", "final")
                    ):
                        comp_vol *= 1.05
                    dur *= 1.02 if role == "chorus" else 0.96
                if song_profile.get("jewish_traditional"):
                    comp_vol *= 0.62 if role == "verse" else 0.74
                    if "instrumental" in str(section_name).lower():
                        comp_vol *= 0.88
                    if "verse 4" in str(section_name).lower():
                        comp_vol *= 1.06
                    if "outro" in str(section_name).lower():
                        comp_vol *= 0.92
                    dur *= 1.10
                # ----- Style articulation ----------------------------
                # Shape the comp attack/sustain so each style's chords
                # read characteristically by ear, not just by timing.
                if style == "Funk groove":
                    dur = min(dur, pulse * 0.10)
                    comp_vol *= 1.55
                elif style == "Rock groove":
                    dur = min(dur, pulse * 0.42)
                    comp_vol *= 1.50
                elif style == "Jazz swing":
                    comp_vol *= 0.48
                    dur = min(dur, pulse * 0.30)
                elif style == "Bossa nova":
                    comp_vol *= 0.72
                    dur *= 1.28
                elif style == "Blues groove":
                    dur *= 1.38
                    comp_vol *= 1.18
                elif style in ("Pop groove", "Pop"):
                    comp_vol *= 0.68
                    dur = min(dur, pulse * 0.30)
                comp_vol *= arr_char["comp_vol_mul"]
                if song_profile.get("comp_stab"):
                    dur *= 0.55
                    comp_vol *= 1.2
                t_comp = _humanize_time(
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    seed=idx * 53 + comp_idx + loop_seed,
                    amount=humanize * 0.7,
                    beat_len=pulse,
                )
                # A comp chord is held no longer than its chord: ringing past the
                # bar line sounded the old harmony over the new one (Eb over Bb in
                # Bossa). Written anticipations come through push markers instead.
                dur = max(0.03, min(dur, bar_start + bar - t_comp - 0.01))
                _add_comp_chord(
                    keys_bus, sr, t_comp, dur, voicing, comp_vol, comp_wave,
                    beat=b, seed=idx * 53 + comp_idx + loop_seed, pulses_per_bar=pulses_per_bar,
                    roll=bool(style == "Ballad" and dur >= pulse * 0.5),
                )

        # ----- Strings (optional) ----------------------------------------
        # One sustained, voice-led chord per chord segment of the bar -- the
        # same segments the chord timeline highlights -- with a slow bow attack
        # and a release that overlaps the next chord. Laid out on N.C. / hit bars.
        if strings_bus is not None and not bar_is_no_chord and not bar_is_hit:
            if bar_is_subdivided:
                _segs = []
                _cursor = 0.0
                for _sub in _sub_parse_subdivisions(chord, beats_per_bar=pulses_per_bar):
                    _segs.append((_cursor, float(_sub.weight), _sub.chord))
                    _cursor += float(_sub.weight)
            else:
                _segs = [(0.0, float(pulses_per_bar), chord)]
            _s_level, _s_low, _s_high, _s_voices = _kv.strings_style(style)
            _s_role = {"verse": 0.82, "intro": 0.85, "pre": 0.95, "chorus": 1.1, "bridge": 0.95}.get(role, 0.9)
            for _beat0, _beats, _seg_chord in _segs:
                if is_no_chord_token(_seg_chord):
                    continue
                _tones = chord_notes(_sub_primary_chord(_seg_chord) or _seg_chord)
                _svoice = _kv.strings_voicing(_tones, prev_strings, style)
                prev_strings = _svoice or prev_strings
                _t0 = bar_start + _beat0 * pulse
                for _note in _svoice:
                    _kv.add_string_note(
                        strings_bus, sr, _t0, _beats * pulse, _note,
                        0.02 * _s_level * _s_role * min(1.25, intensity),
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

        if not bar_drums_silent and not bar_bridge_breakdown and not drum_char.get("suppress_hats"):
            bar_open_ands = list(bar_patterns.get("hat_open_ands", hat_open_ands))
            for b in bar_patterns["hat_beats"]:
                hat_vol = (0.006 if style == "Ballad" else 0.010) * hat_mul * drum_char["hat_vol_mul"]
                if role == "chorus":
                    hat_vol *= 1.28
                if groove is not None:
                    hat_vol *= groove.hat_accent(b)
                is_open_hat = any(abs(b - oa) < 0.06 for oa in bar_open_ands)
                hat_t = _humanize_time(
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    seed=idx * 31 + int(b * 100) + loop_seed,
                    amount=humanize * 0.5,
                    beat_len=pulse,
                )
                if drum_char["use_ride"]:
                    # Spang-a-lang: loud downbeats, softer skip beats.
                    is_accent = float(b) == int(float(b))
                    ride_vol = hat_vol * (2.8 if is_accent else 1.0) * drum_char["ride_vol_mul"]
                    _add_ride(
                        audio,
                        sr,
                        hat_t,
                        ride_vol * intensity,
                        seed=idx * 31 + int(b * 100) + loop_seed,
                    )
                    continue
                hat_dur = 0.090 if is_open_hat else 0.028
                hat_vol_local = hat_vol
                if is_open_hat:
                    hat_vol_local *= 1.35
                _add_noise_hit(
                    audio,
                    sr,
                    hat_t,
                    hat_dur,
                    hat_vol_local * intensity,
                    seed=idx * 31 + int(b * 100) + (groove_seed % 997) + loop_seed,
                    tone=drum_char["hat_tone"],
                )

        if not bar_drums_silent and not bar_bridge_breakdown and not drum_char.get("suppress_snare"):
            for b in bar_patterns["snare_beats"]:
                snare_vol = 0.040 * intensity * drum_char["snare_vol_mul"]
                if song_profile.get("cross_stick") and style != "Bossa nova":
                    snare_vol *= 0.65
                _add_snare(
                    audio,
                    sr,
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    _humanize_volume(snare_vol, idx * 67 + int(b * 100) + loop_seed),
                    crack=drum_char["snare_crack"],
                    seed=idx * 67 + int(b * 100) + loop_seed,
                )

        if not bar_drums_silent and not bar_bridge_breakdown:
            for b in bar_patterns.get("ghost_snare", []):
                _add_snare(
                    audio,
                    sr,
                    _groove_time(bar_start, b, pulse, style, swing=swing_amt, pocket=pocket_offset),
                    0.014 * intensity * drum_char["snare_vol_mul"] * drum_char["ghost_vol_mul"],
                    crack=drum_char["snare_crack"] * 0.7,
                    seed=idx * 71 + int(b * 50) + loop_seed,
                )

        # Cross-stick keeps its 2/4 colouring even on a bridge
        # dropout — that's the only piece of the kit that stays so
        # the listener still has a pulse reference to count against.
        if not bar_drums_silent:
            cross_beats = bar_patterns.get("cross_stick", [])
            if bar_bridge_breakdown and not cross_beats:
                # Bridge bar without baked-in cross-stick gets a soft
                # 2 & 4 click so the dropout still has a pulse.
                cross_beats = [b for b in (1.0, 3.0) if b < pulses_per_bar]
            for b in cross_beats:
                _add_noise_hit(
                    audio,
                    sr,
                    _groove_time(bar_start, b, pulse, style),
                    0.050,
                    0.028 * intensity * drum_char["cross_stick_vol_mul"] * (0.85 if bar_bridge_breakdown else 1.0),
                    seed=idx * 73 + int(b * 40) + loop_seed,
                    tone=0.45,
                )

        if not bar_drums_silent:
            kick_beats = bar_patterns["kick_beats"]
            if bar_bridge_breakdown:
                # Pull kicks down to just beat 1 (and beat 3 in 4/4)
                # so the bridge breakdown reads as dropout, not as a
                # full bar of drums under N.C.
                kick_beats = [b for b in kick_beats if b in (0.0, 2.0)]
            kick_vol_mul = 0.78 if bar_bridge_breakdown else 1.0
            for b in kick_beats:
                _add_kick(
                    audio,
                    sr,
                    _humanize_time(
                        bar_start + b * pulse,
                        seed=idx * 83 + int(b * 10) + loop_seed,
                        amount=humanize * 0.35,
                        beat_len=pulse,
                    ),
                    _humanize_volume(
                        0.095 * intensity * kick_mul * kick_vol_mul * drum_char["kick_vol_mul"],
                        idx * 83 + loop_seed,
                    ),
                    punch=drum_char["kick_punch"],
                    seed=idx * 83 + int(b * 10) + loop_seed,
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
                and style not in ("Ballad", "Bossa nova")  # Bossa writes its own "and" of 4
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
                        # next downbeat, in the octave it is played
                        # (C2 .. B2), not the one nearest this root.
                        here = _bass_register(cur_root)
                        target = _bass_register(nxt_root)
                        approach_pitch = (
                            target - 1 if target > here else target + 1
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

        # Phrase-end fill inside a section (the groove's lighter version).
        if (
            groove is not None
            and groove.phrase_fill_bars
            and not section_edge
            and not bar_drums_silent
            and not bar_is_no_chord
            and (int(event.get("bar_in_section", 0) or 0) + 1) % groove.phrase_fill_bars == 0
        ):
            _add_groove_fill(
                audio, sr, bar_start, pulse, pulses_per_bar, groove.fill, intensity * 0.8,
                seed_base=idx, light=True,
            )

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
            if groove is None:
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
            elif not bar_drums_silent:
                _add_groove_fill(
                    audio, sr, bar_start, pulse, pulses_per_bar, groove.fill,
                    intensity * max(0.7, min(1.3, next_intensity_estimate)), seed_base=idx,
                )
                if next_role_for_fill == "chorus" and groove.fill != "none":
                    _add_crash(audio, sr, bar_start + bar, intensity * (1.3 if into_final_chorus else 1.0), seed=idx)
            tail = max(0.0, pulses_per_bar - 0.45)
            tail_chord = _pulse_chord(tail)
            tail_next = next_chord if not bar_is_subdivided else (
                _sub_primary_chord(next_chord) if next_chord else None
            )
            # Skip the pickup bass note if this bar (or its tail
            # segment) is tacet — N.C. bars shouldn't suddenly fire a
            # bass attack just because a section ends.
            # Bossa's own bar line already leads into the next section.
            if not bar_is_no_chord and not is_no_chord_token(tail_chord) and style != "Bossa nova":
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
                and style != "Bossa nova"
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
                        if style != "Bossa nova":  # Bossa's bar line already plays the pushed chord
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
                        push_voicing = _kv.lead_voicing(_voicing_for_comp(sub.chord, level, style, 0), prev_comp)
                        prev_comp = push_voicing or prev_comp
                        _add_comp_chord(
                            keys_bus, sr, bar_start + push_b * pulse, pulse * 0.55, push_voicing,
                            0.020 * intensity, comp_wave,
                            beat=push_b, seed=idx * 59 + loop_seed, pulses_per_bar=pulses_per_bar,
                        )
                    beat_cursor += float(sub.weight)

    # Keys bus level per style, relative to the rhythm section (bass + drums):
    # the old per-style comp multipliers were tuned for a sustained organ and
    # left the piano at 0.05x the rhythm in Jazz and 0.2x in Pop / Bossa.
    _rhythm_rms = float(np.sqrt(np.mean(audio ** 2)))
    _keys_rms = float(np.sqrt(np.mean(keys_bus ** 2)))
    if _rhythm_rms > 1e-6 and _keys_rms > 1e-6:
        _target = _KEYS_BALANCE.get(style, 0.55) * float(song_profile.get("keys_level", 1.0))
        keys_bus *= float(np.clip(_target * _rhythm_rms / _keys_rms, 0.25, 12.0))
    if strings_bus is not None:
        _strings_rms = float(np.sqrt(np.mean(strings_bus ** 2)))
        if _rhythm_rms > 1e-6 and _strings_rms > 1e-6:
            # Supportive, never on top: a fraction of the piano's level, and
            # less where the style's groove needs the space (strings_style).
            _s_target = (
                _KEYS_BALANCE.get(style, 0.55)
                * 0.55
                * _kv.strings_style(style)[0]
                * float(song_profile.get("strings_level", 1.0))
            )
            strings_bus *= float(np.clip(_s_target * _rhythm_rms / _strings_rms, 0.05, 20.0))
    LAST_MIX_STATS.clear()
    LAST_MIX_STATS.update(
        rhythm_rms=float(np.sqrt(np.mean(audio ** 2))),
        keys_rms=float(np.sqrt(np.mean(keys_bus ** 2))),
        strings_rms=float(np.sqrt(np.mean(strings_bus ** 2))) if strings_bus is not None else 0.0,
    )
    want = {"rhythm", "keys", "strings"} if layers is None else set(layers)
    if "rhythm" not in want:
        audio[:] = 0.0
    if "keys" in want:
        audio += keys_bus
    if strings_bus is not None and "strings" in want:
        audio += strings_bus
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
    *,
    mood: str = "",
    intensity: str = "",
    musical_profile=None,
    strings: bool = False,
):

    if musical_profile is None and (mood or intensity):
        try:
            from backing_musical_profile import resolve_backing_musical_profile

            musical_profile = resolve_backing_musical_profile(
                style=style,
                mood=mood,
                intensity=intensity,
                tempo=int(bpm),
                level=level,
                time_signature=time_signature,
            )
        except ImportError:
            musical_profile = None

    audio, sr = synthesize_chords_to_numpy(
        chords,
        bpm=bpm,
        loops=loops,
        style=style,
        level=level,
        song_title=song_title,
        song_artist=song_artist,
        time_signature=time_signature,
        musical_profile=musical_profile,
        strings=bool(strings),
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
