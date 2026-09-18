"""Audition backing (and optional melody) audio for Composition Studio."""

from __future__ import annotations

import base64
import html
import io
import math
import re
import struct
import wave
from typing import Any

from composition_document import chords_for_playback, playback_globals, section_by_id, section_melody_events

COMPOSER_PREVIEW_NONCE_KEY = "composer_preview_nonce"
COMPOSER_PREVIEW_AUTOPLAY_KEY = "composer_preview_autoplay"
COMPOSER_PREVIEW_SLOT_KEY = "composer_preview_slot"
COMPOSER_PREVIEW_LABEL_KEY = "composer_preview_label"
COMPOSER_PREVIEW_COUNT_IN_KEY = "composer_preview_count_in_bars"
_MIN_PLAYABLE_PEAK = 0.02
_MIN_PLAYABLE_SECONDS = 0.2


def preview_signature(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    loops: int = 2,
    chord_override: list[str] | None = None,
    include_melody: bool = False,
    melody_override: list[dict[str, Any]] | None = None,
) -> tuple:
    pg = playback_globals(doc)
    if chord_override is not None:
        chords = [str(c) for c in chord_override if str(c).strip()]
    else:
        chords = chords_for_playback(doc, scope=scope, section_id=section_id)
    mel_sig: tuple = ()
    if include_melody:
        events = melody_override if melody_override is not None else _resolve_melody_events(doc, section_id)
        mel_sig = tuple(
            (str(e.get("pitch") or ""), float(e.get("duration_beats") or 1.0), float(e.get("beat") or 0.0))
            for e in events
        )
    return (
        str(doc.get("id") or ""),
        scope,
        section_id or "",
        tuple(chords),
        pg["bpm"],
        pg["time_signature"],
        pg["style"],
        pg["groove"],
        int(loops),
        bool(include_melody),
        mel_sig,
    )


def _resolve_melody_events(doc: dict[str, Any], section_id: str | None) -> list[dict[str, Any]]:
    if not section_id:
        return []
    sec = section_by_id(doc, section_id)
    return section_melody_events(sec)


def _beats_per_bar(time_signature: str) -> float:
    text = str(time_signature or "4/4").strip()
    if "/" in text:
        try:
            num, _den = text.split("/", 1)
            return float(int(num))
        except ValueError:
            return 4.0
    return 4.0


def _midi_to_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((int(midi) - 69) / 12.0))


def _pitch_to_midi(pitch: str, fallback: int = 60) -> int:
    from music_theory import NOTE_TO_MIDI, split_chord

    text = str(pitch or "").strip()
    if not text:
        return fallback
    # Optional octave digit: C4, Eb5
    if text[-1].isdigit():
        octv = int(text[-1])
        name = text[:-1]
        root, _ = split_chord(name)
        base = NOTE_TO_MIDI.get(root) or NOTE_TO_MIDI.get(root.replace("b", ""))
        if base is None:
            return fallback
        # NOTE_TO_MIDI is around octave 4 (C=60). Adjust relative octave.
        return int(base + (octv - 4) * 12)
    root, _ = split_chord(text)
    return int(NOTE_TO_MIDI.get(root) or NOTE_TO_MIDI.get(root.replace("b", "")) or fallback)


def _wav_to_mono_floats(wav_bytes: bytes) -> tuple[list[float], int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if sampwidth != 2:
        # Only PCM16 expected from backing_audio.
        return [], sr
    count = len(frames) // 2
    samples = list(struct.unpack("<" + "h" * count, frames))
    if channels > 1:
        mono = [
            sum(samples[i : i + channels]) / float(channels)
            for i in range(0, len(samples), channels)
        ]
    else:
        mono = [float(s) for s in samples]
    return [s / 32768.0 for s in mono], sr


def _floats_to_wav_bytes(samples: list[float], sr: int) -> bytes:
    clipped = [max(-1.0, min(1.0, float(s))) for s in samples]
    pcm = [int(s * 32767.0) for s in clipped]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sr))
        wf.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))
    return buf.getvalue()


