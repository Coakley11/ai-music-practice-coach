"""Focused Manual / advanced chord editor for Composition Studio.

Edits the already-chosen selected-section progression. Distinct from Custom
Progression Lab: no song-source ownership, no Custom backing navigation, no
open-ended click-grid builder.

Widget ownership: never write a Streamlit widget key after that widget has
been instantiated in the same run. Programmatic changes go to pending keys
and are applied in ``prepare_*`` before widgets exist.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from composition_melody_notation import beats_per_bar, timed_chord_spans
from custom_progression_lab import normalize_chord_symbol
from music_theory import key_is_minor, split_chord, split_key_center, transpose_chord

CHORD_QUALITY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("", "Major"),
    ("m", "Minor"),
    ("7", "7"),
    ("maj7", "maj7"),
    ("m7", "m7"),
    ("sus4", "sus"),
    ("add9", "add9"),
    ("dim", "Diminished"),
    ("m7b5", "Half-diminished"),
    ("aug", "Augmented"),
    ("7b5", "7♭5"),
    ("7#5", "7♯5"),
)

CHORD_ROOTS: tuple[str, ...] = (
    "C",
    "C#",
    "Db",
    "D",
    "D#",
    "Eb",
    "E",
    "F",
    "F#",
    "Gb",
    "G",
    "G#",
    "Ab",
    "A",
    "A#",
    "Bb",
    "B",
)

DURATION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("1bar", "1 bar"),
    ("2bar", "2 bars"),
    ("2beat", "2 beats"),
    ("1beat", "1 beat"),
    ("3beat", "3 beats"),
)

EDIT_ID_KEY = "_edit_id"

REFINE_INTENT_WIDGET_PREFIX = "composer_refine_intent_widget_"
REFINE_INTENT_VALUE_PREFIX = "composer_refine_intent_value_"
REFINE_INTENT_PENDING_PREFIX = "composer_refine_intent_pending_"
# Legacy widget key that crashed when written after instantiation.
LEGACY_REFINE_INTENT_KEY_PREFIX = "composer_refine_intent_"

DRAFT_KEY_PREFIX = "composer_cedit_draft_"
BASELINE_KEY_PREFIX = "composer_cedit_baseline_"
HISTORY_KEY_PREFIX = "composer_cedit_history_"
PENDING_DRAFT_KEY_PREFIX = "composer_cedit_pending_"
PENDING_WIDGETS_KEY_PREFIX = "composer_cedit_pending_widgets_"
SEQ_KEY_PREFIX = "composer_cedit_seq_"
MANUAL_EDITOR_EXPANDED_KEY = "composer_manual_editor_expanded"


def refine_intent_widget_key(section_id: str) -> str:
    return f"{REFINE_INTENT_WIDGET_PREFIX}{section_id}"


def refine_intent_value_key(section_id: str) -> str:
    return f"{REFINE_INTENT_VALUE_PREFIX}{section_id}"


def refine_intent_pending_key(section_id: str) -> str:
    return f"{REFINE_INTENT_PENDING_PREFIX}{section_id}"


def legacy_refine_intent_key(section_id: str) -> str:
    return f"{LEGACY_REFINE_INTENT_KEY_PREFIX}{section_id}"


def draft_key(section_id: str) -> str:
    return f"{DRAFT_KEY_PREFIX}{section_id}"


def baseline_key(section_id: str) -> str:
    return f"{BASELINE_KEY_PREFIX}{section_id}"


def history_key(section_id: str) -> str:
    return f"{HISTORY_KEY_PREFIX}{section_id}"


def pending_draft_key(section_id: str) -> str:
    return f"{PENDING_DRAFT_KEY_PREFIX}{section_id}"


def pending_widgets_key(section_id: str) -> str:
    return f"{PENDING_WIDGETS_KEY_PREFIX}{section_id}"


def editor_root_widget_key(section_id: str, edit_id: str) -> str:
    return f"composer_cedit_root_{section_id}_{edit_id}"


def editor_quality_widget_key(section_id: str, edit_id: str) -> str:
    return f"composer_cedit_qual_{section_id}_{edit_id}"


def editor_duration_widget_key(section_id: str, edit_id: str) -> str:
    return f"composer_cedit_dur_{section_id}_{edit_id}"


def prepare_refine_intent_widget(
    session_state: dict,
    section_id: str,
    intent_ids: list[str],
) -> str:
    """Seed / apply pending refine intent BEFORE the selectbox is created.

    Never writes the widget key after instantiation — callers must invoke this
    at the top of the panel, then pass the widget key only to ``st.selectbox``.
    """
    ids = [str(i) for i in intent_ids if str(i)]
    default = ids[0] if ids else "happier"
    pending_k = refine_intent_pending_key(section_id)
    widget_k = refine_intent_widget_key(section_id)
    value_k = refine_intent_value_key(section_id)

    pending = session_state.pop(pending_k, None)
    if pending in ids:
        session_state[value_k] = pending
        session_state[widget_k] = pending
    elif widget_k not in session_state:
        seed = session_state.get(value_k)
        if seed not in ids:
            seed = default
        session_state[widget_k] = seed
        session_state[value_k] = seed
    current = session_state.get(widget_k)
    if current not in ids:
        session_state[widget_k] = default
        current = default
    session_state[value_k] = current
    return str(current)


def queue_refine_intent_change(session_state: dict, section_id: str, intent: str) -> str:
    """Queue an intent rotation without touching the live widget key."""
    nxt = str(intent or "").strip()
    session_state[refine_intent_pending_key(section_id)] = nxt
    session_state[refine_intent_value_key(section_id)] = nxt
    return nxt


def consume_refine_intent_choice(session_state: dict, section_id: str, picked: str) -> str:
    """Record the selectbox return value on the canonical key only."""
    value = str(picked or "").strip()
    session_state[refine_intent_value_key(section_id)] = value
    return value


def _entry_symbol(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("chord") or "").strip()
    return str(entry or "").strip()


def strip_edit_metadata(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            sym = str(entry or "").strip()
            if sym:
                out.append({"chord": normalize_chord_symbol(sym) or sym, "bars": 1})
            continue
        row = {k: v for k, v in entry.items() if k != EDIT_ID_KEY}
        sym = str(row.get("chord") or "").strip()
        if not sym:
            continue
        row["chord"] = normalize_chord_symbol(sym) or sym
        out.append(row)
    return out


def clone_entries(entries: list[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in entries or []:
        if isinstance(entry, dict):
            row = copy.deepcopy(entry)
            if not str(row.get("chord") or "").strip():
                continue
            out.append(row)
        else:
            sym = str(entry or "").strip()
            if sym:
                out.append({"chord": normalize_chord_symbol(sym) or sym, "bars": 1})
    return out


def ensure_edit_ids(session_state: dict, section_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seq_k = f"{SEQ_KEY_PREFIX}{section_id}"
    seq = int(session_state.get(seq_k) or 0)
    for row in entries:
        if not str(row.get(EDIT_ID_KEY) or "").strip():
            row[EDIT_ID_KEY] = str(seq)
            seq += 1
    session_state[seq_k] = max(seq, int(session_state.get(seq_k) or 0))
    return entries


def seed_editor_draft(
    session_state: dict,
    section_id: str,
    entries: list[Any] | None,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    if not force and isinstance(session_state.get(draft_key(section_id)), list):
        return list(session_state[draft_key(section_id)])
    draft = ensure_edit_ids(session_state, section_id, clone_entries(entries))
    session_state[draft_key(section_id)] = draft
    session_state[baseline_key(section_id)] = clone_entries(strip_edit_metadata(draft))
    session_state.setdefault(history_key(section_id), [])
    return draft


def prepare_editor_widgets(session_state: dict, section_id: str, entries: list[Any] | None) -> list[dict[str, Any]]:
    """Apply pending draft / widget seeds BEFORE any editor widgets exist."""
    pending = session_state.pop(pending_draft_key(section_id), None)
    if isinstance(pending, list):
        session_state[draft_key(section_id)] = ensure_edit_ids(
            session_state, section_id, clone_entries(pending)
        )
    draft = seed_editor_draft(session_state, section_id, entries)
    pending_widgets = session_state.pop(pending_widgets_key(section_id), None)
    if isinstance(pending_widgets, dict):
        for edit_id, payload in pending_widgets.items():
            if not isinstance(payload, dict):
                continue
            eid = str(edit_id)
            if payload.get("root") is not None:
                session_state[editor_root_widget_key(section_id, eid)] = payload["root"]
            if payload.get("quality") is not None:
                session_state[editor_quality_widget_key(section_id, eid)] = payload["quality"]
            if payload.get("duration") is not None:
                session_state[editor_duration_widget_key(section_id, eid)] = payload["duration"]
    return list(draft)


def queue_editor_draft(
    session_state: dict,
    section_id: str,
    draft: list[dict[str, Any]],
    *,
    widget_seeds: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Replace the draft on the next run; optionally reseeds widget keys first."""
    prepared = ensure_edit_ids(session_state, section_id, clone_entries(draft))
    session_state[pending_draft_key(section_id)] = prepared
    if widget_seeds:
        session_state[pending_widgets_key(section_id)] = dict(widget_seeds)
    return prepared


