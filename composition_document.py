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
    "Breakdown",
    "Outro",
    "Custom",
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
    "Breakdown": "interlude",
    "Outro": "outro",
    "Custom": "interlude",
}

DEFAULT_PROGRESSION_STYLE = "Pop"
DEFAULT_GROOVE = "Auto"
DEFAULT_BPM = 96
DEFAULT_KEY = "C"
DEFAULT_METER = "4/4"
DEFAULT_KEY_LABEL = "C major"

# Common meters plus room for a free-form custom value (e.g. 11/8).
COMPOSITION_METERS: tuple[str, ...] = (
    "4/4",
    "3/4",
    "6/8",
    "12/8",
    "5/4",
    "7/8",
    "2/4",
    "9/8",
)
COMPOSITION_METER_CUSTOM = "Custom…"

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
    "Jewish",
    "Other",
)

# Legacy short tokens kept for older documents / tests. Prefer
# ``composition_key_choice_labels()`` for musician-facing UI.
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

# Canonical melody origin — persisted on section.melody.source.
# "edit" is a correction flag, not a competing melody authority.
MELODY_SOURCES: tuple[str, ...] = ("ai", "recorded", "manual", "edit")
_MELODY_SOURCE_ALIASES: dict[str, str] = {
    "ai": "ai",
    "generated": "ai",
    "suggestion": "ai",
    "recorded": "recorded",
    "hum": "recorded",
    "hum_transcription": "recorded",
    "transcription": "recorded",
    "manual": "manual",
    "user": "manual",
    "edit": "edit",
    "edited": "edit",
}

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


def composition_key_choice_labels() -> list[str]:
    """Musician-facing key dropdown — major + minor with distinct enharmonic spellings.

    C# minor and Db minor remain separate choices. Built from music_theory SSOT.
    """
    from music_theory import ENHARMONIC_MAJOR_KEYS, ENHARMONIC_MINOR_KEYS, display_key_label

    labels: list[str] = []
    seen: set[str] = set()
    for token in list(ENHARMONIC_MAJOR_KEYS) + list(ENHARMONIC_MINOR_KEYS):
        label = display_key_label(token)
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def composition_key_token_from_choice(choice: str) -> str:
    """Map UI label ('Db minor') → composition token ('Dbm'), preserving tonic spelling."""
    text = str(choice or "").strip()
    if not text:
        return DEFAULT_KEY
    try:
        from music_theory import split_key_center

        tonic, mode = split_key_center(text)
        tonic = str(tonic or "").strip() or DEFAULT_KEY
        if str(mode).lower() == "minor":
            return tonic if tonic.endswith("m") else f"{tonic}m"
        return tonic
    except Exception:
        return text


def composition_key_label_from_token(token: str) -> str:
    """Map composition token ('Dbm') → UI label ('Db minor'), preserving spelling."""
    text = str(token or "").strip() or DEFAULT_KEY
    try:
        from music_theory import display_key_label

        label = str(display_key_label(text) or "").strip()
        labels = composition_key_choice_labels()
        if label in labels:
            return label
        # Token may already be a label.
        if text in labels:
            return text
        return label or DEFAULT_KEY_LABEL
    except Exception:
        return DEFAULT_KEY_LABEL


def coerce_composition_key_choice(choice: str, *, fallback: str = DEFAULT_KEY_LABEL) -> str:
    """Return a label present in ``composition_key_choice_labels()``."""
    options = composition_key_choice_labels()
    text = str(choice or "").strip()
    if text in options:
        return text
    if text:
        mapped = composition_key_label_from_token(text)
        if mapped in options:
            return mapped
    if fallback in options:
        return fallback
    return options[0] if options else DEFAULT_KEY_LABEL


_METER_RE = re.compile(r"^([1-9]\d{0,1})\s*/\s*([1-9]\d{0,1})$")


def coerce_composition_meter(value: str, *, fallback: str = DEFAULT_METER) -> str:
    """Normalize a meter string (common list or custom N/D)."""
    text = str(value or "").strip().replace(" ", "")
    if not text or text == COMPOSITION_METER_CUSTOM:
        return fallback if fallback else DEFAULT_METER
    if text in COMPOSITION_METERS:
        return text
    m = _METER_RE.match(text)
    if m:
        return f"{int(m.group(1))}/{int(m.group(2))}"
    return fallback if fallback else DEFAULT_METER