def _mix_melody_onto_backing(
    wav_bytes: bytes,
    events: list[dict[str, Any]],
    *,
    bpm: int,
    time_signature: str = "4/4",
    loops: int = 1,
    melody_gain: float = 0.45,
    backing_gain: float = 0.85,
    count_in_sec: float = 0.0,
) -> bytes:
    if not events or not wav_bytes:
        return wav_bytes
    mono, sr = _wav_to_mono_floats(wav_bytes)
    if not mono:
        return wav_bytes
    seconds_per_beat = 60.0 / max(40.0, float(bpm))
    bpb = _beats_per_bar(time_signature)
    count_in_offset_samples = int(max(0.0, float(count_in_sec)) * sr)
    # Melody may be shorter than looped backing — repeat softly to fill.
    body_samples = max(0, len(mono) - count_in_offset_samples)
    total_beats = body_samples / float(sr) / seconds_per_beat
    bg = max(0.05, min(1.0, float(backing_gain)))
    mg = max(0.05, min(1.2, float(melody_gain)))
    out = [s * bg for s in mono]
    gain = mg
    for loop_i in range(max(1, int(loops))):
        loop_offset = loop_i * max(bpb, sum(float(e.get("duration_beats") or 1.0) for e in events))
        if loop_offset > total_beats + 0.5:
            break
        for ev in events:
            if ev.get("is_rest") or str(ev.get("pitch") or "").strip().lower() == "rest":
                continue
            midi = ev.get("midi")
            try:
                midi_i = int(midi) if midi is not None else _pitch_to_midi(str(ev.get("pitch") or ""))
            except (TypeError, ValueError):
                midi_i = _pitch_to_midi(str(ev.get("pitch") or ""))
            start_beat = float(ev.get("beat") or 0.0) + loop_offset
            dur_beats = float(ev.get("duration_beats") or 1.0)
            start = count_in_offset_samples + int(start_beat * seconds_per_beat * sr)
            length = int(dur_beats * seconds_per_beat * sr)
            if start >= len(out) or length <= 0:
                continue
            end = min(len(out), start + length)
            hz = _midi_to_hz(midi_i)
            for i in range(start, end):
                t = (i - start) / float(sr)
                # Soft attack / release envelope
                env = 1.0
                attack = min(0.02, (end - start) / float(sr) * 0.2)
                release = min(0.05, (end - start) / float(sr) * 0.3)
                local_t = t
                local_end = (end - start) / float(sr)
                if attack > 0 and local_t < attack:
                    env = local_t / attack
                elif release > 0 and local_t > local_end - release:
                    env = max(0.0, (local_end - local_t) / release)
                out[i] += gain * env * math.sin(2.0 * math.pi * hz * t)
    # Prevent clipping
    peak = max(abs(s) for s in out) if out else 1.0
    if peak > 0.98:
        scale = 0.98 / peak
        out = [s * scale for s in out]
    return _floats_to_wav_bytes(out, sr)


def _mix_recorded_audio_onto_backing(
    wav_bytes: bytes,
    recorded_bytes: bytes,
    *,
    recorded_trim_sec: float = 0.0,
    melody_gain: float = 0.55,
    backing_gain: float = 0.75,
) -> bytes:
    """Overlay the user's exact microphone take onto chord backing (no synth substitute).

    ``recorded_trim_sec`` skips count-in / pre-roll already present in the capture so
    the performance aligns with beat 0 of the chord body.
    """
    if not wav_bytes or not recorded_bytes:
        return wav_bytes
    mono, sr = _wav_to_mono_floats(wav_bytes)
    if not mono:
        return wav_bytes
    rec = _decode_recorded_mono(recorded_bytes, target_sr=sr)
    if not rec:
        return wav_bytes
    trim = max(0, int(float(recorded_trim_sec or 0.0) * sr))
    if trim >= len(rec):
        return wav_bytes
    rec = rec[trim:]
    bg = max(0.05, min(1.0, float(backing_gain)))
    mg = max(0.05, min(1.5, float(melody_gain)))
    out = [s * bg for s in mono]
    end = min(len(out), len(rec))
    for i in range(end):
        out[i] = out[i] + rec[i] * mg
    peak = max((abs(s) for s in out), default=0.0)
    if peak > 1.0:
        scale = 0.95 / peak
        out = [s * scale for s in out]
    return _floats_to_wav_bytes(out, sr)


