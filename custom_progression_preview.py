"""Custom Progressions: Preview Section / Preview Entire Song.

Pure timeline + light piano-comp audio + Streamlit state for the two preview buttons.
Deliberately independent of the full Backing engine: it
voices each chord with ``backing_audio.chord_notes`` and plays it with the shared
piano voice (``backing_keys_voice``), then drives the shared synced chord-chip player
(``composition_playback_sync.render_synced_score_playback_html``).

Nothing here writes the draft, the saved library or the active-song identity: the
preview is read-only over ``cpl_active_progression`` plus the live BPM / meter widgets.
"""

from __future__ import annotations

import hashlib
import io
import json
import wave
from typing import Any, Iterable

import chord_subdivisions as _cs
from songs.meter import meter_timing

PREVIEW_STATE_KEY = "_cpl_preview_state"
PREVIEW_KIND_SECTION = "section"
PREVIEW_KIND_SONG = "song"

MAX_PREVIEW_SECONDS = 240.0
MAX_PREVIEW_EVENTS = 1500
PREVIEW_SAMPLE_RATE = 22050

_REST_TOKENS = {"n.c.", "n.c", "nc", "(n.c.)", "rest", "tacet", "-"}

# Typical song form. Pre-Chorus precedes each Chorus, Solo precedes the Bridge
# (or the final Chorus when there is no Bridge). Sections without chords are skipped.
_FORM_TEMPLATE = (
    "Intro", "Verse", "Pre-Chorus", "Chorus", "Solo", "Bridge", "Outro",
)


# --------------------------------------------------------------------------- order


def _filled(entries: Iterable[dict] | None) -> bool:
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        if e.get("repeat") or str(e.get("chord") or "").strip():
            return True
    return False


def song_play_order(
    sections: dict[str, list[dict]] | None,
    arrangement: list[str] | None = None,
) -> list[str]:
    """Section names in the order the full song is played.

    ``arrangement`` (a user-defined order, e.g. ``active["section_arrangement"]``) wins
    when given - repeats the user wrote are kept; entries naming an empty/unknown
    section are skipped. Custom songs carry no repetition information, so otherwise the
    default order plays every section that has chords exactly ONCE (nothing is invented;
    see ``order_note`` for what the user is told).
    """
    secs = sections or {}
    if arrangement:
        return [n for n in arrangement if _filled(secs.get(n))]
    out = [n for n in _FORM_TEMPLATE if _filled(secs.get(n))]
    # Sections that exist but are not in the template (should not happen) still play once.
    for n in secs:
        if _filled(secs.get(n)) and n not in out and n != "Full Song":
            out.append(n)
    return out


def order_note(order: list[str], arrangement: list[str] | None = None) -> str:
    """One visible sentence naming the order the whole-song preview will play and where it
    comes from, so the default is never mistaken for the user's intended structure."""
    if not order:
        return ""
    chain = " → ".join(order)
    if arrangement:
        return f"Plays your song arrangement: {chain}."
    return (
        f"Plays in default order: {chain}. This song has no saved arrangement, so each section "
        "that has chords plays once — this is not your song structure."
    )


# ------------------------------------------------------------------------ timeline


def beats_per_bar(time_signature: str) -> int:
    """Pulses per bar (6 for 6/8: the pulse grid ``songs.meter`` uses)."""
    return int(meter_timing(100, time_signature).pulses_per_bar)


def pulse_seconds(bpm: int, time_signature: str) -> float:
    return float(meter_timing(int(bpm), time_signature).pulse_sec)


def _is_rest(chord: str) -> bool:
    return str(chord or "").strip().lower() in _REST_TOKENS


def _section_labels(order: list[str]) -> list[tuple[str, int, str]]:
    """(section, instance_index, display label) per position; numbered only when repeated."""
    totals: dict[str, int] = {}
    for n in order:
        totals[n] = totals.get(n, 0) + 1
    seen: dict[str, int] = {}
    out = []
    for n in order:
        inst = seen.get(n, 0)
        seen[n] = inst + 1
        label = f"{n} {inst + 1}" if totals[n] > 1 else n
        out.append((n, inst, label))
    return out