def coerce_composition_bpm(value: Any, *, fallback: int = DEFAULT_BPM) -> int:
    try:
        bpm = int(value)
    except (TypeError, ValueError):
        bpm = int(fallback or DEFAULT_BPM)
    return max(40, min(240, bpm))


def document_has_structure(doc: dict[str, Any]) -> bool:
    return bool(ordered_sections(doc))


def section_lane_status(doc: dict[str, Any], section_id: str) -> dict[str, str]:
    """Per-section completion: complete / incomplete / not_applicable."""
    sec = section_by_id(doc, section_id)
    wf = ensure_workflow(doc)
    skip_lyrics = bool(wf.get("skip_lyrics"))
    if not sec:
        return {"chords": "incomplete", "melody": "incomplete", "lyrics": "not_applicable" if skip_lyrics else "incomplete"}
    return {
        "chords": "complete" if section_has_resolved_chords(doc, section_id) else "incomplete",
        "melody": "complete" if section_has_melody(sec) else "incomplete",
        "lyrics": (
            "not_applicable"
            if skip_lyrics
            else ("complete" if section_has_lyrics(sec) else "incomplete")
        ),
    }


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
        "melody": {
            "intent": {
                "remember": "",
                "feel": "",
                "style": "simple",
                "hum_notes": "",
            },
            "phrases": [],
            "events": [],
            "source": "",
            "edited": False,
        },
        "lyrics": {
            "intent": {
                "communicate": "",
                "emotion": "",
                "role": "",
                "remember": "",
            },
            "lines": [],
            "raw_text": "",
        },
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
    """Guided-but-nonlinear navigation.

    Vision and Structure are always available once a composition exists.
    After structure sections exist (or Structure is completed), Chords / Melody /
    Lyrics / Review are freely reachable so the composer can jump between
    sections and lanes without a one-way lock.
    """
    if phase not in COMPOSITION_PHASES:
        return False
    wf = ensure_workflow(doc)
    if phase == "lyrics" and wf.get("skip_lyrics"):
        return False

    current = get_workflow_phase(doc)
    completed = set(wf.get("completed_phases") or [])
    if phase == current or phase in completed:
        return True
    if phase in {"vision", "structure"}:
        return True

    structure_ready = ("structure" in completed) or document_has_structure(doc)
    if phase in {"chords", "melody", "lyrics", "review"} and structure_ready:
        return True

    try:
        return COMPOSITION_PHASES.index(phase) < COMPOSITION_PHASES.index(current)
    except ValueError:
        return False


def suggest_musical_defaults(*, genre: str, song_idea: str) -> dict[str, Any]:
    """Optional heuristics for mood/energy/tempo/key/meter — never forced ownership."""
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

    key_label = composition_key_label_from_token(key)
    return {
        "mood": mood,
        "energy": energy,
        "bpm": bpm,
        "key": key,
        "key_label": key_label,
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
    key: str = "",
    bpm: Any = None,
    meter: str = "",
) -> dict[str, Any]:
    """Create a new document from Song Vision with user-owned key / BPM / meter.

    Optional ``key`` / ``bpm`` / ``meter`` are authoritative when provided.
    Heuristic suggestions only fill gaps — they do not silently override the user.
    """
    genre = str(genre or "").strip() or "Pop"
    song_idea = str(song_idea or "").strip()
    suggestions = suggest_musical_defaults(genre=genre, song_idea=song_idea)

    key_raw = str(key or "").strip()
    if key_raw:
        key_label = coerce_composition_key_choice(key_raw)
        key_token = composition_key_token_from_choice(key_label)
    else:
        key_token = str(suggestions["key"] or DEFAULT_KEY)
        key_label = composition_key_label_from_token(key_token)

    bpm_value = coerce_composition_bpm(
        bpm if bpm is not None and str(bpm).strip() != "" else suggestions["bpm"]
    )
    meter_value = coerce_composition_meter(
        meter if str(meter or "").strip() else suggestions["meter"]
    )

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
            "key_label": key_label,
            "user_chose_key": bool(key_raw),
            "user_chose_bpm": bpm is not None and str(bpm).strip() != "",
            "user_chose_meter": bool(str(meter or "").strip()),
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
            "original_key_center": key_token,
            "original_key_label": key_label,
            "time_signature": meter_value,
            "bpm": bpm_value,
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
        "original_key_label": DEFAULT_KEY_LABEL,
        "time_signature": DEFAULT_METER,
        "bpm": DEFAULT_BPM,
        "groove_style": DEFAULT_GROOVE,
        "progression_style": DEFAULT_PROGRESSION_STYLE,
    }


