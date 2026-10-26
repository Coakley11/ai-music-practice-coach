"""Composition Studio — import melody from MIDI, MusicXML, or audio files.

Converts supported file formats into canonical Composition melody events
(same shape as hum transcription output). Never modifies the Composition
document directly — returns a proposal dict for the UI review flow.

Supported formats:
  - MIDI (.mid, .midi) — monophonic extraction via mido
  - MusicXML (.xml, .musicxml, .mxl) — monophonic extraction via xml.etree
  - Audio (.wav, .mp3, .ogg, .flac) — pitch detection via existing transcription engine
"""

from __future__ import annotations

import io
import math
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

from composition_hum_transcription import (
    quantize_beats,
    spell_midi_in_key,
    parse_meter,
    is_compound_meter,
)

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac"}
SUPPORTED_MIDI_EXTENSIONS = {".mid", ".midi"}
SUPPORTED_MUSICXML_EXTENSIONS = {".xml", ".musicxml", ".mxl"}
SUPPORTED_EXTENSIONS = SUPPORTED_AUDIO_EXTENSIONS | SUPPORTED_MIDI_EXTENSIONS | SUPPORTED_MUSICXML_EXTENSIONS

FILE_IMPORT_SOURCE_ID = "file_import"


def supported_format_label() -> str:
    return "MIDI (.mid), MusicXML (.xml, .musicxml), WAV, MP3, OGG, FLAC"


def file_extension(filename: str) -> str:
    name = str(filename or "").strip().lower()
    for ext in sorted(SUPPORTED_EXTENSIONS, key=len, reverse=True):
        if name.endswith(ext):
            return ext
    dot = name.rfind(".")
    return name[dot:] if dot >= 0 else ""


def is_supported_file(filename: str) -> bool:
    return file_extension(filename) in SUPPORTED_EXTENSIONS


def _import_category(filename: str) -> str:
    ext = file_extension(filename)
    if ext in SUPPORTED_MIDI_EXTENSIONS:
        return "midi"
    if ext in SUPPORTED_MUSICXML_EXTENSIONS:
        return "musicxml"
    if ext in SUPPORTED_AUDIO_EXTENSIONS:
        return "audio"
    return "unknown"


# ---------------------------------------------------------------------------
# MIDI import
# ---------------------------------------------------------------------------

def _midi_available() -> bool:
    try:
        import mido  # noqa: F401
        return True
    except ImportError:
        return False


def _parse_midi_to_events(
    data: bytes,
    *,
    key: str = "C",
    bpm: int = 120,
    meter: str = "4/4",
    track_index: int | None = None,
) -> list[dict[str, Any]]:
    """Extract monophonic melody events from a Standard MIDI file.

    When ``track_index`` is None, picks the track with the most note-on
    messages (melodic heuristic). Polyphonic passages collapse to the
    highest sounding pitch per onset (top-line melody extraction).
    """
    import mido

    mid = mido.MidiFile(file=io.BytesIO(data))
    ticks_per_beat = mid.ticks_per_beat or 480

    # Resolve tempo from MIDI (first set_tempo event) or use caller BPM.
    midi_tempo = 500000  # 120 BPM default
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                midi_tempo = msg.tempo
                break
        if midi_tempo != 500000:
            break
    sec_per_tick = midi_tempo / (1_000_000.0 * ticks_per_beat)
    effective_bpm = bpm or round(60_000_000 / midi_tempo)
    sec_per_beat = 60.0 / max(40.0, float(effective_bpm))

    # Pick the best melodic track.
    if track_index is not None and 0 <= track_index < len(mid.tracks):
        tracks_to_scan = [mid.tracks[track_index]]
    else:
        scored = []
        for i, trk in enumerate(mid.tracks):
            note_count = sum(1 for m in trk if m.type == "note_on" and m.velocity > 0)
            scored.append((note_count, i))
        scored.sort(key=lambda x: -x[0])
        best = [mid.tracks[s[1]] for s in scored[:3] if s[0] > 0]
        tracks_to_scan = best if best else mid.tracks[:1]

    # Collect note-on/note-off pairs across candidate tracks, keep highest per onset.
    raw_notes: list[tuple[float, float, int]] = []  # (start_sec, dur_sec, midi)
    for trk in tracks_to_scan:
        abs_tick = 0
        pending: dict[int, float] = {}
        for msg in trk:
            abs_tick += msg.time
            t_sec = abs_tick * sec_per_tick
            if msg.type == "note_on" and msg.velocity > 0:
                pending[msg.note] = t_sec
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                start = pending.pop(msg.note, None)
                if start is not None:
                    dur = t_sec - start
                    if dur > 0.01:
                        raw_notes.append((start, dur, msg.note))

    if not raw_notes:
        return []

    raw_notes.sort(key=lambda n: (n[0], -n[2]))

    # Collapse to monophonic: group by onset (within 30ms), keep highest pitch.
    mono: list[tuple[float, float, int]] = []
    i = 0
    while i < len(raw_notes):
        onset = raw_notes[i][0]
        group = [raw_notes[i]]
        j = i + 1
        while j < len(raw_notes) and abs(raw_notes[j][0] - onset) < 0.03:
            group.append(raw_notes[j])
            j += 1
        best_note = max(group, key=lambda n: n[2])
        mono.append(best_note)
        i = j

    events: list[dict[str, Any]] = []
    bpb = float(parse_meter(meter)[0])
    prev_end = 0.0

    for start_sec, dur_sec, midi_note in mono:
        # Insert rest for gaps > half a beat.
        gap = start_sec - prev_end
        if gap > sec_per_beat * 0.4 and events:
            rest_beats = quantize_beats(gap / sec_per_beat, meter=meter)
            if rest_beats >= 0.5:
                rest_start_beat = sum(
                    float(e.get("duration_beats") or 1.0) for e in events
                )
                events.append({
                    "pitch": "rest",
                    "midi": None,
                    "duration_beats": rest_beats,
                    "beat": rest_start_beat,
                    "measure": int(rest_start_beat // bpb) + 1,
                    "is_rest": True,
                    "confidence": 1.0,
                    "uncertain": False,
                })

        dur_beats = quantize_beats(dur_sec / sec_per_beat, meter=meter)
        start_beat = sum(float(e.get("duration_beats") or 1.0) for e in events)
        pitch = spell_midi_in_key(midi_note, key)

        events.append({
            "pitch": pitch,
            "midi": midi_note,
            "duration_beats": dur_beats,
            "beat": start_beat,
            "measure": int(start_beat // bpb) + 1,
            "is_rest": False,
            "confidence": 0.95,
            "uncertain": False,
        })
        prev_end = start_sec + dur_sec

    return events


# ---------------------------------------------------------------------------
# MusicXML import
# ---------------------------------------------------------------------------

_MUSICXML_DURATION_MAP = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "16th": 0.25,
    "32nd": 0.125,
}

_MUSICXML_STEP_TO_PC = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}