def _expand_section(
    entries: list[dict],
    *,
    bpb: float,
) -> list[dict[str, Any]]:
    """Events of one section with beats relative to the section start."""
    events: list[dict[str, Any]] = []
    cursor = 0.0
    bar = 0
    last_sound = ""
    for entry_index, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("chord") or "").strip()
        try:
            nbars = max(1, int(entry.get("bars", 1) or 1))
        except (TypeError, ValueError):
            nbars = 1
        is_repeat = bool(entry.get("repeat")) or raw == "%"
        if not raw and not is_repeat:
            continue
        if is_repeat:
            sound = last_sound
            dur = nbars * bpb
            events.append({
                "chord": sound, "label": "%", "start_beat": cursor, "duration_beats": dur,
                "bar_in_section": bar, "is_rest": not sound, "is_repeat": True, "hit": False,
                "entry_index": entry_index, "sub_index": 0,
            })
            cursor += dur
            bar += nbars
            continue
        hit = _cs.is_hit_token(raw)
        token = _cs.hit_underlying_chord(raw) if hit else raw
        subs = _cs.parse_subdivisions(token, beats_per_bar=bpb)
        if not subs:
            continue
        if len(subs) == 1:
            sub = subs[0]
            chord = sub.chord
            dur = nbars * bpb
            rest = _is_rest(chord)
            if not rest:
                last_sound = chord
            events.append({
                "chord": chord, "label": chord, "start_beat": cursor, "duration_beats": dur,
                "bar_in_section": bar, "is_rest": rest, "is_repeat": False, "hit": hit,
                "entry_index": entry_index, "sub_index": 0, "push": sub.push,
            })
            cursor += dur
            bar += nbars
            continue
        for _copy in range(nbars):
            for si, sub in enumerate(subs):
                rest = _is_rest(sub.chord)
                if not rest:
                    last_sound = sub.chord
                events.append({
                    "chord": sub.chord, "label": sub.chord, "start_beat": cursor,
                    "duration_beats": float(sub.weight),
                    "bar_in_section": bar, "is_rest": rest, "is_repeat": False, "hit": hit,
                    "entry_index": entry_index, "sub_index": si, "push": sub.push,
                })
                cursor += float(sub.weight)
            bar += 1
    return events