def default_metadata(*, style: str = "", mood: str = "", description: str = "", energy: str = "") -> dict[str, Any]:
    return {
        "style": style or DEFAULT_PROGRESSION_STYLE,
        "mood": mood or "",
        "energy": energy or "",
        "language": "en",
        "description": description or "",
    }


def composition_song_brief(doc: dict[str, Any] | None) -> dict[str, Any]:
    """Read-only song brief from the existing metadata/origin/global authority.

    Does not introduce a second store. Theme maps to ``metadata.description``
    (vision song idea); style maps to ``metadata.style``.
    """
    if not isinstance(doc, dict):
        return {
            "title": "",
            "style": "",
            "mood": "",
            "energy": "",
            "theme": "",
            "references": "",
            "key": "",
            "key_label": "",
            "tempo": DEFAULT_BPM,
            "meter": DEFAULT_METER,
            "instrumental": False,
        }
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    origin = doc.get("origin") if isinstance(doc.get("origin"), dict) else {}
    payload = origin.get("seed_payload") if isinstance(origin.get("seed_payload"), dict) else {}
    g = doc.get("global") if isinstance(doc.get("global"), dict) else {}
    wf = doc.get("workflow") if isinstance(doc.get("workflow"), dict) else {}
    key_token = str(g.get("original_key_center") or DEFAULT_KEY)
    key_label = str(g.get("original_key_label") or "").strip() or composition_key_label_from_token(key_token)
    return {
        "title": str(doc.get("title") or "").strip(),
        "style": str(meta.get("style") or payload.get("genre") or "").strip(),
        "mood": str(meta.get("mood") or "").strip(),
        "energy": str(meta.get("energy") or payload.get("energy") or "").strip(),
        "theme": str(meta.get("description") or origin.get("seed_summary") or "").strip(),
        "references": str(meta.get("references") or payload.get("references") or "").strip(),
        "key": key_token,
        "key_label": key_label,
        "tempo": coerce_composition_bpm(g.get("bpm")),
        "meter": coerce_composition_meter(str(g.get("time_signature") or DEFAULT_METER)),
        "instrumental": bool(wf.get("skip_lyrics")),
    }


def apply_song_brief(
    doc: dict[str, Any],
    *,
    title: str | None = None,
    style: str | None = None,
    mood: str | None = None,
    energy: str | None = None,
    theme: str | None = None,
    references: str | None = None,
) -> dict[str, Any]:
    """Write brief fields into the existing metadata/origin authority only."""
    meta = doc.setdefault("metadata", default_metadata())
    if not isinstance(meta, dict):
        meta = default_metadata()
        doc["metadata"] = meta
    origin = doc.setdefault("origin", {"seed_type": "vision", "seed_summary": "", "seed_payload": {}})
    if not isinstance(origin, dict):
        origin = {"seed_type": "vision", "seed_summary": "", "seed_payload": {}}
        doc["origin"] = origin
    payload = origin.setdefault("seed_payload", {})
    if not isinstance(payload, dict):
        payload = {}
        origin["seed_payload"] = payload
    if title is not None:
        text = str(title).strip()
        if text:
            doc["title"] = text
    if style is not None:
        meta["style"] = str(style).strip()
        payload["genre"] = meta["style"]
    if mood is not None:
        meta["mood"] = str(mood).strip()
    if energy is not None:
        meta["energy"] = str(energy).strip()
        payload["energy"] = meta["energy"]
    if theme is not None:
        text = str(theme).strip()
        meta["description"] = text
        origin["seed_summary"] = text[:500]
    if references is not None:
        meta["references"] = str(references).strip()
        payload["references"] = meta["references"]
    touch_composition(doc)
    return composition_song_brief(doc)


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


