"""Composition Studio — canonical song document schema and helpers."""

from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from custom_progression_lab import (
    CPL_PROGRESSION_STYLES,
    CPL_TIME_SIGNATURES,
    expand_entries_to_chords,
    normalize_chord_symbol,
)

COMPOSITION_SCHEMA_VERSION = 1

COMPOSER_SECTION_LABELS: tuple[str, ...] = (
    "Intro",
    "Verse",
    "Pre-Chorus",
    "Chorus",
    "Bridge",
    "Solo",
    "Interlude",
    "Outro",
)

REPEAT_LINK_LABELS: frozenset[str] = frozenset({"Verse", "Chorus", "Pre-Chorus", "Bridge"})

STRUCTURE_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "pop": [
        ("Intro", "Intro"),
        ("Verse", "Verse 1"),
        ("Pre-Chorus", "Pre-Chorus"),
        ("Chorus", "Chorus"),
        ("Verse", "Verse 2"),
        ("Chorus", "Chorus"),
        ("Bridge", "Bridge"),
        ("Chorus", "Chorus"),
        ("Outro", "Outro"),
    ],
    "simple": [
        ("Verse", "Verse 1"),
        ("Chorus", "Chorus"),
        ("Verse", "Verse 2"),
        ("Chorus", "Chorus"),
    ],
    "ballad": [
        ("Intro", "Intro"),
        ("Verse", "Verse 1"),
        ("Chorus", "Chorus"),
        ("Verse", "Verse 2"),
        ("Chorus", "Chorus"),
        ("Bridge", "Bridge"),
        ("Outro", "Outro"),
    ],
}

SECTION_TYPE_CSS: dict[str, str] = {
    "Intro": "intro",
    "Verse": "verse",
    "Pre-Chorus": "prechorus",
    "Chorus": "chorus",
    "Bridge": "bridge",
    "Solo": "solo",
    "Interlude": "interlude",
    "Outro": "outro",
}

DEFAULT_PROGRESSION_STYLE = "Pop"
DEFAULT_GROOVE = "Auto"
DEFAULT_BPM = 96
DEFAULT_KEY = "C"
DEFAULT_METER = "4/4"

COMPOSITION_PHASES: tuple[str, ...] = (
    "vision",
    "structure",
    "chords",
    "melody",
    "lyrics",
    "review",
)

COMPOSITION_PHASE_LABELS: dict[str, str] = {
    "vision": "Song Vision",
    "structure": "Song Structure",
    "chords": "Chords",
    "melody": "Melody",
    "lyrics": "Lyrics",
    "review": "Review",
}

COMPOSITION_GENRES: tuple[str, ...] = (
    "Pop",
    "Rock",
    "Jazz",
    "Blues",
    "Folk",
    "Soul/R&B",
    "Country",
    "Hip-Hop",
    "Electronic",
    "Classical",
    "Other",
)

COMPOSITION_PRACTICE_KEYS: tuple[str, ...] = (
    "C",
    "G",
    "D",
    "A",
    "E",
    "F",
    "Bb",
    "Eb",
    "Ab",
    "Db",
    "Am",
    "Em",
    "Dm",
)

COMPOSITION_ENERGY_LEVELS: tuple[str, ...] = (
    "Ballad — slow and intimate",
    "Mid-tempo — steady groove",
    "Driving — high energy",
)

