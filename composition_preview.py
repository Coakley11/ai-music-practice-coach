"""Audition backing (and optional melody) audio for Composition Studio."""

from __future__ import annotations

import base64
import io
import math
import struct
import wave
from typing import Any

from composition_document import (
    chords_for_playback,
    playback_globals,
    section_by_id,
    section_melody_events,
    section_playback_bars,
    song_melody_events,
)

COMPOSER_PREVIEW_NONCE_KEY = "composer_preview_nonce"
COMPOSER_PREVIEW_AUTOPLAY_KEY = "composer_preview_autoplay"
COMPOSER_PREVIEW_DOCK_STOP_KEY = "_composer_preview_dock_stop_key"
_MIN_PLAYABLE_PEAK = 0.02
_MIN_PLAYABLE_SECONDS = 0.2


def resolve_preview_groove(doc: dict[str, Any], arrangement_style: str | None = None) -> str:
    """Backing groove for preview. Override never writes back to the document."""
    pg = playback_globals(doc)
    override = str(arrangement_style or "").strip()
    if not override:
        return str(pg.get("groove") or "")
    if "groove" in override.lower():
        return override
    return f"{override} groove"


def section_chords_for_declared_length(
    doc: dict[str, Any],
    section_id: str | None,
) -> list[str]:
    """Chord symbols padded/cycled to the section's declared playback length."""
    chords = chords_for_playback(doc, scope="section", section_id=section_id)
    if not chords or not section_id:
        return list(chords)
    sec = section_by_id(doc, section_id)
    bars = section_playback_bars(doc, sec)
    if bars <= 0 or len(chords) >= bars:
        return list(chords)
    out = list(chords)
    i = 0
    while len(out) < bars:
        out.append(chords[i % len(chords)])
        i += 1
    return out


def resolve_preview_chords(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    chord_override: list[str] | None = None,
) -> list[str]:
    if chord_override is not None:
        return [str(c) for c in chord_override if str(c).strip()]
    if str(scope or "section").strip().lower() == "section":
        return section_chords_for_declared_length(doc, section_id)
    return chords_for_playback(doc, scope=scope, section_id=section_id)


def preview_signature(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    loops: int = 2,
    chord_override: list[str] | None = None,
    include_melody: bool = False,
    melody_override: list[dict[str, Any]] | None = None,
    arrangement_style: str | None = None,
    count_in_bars: int = 0,
) -> tuple:
    pg = playback_globals(doc)
    chords = resolve_preview_chords(
        doc, scope=scope, section_id=section_id, chord_override=chord_override
    )
    mel_sig: tuple = ()
    if include_melody:
        events = (
            melody_override
            if melody_override is not None
            else _resolve_melody_events(doc, section_id, scope=scope)
        )
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
        resolve_preview_groove(doc, arrangement_style),
        int(loops),
        bool(include_melody),
        mel_sig,
        int(count_in_bars or 0),
    )


def _resolve_melody_events(
    doc: dict[str, Any],
    section_id: str | None,
    *,
    scope: str = "section",
) -> list[dict[str, Any]]:
    if str(scope or "section").strip().lower() == "song":
        return song_melody_events(doc)
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
) -> bytes:
    if not events or not wav_bytes:
        return wav_bytes
    mono, sr = _wav_to_mono_floats(wav_bytes)
    if not mono:
        return wav_bytes
    seconds_per_beat = 60.0 / max(40.0, float(bpm))
    bpb = _beats_per_bar(time_signature)
    # Melody may be shorter than looped backing — repeat softly to fill.
    total_beats = len(mono) / float(sr) / seconds_per_beat
    out = list(mono)
    gain = 0.22
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
            start = int(start_beat * seconds_per_beat * sr)
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
    arrangement_style: str | None = None,
    count_in_bars: int = 0,
) -> bytes | None:
    chords = resolve_preview_chords(
        doc, scope=scope, section_id=section_id, chord_override=chord_override
    )
    if not chords:
        return None
    pg = playback_globals(doc)
    from backing_audio import generate_backing_track

    wav = generate_backing_track(
        chords,
        bpm=pg["bpm"],
        loops=max(1, int(loops)),
        style=resolve_preview_groove(doc, arrangement_style),
        level=level,
        song_title=str(doc.get("title") or "Composition"),
        song_artist="",
        time_signature=pg["time_signature"],
        mood=pg.get("mood") or "",
    )
    if not wav:
        return None
    if include_melody:
        events = (
            list(melody_override)
            if melody_override is not None
            else _resolve_melody_events(doc, section_id, scope=scope)
        )
        if events:
            wav = _mix_melody_onto_backing(
                wav,
                events,
                bpm=int(pg["bpm"]),
                time_signature=str(pg["time_signature"]),
                loops=max(1, int(loops)),
            )
    if int(count_in_bars or 0) > 0:
        from composition_hum_transcription import prepend_count_in_wav

        wav = prepend_count_in_wav(
            wav,
            bpm=int(pg["bpm"]),
            meter=str(pg["time_signature"]),
            bars=int(count_in_bars),
        )
    return wav


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