def replace_section_chord(
    doc: dict[str, Any],
    section_id: str,
    index: int,
    chord: str,
    *,
    propagate_links: bool = True,
) -> bool:
    edit_id, sec = harmony_edit_target(doc, section_id)
    if not sec:
        return False
    entries = list(sec.get("chords") or [])
    if index < 0 or index >= len(entries):
        return False
    row = dict(entries[index]) if isinstance(entries[index], dict) else {"chord": "", "bars": 1}
    row["chord"] = normalize_chord_symbol(chord) or str(chord).strip()
    entries[index] = row
    sec["chords"] = entries
    if propagate_links and edit_id:
        sync_linked_chord_sections(doc, edit_id)
    touch_composition(doc)
    return True


def insert_section_chord(
    doc: dict[str, Any],
    section_id: str,
    index: int,
    chord: str,
    *,
    bars: int = 1,
    propagate_links: bool = True,
) -> bool:
    edit_id, sec = harmony_edit_target(doc, section_id)
    if not sec:
        return False
    entries = list(sec.get("chords") or [])
    idx = max(0, min(int(index), len(entries)))
    entries.insert(
        idx,
        {"chord": normalize_chord_symbol(chord) or str(chord).strip(), "bars": max(1, int(bars or 1))},
    )
    sec["chords"] = entries
    if propagate_links and edit_id:
        sync_linked_chord_sections(doc, edit_id)
    touch_composition(doc)
    return True


def remove_section_chord(
    doc: dict[str, Any],
    section_id: str,
    index: int,
    *,
    propagate_links: bool = True,
) -> bool:
    edit_id, sec = harmony_edit_target(doc, section_id)
    if not sec:
        return False
    entries = list(sec.get("chords") or [])
    if index < 0 or index >= len(entries):
        return False
    entries.pop(index)
    sec["chords"] = entries
    if propagate_links and edit_id:
        sync_linked_chord_sections(doc, edit_id)
    touch_composition(doc)
    return True


def move_section_chord(
    doc: dict[str, Any],
    section_id: str,
    index: int,
    delta: int,
    *,
    propagate_links: bool = True,
) -> bool:
    edit_id, sec = harmony_edit_target(doc, section_id)
    if not sec:
        return False
    entries = list(sec.get("chords") or [])
    if index < 0 or index >= len(entries):
        return False
    new_idx = index + int(delta)
    if new_idx < 0 or new_idx >= len(entries):
        return False
    entries[index], entries[new_idx] = entries[new_idx], entries[index]
    sec["chords"] = entries
    if propagate_links and edit_id:
        sync_linked_chord_sections(doc, edit_id)
    touch_composition(doc)
    return True


def section_has_chords(sec: dict[str, Any]) -> bool:
    return bool(sec.get("chords"))


def section_has_resolved_chords(doc: dict[str, Any], section_id: str) -> bool:
    """True when this section (or its linked harmony source) has chords."""
    _, sec = harmony_edit_target(doc, section_id)
    return bool(sec and sec.get("chords"))


def harmonized_section_count(doc: dict[str, Any]) -> tuple[int, int]:
    sections = ordered_sections(doc)
    if not sections:
        return 0, 0
    done = sum(1 for s in sections if section_has_resolved_chords(doc, str(s.get("id") or "")))
    return done, len(sections)