def _decode_recorded_mono(recorded_bytes: bytes, *, target_sr: int) -> list[float]:
    """Decode mic capture to mono floats at ``target_sr``."""
    raw = bytes(recorded_bytes or b"")
    if not raw:
        return []
    # Prefer librosa (handles webm/ogg/wav from st.audio_input).
    try:
        from composition_hum_transcription import load_hum_audio_mono

        y, sr = load_hum_audio_mono(raw, sr=int(target_sr))
        return [float(s) for s in list(y)]
    except Exception:
        pass
    # Fallback: PCM WAV only
    try:
        mono, sr = _wav_to_mono_floats(raw)
        if not mono:
            return []
        if int(sr) == int(target_sr):
            return mono
        # Naive linear resample
        if sr <= 0 or target_sr <= 0:
            return mono
        ratio = float(target_sr) / float(sr)
        n = max(1, int(len(mono) * ratio))
        out: list[float] = []
        for i in range(n):
            src = i / ratio
            j = int(src)
            frac = src - j
            a = mono[j] if j < len(mono) else 0.0
            b = mono[j + 1] if j + 1 < len(mono) else a
            out.append(a + (b - a) * frac)
        return out
    except Exception:
        return []


def generate_preview_wav(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    loops: int = 2,
    level: str = "Intermediate",
    chord_override: list[str] | None = None,
    include_melody: bool = False,
    melody_override: list[dict[str, Any]] | None = None,
    melody_gain: float | None = None,
    backing_gain: float | None = None,
    count_in_bars: int = 0,
    recorded_audio: bytes | None = None,
    recorded_trim_sec: float = 0.0,
) -> bytes | None:
    if chord_override is not None:
        chords = [str(c) for c in chord_override if str(c).strip()]
    else:
        chords = chords_for_playback(doc, scope=scope, section_id=section_id)
    if not chords:
        # Melody-first / recording-first: allow preview without inventing fake chords.
        events = (
            list(melody_override)
            if melody_override is not None
            else (_resolve_melody_events(doc, section_id) if include_melody else [])
        )
        if recorded_audio:
            # Play the user's recording alone (no chord bed).
            try:
                rec = _decode_recorded_mono(bytes(recorded_audio), target_sr=44100)
                if rec:
                    wav = _floats_to_wav_bytes(rec, 44100)
                    if wav:
                        return wav
            except Exception:
                return None
            return None
        if include_melody and events:
            pg = playback_globals(doc)
            bpm = int(pg.get("bpm") or 96)
            meter = str(pg.get("time_signature") or "4/4")
            # Silent bed sized to the melody, then mix synth melody (no fake chords).
            span = 0.0
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                end = float(ev.get("beat") or 0.0) + float(ev.get("duration_beats") or 1.0)
                if end > span:
                    span = end
            span = max(span, _beats_per_bar(meter))
            seconds = (span / max(40.0, float(bpm))) * 60.0 * max(1, int(loops))
            sr = 44100
            silent = [0.0] * max(sr, int(seconds * sr) + sr)
            bed = _floats_to_wav_bytes(silent, sr)
            return _mix_melody_onto_backing(
                bed,
                events,
                bpm=bpm,
                time_signature=meter,
                loops=max(1, int(loops)),
                melody_gain=0.7 if melody_gain is None else float(melody_gain),
                backing_gain=0.05,
                count_in_sec=0.0,
            )
        return None
    pg = playback_globals(doc)
    from backing_audio import generate_backing_track
    from composition_sync_transport import count_in_seconds, prepend_count_in_clicks

    wav = generate_backing_track(
        chords,
        bpm=pg["bpm"],
        loops=max(1, int(loops)),
        style=pg["groove"],
        level=level,
        song_title=str(doc.get("title") or "Composition"),
        song_artist="",
        time_signature=pg["time_signature"],
        mood=pg.get("mood") or "",
    )
    if not wav:
        return None

    bars = max(0, int(count_in_bars))
    cin_sec = count_in_seconds(bpm=int(pg["bpm"]), meter=str(pg["time_signature"]), bars=bars)
    mg = 0.45 if melody_gain is None else float(melody_gain)
    bg = 0.85 if backing_gain is None else float(backing_gain)

    # Recorded performance takes priority over synthesized transcription tones.
    if recorded_audio:
        trim = float(recorded_trim_sec or 0.0)
        if trim <= 0 and bars > 0:
            trim = float(cin_sec)
        wav = _mix_recorded_audio_onto_backing(
            wav,
            bytes(recorded_audio),
            recorded_trim_sec=trim,
            melody_gain=mg,
            backing_gain=bg,
        )
    elif include_melody:
        events = (
            list(melody_override)
            if melody_override is not None
            else _resolve_melody_events(doc, section_id)
        )
        if events:
            # Mix melody onto body first (beat 0 = first chord), then prepend clicks once.
            wav = _mix_melody_onto_backing(
                wav,
                events,
                bpm=int(pg["bpm"]),
                time_signature=str(pg["time_signature"]),
                loops=max(1, int(loops)),
                melody_gain=mg,
                backing_gain=bg,
                count_in_sec=0.0,
            )

    if bars > 0:
        wav = prepend_count_in_clicks(
            wav,
            bpm=int(pg["bpm"]),
            meter=str(pg["time_signature"]),
            bars=bars,
        )
        _ = cin_sec  # documented shared timeline offset for callers/tests
    return wav