def push_editor_history(session_state: dict, section_id: str, draft: list[dict[str, Any]]) -> None:
    hist = list(session_state.get(history_key(section_id)) or [])
    hist.append(clone_entries(draft))
    session_state[history_key(section_id)] = hist[-20:]


def undo_editor_draft(session_state: dict, section_id: str) -> list[dict[str, Any]] | None:
    hist = list(session_state.get(history_key(section_id)) or [])
    if not hist:
        return None
    previous = hist.pop()
    session_state[history_key(section_id)] = hist
    seeds = widget_seeds_from_draft(section_id, previous)
    return queue_editor_draft(session_state, section_id, previous, widget_seeds=seeds)


def cancel_editor_draft(session_state: dict, section_id: str) -> list[dict[str, Any]]:
    baseline = clone_entries(session_state.get(baseline_key(section_id)) or [])
    session_state[history_key(section_id)] = []
    seeds = widget_seeds_from_draft(section_id, baseline)
    queued = queue_editor_draft(session_state, section_id, baseline, widget_seeds=seeds)
    return queued


def clear_editor_session(session_state: dict, section_id: str) -> None:
    for fn in (draft_key, baseline_key, history_key, pending_draft_key, pending_widgets_key):
        session_state.pop(fn(section_id), None)


def widget_seeds_from_draft(section_id: str, draft: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    seeds: dict[str, dict[str, str]] = {}
    for row in draft:
        eid = str(row.get(EDIT_ID_KEY) or "")
        if not eid:
            continue
        parts = parse_chord_parts(str(row.get("chord") or ""))
        seeds[eid] = {
            "root": parts["root"],
            "quality": parts["quality"],
            "duration": duration_token(row),
        }
    return seeds


def parse_chord_parts(symbol: str) -> dict[str, str]:
    raw = normalize_chord_symbol(symbol) or str(symbol or "").strip()
    bass = ""
    head = raw
    if "/" in raw:
        head, bass = raw.split("/", 1)
        bass = bass.strip()
    root, suffix = split_chord(head or "C")
    root = str(root or "C")
    root = root[0].upper() + root[1:] if root else "C"
    suffix = str(suffix or "")
    quality = _match_quality(suffix)
    return {"root": root, "quality": quality, "bass": bass, "suffix": suffix}


def _match_quality(suffix: str) -> str:
    text = str(suffix or "")
    if not text:
        return ""
    known = [qid for qid, _label in CHORD_QUALITY_OPTIONS if qid]
    known.sort(key=len, reverse=True)
    if text in known:
        return text
    for qid in known:
        if not text.startswith(qid):
            continue
        if qid == "m" and text.startswith("maj"):
            continue
        if qid == "7" and (text.startswith("maj") or text.startswith("m7") or text.startswith("m9")):
            continue
        return qid
    return text


def quality_choices(current: str) -> list[str]:
    ids = [qid for qid, _label in CHORD_QUALITY_OPTIONS]
    if current and current not in ids:
        ids.append(current)
    return ids


def quality_label(quality_id: str) -> str:
    for qid, label in CHORD_QUALITY_OPTIONS:
        if qid == quality_id:
            return label
    return quality_id or "Major"


def build_chord_symbol(root: str, quality: str, bass: str = "") -> str:
    r = str(root or "C").strip() or "C"
    r = r[0].upper() + r[1:] if r else "C"
    sym = f"{r}{quality or ''}"
    b = str(bass or "").strip()
    if b:
        sym = f"{sym}/{b}"
    return normalize_chord_symbol(sym) or sym


def duration_token(entry: dict[str, Any] | None, *, meter: str = "4/4") -> str:
    bar = beats_per_bar(meter)
    if not isinstance(entry, dict):
        return "1bar"
    raw = entry.get("duration_beats")
    beats: float | None = None
    if raw is not None:
        try:
            beats = float(raw)
        except (TypeError, ValueError):
            beats = None
    if beats is None or beats <= 0:
        try:
            bars = max(1, int(entry.get("bars") or 1))
        except (TypeError, ValueError):
            bars = 1
        beats = float(bars) * bar
    if abs(beats - (2.0 * bar)) < 0.05:
        return "2bar"
    if abs(beats - bar) < 0.05:
        return "1bar"
    if abs(beats - 3.0) < 0.05:
        return "3beat"
    if abs(beats - 2.0) < 0.05:
        return "2beat"
    if abs(beats - 1.0) < 0.05:
        return "1beat"
    return "1bar"


def apply_duration_token(entry: dict[str, Any], token: str, *, meter: str = "4/4") -> dict[str, Any]:
    row = {k: v for k, v in entry.items() if k not in {"bars", "duration_beats"}}
    tok = str(token or "1bar")
    bar = beats_per_bar(meter)
    if tok == "2bar":
        row["bars"] = 2
    elif tok == "2beat":
        row["duration_beats"] = 2.0
        row["bars"] = 1 if bar <= 2.0 else 1
    elif tok == "1beat":
        row["duration_beats"] = 1.0
    elif tok == "3beat":
        row["duration_beats"] = 3.0
    else:
        row["bars"] = 1
    return row


def location_labels(entries: list[Any] | None, *, meter: str = "4/4") -> list[str]:
    spans = timed_chord_spans(entries, meter=meter)
    bar = max(1.0, beats_per_bar(meter))
    labels: list[str] = []
    for span in spans:
        start = float(span.get("start_beat") or 0.0)
        dur = float(span.get("duration_beats") or bar)
        measure = int(start // bar) + 1
        beat = int(start % bar) + 1
        if abs(dur - (2.0 * bar)) < 0.05:
            length = "2 bars"
        elif abs(dur - bar) < 0.05:
            length = "1 bar"
        else:
            beats = max(1, int(round(dur)))
            length = f"{beats} beat" if beats == 1 else f"{beats} beats"
        labels.append(f"Bar {measure} · beat {beat} · {length}")
    return labels


def _key_token(doc: dict[str, Any] | None) -> str:
    g = (doc or {}).get("global") if isinstance(doc, dict) else {}
    return str((g or {}).get("original_key_center") or "C")


def diatonic_triads_for_key(key: str) -> list[str]:
    tonic, mode = split_key_center(key)
    minor = mode == "minor" or key_is_minor(key)
    if minor:
        degrees = [(0, "m"), (3, ""), (5, "m"), (7, ""), (8, ""), (10, "")]
    else:
        degrees = [(0, ""), (2, "m"), (4, "m"), (5, ""), (7, ""), (9, "m")]
    out: list[str] = []
    seen: set[str] = set()
    for steps, qual in degrees:
        sym = f"{transpose_chord(tonic, steps, reference_key=key)}{qual}"
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def diatonic_pitch_classes(key: str) -> set[int]:
    from creative_lab_text import NOTE_TO_PC, chord_root

    pcs: set[int] = set()
    for sym in diatonic_triads_for_key(key):
        pc = NOTE_TO_PC.get(chord_root(sym))
        if pc is not None:
            pcs.add(int(pc))
    return pcs


def is_chromatic_to_key(symbol: str, key: str) -> bool:
    from creative_lab_text import NOTE_TO_PC, chord_root

    root = chord_root(symbol)
    pc = NOTE_TO_PC.get(root)
    if pc is None:
        return False
    return int(pc) not in diatonic_pitch_classes(key)


def chromatic_warning(symbol: str, key: str) -> str:
    if not is_chromatic_to_key(symbol, key):
        return ""
    tonic, mode = split_key_center(key)
    scale = f"{tonic} {mode}" if mode else tonic
    return f"{symbol} sits outside {scale} — a color choice, not a mistake."


def suggest_slot_chords(
    doc: dict[str, Any],
    section: dict[str, Any] | None,
    entries: list[dict[str, Any]],
    index: int,
    *,
    for_insert: bool = False,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Key- and neighbor-aware ideas for replacing or inserting at ``index``."""
    key = _key_token(doc)
    diatonic = diatonic_triads_for_key(key)
    symbols = [_entry_symbol(e) for e in entries if _entry_symbol(e)]
    prev = symbols[index - 1] if index > 0 and index - 1 < len(symbols) else ""
    if for_insert:
        nxt = symbols[index] if 0 <= index < len(symbols) else ""
        current = ""
    else:
        current = symbols[index] if 0 <= index < len(symbols) else ""
        nxt = symbols[index + 1] if index + 1 < len(symbols) else ""

    tonic = diatonic[0] if diatonic else "C"
    ideas: list[tuple[str, str, bool]] = []

    def _add(sym: str, why: str) -> None:
        cleaned = normalize_chord_symbol(sym) or sym
        if not cleaned or cleaned == current:
            return
        if any(existing == cleaned for existing, _w, _c in ideas):
            return
        ideas.append((cleaned, why, is_chromatic_to_key(cleaned, key)))

    if prev:
        prev_parts = parse_chord_parts(prev)
        if prev_parts["quality"] in {"m", "m7"}:
            _add(_dominantish(key, nxt or tonic), "Answers the previous minor chord with pull toward home.")
        if (prev_parts["quality"] in {"7", "7b5", "7#5"}) or prev.endswith("7"):
            _add(tonic, "Resolves the previous dominant into the home chord.")
        _add(_relative_of(prev, key), "A close neighbor that keeps the story moving.")

    if nxt:
        _add(_dominant_of(nxt, key), "Sets up the next chord with a V–I handoff.")
        _add(nxt, "Repeats the upcoming chord as a passing hold.")

    for sym in diatonic:
        role = "Stays in the song key."
        _add(sym, role)

    # Deliberate color (always offered, never blocked).
    borrowed = _borrowed_color(key)
    _add(borrowed, "A borrowed color — chromatic on purpose.")

    out: list[dict[str, Any]] = []
    for sym, why, chromatic in ideas[: max(1, int(limit))]:
        out.append(
            {
                "symbol": sym,
                "why": why,
                "chromatic": chromatic,
                "warning": chromatic_warning(sym, key) if chromatic else "",
            }
        )
    _ = section
    return out


def _relative_of(symbol: str, key: str) -> str:
    parts = parse_chord_parts(symbol)
    if parts["quality"] in {"", "7", "maj7", "add9", "sus4", "aug"}:
        return build_chord_symbol(parts["root"], "m")
    return build_chord_symbol(parts["root"], "")


def _dominant_of(symbol: str, key: str) -> str:
    parts = parse_chord_parts(symbol)
    return f"{transpose_chord(parts['root'], 7, reference_key=key)}7"


def _dominantish(key: str, target: str) -> str:
    if target:
        return _dominant_of(target, key)
    tonic, _mode = split_key_center(key)
    return f"{transpose_chord(tonic, 7, reference_key=key)}7"


def _borrowed_color(key: str) -> str:
    tonic, mode = split_key_center(key)
    if mode == "minor" or key_is_minor(key):
        return transpose_chord(tonic, 8, reference_key=key)  # bVI
    return f"{tonic}m"


def replace_draft_chord(
    draft: list[dict[str, Any]],
    index: int,
    symbol: str,
    *,
    duration: str | None = None,
    meter: str = "4/4",
) -> list[dict[str, Any]]:
    out = clone_entries(draft)
    if index < 0 or index >= len(out):
        return out
    row = dict(out[index])
    row["chord"] = normalize_chord_symbol(symbol) or str(symbol).strip()
    if duration:
        row = apply_duration_token(row, duration, meter=meter)
    out[index] = row
    return out


def insert_draft_chord(
    draft: list[dict[str, Any]],
    index: int,
    symbol: str,
    *,
    duration: str = "1bar",
    meter: str = "4/4",
    edit_id: str | None = None,
) -> list[dict[str, Any]]:
    out = clone_entries(draft)
    idx = max(0, min(int(index), len(out)))
    row = apply_duration_token(
        {"chord": normalize_chord_symbol(symbol) or str(symbol).strip()},
        duration,
        meter=meter,
    )
    row[EDIT_ID_KEY] = str(edit_id or uuid.uuid4().hex[:8])
    out.insert(idx, row)
    return out


def remove_draft_chord(draft: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    out = clone_entries(draft)
    if 0 <= index < len(out):
        out.pop(index)
    return out


def apply_draft_to_document(
    doc: dict[str, Any],
    section_id: str,
    draft: list[dict[str, Any]],
) -> bool:
    from composition_document import apply_section_chords

    return apply_section_chords(doc, section_id, strip_edit_metadata(draft))


def draft_changed(draft: list[dict[str, Any]], baseline: list[dict[str, Any]] | None) -> bool:
    return strip_edit_metadata(draft) != strip_edit_metadata(baseline or [])


def next_edit_id(session_state: dict, section_id: str) -> str:
    seq_k = f"{SEQ_KEY_PREFIX}{section_id}"
    seq = int(session_state.get(seq_k) or 0)
    session_state[seq_k] = seq + 1
    return str(seq)