SEED_TYPES: frozenset[str] = frozenset(
    {
        "style_intent",
        "chords",
        "rhythm",
        "lyrics",
        "title",
        "mood",
        "melody",
        "exploring",
        "mixed",
    }
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_section_id() -> str:
    return str(uuid.uuid4())


def empty_section(label: str, *, label_variant: str = "") -> dict[str, Any]:
    return {
        "id": _new_section_id(),
        "label": label,
        "label_variant": label_variant or label,
        "bars": 8,
        "chords": [],
        "chord_link": {"source_section_id": None, "linked": False},
        "harmony": {"feeling": ""},
        "melody": {"phrases": []},
        "lyrics": {"lines": [], "raw_text": ""},
        "rhythm_override": None,
    }


def default_integration_stub() -> dict[str, Any]:
    return {
        "practice_ready": False,
        "backing_preset_id": None,
        "notes_for_coach": "",
    }


def default_workflow(*, skip_lyrics: bool = False) -> dict[str, Any]:
    return {
        "current_phase": "vision",
        "completed_phases": [],
        "skip_lyrics": bool(skip_lyrics),
    }


def ensure_workflow(doc: dict[str, Any]) -> dict[str, Any]:
    wf = doc.get("workflow")
    if isinstance(wf, dict) and str(wf.get("current_phase") or "") in COMPOSITION_PHASES:
        wf.setdefault("completed_phases", [])
        wf.setdefault("skip_lyrics", False)
        return wf
    wf = default_workflow()
    if _document_has_chord_content(doc):
        wf["current_phase"] = "chords"
        wf["completed_phases"] = ["vision", "structure"]
    elif _document_has_structure(doc):
        wf["current_phase"] = "structure"
        wf["completed_phases"] = ["vision"]
    doc["workflow"] = wf
    return wf


def _document_has_structure(doc: dict[str, Any]) -> bool:
    order = list((doc.get("form") or {}).get("section_order") or [])
    return len(order) > 0


def _document_has_chord_content(doc: dict[str, Any]) -> bool:
    sections = (doc.get("form") or {}).get("sections") or {}
    for sec in sections.values():
        if not isinstance(sec, dict):
            continue
        if sec.get("chords"):
            return True
    return False


def get_workflow_phase(doc: dict[str, Any]) -> str:
    wf = ensure_workflow(doc)
    phase = str(wf.get("current_phase") or "vision")
    return phase if phase in COMPOSITION_PHASES else "vision"


def set_workflow_phase(doc: dict[str, Any], phase: str) -> None:
    if phase not in COMPOSITION_PHASES:
        return
    wf = ensure_workflow(doc)
    wf["current_phase"] = phase


def complete_workflow_phase(doc: dict[str, Any], phase: str) -> None:
    if phase not in COMPOSITION_PHASES:
        return
    wf = ensure_workflow(doc)
    completed = list(wf.get("completed_phases") or [])
    if phase not in completed:
        completed.append(phase)
    wf["completed_phases"] = completed


def next_workflow_phase(doc: dict[str, Any], after: str) -> str | None:
    wf = ensure_workflow(doc)
    try:
        idx = COMPOSITION_PHASES.index(after)
    except ValueError:
        return None
    for phase in COMPOSITION_PHASES[idx + 1 :]:
        if phase == "lyrics" and wf.get("skip_lyrics"):
            continue
        return phase
    return None


def advance_workflow(doc: dict[str, Any], *, from_phase: str | None = None) -> str | None:
    current = from_phase or get_workflow_phase(doc)
    complete_workflow_phase(doc, current)
    nxt = next_workflow_phase(doc, current)
    if nxt:
        set_workflow_phase(doc, nxt)
    return nxt


def phase_is_reachable(doc: dict[str, Any], phase: str) -> bool:
    """Backward navigation and revisiting completed phases — not forward jumps."""
    if phase not in COMPOSITION_PHASES:
        return False
    wf = ensure_workflow(doc)
    current = get_workflow_phase(doc)
    completed = set(wf.get("completed_phases") or [])
    if phase == current or phase in completed:
        return True
    try:
        return COMPOSITION_PHASES.index(phase) < COMPOSITION_PHASES.index(current)
    except ValueError:
        return False


def suggest_musical_defaults(*, genre: str, song_idea: str) -> dict[str, Any]:
    """Lightweight heuristics for mood, energy, tempo, key, and meter."""
    text = f"{genre} {song_idea}".lower()
    mood = ""
    energy = COMPOSITION_ENERGY_LEVELS[1]
    bpm = DEFAULT_BPM
    key = DEFAULT_KEY
    meter = DEFAULT_METER
    groove = DEFAULT_GROOVE
    style = genre if genre in CPL_PROGRESSION_STYLES else _style_from_text(genre)

    if any(w in text for w in ("ballad", "slow", "gentle", "soft", "tender", "melancholy", "sad")):
        mood = "Melancholy / tender"
        energy = COMPOSITION_ENERGY_LEVELS[0]
        bpm = 68
        groove = "Ballad"
    elif any(w in text for w in ("upbeat", "party", "dance", "energetic", "anthem", "driving", "rock")):
        mood = "Uplifting / energetic"
        energy = COMPOSITION_ENERGY_LEVELS[2]
        bpm = 118
        groove = "Rock groove"
    elif any(w in text for w in ("hope", "warm", "love", "joy", "bright")):
        mood = "Warm / hopeful"
        bpm = 92

    if genre == "Jazz":
        style = "Jazz"
        bpm = max(72, min(bpm, 120))
        key = "Bb"
    elif genre == "Blues":
        style = "Blues"
        bpm = 88
        key = "E"
    elif genre == "Soul/R&B":
        style = "Soul/R&B"
        bpm = 86
    elif genre == "Folk":
        style = "Folk"
        bpm = 84
        key = "G"
    elif genre == "Rock":
        style = "Rock"
        bpm = max(bpm, 108)
    elif genre == "Classical":
        style = "Pop"
        bpm = 76
        meter = "3/4"

    if "minor" in text or any(w in text for w in ("dark", "brooding", "haunting")):
        key = "Am" if key == "C" else key
        if not mood:
            mood = "Dark / introspective"

    if not mood:
        mood = "Open — still taking shape"

    return {
        "mood": mood,
        "energy": energy,
        "bpm": bpm,
        "key": key,
        "meter": meter,
        "groove": groove,
        "style": style,
    }


def bootstrap_from_vision(
    *,
    genre: str,
    song_idea: str,
    title: str = "",
    mood: str = "",
    energy: str = "",
    references: str = "",
    instrumental: bool = False,
) -> dict[str, Any]:
    """Create a new document from Phase 1 Song Vision (minimal required fields)."""
    genre = str(genre or "").strip() or "Pop"
    song_idea = str(song_idea or "").strip()
    suggestions = suggest_musical_defaults(genre=genre, song_idea=song_idea)

    working_title = str(title or "").strip()
    if not working_title and song_idea:
        working_title = song_idea.split(".")[0][:80].strip() or "Untitled Song"
    if not working_title:
        working_title = "Untitled Song"

    origin = {
        "seed_type": "vision",
        "seed_summary": song_idea[:500],
        "seed_payload": {
            "genre": genre,
            "references": str(references or "").strip(),
            "energy": str(energy or suggestions["energy"]).strip(),
        },
    }
    doc = {
        "schema_version": COMPOSITION_SCHEMA_VERSION,
        "id": str(uuid.uuid4()),
        "title": working_title,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "status": "draft",
        "origin": origin,
        "metadata": {
            "style": genre,
            "mood": str(mood or suggestions["mood"]).strip(),
            "energy": str(energy or suggestions["energy"]).strip(),
            "references": str(references or "").strip(),
            "language": "en",
            "description": song_idea[:2000],
        },
        "global": {
            "original_key_center": suggestions["key"],
            "time_signature": suggestions["meter"],
            "bpm": suggestions["bpm"],
            "groove_style": suggestions["groove"],
            "progression_style": suggestions["style"],
        },
        "form": {"section_order": [], "sections": {}},
        "integration": default_integration_stub(),
        "ai_settings": {"creativity": "balanced", "explicit_user_is_composer": True},
        "workflow": default_workflow(skip_lyrics=instrumental),
    }
    return touch_composition(doc)


def default_global() -> dict[str, Any]:
    return {
        "original_key_center": DEFAULT_KEY,
        "time_signature": DEFAULT_METER,
        "bpm": DEFAULT_BPM,
        "groove_style": DEFAULT_GROOVE,
        "progression_style": DEFAULT_PROGRESSION_STYLE,
    }


def default_metadata(*, style: str = "", mood: str = "", description: str = "") -> dict[str, Any]:
    return {
        "style": style or DEFAULT_PROGRESSION_STYLE,
        "mood": mood or "",
        "language": "en",
        "description": description or "",
    }


def new_composition_document(
    *,
    title: str = "Untitled Song",
    origin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verse = empty_section("Verse", label_variant="Verse 1")
    chorus = empty_section("Chorus")
    sections = {verse["id"]: verse, chorus["id"]: chorus}
    return {
        "schema_version": COMPOSITION_SCHEMA_VERSION,
        "id": str(uuid.uuid4()),
        "title": str(title or "Untitled Song").strip() or "Untitled Song",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "status": "draft",
        "origin": origin or {"seed_type": "exploring", "seed_summary": "", "seed_payload": {}},
        "metadata": default_metadata(),
        "global": default_global(),
        "form": {
            "section_order": [verse["id"], chorus["id"]],
            "sections": sections,
        },
        "integration": default_integration_stub(),
        "ai_settings": {"creativity": "balanced", "explicit_user_is_composer": True},
    }


def touch_composition(doc: dict[str, Any]) -> dict[str, Any]:
    doc["updated_at"] = _now_iso()
    return doc


def deep_copy_document(doc: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(doc)


def section_by_id(doc: dict[str, Any], section_id: str) -> dict[str, Any] | None:
    sections = (doc.get("form") or {}).get("sections") or {}
    sec = sections.get(section_id)
    return sec if isinstance(sec, dict) else None


def ordered_sections(doc: dict[str, Any]) -> list[dict[str, Any]]:
    order = list((doc.get("form") or {}).get("section_order") or [])
    sections = (doc.get("form") or {}).get("sections") or {}
    out: list[dict[str, Any]] = []
    for sid in order:
        sec = sections.get(sid)
        if isinstance(sec, dict):
            out.append(sec)
    return out


def _ensure_chord_link(sec: dict[str, Any]) -> dict[str, Any]:
    link = sec.get("chord_link")
    if not isinstance(link, dict):
        link = {"source_section_id": None, "linked": False}
        sec["chord_link"] = link
    link.setdefault("source_section_id", None)
    link.setdefault("linked", False)
    return link


def next_label_variant(doc: dict[str, Any], base_label: str, *, exclude_id: str | None = None) -> str:
    """Return Verse 1, Verse 2, … for repeated section types."""
    base_label = str(base_label or "Section").strip() or "Section"
    numbers: list[int] = []
    for sec in ordered_sections(doc):
        sid = str(sec.get("id") or "")
        if exclude_id and sid == exclude_id:
            continue
        if str(sec.get("label") or "") != base_label:
            continue
        variant = str(sec.get("label_variant") or base_label)
        match = re.match(rf"^{re.escape(base_label)}\s*(\d+)?$", variant.strip())
        if match:
            num = match.group(1)
            numbers.append(int(num) if num else 1)
    if not numbers:
        return f"{base_label} 1" if base_label in REPEAT_LINK_LABELS else base_label
    return f"{base_label} {max(numbers) + 1}"


def section_css_type(sec: dict[str, Any]) -> str:
    label = str(sec.get("label") or "Section")
    return SECTION_TYPE_CSS.get(label, "verse")


def chord_link_display(sec: dict[str, Any], doc: dict[str, Any]) -> str:
    link = _ensure_chord_link(sec)
    if not link.get("linked"):
        return ""
    source_id = str(link.get("source_section_id") or "")
    source = section_by_id(doc, source_id) if source_id else None
    if not source:
        return "Linked"
    src_label = str(source.get("label_variant") or source.get("label") or "section")
    return f"Linked to {src_label}"


def apply_structure_template(doc: dict[str, Any], template_key: str = "pop") -> list[dict[str, Any]]:
    """Replace form with a visual starter template; repeats link to first instance."""
    rows = STRUCTURE_TEMPLATES.get(template_key) or STRUCTURE_TEMPLATES["simple"]
    form = doc.setdefault("form", {})
    form["sections"] = {}
    form["section_order"] = []
    first_of_label: dict[str, str] = {}
    created: list[dict[str, Any]] = []

    for label, variant in rows:
        sec = empty_section(label, label_variant=variant)
        form.setdefault("sections", {})[sec["id"]] = sec
        form.setdefault("section_order", []).append(sec["id"])
        created.append(sec)

        if label not in first_of_label:
            first_of_label[label] = sec["id"]
            continue
        if label not in REPEAT_LINK_LABELS:
            continue
        source_id = first_of_label[label]
        source = section_by_id(doc, source_id)
        link = _ensure_chord_link(sec)
        link["source_section_id"] = source_id
        link["linked"] = True
        if source:
            sec["chords"] = copy.deepcopy(source.get("chords") or [])

    touch_composition(doc)
    return created


def break_chord_link(doc: dict[str, Any], section_id: str) -> bool:
    sec = section_by_id(doc, section_id)
    if not sec:
        return False
    link = _ensure_chord_link(sec)
    if not link.get("linked"):
        return False
    link["linked"] = False
    link["source_section_id"] = None
    return True


def harmony_edit_target(doc: dict[str, Any], section_id: str) -> tuple[str, dict[str, Any] | None]:
    """Return the section that owns editable harmony (follows chord links to source)."""
    sec = section_by_id(doc, section_id)
    if not sec:
        return section_id, None
    link = _ensure_chord_link(sec)
    source_id = str(link.get("source_section_id") or "")
    if link.get("linked") and source_id:
        source = section_by_id(doc, source_id)
        if source:
            return source_id, source
    return section_id, sec


def sync_linked_chord_sections(doc: dict[str, Any], source_section_id: str) -> None:
    source = section_by_id(doc, source_section_id)
    if not source:
        return
    chords = copy.deepcopy(source.get("chords") or [])
    sections = (doc.get("form") or {}).get("sections") or {}
    for sec in sections.values():
        if not isinstance(sec, dict):
            continue
        link = _ensure_chord_link(sec)
        if link.get("linked") and str(link.get("source_section_id") or "") == source_section_id:
            sec["chords"] = copy.deepcopy(chords)


def apply_section_chords(
    doc: dict[str, Any],
    section_id: str,
    entries: list[dict[str, Any]],
    *,
    propagate_links: bool = True,
) -> bool:
    edit_id, sec = harmony_edit_target(doc, section_id)
    if not sec:
        return False
    sec["chords"] = copy.deepcopy(entries)
    if propagate_links and edit_id:
        sync_linked_chord_sections(doc, edit_id)
    touch_composition(doc)
    return True


def section_has_chords(sec: dict[str, Any]) -> bool:
    return bool(sec.get("chords"))


def harmonized_section_count(doc: dict[str, Any]) -> tuple[int, int]:
    sections = ordered_sections(doc)
    if not sections:
        return 0, 0
    done = sum(1 for s in sections if section_has_chords(s))
    return done, len(sections)


def add_section(
    doc: dict[str, Any],
    label: str,
    *,
    after_id: str | None = None,
    link_to_id: str | None = None,
) -> dict[str, Any]:
    label = str(label or "Section").strip() or "Section"
    variant = next_label_variant(doc, label)
    sec = empty_section(label, label_variant=variant)
    form = doc.setdefault("form", {})
    sections = form.setdefault("sections", {})
    sections[sec["id"]] = sec
    order = list(form.get("section_order") or [])

    if after_id and after_id in order:
        idx = order.index(after_id) + 1
        order.insert(idx, sec["id"])
    else:
        order.append(sec["id"])
    form["section_order"] = order

    source_id = link_to_id
    if not source_id and label in REPEAT_LINK_LABELS:
        for existing in ordered_sections(doc):
            if str(existing.get("id")) == sec["id"]:
                continue
            if str(existing.get("label") or "") == label:
                source_id = str(existing.get("id") or "")
                break
    if source_id:
        source = section_by_id(doc, source_id)
        if source:
            link = _ensure_chord_link(sec)
            link["source_section_id"] = source_id
            link["linked"] = True
            sec["chords"] = copy.deepcopy(source.get("chords") or [])

    return sec


def duplicate_section(
    doc: dict[str, Any],
    section_id: str,
    *,
    link_chords: bool = True,
) -> dict[str, Any] | None:
    src = section_by_id(doc, section_id)
    if not src:
        return None
    clone = deep_copy_document({"form": {"sections": {section_id: src}}})["form"]["sections"][section_id]
    clone["id"] = _new_section_id()
    base = str(src.get("label") or "Section")
    clone["label"] = base
    clone["label_variant"] = next_label_variant(doc, base, exclude_id=clone["id"])
    link = _ensure_chord_link(clone)
    if link_chords and base in REPEAT_LINK_LABELS:
        link["source_section_id"] = section_id
        link["linked"] = True
    else:
        link["source_section_id"] = None
        link["linked"] = False

    form = doc.setdefault("form", {})
    sections = form.setdefault("sections", {})
    sections[clone["id"]] = clone
    order = list(form.get("section_order") or [])
    try:
        idx = order.index(section_id)
        order.insert(idx + 1, clone["id"])
    except ValueError:
        order.append(clone["id"])
    form["section_order"] = order
    return clone


def move_section(doc: dict[str, Any], section_id: str, direction: int) -> bool:
    form = doc.get("form") or {}
    order = list(form.get("section_order") or [])
    if section_id not in order:
        return False
    idx = order.index(section_id)
    new_idx = idx + int(direction)
    if new_idx < 0 or new_idx >= len(order):
        return False
    order[idx], order[new_idx] = order[new_idx], order[idx]
    form["section_order"] = order
    return True


def remove_section(doc: dict[str, Any], section_id: str) -> bool:
    form = doc.get("form") or {}
    order = list(form.get("section_order") or [])
    if section_id not in order or len(order) <= 1:
        return False
    order = [s for s in order if s != section_id]
    form["section_order"] = order
    sections = form.get("sections") or {}
    for sec in sections.values():
        if not isinstance(sec, dict):
            continue
        link = _ensure_chord_link(sec)
        if str(link.get("source_section_id") or "") == section_id:
            link["linked"] = False
            link["source_section_id"] = None
    sections.pop(section_id, None)
    return True


def parse_chord_paste(text: str) -> list[dict[str, Any]]:
    """Parse '| G | Am | C |', comma-separated, or space-separated symbols."""
    raw = str(text or "").strip()
    if not raw:
        return []
    if "|" in raw or "\n" in raw or "," in raw or ";" in raw:
        parts = re.split(r"[|\n,;/]+", raw)
    else:
        parts = raw.split()
    entries: list[dict[str, Any]] = []
    for part in parts:
        sym = normalize_chord_symbol(part.strip())
        if sym:
            entries.append({"chord": sym, "bars": 1})
    return entries


def _style_from_text(text: str) -> str:
    lower = text.lower()
    for style in CPL_PROGRESSION_STYLES:
        if style.lower() in lower:
            return style
    keywords = {
        "jazz": "Jazz",
        "blues": "Blues",
        "rock": "Rock",
        "folk": "Folk",
        "bossa": "Bossa",
        "funk": "Funk",
        "ballad": "Pop",
        "worship": "Pop",
        "classical": "Pop",
        "film": "Pop",
    }
    for key, style in keywords.items():
        if key in lower:
            return style
    return DEFAULT_PROGRESSION_STYLE


def bootstrap_from_seed(
    *,
    seed_type: str,
    seed_text: str = "",
    seed_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new document from the user's starting idea."""
    payload = dict(seed_payload or {})
    text = str(seed_text or "").strip()
    stype = str(seed_type or "exploring").strip().lower()
    if stype not in SEED_TYPES:
        stype = "mixed" if text else "exploring"

    title = str(payload.get("title") or "").strip()
    if not title and stype == "title" and text:
        title = text[:120]
    if not title:
        title = "Untitled Song"

    mood = str(payload.get("mood") or "").strip()
    style = str(payload.get("style") or "").strip()
    if stype == "mood" and text:
        mood = text[:200]
    if stype in {"style_intent", "exploring", "mixed"} and text:
        if not style:
            style = _style_from_text(text)
        if not mood and any(w in text.lower() for w in ("sad", "hope", "joy", "dark", "love", "bitter")):
            mood = text[:120]

    origin = {
        "seed_type": stype,
        "seed_summary": text[:500] if text else str(payload.get("summary") or ""),
        "seed_payload": payload,
    }
    doc = new_composition_document(title=title, origin=origin)
    meta = doc.setdefault("metadata", default_metadata())
    if style:
        meta["style"] = style
        doc.setdefault("global", default_global())["progression_style"] = style
    if mood:
        meta["mood"] = mood
    if text and stype in {"style_intent", "exploring", "mixed"}:
        meta["description"] = text[:2000]

    sections = ordered_sections(doc)
    first = sections[0] if sections else add_section(doc, "Verse")

    if stype == "chords" and text:
        first["chords"] = parse_chord_paste(text)
    elif stype == "lyrics" and text:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        first["lyrics"] = {"lines": lines, "raw_text": text}
    elif stype == "rhythm":
        bpm = payload.get("bpm")
        meter = payload.get("time_signature")
        g = doc.setdefault("global", default_global())
        if bpm:
            g["bpm"] = int(bpm)
        if meter in CPL_TIME_SIGNATURES:
            g["time_signature"] = meter
        if style:
            g["progression_style"] = style

    if stype == "style_intent" and "ballad" in text.lower():
        g = doc.setdefault("global", default_global())
        g["bpm"] = min(g.get("bpm", DEFAULT_BPM), 72)
        g["groove_style"] = "Ballad"

    return touch_composition(doc)


def chords_for_playback(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
) -> list[str]:
    """Flatten chord entries for backing preview."""
    sections_map = (doc.get("form") or {}).get("sections") or {}
    order = list((doc.get("form") or {}).get("section_order") or [])
    if scope == "section" and section_id:
        sec = sections_map.get(section_id) or {}
        return expand_entries_to_chords(sec.get("chords") or [])
    chords: list[str] = []
    for sid in order:
        sec = sections_map.get(sid) or {}
        chords.extend(expand_entries_to_chords(sec.get("chords") or []))
    return chords


def playback_globals(doc: dict[str, Any]) -> dict[str, Any]:
    g = doc.get("global") or {}
    meta = doc.get("metadata") or {}
    style = str(g.get("progression_style") or meta.get("style") or DEFAULT_PROGRESSION_STYLE)
    groove = str(g.get("groove_style") or DEFAULT_GROOVE)
    if groove == "Auto":
        groove = f"{style} groove" if "groove" not in style.lower() else style
    return {
        "bpm": int(g.get("bpm") or DEFAULT_BPM),
        "time_signature": str(g.get("time_signature") or DEFAULT_METER),
        "style": style,
        "groove": groove,
        "key_center": str(g.get("original_key_center") or DEFAULT_KEY),
        "mood": str(meta.get("mood") or ""),
    }


def document_summary_line(doc: dict[str, Any]) -> str:
    pg = playback_globals(doc)
    parts = [
        pg["key_center"],
        pg["style"],
        f"{pg['bpm']} BPM",
        pg["time_signature"],
    ]
    if pg["mood"]:
        parts.append(pg["mood"])
    return " · ".join(parts)