def set_composer_preview(
    session_state: dict,
    wav: bytes | None,
    signature: tuple | None = None,
) -> None:
    """Replace the active Composition preview (single owner — no stacked mystery audio)."""
    if not wav:
        invalidate_composer_preview(session_state)
        return
    session_state["composer_preview_wav"] = wav
    if signature is not None:
        session_state["composer_preview_signature"] = signature
    session_state[COMPOSER_PREVIEW_AUTOPLAY_KEY] = True
    if not session_state.get(COMPOSER_PREVIEW_NONCE_KEY):
        session_state[COMPOSER_PREVIEW_NONCE_KEY] = 1


def invalidate_composer_preview(session_state: dict) -> None:
    session_state.pop("composer_preview_wav", None)
    session_state.pop("composer_preview_signature", None)
    session_state.pop(COMPOSER_PREVIEW_SLOT_KEY, None)
    session_state.pop(COMPOSER_PREVIEW_LABEL_KEY, None)
    session_state.pop(COMPOSER_PREVIEW_COUNT_IN_KEY, None)
    session_state[COMPOSER_PREVIEW_AUTOPLAY_KEY] = False


def inspect_preview_wav(wav: bytes | None) -> dict[str, Any]:
    """Deterministic playability check — header + non-silent PCM, not mere presence."""
    empty = {
        "playable": False,
        "reason": "empty",
        "byte_len": 0,
        "frames": 0,
        "sample_rate": 0,
        "duration_seconds": 0.0,
        "peak": 0.0,
    }
    if not wav or not isinstance(wav, (bytes, bytearray)):
        return dict(empty)
    raw = bytes(wav)
    empty["byte_len"] = len(raw)
    if len(raw) < 44 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        return {**empty, "reason": "not_wav"}
    try:
        mono, sr = _wav_to_mono_floats(raw)
    except Exception:
        return {**empty, "reason": "unreadable"}
    if not mono or int(sr) <= 0:
        return {**empty, "reason": "no_pcm", "sample_rate": int(sr or 0)}
    peak = max(abs(s) for s in mono)
    duration = len(mono) / float(sr)
    playable = peak >= _MIN_PLAYABLE_PEAK and duration >= _MIN_PLAYABLE_SECONDS
    return {
        "playable": playable,
        "reason": "" if playable else ("silent" if peak < _MIN_PLAYABLE_PEAK else "too_short"),
        "byte_len": len(raw),
        "frames": len(mono),
        "sample_rate": int(sr),
        "duration_seconds": duration,
        "peak": float(peak),
    }


def composer_preview_slot(session_state: dict) -> str:
    return str(session_state.get(COMPOSER_PREVIEW_SLOT_KEY) or "")


def composer_preview_label(session_state: dict) -> str:
    return str(session_state.get(COMPOSER_PREVIEW_LABEL_KEY) or "Now playing")


def composer_playback_is_armed(session_state: dict) -> bool:
    wav = session_state.get("composer_preview_wav")
    return bool(inspect_preview_wav(wav if isinstance(wav, (bytes, bytearray)) else None).get("playable"))