def normalize_melody_source(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return ""
    if text in MELODY_SOURCES:
        return text
    return _MELODY_SOURCE_ALIASES.get(text, "")


def infer_melody_source_from_concept(concept: dict[str, Any] | None) -> str:
    if not isinstance(concept, dict) or not concept:
        return ""
    cid = str(concept.get("id") or "").strip().lower()
    mapped = normalize_melody_source(cid)
    if mapped:
        return mapped
    name = str(concept.get("name") or "").strip().lower()
    if "record" in name or "hum" in name or "transcri" in name:
        return "recorded"
    return "ai"


def section_melody_source(sec: dict[str, Any] | None) -> str:
    if not isinstance(sec, dict):
        return ""
    melody = _ensure_melody_block(sec)
    return normalize_melody_source(melody.get("source"))


def _set_melody_source(melody: dict[str, Any], source: str, *, mark_edited: bool = False) -> None:
    resolved = normalize_melody_source(source)
    existing = normalize_melody_source(melody.get("source"))
    if mark_edited or resolved == "edit":
        melody["edited"] = True
        if not existing:
            melody["source"] = resolved or "edit"
        return
    if resolved:
        if existing and existing != resolved:
            melody["edited"] = True
        melody["source"] = resolved


def _ensure_melody_block(sec: dict[str, Any]) -> dict[str, Any]:
    melody = sec.get("melody")
    if not isinstance(melody, dict):
        melody = {"intent": {}, "phrases": [], "events": [], "source": "", "edited": False}
        sec["melody"] = melody
    intent = melody.get("intent")
    if not isinstance(intent, dict):
        melody["intent"] = intent = {}
    intent.setdefault("remember", "")
    intent.setdefault("feel", "")
    intent.setdefault("style", "simple")
    intent.setdefault("hum_notes", "")
    if not isinstance(melody.get("phrases"), list):
        melody["phrases"] = []
    if not isinstance(melody.get("events"), list):
        melody["events"] = []
    melody.setdefault("source", "")
    melody.setdefault("edited", False)
    return melody


def normalize_melody_event(raw: Any) -> dict[str, Any] | None:
    """Canonical melody event: pitch name, duration beats, optional beat/measure."""
    if not isinstance(raw, dict):
        return None
    pitch = str(raw.get("pitch") or raw.get("note") or "").strip()
    is_rest = bool(raw.get("is_rest")) or pitch.lower() == "rest"
    if not pitch and not is_rest:
        return None
    if is_rest:
        pitch = "rest"
    try:
        duration = float(raw.get("duration_beats") or raw.get("duration") or 1.0)
    except (TypeError, ValueError):
        duration = 1.0
    duration = max(0.25, min(8.0, duration))
    try:
        beat = float(raw.get("beat") if raw.get("beat") is not None else raw.get("start_beat") or 0.0)
    except (TypeError, ValueError):
        beat = 0.0
    try:
        measure = int(raw.get("measure") or 1)
    except (TypeError, ValueError):
        measure = 1
    midi = raw.get("midi")
    try:
        midi_i = int(midi) if midi is not None and not is_rest else None
    except (TypeError, ValueError):
        midi_i = None
    out: dict[str, Any] = {
        "pitch": pitch,
        "midi": midi_i,
        "duration_beats": duration,
        "beat": max(0.0, beat),
        "measure": max(1, measure),
    }
    if is_rest:
        out["is_rest"] = True
    if "confidence" in raw:
        try:
            out["confidence"] = float(raw.get("confidence"))
        except (TypeError, ValueError):
            pass
    if "uncertain" in raw:
        out["uncertain"] = bool(raw.get("uncertain"))
    return out


def normalize_melody_events(events: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cursor = 0.0
    for raw in list(events or []):
        ev = normalize_melody_event(raw)
        if not ev:
            continue
        if ev["beat"] <= 0 and cursor > 0:
            ev["beat"] = cursor
        out.append(ev)
        cursor = float(ev["beat"]) + float(ev["duration_beats"])
    return out


def section_melody_events(sec: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(sec, dict):
        return []
    melody = _ensure_melody_block(sec)
    events = normalize_melody_events(melody.get("events"))
    if events:
        return events
    # Fallback: parse simple space-separated note names from the first phrase.
    for phrase in melody.get("phrases") or []:
        if not isinstance(phrase, dict):
            continue
        notes = str(phrase.get("notes") or "").strip()
        if not notes:
            continue
        tokens = [t for t in re.split(r"[\s,|]+", notes) if t]
        built: list[dict[str, Any]] = []
        beat = 0.0
        for tok in tokens:
            built.append({"pitch": tok, "duration_beats": 1.0, "beat": beat, "measure": 1})
            beat += 1.0
        return normalize_melody_events(built)
    return []


def apply_melody_events(
    doc: dict[str, Any],
    section_id: str,
    events: list[dict[str, Any]],
    *,
    concept: dict[str, Any] | None = None,
    replace: bool = True,
    source: str = "",
    edited: bool = False,
) -> list[dict[str, Any]]:
    sec = section_by_id(doc, section_id)
    if not sec:
        return []
    melody = _ensure_melody_block(sec)
    normalized = normalize_melody_events(events)
    if replace:
        melody["events"] = normalized
    else:
        melody["events"] = normalize_melody_events(list(melody.get("events") or []) + normalized)
    resolved = normalize_melody_source(source) or infer_melody_source_from_concept(concept)
    _set_melody_source(melody, resolved, mark_edited=edited)
    if concept:
        phrase = {
            "id": str(uuid.uuid4()),
            "label": str(concept.get("name") or "Melodic idea"),
            "concept_id": str(concept.get("id") or ""),
            "motif": str(concept.get("motif_hint") or concept.get("contour") or ""),
            "notes": " ".join(str(e.get("pitch") or "") for e in normalized),
        }
        melody.setdefault("phrases", []).append(phrase)
    touch_composition(doc)
    return normalized


def section_has_melody(sec: dict[str, Any]) -> bool:
    melody = _ensure_melody_block(sec)
    if normalize_melody_events(melody.get("events")):
        return True
    for phrase in melody.get("phrases") or []:
        if not isinstance(phrase, dict):
            continue
        if str(phrase.get("motif") or "").strip() or str(phrase.get("notes") or "").strip():
            return True
    return bool(str((melody.get("intent") or {}).get("hum_notes") or "").strip())


def melodized_section_count(doc: dict[str, Any]) -> tuple[int, int]:
    sections = ordered_sections(doc)
    if not sections:
        return 0, 0
    done = sum(1 for s in sections if section_has_melody(s))
    return done, len(sections)


def apply_melody_concept(
    doc: dict[str, Any],
    section_id: str,
    concept: dict[str, Any],
) -> dict[str, Any]:
    sec = section_by_id(doc, section_id)
    if not sec:
        return {}
    melody = _ensure_melody_block(sec)
    events = normalize_melody_events(concept.get("events") or concept.get("notes_events") or [])
    note_line = " ".join(str(e.get("pitch") or "") for e in events) if events else str(concept.get("notes_line") or "")
    phrase = {
        "id": str(uuid.uuid4()),
        "label": str(concept.get("name") or "Melodic idea"),
        "concept_id": str(concept.get("id") or ""),
        "motif": str(concept.get("motif_hint") or concept.get("contour") or ""),
        "notes": note_line,
    }
    melody.setdefault("phrases", []).append(phrase)
    if events:
        melody["events"] = events
    _set_melody_source(melody, infer_melody_source_from_concept(concept) or "ai")
    touch_composition(doc)
    return phrase


def add_melody_phrase(
    doc: dict[str, Any],
    section_id: str,
    *,
    label: str = "My phrase",
    motif: str = "",
    notes: str = "",
) -> dict[str, Any]:
    sec = section_by_id(doc, section_id)
    if not sec:
        return {}
    melody = _ensure_melody_block(sec)
    phrase = {
        "id": str(uuid.uuid4()),
        "label": str(label or "My phrase").strip() or "My phrase",
        "concept_id": "",
        "motif": str(motif or "").strip(),
        "notes": str(notes or "").strip(),
    }
    melody.setdefault("phrases", []).append(phrase)
    if not normalize_melody_source(melody.get("source")):
        melody["source"] = "manual"
    touch_composition(doc)
    return phrase


def remove_melody_phrase(doc: dict[str, Any], section_id: str, phrase_id: str) -> bool:
    sec = section_by_id(doc, section_id)
    if not sec:
        return False
    melody = _ensure_melody_block(sec)
    phrases = [p for p in (melody.get("phrases") or []) if str(p.get("id") or "") != phrase_id]
    melody["phrases"] = phrases
    touch_composition(doc)
    return True


def _ensure_lyrics_block(sec: dict[str, Any]) -> dict[str, Any]:
    lyrics = sec.get("lyrics")
    if not isinstance(lyrics, dict):
        lyrics = {"intent": {}, "lines": [], "raw_text": ""}
        sec["lyrics"] = lyrics
    intent = lyrics.get("intent")
    if not isinstance(intent, dict):
        lyrics["intent"] = intent = {}
    intent.setdefault("communicate", "")
    intent.setdefault("emotion", "")
    intent.setdefault("role", "")
    intent.setdefault("remember", "")
    if not isinstance(lyrics.get("lines"), list):
        lyrics["lines"] = []
    lyrics.setdefault("raw_text", "")
    return lyrics


def section_has_lyrics(sec: dict[str, Any]) -> bool:
    lyrics = _ensure_lyrics_block(sec)
    if str(lyrics.get("raw_text") or "").strip():
        return True
    return any(str(line or "").strip() for line in (lyrics.get("lines") or []))


def lyrics_section_count(doc: dict[str, Any]) -> tuple[int, int]:
    sections = ordered_sections(doc)
    if not sections:
        return 0, 0
    done = sum(1 for s in sections if section_has_lyrics(s))
    return done, len(sections)


def apply_lyric_prompt_to_section(
    doc: dict[str, Any],
    section_id: str,
    prompt: dict[str, Any],
) -> None:
    sec = section_by_id(doc, section_id)
    if not sec:
        return
    lyrics = _ensure_lyrics_block(sec)
    starter = str(prompt.get("prompt") or "").strip()
    if starter:
        existing = str(lyrics.get("raw_text") or "").strip()
        lyrics["raw_text"] = f"{existing}\n\n{starter}".strip() if existing else starter
    touch_composition(doc)


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


def move_section(doc: dict[str, Any], section_id: str, direction: int) -> bool:
    form = doc.setdefault("form", {})
    order = list(form.get("section_order") or [])
    if section_id not in order:
        return False
    idx = order.index(section_id)
    new_idx = idx + int(direction)
    if new_idx < 0 or new_idx >= len(order):
        return False
    order[idx], order[new_idx] = order[new_idx], order[idx]
    form["section_order"] = order
    touch_composition(doc)
    return True


def remove_section(doc: dict[str, Any], section_id: str) -> bool:
    form = doc.setdefault("form", {})
    order = list(form.get("section_order") or [])
    if section_id not in order or len(order) <= 1:
        return False
    idx = order.index(section_id)
    order = [s for s in order if s != section_id]
    form["section_order"] = order
    sections = form.setdefault("sections", {})
    for sec in sections.values():
        if not isinstance(sec, dict):
            continue
        link = _ensure_chord_link(sec)
        if str(link.get("source_section_id") or "") == section_id:
            link["linked"] = False
            link["source_section_id"] = None
    sections.pop(section_id, None)
    touch_composition(doc)
    return True


def neighbor_section_after_remove(doc: dict[str, Any], removed_id: str, prior_order: list[str]) -> str:
    """Pick a sensible section to select after removing ``removed_id``."""
    order = list((doc.get("form") or {}).get("section_order") or [])
    if not order:
        return ""
    if removed_id in prior_order:
        idx = prior_order.index(removed_id)
        # Prefer the next section, else previous.
        for candidate in prior_order[idx + 1 :] + list(reversed(prior_order[:idx])):
            if candidate in order:
                return candidate
    return order[0]


def duplicate_section(
    doc: dict[str, Any],
    section_id: str,
    *,
    link_chords: bool = False,
) -> dict[str, Any] | None:
    """Duplicate a section as an independent instance by default (no auto-link)."""
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
        # Independent copy keeps its own chord snapshot from the deep copy.

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
    touch_composition(doc)
    return clone


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
        _, sec = harmony_edit_target(doc, section_id)
        if sec:
            return expand_entries_to_chords(sec.get("chords") or [])
        sec = sections_map.get(section_id) or {}
        return expand_entries_to_chords(sec.get("chords") or [])
    chords: list[str] = []
    for sid in order:
        _, sec = harmony_edit_target(doc, str(sid))
        if not sec:
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
    key_token = str(g.get("original_key_center") or DEFAULT_KEY)
    key_label = str(g.get("original_key_label") or "").strip() or composition_key_label_from_token(
        key_token
    )
    return {
        "bpm": coerce_composition_bpm(g.get("bpm")),
        "time_signature": coerce_composition_meter(str(g.get("time_signature") or DEFAULT_METER)),
        "style": style,
        "groove": groove,
        "key_center": key_token,
        "key_label": key_label,
        "mood": str(meta.get("mood") or ""),
    }


def document_summary_line(doc: dict[str, Any]) -> str:
    pg = playback_globals(doc)
    parts = [
        pg.get("key_label") or pg["key_center"],
        pg["style"],
        f"{pg['bpm']} BPM",
        pg["time_signature"],
    ]
    if pg["mood"]:
        parts.append(pg["mood"])
    return " · ".join(parts)
