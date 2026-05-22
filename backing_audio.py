"""Backing track synthesis and groove inference (no Streamlit UI)."""

from __future__ import annotations

import io
import wave

import numpy as np

from music_theory import NOTE_TO_MIDI, normalize_root, split_chord

try:
    from practice_studio import song_groove_seed
except ImportError:

    def song_groove_seed(title: str, artist: str = "") -> int:
        return 0


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
    parts = str(chord).strip().split("/", 1)
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


def _freq(midi_num):
    return 440 * (2 ** ((midi_num - 69) / 12))


def _add_tone(audio, sr, start_sec, dur_sec, midi_num, volume, wave_type="sine"):
    start = int(start_sec * sr)
    if start >= len(audio) or dur_sec <= 0:
        return
    n = max(1, int(dur_sec * sr))
    end = min(len(audio), start + n)
    n = end - start
    t = np.linspace(0, dur_sec, n, False)
    if wave_type == "bass":
        sig = np.sin(2 * np.pi * _freq(midi_num) * t)
        sig += 0.35 * np.sin(2 * np.pi * _freq(midi_num) * 2 * t)
    elif wave_type == "organ":
        sig = np.sin(2 * np.pi * _freq(midi_num) * t)
        sig += 0.25 * np.sin(2 * np.pi * _freq(midi_num + 12) * t)
    else:
        sig = np.sin(2 * np.pi * _freq(midi_num) * t)
    attack = max(1, int(0.01 * sr))
    release = max(1, int(min(0.08, dur_sec * 0.35) * sr))
    env = np.ones(n)
    env[:min(attack, n)] = np.linspace(0, 1, min(attack, n))
    env[-min(release, n):] *= np.linspace(1, 0.02, min(release, n))
    audio[start:end] += sig * env * volume


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


def _groove_time(bar_start, beat, beat_len, style):
    if style == "Jazz swing" and beat % 1:
        return bar_start + (beat + 0.08) * beat_len
    if style == "Funk groove" and beat % 1:
        return bar_start + (beat - 0.02) * beat_len
    return bar_start + beat * beat_len


def _add_section_transition_fill(
    audio,
    sr,
    bar_start,
    beat,
    bar_len,
    style,
    role,
    next_event,
    intensity,
    *,
    seed_base: int,
):
    """Drum fill and lift between sections."""
    fill_start = bar_start + 3.2 * beat
    next_role = _section_role(next_event.get("section")) if next_event else "neutral"
    for i, off in enumerate([0.0, 0.5, 1.0, 1.5, 2.0, 2.5]):
        _add_noise_hit(
            audio,
            sr,
            fill_start + off * beat * 0.15,
            0.04,
            0.022 * intensity,
            seed=seed_base * 17 + i,
        )
    if next_role == "chorus":
        for t, freq in [(3.5, 200), (3.65, 260), (3.8, 330)]:
            _add_tone(audio, sr, bar_start + t * beat, 0.06, freq, 0.04 * intensity, "bass")
    elif next_role == "bridge":
        _add_tone(audio, sr, bar_start + 3.4 * beat, 0.12, 90, 0.05 * intensity, "organ")
    if role == "intro":
        _add_noise_hit(audio, sr, bar_start + 0.1 * beat, 0.08, 0.012 * intensity, seed=seed_base * 3)


def _comp_wave_for_style(style: str, role: str) -> str:
    if style == "Ballad":
        return "organ"
    if style == "Rock groove" and role == "chorus":
        return "sine"
    return "organ"