def _safe_preview_key(slot: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", str(slot or "preview")).strip("_")
    return text[:48] or "preview"


def build_composer_playback_html(
    wav: bytes,
    *,
    nonce: int,
    autoplay: bool = True,
    stats: dict[str, Any] | None = None,
) -> str:
    """HTML5 player payload (fallback). Prefer native st.audio for click-gesture autoplay."""
    info = stats or inspect_preview_wav(wav)
    b64 = base64.b64encode(bytes(wav)).decode("ascii")
    auto_attr = "autoplay" if autoplay else ""
    nid = int(nonce)
    peak = float(info.get("peak") or 0.0)
    dur = float(info.get("duration_seconds") or 0.0)
    n_bytes = int(info.get("byte_len") or len(wav))
    return f"""<div class="composer-playback" data-nonce="{nid}" data-bytes="{n_bytes}" data-duration="{dur:.3f}" data-peak="{peak:.4f}" data-autoplay="{'1' if autoplay else '0'}">
<audio class="composer-playback-audio" id="composer-playback-{nid}" controls {auto_attr} preload="auto" src="data:audio/wav;base64,{b64}"></audio>
<script>
(function() {{
  var id = "composer-playback-{nid}";
  var current = document.getElementById(id);
  var nodes = document.querySelectorAll("audio");
  for (var i = 0; i < nodes.length; i++) {{
    if (nodes[i] !== current) {{
      try {{ nodes[i].pause(); nodes[i].currentTime = 0; }} catch (e) {{}}
    }}
  }}
  if (!current) return;
  try {{ current.currentTime = 0; }} catch (e) {{}}
  var p = current.play();
  if (p && p.catch) p.catch(function() {{}});
}})();
</script>
</div>"""


def play_composer_preview(
    session_state: dict,
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    loops: int = 2,
    chord_override: list[str] | None = None,
    include_melody: bool = False,
    melody_override: list[dict[str, Any]] | None = None,
    level: str = "Intermediate",
    count_in_bars: int = 0,
    melody_gain: float | None = None,
    backing_gain: float | None = None,
    slot: str = "",
    label: str = "",
    recorded_audio: bytes | None = None,
    recorded_trim_sec: float = 0.0,
) -> dict[str, Any]:
    """Button-path seam: generate, validate, arm a remounting autoplay payload (no extra rerun)."""
    pg = playback_globals(doc)
    if chord_override is not None:
        chords = [str(c) for c in chord_override if str(c).strip()]
    else:
        chords = chords_for_playback(doc, scope=scope, section_id=section_id)
    sig = preview_signature(
        doc,
        scope=scope,
        section_id=section_id,
        loops=loops,
        chord_override=chord_override,
        include_melody=include_melody and not recorded_audio,
        melody_override=melody_override,
    )
    if recorded_audio:
        sig = tuple(list(sig) + ["recorded", len(recorded_audio), float(recorded_trim_sec or 0.0)])
    result: dict[str, Any] = {
        "ok": False,
        "reason": "no_chords",
        "wav": None,
        "signature": sig,
        "nonce": int(session_state.get(COMPOSER_PREVIEW_NONCE_KEY) or 0),
        "html": "",
        "playable": False,
        "chords": list(chords),
        "include_melody": bool(include_melody) or bool(recorded_audio),
        "recorded_audio": bool(recorded_audio),
        "bpm": int(pg.get("bpm") or 0),
        "meter": str(pg.get("time_signature") or ""),
        "scope": scope,
        "section_id": section_id or "",
        "loops": int(loops),
        "count_in_bars": int(count_in_bars or 0),
        "slot": str(slot or ""),
        "label": str(label or ""),
    }
    if not chords:
        # Melody-only / recording-only path (no fake default chords).
        has_melody = bool(include_melody) or melody_override is not None or bool(recorded_audio)
        if not has_melody:
            invalidate_composer_preview(session_state)
            result["reason"] = "Add chords or a melody to preview this section."
            return result
        wav = generate_preview_wav(
            doc,
            scope=scope,
            section_id=section_id,
            loops=loops,
            level=level,
            chord_override=[],
            include_melody=include_melody or bool(melody_override),
            melody_override=melody_override,
            melody_gain=melody_gain,
            backing_gain=backing_gain,
            count_in_bars=count_in_bars,
            recorded_audio=recorded_audio,
            recorded_trim_sec=recorded_trim_sec,
        )
        stats = inspect_preview_wav(wav)
        result.update(stats)
        if not wav or not stats.get("playable"):
            invalidate_composer_preview(session_state)
            result["reason"] = "Could not build a melody-only preview."
            return result
        nonce = int(session_state.get(COMPOSER_PREVIEW_NONCE_KEY) or 0) + 1
        session_state[COMPOSER_PREVIEW_NONCE_KEY] = nonce
        session_state[COMPOSER_PREVIEW_AUTOPLAY_KEY] = True
        session_state[COMPOSER_PREVIEW_SLOT_KEY] = str(slot or "")
        session_state[COMPOSER_PREVIEW_LABEL_KEY] = str(label or "Preview melody")
        session_state[COMPOSER_PREVIEW_COUNT_IN_KEY] = int(count_in_bars or 0)
        set_composer_preview(session_state, wav, sig)
        html = build_composer_playback_html(bytes(wav), nonce=nonce, autoplay=True, stats=stats)
        result.update(
            {
                "ok": True,
                "reason": "melody_only",
                "wav": wav,
                "playable": True,
                "nonce": nonce,
                "html": html or "",
                "chords": [],
                "label": str(label or "Preview melody"),
            }
        )
        return result
    wav = generate_preview_wav(
        doc,
        scope=scope,
        section_id=section_id,
        loops=loops,
        level=level,
        chord_override=chord_override,
        include_melody=include_melody,
        melody_override=melody_override,
        melody_gain=melody_gain,
        backing_gain=backing_gain,
        count_in_bars=count_in_bars,
        recorded_audio=recorded_audio,
        recorded_trim_sec=recorded_trim_sec,
    )
    stats = inspect_preview_wav(wav)
    result.update(stats)
    if not stats.get("playable"):
        invalidate_composer_preview(session_state)
        result["reason"] = "Could not generate playable audio."
        return result
    nonce = int(session_state.get(COMPOSER_PREVIEW_NONCE_KEY) or 0) + 1
    session_state[COMPOSER_PREVIEW_NONCE_KEY] = nonce
    session_state[COMPOSER_PREVIEW_AUTOPLAY_KEY] = True
    session_state[COMPOSER_PREVIEW_SLOT_KEY] = str(slot or "")
    session_state[COMPOSER_PREVIEW_LABEL_KEY] = str(label or "Now playing")
    session_state[COMPOSER_PREVIEW_COUNT_IN_KEY] = int(count_in_bars or 0)
    set_composer_preview(session_state, wav, sig)
    html = build_composer_playback_html(bytes(wav), nonce=nonce, autoplay=True, stats=stats)
    result.update(
        {
            "ok": True,
            "reason": "",
            "wav": bytes(wav),
            "nonce": nonce,
            "html": html,
        }
    )
    return result


def render_composer_playback(
    st_mod: Any,
    session_state: dict,
    *,
    stop_key: str = "composer_preview_stop",
    label: str | None = None,
) -> bool:
    """Render the armed payload. Returns True when a playable player was mounted."""
    wav = session_state.get("composer_preview_wav")
    stats = inspect_preview_wav(wav if isinstance(wav, (bytes, bytearray)) else None)
    if not stats.get("playable"):
        return False
    nonce = int(session_state.get(COMPOSER_PREVIEW_NONCE_KEY) or 1)
    autoplay = bool(session_state.get(COMPOSER_PREVIEW_AUTOPLAY_KEY, True))
    heading = str(label or composer_preview_label(session_state) or "Now playing")
    st_mod.markdown(f"**{heading}**")
    c1, c2 = st_mod.columns([4, 1])
    with c1:
        html = build_composer_playback_html(bytes(wav), nonce=nonce, autoplay=autoplay, stats=stats)
        mounted = False
        # Same-click Preview: HTML5 <audio autoplay> keeps the user gesture.
        # (st.audio often shows a long skeleton for large WAV payloads.)
        if autoplay:
            try:
                import streamlit.components.v1 as components

                components.html(html, height=88)
                mounted = True
            except Exception:
                mounted = False
        if not mounted:
            try:
                st_mod.audio(
                    bytes(wav),
                    format="audio/wav",
                    autoplay=autoplay,
                    start_time=0,
                    key=f"composer_preview_audio_{nonce}",
                )
            except TypeError:
                st_mod.audio(bytes(wav), format="audio/wav")
        st_mod.caption(
            f"Playable · {float(stats.get('duration_seconds') or 0.0):.1f}s · "
            f"peak {float(stats.get('peak') or 0.0):.2f}"
        )
    with c2:
        if st_mod.button("Stop", key=stop_key, use_container_width=True):
            invalidate_composer_preview(session_state)
            st_mod.rerun()
    return True


def render_local_composer_playback(
    st_mod: Any,
    session_state: dict,
    *,
    slot: str,
    stop_key: str | None = None,
) -> bool:
    """Mount the player only on the item that armed this slot (same click-run)."""
    wanted = str(slot or "")
    if not wanted or composer_preview_slot(session_state) != wanted:
        return False
    if not composer_playback_is_armed(session_state):
        return False
    label = composer_preview_label(session_state)
    st_mod.markdown(
        f'<div class="composer-local-player" data-preview-slot="{html.escape(wanted)}" '
        f'data-playing-label="{html.escape(label)}">',
        unsafe_allow_html=True,
    )
    mounted = render_composer_playback(
        st_mod,
        session_state,
        stop_key=stop_key or f"composer_preview_stop_{_safe_preview_key(wanted)}",
        label=label,
    )
    st_mod.markdown("</div>", unsafe_allow_html=True)
    return mounted