def build_preview_timeline(
    sections: dict[str, list[dict]] | None,
    order: list[str],
    *,
    time_signature: str = "4/4",
    bpm: int = 100,
    max_seconds: float = MAX_PREVIEW_SECONDS,
    max_events: int = MAX_PREVIEW_EVENTS,
) -> dict[str, Any]:
    """Ordered chord-event timeline for ``order`` (section names, repeats allowed).

    Returns ``{"events": [...], "truncated": bool, "total_beats": float, "bpb": int,
    "pulse_sec": float, "bpm": int, "time_signature": str}``. Each event has chord,
    label, start_beat, duration_beats, section, section_label, section_index (position
    in ``order``), section_instance, bar_in_section, bar_index (global, 0-based) and
    flags is_rest / is_repeat / hit. Beats are pulses (``songs.meter``); an empty
    section contributes nothing.
    """
    bpb = beats_per_bar(time_signature)
    psec = pulse_seconds(bpm, time_signature)
    max_beats = max(1.0, float(max_seconds) / psec)
    events: list[dict[str, Any]] = []
    offset = 0.0
    bar_offset = 0
    truncated = False
    secs = sections or {}
    for pos, (name, inst, label) in enumerate(_section_labels(list(order))):
        local = _expand_section(list(secs.get(name) or []), bpb=float(bpb))
        if not local:
            continue
        first = True
        sec_end = 0.0
        for ev in local:
            row = dict(ev)
            row["start_beat"] = offset + float(ev["start_beat"])
            row["bar_index"] = bar_offset + int(ev["bar_in_section"])
            row.update(section=name, section_label=label, section_index=pos,
                       section_instance=inst, section_start=first)
            first = False
            sec_end = max(sec_end, float(ev["start_beat"]) + float(ev["duration_beats"]))
            if row["start_beat"] >= max_beats or len(events) >= max_events:
                truncated = True
                break
            if row["start_beat"] + row["duration_beats"] > max_beats:
                row["duration_beats"] = max_beats - row["start_beat"]
                truncated = True
            events.append(row)
        if truncated:
            break
        offset += sec_end
        # bars consumed by this section instance (ceil for irregular weights)
        bar_offset += int(-(-sec_end // bpb))
    for i, ev in enumerate(events):
        ev["index"] = i
    total = (events[-1]["start_beat"] + events[-1]["duration_beats"]) if events else 0.0
    return {
        "events": events, "truncated": truncated, "total_beats": total,
        "bpb": bpb, "pulse_sec": psec, "bpm": int(bpm), "time_signature": time_signature,
    }


def timeline_spans(
    timeline: dict[str, Any],
    *,
    romans: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """Chord spans (seconds) in the shape the shared synced player consumes."""
    psec = float(timeline["pulse_sec"])
    spans: list[dict[str, Any]] = []
    for ev in timeline["events"]:
        start = float(ev["start_beat"]) * psec
        end = start + float(ev["duration_beats"]) * psec
        now = f'{ev["section_label"]} · bar {int(ev["bar_in_section"]) + 1} · {ev["label"]}'
        spans.append({
            "index": ev["index"], "loop": 0, "chord": ev["label"] if ev["is_rest"] else ev["chord"],
            "label": ev["label"], "start_sec": round(start, 4), "end_sec": round(end, 4),
            "kind": "chord", "highlightable": True,
            "section": ev["section"], "section_label": ev["section_label"],
            "section_start": bool(ev.get("section_start")),
            "section_key": f'{ev["section_index"]}',
            "now_label": now,
        })
    return spans


# ---------------------------------------------------------------------------- audio


def _voicing(chord: str, prev: list[int] | None) -> list[int]:
    from backing_audio import _voice_lead, chord_notes

    notes = sorted({int(n) for n in chord_notes(chord)})
    if not notes:
        return []
    root = notes[0]
    folded = sorted({n if n - root < 14 else n - 12 for n in notes})
    if len(folded) > 5:
        folded = [folded[0]] + folded[2:]  # drop the 5th/3rd-adjacent doubling, keep colour
    return [int(n) for n in _voice_lead(folded, prev)]


def _bass_midi(chord: str) -> int:
    from backing_audio import _chord_bass, _midi_for_root_symbol

    return 36 + int(_midi_for_root_symbol(_chord_bass(chord))) % 12


def render_preview_wav(timeline: dict[str, Any], *, sr: int = PREVIEW_SAMPLE_RATE) -> bytes:
    """Mono 16-bit WAV of a simple piano accompaniment for the timeline (concert pitch)."""
    import numpy as np
    import backing_keys_voice as kv

    events = timeline["events"]
    if not events:
        return b""
    psec = float(timeline["pulse_sec"])
    bpb = int(timeline["bpb"])
    total_sec = float(timeline["total_beats"]) * psec + 1.2
    bus = np.zeros(int(total_sec * sr), dtype=np.float32)
    prev: list[int] | None = None
    for ev in events:
        if ev["is_rest"] or not ev["chord"]:
            continue
        t0 = float(ev["start_beat"]) * psec
        dur = float(ev["duration_beats"]) * psec
        voicing = _voicing(ev["chord"], prev)
        if not voicing:
            continue
        prev = voicing
        bass = _bass_midi(ev["chord"])
        strikes = [0.0]
        if not ev.get("hit"):
            k = 1
            while k * bpb < float(ev["duration_beats"]) - 1e-6:
                strikes.append(k * bpb * psec)
                k += 1
        for si, off in enumerate(strikes):
            held = (min(dur - off, psec) if ev.get("hit") else (dur - off)) * 0.97
            if held <= 0.02:
                continue
            beat_in_bar = (float(ev["start_beat"]) + off / psec) % bpb
            vel = kv.hit_velocity(beat_in_bar, seed=int(ev["index"]) * 7 + si, pulses_per_bar=bpb)
            vel = vel if si == 0 else vel * 0.85
            gains = kv.voice_gains(voicing)
            for note, g in zip(sorted(voicing), gains):
                kv.add_piano_note(bus, sr, t0 + off, held, int(note), 0.5 * g, vel)
            kv.add_piano_note(bus, sr, t0 + off, held, bass, 0.45, vel)
    peak = float(np.max(np.abs(bus))) if bus.size else 0.0
    if peak > 0:
        bus = bus * (0.85 / peak)
    pcm = np.clip(bus * 32767.0, -32767, 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


# ----------------------------------------------------------------- inputs / payload


def preview_inputs(session_state: Any) -> dict[str, Any]:
    """Live draft (incl. unsaved edits) -> chords at the sounding (concert/Practice) key."""
    from custom_progression_lab import (
        CPL_EDITABLE_SECTIONS,
        CPL_TIME_SIGNATURES,
        cpl_active_from_session,
        cpl_workspace_practice_key,
        display_entries_for_section,
    )

    active = cpl_active_from_session(session_state)
    key = cpl_workspace_practice_key(session_state, active)
    ts = str(session_state.get("cpl_time_signature") or active.get("time_signature") or "4/4")
    if ts not in CPL_TIME_SIGNATURES:
        ts = str(active.get("time_signature") or "4/4")
    try:
        bpm = int(session_state.get("cpl_bpm_builder") or active.get("bpm") or 100)
    except (TypeError, ValueError):
        bpm = 100
    sections = {
        n: display_entries_for_section(active, key, n) for n in CPL_EDITABLE_SECTIONS
    }
    arrangement = active.get("section_arrangement")
    return {
        "sections": sections, "key": key, "time_signature": ts, "bpm": max(40, bpm),
        "arrangement": list(arrangement) if isinstance(arrangement, list) else None,
    }


def preview_signature(inputs: dict[str, Any], kind: str, section: str = "") -> str:
    order = [section] if kind == PREVIEW_KIND_SECTION else song_play_order(
        inputs["sections"], inputs.get("arrangement"))
    blob = json.dumps(
        [kind, section, order, inputs["key"], inputs["time_signature"], inputs["bpm"],
         {n: inputs["sections"].get(n) for n in sorted(set(order))}],
        sort_keys=True, default=str,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def build_preview(inputs: dict[str, Any], kind: str, section: str = "") -> dict[str, Any]:
    order = [section] if kind == PREVIEW_KIND_SECTION else song_play_order(
        inputs["sections"], inputs.get("arrangement"))
    tl = build_preview_timeline(
        inputs["sections"], order, time_signature=inputs["time_signature"], bpm=inputs["bpm"])
    return {"timeline": tl, "order": order}


# --------------------------------------------------------------------- Streamlit


def request_preview(session_state: Any, kind: str, section: str = "") -> None:
    """Button callback: arm a preview. Writes only the non-widget state key."""
    inputs = preview_inputs(session_state)
    prev = session_state.get(PREVIEW_STATE_KEY) or {}
    session_state[PREVIEW_STATE_KEY] = {
        "kind": kind,
        "section": section if kind == PREVIEW_KIND_SECTION else "",
        "sig": preview_signature(inputs, kind, section),
        "nonce": int(prev.get("nonce", 0) or 0) + 1,
    }


def active_preview(session_state: Any, kind: str, section: str = "") -> dict[str, Any] | None:
    """The armed preview if it is for this surface and still matches the live draft.

    A stale preview (section switched, chord/BPM/meter/key edited) is dropped, which
    unmounts the player so it can never sound or highlight outdated chords.
    """
    state = session_state.get(PREVIEW_STATE_KEY)
    if not isinstance(state, dict):
        return None
    if state.get("kind") != kind:
        return None
    want = section if kind == PREVIEW_KIND_SECTION else ""
    if state.get("section") != want:
        session_state.pop(PREVIEW_STATE_KEY, None)
        return None
    if state.get("sig") != preview_signature(preview_inputs(session_state), kind, section):
        session_state.pop(PREVIEW_STATE_KEY, None)
        return None
    return state


def build_player_html(inputs: dict[str, Any], kind: str, section: str, nonce: int = 1):
    """(html, frame_height, meta) for the shared synced player, or ("", 0, meta)."""
    from composition_playback_sync import render_synced_score_playback_html

    built = build_preview(inputs, kind, section)
    tl = built["timeline"]
    meta = {"order": built["order"], "truncated": tl["truncated"], "events": len(tl["events"])}
    if not tl["events"]:
        return "", 0, meta
    wav = render_preview_wav(tl)
    spans = timeline_spans(tl)
    try:
        from roman_numeral_analysis import chord_to_roman

        romans = [
            "" if (e["is_rest"] or e["is_repeat"]) else (chord_to_roman(e["chord"], inputs["key"]) or "")
            for e in tl["events"]
        ]
    except Exception:
        romans = []
    n = len(spans)
    scroll_px = 220 if kind == PREVIEW_KIND_SONG else 0
    rows = -(-(n + (len({s["section_key"] for s in spans}) * 4 if kind == PREVIEW_KIND_SONG else 0)) // 4)
    chips_h = min(scroll_px, rows * 50 + 8) if scroll_px else rows * 50 + 8
    bundle = {
        "mode": "chords", "bpm": inputs["bpm"], "meter": inputs["time_signature"],
        "melody_spans": [], "chord_spans": spans, "cursor_spans": spans, "primary": "chords",
        "lyric_timeline": [], "chips_per_row": 4, "chips_scroll_px": scroll_px,
    }
    caption = (
        f"{built['order'][0]} preview" if kind == PREVIEW_KIND_SECTION else "Entire song preview"
    ) + f" · {inputs['time_signature']} · {inputs['bpm']} BPM · key {inputs['key']} (concert pitch)"
    if tl["truncated"]:
        caption += f" · first {int(MAX_PREVIEW_SECONDS // 60)} min only"
    html_doc = render_synced_score_playback_html(
        wav_bytes=wav, chord_labels=[s["label"] for s in spans], bundle=bundle,
        caption=caption, dom_id=f"cplprev-{kind}-{nonce}", chord_roman_labels=romans or None,
    )
    return html_doc, 150 + chips_h, meta


def mount_active_preview(st: Any, kind: str, section: str = "") -> bool:
    """Mount the player for the armed preview of this surface. Read-only over the draft."""
    state = active_preview(st.session_state, kind, section)
    if not state:
        return False
    inputs = preview_inputs(st.session_state)
    html_doc, height, meta = build_player_html(inputs, kind, section, int(state.get("nonce", 1)))
    if not html_doc:
        st.caption("Nothing to preview yet: add a chord first.")
        return False
    try:
        import streamlit.components.v1 as components

        components.html(html_doc, height=height, scrolling=False)
    except Exception:
        return False
    return True


def render_preview_buttons(st: Any, *, kind: str, section: str = "", disabled: bool = False) -> None:
    """The ``Preview Section`` / ``Preview Entire Song`` button (no widget-key writes)."""
    if kind == PREVIEW_KIND_SECTION:
        label, key = "▶ Preview Section", f"cpl_preview_section_{section}"
    else:
        label, key = "▶ Preview Entire Song", "cpl_preview_song"
    st.button(
        label, key=key, use_container_width=True, disabled=disabled,
        on_click=request_preview, args=(st.session_state, kind, section),
        help="Plays the chords as entered (including unsaved edits) with a simple piano. "
        "Does not save or change your active song.",
    )