def _style_patterns(style):
    if style == "Jazz swing":
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [1.0, 2.65, 3.65],
            "hat_beats": [0, 1.65, 2, 3.65],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "comp_dur": 0.45,
        }
    if style == "Bossa nova":
        return {
            "bass_beats": [0, 1.5, 2, 3.5],
            "comp_beats": [0.0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 0.5, 1.5, 2, 2.5, 3.5],
            "snare_beats": [1.5, 3.5],
            "kick_beats": [0, 2],
            "comp_dur": 0.32,
        }
    if style == "Funk groove":
        return {
            "bass_beats": [0, 0.75, 1.5, 2, 2.75, 3.5],
            "comp_beats": [0.75, 1.75, 2.5, 3.25],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 1.5, 2.75],
            "comp_dur": 0.22,
        }
    if style == "Rock groove":
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [0, 1, 2, 3],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "comp_dur": 0.50,
        }
    if style == "Ballad":
        return {
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5, 3.5],
            "hat_beats": [0, 1, 2, 3],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "comp_dur": 0.90,
        }
    return {
        "bass_beats": [0, 2],
        "comp_beats": [0, 1.5, 2.5, 3.5],
        "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
        "snare_beats": [1.0, 3.0],
        "kick_beats": [0, 2.5],
        "comp_dur": 0.38,
    }


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
):

    beat = 60 / bpm
    bar = beat * 4
    event_cycle = _coerce_chord_events(chords)
    chord_list = event_cycle * max(1, int(loops))
    audio = np.zeros(int(sr * bar * len(chord_list)) + sr)
    patterns = _style_patterns(style)
    groove_seed = song_groove_seed(song_title, song_artist) if song_title else 0

    for idx, event in enumerate(chord_list):

        chord = event["chord"]
        next_event = chord_list[idx + 1] if idx + 1 < len(chord_list) else None
        next_chord = next_event["chord"] if next_event else None
        bar_start = idx * bar
        section_name = event.get("section", "Practice Loop")
        intensity = _section_intensity(section_name, style)
        role = _section_role(section_name)
        section_edge = _is_section_edge(event, next_event)
        notes = chord_notes(chord)
        bass_hits = patterns["bass_beats"]
        if groove_seed % 3 == 0 and role == "verse":
            bass_hits = bass_hits[: max(2, len(bass_hits) - 1)]
        comp_wave = _comp_wave_for_style(style, role)

        for n, b in enumerate(bass_hits):
            bass_pitch = _bass_motion_pitch(chord, next_chord, style, n, len(bass_hits))
            bass_dur = beat * (0.72 if style in ["Ballad", "Jazz swing"] else 0.50)
            if style == "Funk groove":
                bass_dur = beat * 0.32
            _add_tone(
                audio,
                sr,
                _groove_time(bar_start, b, beat, style),
                bass_dur,
                bass_pitch,
                0.11 * intensity,
                "bass",
            )

        for comp_idx, b in enumerate(patterns["comp_beats"]):
            if role == "verse" and comp_idx % 3 == 2:
                continue
            if role == "intro" and comp_idx > 1:
                continue
            dur = beat * patterns.get("comp_dur", 0.45)
            if role == "chorus":
                dur *= 1.15
            elif role == "bridge":
                dur *= 0.95
            voicing = _voicing_for_comp(chord, level, style, comp_idx)
            comp_vol = 0.022 * intensity
            if role == "verse":
                comp_vol *= 0.72
            elif role == "chorus":
                comp_vol *= 1.12
            for note in voicing:
                _add_tone(
                    audio,
                    sr,
                    _groove_time(bar_start, b, beat, style),
                    dur,
                    note,
                    comp_vol,
                    comp_wave,
                )

        for b in patterns["hat_beats"]:
            hat_vol = 0.007 if style == "Ballad" else 0.011
            if role == "chorus":
                hat_vol *= 1.25
            _add_noise_hit(
                audio,
                sr,
                _groove_time(bar_start, b, beat, style),
                0.030,
                hat_vol * intensity,
                seed=idx * 31 + int(b * 100) + (groove_seed % 997),
            )

        for b in patterns["snare_beats"]:
            _add_noise_hit(
                audio,
                sr,
                _groove_time(bar_start, b, beat, style),
                0.055,
                0.030 * intensity,
                seed=idx * 67 + int(b * 100),
            )

        for b in patterns["kick_beats"]:
            _add_tone(
                audio,
                sr,
                bar_start + b * beat,
                0.07,
                36,
                0.070 * intensity,
                "bass",
            )

        if section_edge:
            _add_section_transition_fill(
                audio,
                sr,
                bar_start,
                beat,
                bar,
                style,
                role,
                next_event,
                intensity,
                seed_base=idx,
            )
            approach = _bass_motion_pitch(chord, next_chord, style, len(bass_hits) - 1, len(bass_hits))
            _add_tone(audio, sr, bar_start + 3.55 * beat, beat * 0.25, approach, 0.075 * intensity, "bass")
            _add_noise_hit(audio, sr, bar_start + 3.75 * beat, 0.050, 0.018 * intensity, seed=idx * 101)
            if next_event and _section_role(next_event.get("section")) == "chorus":
                _add_tone(audio, sr, bar_start + 3.88 * beat, 0.09, 48, 0.055, "bass")

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
):

    audio, sr = synthesize_chords_to_numpy(
        chords,
        bpm=bpm,
        loops=loops,
        style=style,
        level=level,
        song_title=song_title,
        song_artist=song_artist,
    )
    return pcm16_wav_bytes_from_float(audio, sr)


def backing_bytes_to_float(chords, bpm=100, style="Pop groove", level="Intermediate"):

    y, _sr = synthesize_chords_to_numpy(
        chords,
        bpm=bpm,
        loops=1,
        style=style,
        level=level,
    )
    return y


def wav_bytes_from_float(audio, sr=44100):

    return pcm16_wav_bytes_from_float(audio, sr)