def _parse_musicxml_to_events(
    data: bytes,
    *,
    key: str = "C",
    meter: str = "4/4",
) -> list[dict[str, Any]]:
    """Extract monophonic melody from MusicXML (Part 1, Voice 1)."""
    xml_data = data
    # Handle .mxl (compressed MusicXML).
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                xml_names = [
                    n for n in zf.namelist()
                    if n.endswith(".xml") and not n.startswith("META-INF")
                ]
                if xml_names:
                    xml_data = zf.read(xml_names[0])
        except Exception:
            pass

    root = ET.fromstring(xml_data)
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    def tag(name: str) -> str:
        return f"{ns}{name}"

    # Find first part.
    part = root.find(f".//{tag('part')}")
    if part is None:
        return []

    divisions = 1
    events: list[dict[str, Any]] = []
    beat_cursor = 0.0
    bpb = float(parse_meter(meter)[0])

    for measure in part.findall(tag("measure")):
        attrs = measure.find(tag("attributes"))
        if attrs is not None:
            div_el = attrs.find(tag("divisions"))
            if div_el is not None and div_el.text:
                try:
                    divisions = max(1, int(div_el.text))
                except ValueError:
                    pass

        for note_el in measure.findall(tag("note")):
            # Skip chord tones (keep only the first / highest voice).
            if note_el.find(tag("chord")) is not None:
                continue

            # Voice filter: prefer voice 1.
            voice_el = note_el.find(tag("voice"))
            if voice_el is not None and voice_el.text:
                try:
                    if int(voice_el.text) > 1:
                        continue
                except ValueError:
                    pass

            dur_el = note_el.find(tag("duration"))
            dur_divs = 1
            if dur_el is not None and dur_el.text:
                try:
                    dur_divs = max(1, int(dur_el.text))
                except ValueError:
                    pass
            dur_beats = float(dur_divs) / float(divisions)

            rest_el = note_el.find(tag("rest"))
            if rest_el is not None:
                q_dur = quantize_beats(dur_beats, meter=meter)
                if q_dur >= 0.5:
                    events.append({
                        "pitch": "rest",
                        "midi": None,
                        "duration_beats": q_dur,
                        "beat": beat_cursor,
                        "measure": int(beat_cursor // bpb) + 1,
                        "is_rest": True,
                        "confidence": 1.0,
                        "uncertain": False,
                    })
                beat_cursor += q_dur
                continue

            pitch_el = note_el.find(tag("pitch"))
            if pitch_el is None:
                beat_cursor += quantize_beats(dur_beats, meter=meter)
                continue

            step_el = pitch_el.find(tag("step"))
            octave_el = pitch_el.find(tag("octave"))
            alter_el = pitch_el.find(tag("alter"))

            step = str(step_el.text).strip() if step_el is not None and step_el.text else "C"
            try:
                octave = int(octave_el.text) if octave_el is not None and octave_el.text else 4
            except ValueError:
                octave = 4
            try:
                alter = int(float(alter_el.text)) if alter_el is not None and alter_el.text else 0
            except ValueError:
                alter = 0

            pc = _MUSICXML_STEP_TO_PC.get(step, 0) + alter
            midi_note = (octave + 1) * 12 + pc
            midi_note = max(21, min(108, midi_note))

            q_dur = quantize_beats(dur_beats, meter=meter)
            pitch_name = spell_midi_in_key(midi_note, key)

            events.append({
                "pitch": pitch_name,
                "midi": midi_note,
                "duration_beats": q_dur,
                "beat": beat_cursor,
                "measure": int(beat_cursor // bpb) + 1,
                "is_rest": False,
                "confidence": 1.0,
                "uncertain": False,
            })
            beat_cursor += q_dur

    return events


# ---------------------------------------------------------------------------
# Audio import (reuse existing transcription engine)
# ---------------------------------------------------------------------------

def _parse_audio_to_events(
    data: bytes,
    *,
    key: str = "C",
    bpm: int = 120,
    meter: str = "4/4",
) -> dict[str, Any]:
    """Transcribe audio file to melody events via existing hum transcription.

    Returns the full proposal dict (status, message, events, confidence)
    so the UI can show warnings about uncertain notes.
    """
    from composition_hum_transcription import transcribe_hum_audio

    return transcribe_hum_audio(
        data,
        bpm=bpm,
        meter=meter,
        key=key,
        count_in_sec=0.0,
        count_in_bars=0,
    )


# ---------------------------------------------------------------------------
# Unified import entry point
# ---------------------------------------------------------------------------

def import_melody_from_file(
    filename: str,
    data: bytes,
    *,
    key: str = "C",
    bpm: int = 120,
    meter: str = "4/4",
    track_index: int | None = None,
) -> dict[str, Any]:
    """Import a melody file and return a proposal for UI review.

    Returns a dict matching the hum-transcription proposal shape:
      status: "usable" | "uncertain" | "unclear" | "unavailable" | "empty"
      message: str
      events: list[dict]
      confidence: float
      source: "file_import"
      filename: str
      format: "midi" | "musicxml" | "audio"
    """
    result: dict[str, Any] = {
        "status": "unclear",
        "message": "",
        "events": [],
        "confidence": 0.0,
        "source": FILE_IMPORT_SOURCE_ID,
        "filename": str(filename or ""),
        "format": "unknown",
    }

    if not data:
        result["message"] = "Empty file — nothing to import."
        return result

    category = _import_category(filename)
    result["format"] = category

    try:
        if category == "midi":
            if not _midi_available():
                result["status"] = "unavailable"
                result["message"] = (
                    "MIDI import needs the mido library. "
                    "Ask your administrator to install it."
                )
                return result
            events = _parse_midi_to_events(
                data, key=key, bpm=bpm, meter=meter, track_index=track_index,
            )
            if not events:
                result["status"] = "empty"
                result["message"] = "No melody notes found in this MIDI file."
                return result
            pitched = [e for e in events if not e.get("is_rest")]
            result["events"] = events
            result["confidence"] = 0.95
            result["status"] = "usable"
            result["message"] = (
                f"Imported {len(pitched)} notes from MIDI — "
                "check the staff before accepting."
            )

        elif category == "musicxml":
            events = _parse_musicxml_to_events(data, key=key, meter=meter)
            if not events:
                result["status"] = "empty"
                result["message"] = "No melody notes found in this MusicXML file."
                return result
            pitched = [e for e in events if not e.get("is_rest")]
            result["events"] = events
            result["confidence"] = 1.0
            result["status"] = "usable"
            result["message"] = (
                f"Imported {len(pitched)} notes from MusicXML — "
                "check the staff before accepting."
            )

        elif category == "audio":
            audio_result = _parse_audio_to_events(
                data, key=key, bpm=bpm, meter=meter,
            )
            result["events"] = audio_result.get("events") or []
            result["confidence"] = float(audio_result.get("confidence") or 0.0)
            result["status"] = str(audio_result.get("status") or "unclear")
            result["message"] = str(audio_result.get("message") or "")
            if not result["events"]:
                result["status"] = result["status"] or "empty"

        else:
            result["message"] = (
                f"Unsupported file format. Supported: {supported_format_label()}"
            )

    except ET.ParseError:
        result["message"] = "Could not parse this file as MusicXML — is the XML valid?"
    except Exception as exc:
        result["status"] = "unclear"
        result["message"] = f"Import failed: {exc}"

    return result