def build_composer_playback_html(
    wav: bytes,
    *,
    nonce: int,
    autoplay: bool = True,
    stats: dict[str, Any] | None = None,
) -> str:
    """HTML5 player payload. Unique nonce remounts; JS restarts and pauses siblings."""
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
    arrangement_style: str | None = None,
    level: str = "Intermediate",
    count_in_bars: int = 0,
) -> dict[str, Any]:
    """Button-path seam: generate, validate, arm a remounting autoplay payload."""
    pg = playback_globals(doc)
    chords = resolve_preview_chords(
        doc, scope=scope, section_id=section_id, chord_override=chord_override
    )
    sig = preview_signature(
        doc,
        scope=scope,
        section_id=section_id,
        loops=loops,
        chord_override=chord_override,
        include_melody=include_melody,
        melody_override=melody_override,
        arrangement_style=arrangement_style,
        count_in_bars=count_in_bars,
    )
    result: dict[str, Any] = {
        "ok": False,
        "reason": "no_chords",
        "wav": None,
        "signature": sig,
        "nonce": int(session_state.get(COMPOSER_PREVIEW_NONCE_KEY) or 0),
        "html": "",
        "playable": False,
        "byte_len": 0,
        "duration_seconds": 0.0,
        "peak": 0.0,
        "frames": 0,
        "sample_rate": 0,
        "chords": list(chords),
        "include_melody": bool(include_melody),
        "bpm": int(pg.get("bpm") or 0),
        "meter": str(pg.get("time_signature") or ""),
        "scope": scope,
        "section_id": section_id or "",
        "loops": int(loops),
        "count_in_bars": int(count_in_bars or 0),
    }
    if not chords:
        invalidate_composer_preview(session_state)
        result["reason"] = "Add chords to this section first — melody sits on your harmony."
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
        arrangement_style=arrangement_style,
        count_in_bars=count_in_bars,
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


def composer_playback_is_armed(session_state: dict) -> bool:
    wav = session_state.get("composer_preview_wav")
    return bool(inspect_preview_wav(wav if isinstance(wav, (bytes, bytearray)) else None).get("playable"))


def request_composer_preview_dock(session_state: dict, stop_key: str = "composer_preview_stop") -> None:
    """Defer the player to the end of this script run (keeps the click gesture)."""
    session_state[COMPOSER_PREVIEW_DOCK_STOP_KEY] = str(stop_key or "composer_preview_stop")


def flush_composer_preview_dock(st_mod: Any, session_state: dict) -> bool:
    """Mount the armed player once, after Play/Preview handlers in the same run."""
    stop_key = session_state.pop(COMPOSER_PREVIEW_DOCK_STOP_KEY, None)
    if not stop_key:
        return False
    return render_composer_playback(st_mod, session_state, stop_key=str(stop_key))


def composition_surface_label() -> str:
    """Exact git surface so QA can tell Cloud `dev` from this PR head."""
    try:
        from suite_deploy_marker import resolve_git_branch, resolve_git_commit_full

        return (
            f"Composition surface · {resolve_git_branch()} · "
            f"{resolve_git_commit_full()}"
        )
    except Exception:
        return "Composition surface · unknown"


def render_composer_playback(
    st_mod: Any,
    session_state: dict,
    *,
    stop_key: str = "composer_preview_stop",
) -> bool:
    """Render the armed payload. Returns True when a playable player was mounted."""
    wav = session_state.get("composer_preview_wav")
    stats = inspect_preview_wav(wav if isinstance(wav, (bytes, bytearray)) else None)
    if not stats.get("playable"):
        return False
    nonce = int(session_state.get(COMPOSER_PREVIEW_NONCE_KEY) or 1)
    autoplay = bool(session_state.get(COMPOSER_PREVIEW_AUTOPLAY_KEY, True))
    st_mod.markdown("**Now playing**")
    c1, c2 = st_mod.columns([4, 1])
    with c1:
        # Native st.audio lives in the main document so the click gesture can
        # autoplay. A sandbox iframe (components.html) is blocked after rerun.
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


def set_composer_preview(
    session_state: dict,
    wav: bytes | None,
    signature: tuple | None = None,
) -> None:
    """Replace the active Composition preview (single owner — no stacked mystery audio)."""
    if not wav or not inspect_preview_wav(wav).get("playable"):
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
    session_state[COMPOSER_PREVIEW_AUTOPLAY_KEY] = False
