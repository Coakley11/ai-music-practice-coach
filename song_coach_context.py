"""Song-Aware Coaching (S1) — the verified song snapshot a coaching session is built on.

:class:`SongCoachContext` is a frozen record of *which* song is being coached and *what
harmony the app actually knows for it*: the global source owner (Catalog / Custom /
Composition), its identity, the concert sections at the concert Practice Key, the
player-facing chart key (Written / Shape), and how far the chart can be trusted.

Rules this module enforces:

- **The global source owner decides the song.** Custom and Composition sections come
  from :func:`workflow_musical_authority.resolve_owner_concert_sections` and are
  authoritative even when empty; the SBI *preview* source never changes the coached song.
- **Fail closed.** No song, no chords, a placeholder chart, an Entry & Jam progression
  or a chart that is out of step with the live song / Practice Key gives an unavailable
  context with a reason — never another source's chords.
- **Theory in concert pitch.** Sections stay at the concert Practice Key; ``chart_key``
  and ``written_key`` are carried for display projection only.
- **Read-only.** :func:`song_coach_context_from_session` never writes session state. It
  takes the concert sections the Creative page already resolved this run instead of
  re-running the catalog resolver (which can reclaim / rewrite the Practice Key).
- **Truthful labels.** :data:`CHART_CONFIDENCE_LABELS` distinguishes verified harmony
  from simplified practice charts; nothing here knows a melody or a recorded solo.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

SOURCE_CATALOG = "catalog"
SOURCE_CUSTOM = "custom"
SOURCE_COMPOSITION = "composition"

CHART_VERIFIED = "verified"
CHART_USER_EDITED = "user_edited"
CHART_USER_AUTHORED = "user_authored"
CHART_PRACTICE = "practice"

CHART_CONFIDENCE_LABELS: dict[str, str] = {
    CHART_VERIFIED: "Verified chord chart",
    CHART_USER_EDITED: "Your edited chord chart",
    CHART_USER_AUTHORED: "Your own progression",
    CHART_PRACTICE: "Simplified practice chart",
}

CHART_CONFIDENCE_NOTES: dict[str, str] = {
    CHART_VERIFIED: "The chords were checked against the song. Coaching uses the chords only — "
    "the app does not know the song's melody or any recorded solo.",
    CHART_USER_EDITED: "Coaching follows your edited chords. The app does not know the song's "
    "melody or any recorded solo.",
    CHART_USER_AUTHORED: "Coaching follows the chords you wrote.",
    CHART_PRACTICE: "A simplified practice chart: the harmony may differ from the recording. "
    "Coaching uses these chords only — the app does not know the song's melody or any recorded solo.",
}

_VERIFIED_STATUSES = frozenset({"verified", "practice_level_verified", "user_verified"})
_USER_EDITED_STATUSES = frozenset({"user_corrected_reference"})
PLACEHOLDER_STATUS = "placeholder"

# Fail-closed reasons (stable ids; the UI maps them to musician-facing copy).
REASON_NO_SONG = "no_song"
REASON_NO_CHORDS = "no_chords"
REASON_PLACEHOLDER = "placeholder_chart"
REASON_NO_KEY = "no_practice_key"
REASON_JAM_PROGRESSION = "jam_progression"
REASON_SONG_OUT_OF_SYNC = "song_out_of_sync"
REASON_CHART_OUT_OF_SYNC = "chart_out_of_sync"
REASON_KEY_OUT_OF_SYNC = "chart_key_out_of_sync"

UNAVAILABLE_MESSAGES: dict[str, str] = {
    REASON_NO_SONG: "Choose a song on the Songs page to start Song-Aware Coaching.",
    REASON_NO_CHORDS: "This song has no chords yet, so there is nothing to coach over.",
    REASON_PLACEHOLDER: "This song only has a placeholder chart, so its harmony can't be coached yet.",
    REASON_NO_KEY: "The Practice Key isn't settled yet — try again in a moment.",
    REASON_JAM_PROGRESSION: "Song-Aware Coaching works on your active song, not on a generated Jam.",
    REASON_SONG_OUT_OF_SYNC: "The active song is still updating — try again in a moment.",
    REASON_CHART_OUT_OF_SYNC: "The chord chart is still updating for this song — try again in a moment.",
    REASON_KEY_OUT_OF_SYNC: "The chord chart is still moving to the new Practice Key — try again in a moment.",
}

_NO_CHORD_TOKENS = frozenset({"N.C.", "N.C", "NC", "N/C", "%"})


def _clean(text: Any) -> str:
    return str(text or "").strip()


def is_no_chord(token: Any) -> bool:
    """True for an explicit no-chord bar (``N.C.``) — a rest, not a harmony."""
    return _clean(token).upper() in _NO_CHORD_TOKENS


def clean_sections(sections: Any) -> dict[str, list[str]]:
    """``{name: [bar tokens]}`` with blank names / bars removed; empty sections dropped."""
    out: dict[str, list[str]] = {}
    if not isinstance(sections, Mapping):
        return out
    for name, bars in sections.items():
        label = _clean(name)
        if not label or not isinstance(bars, (list, tuple)):
            continue
        clean = [_clean(b) for b in bars if _clean(b)]
        if clean:
            out[label] = clean
    return out


def ordered_section_items(
    sections: Mapping[str, Sequence[str]], section_order: Sequence[str] | None = None
) -> list[tuple[str, tuple[str, ...]]]:
    """Sections in chart order (explicit order first, then insertion order) as tuples."""
    from songs.form import section_order as _section_order

    order = [str(n) for n in (section_order or []) if _clean(n)]
    return [(name, tuple(bars)) for name, bars in _section_order(dict(sections), section_names=order or None)]


def chart_confidence(source_kind: str, record: Mapping[str, Any] | None) -> str:
    """How far the chord chart can be trusted (never inferred from the title)."""
    if source_kind in (SOURCE_CUSTOM, SOURCE_COMPOSITION):
        return CHART_USER_AUTHORED
    rec = record if isinstance(record, Mapping) else {}
    status = _clean(rec.get("chart_status")).lower()
    if rec.get("user_override") or status in _USER_EDITED_STATUSES:
        return CHART_USER_EDITED
    # ``trusted_core`` only marks the curated core song list — it is not harmony verification.
    if status in _VERIFIED_STATUSES:
        return CHART_VERIFIED
    return CHART_PRACTICE


def _theory_root_pc(token: str) -> int:
    """Pitch class of a bar's first chord root, or -1 (no chord / unparseable)."""
    from music_theory import chord_root_for_theory, normalize_chord_for_theory, pitch_class_from_spelled_note

    symbol = normalize_chord_for_theory(token)
    if not symbol or is_no_chord(symbol):
        return -1
    root = chord_root_for_theory(symbol)
    if not root or root[0].upper() not in "ABCDEFG":
        return -1
    try:
        return int(pitch_class_from_spelled_note(root)) % 12
    except Exception:
        return -1


def _key_pc(key: str) -> int:
    from music_theory import pitch_class_from_spelled_note, split_key_center

    tonic, _mode = split_key_center(_clean(key) or "C")
    try:
        return int(pitch_class_from_spelled_note(tonic)) % 12
    except Exception:
        return -1


def chart_structure_matches(
    concert: Mapping[str, Sequence[str]], reference: Mapping[str, Sequence[str]]
) -> bool:
    """Same section names and the same number of bars in each — the song's own form."""
    if set(concert) != set(reference):
        return False
    return all(len(concert[name]) == len(reference[name]) for name in reference)


def chart_is_at_key(
    concert: Mapping[str, Sequence[str]],
    reference: Mapping[str, Sequence[str]],
    *,
    reference_key: str,
    concert_key: str,
) -> bool:
    """Every charted bar is the reference bar moved by exactly reference_key → concert_key.

    A map still in an older Practice Key (or the original key after a move) fails, so a
    Practice Key change that has not reached the chart can never be coached.
    """
    shift_from, shift_to = _key_pc(reference_key), _key_pc(concert_key)
    if shift_from < 0 or shift_to < 0:
        return False
    shift = (shift_to - shift_from) % 12
    compared = 0
    for name, ref_bars in reference.items():
        for ref_bar, bar in zip(ref_bars, concert.get(name) or ()):
            a, b = _theory_root_pc(ref_bar), _theory_root_pc(bar)
            if a < 0 and b < 0:
                continue
            if a < 0 or b < 0 or (b - a) % 12 != shift:
                return False
            compared += 1
    return compared > 0


@dataclass(frozen=True)
class SongCoachContext:
    """The coached song. ``available`` False ⇒ ``reason`` says why; nothing else is coachable."""

    available: bool
    reason: str = ""
    identity: str = ""
    source_kind: str = ""
    song_title: str = ""
    artist: str = ""
    chart_confidence: str = CHART_PRACTICE
    chart_structure_verified: bool = False
    concert_key: str = ""
    chart_key: str = ""
    written_key: str = ""
    instrument: str = ""
    meter: str = "4/4"
    bpm: int = 0
    style: str = "default"
    sections: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
    fingerprint: str = ""
    projection_fingerprint: str = ""

    @property
    def chart_label(self) -> str:
        return CHART_CONFIDENCE_LABELS.get(self.chart_confidence, CHART_CONFIDENCE_LABELS[CHART_PRACTICE])

    @property
    def chart_note(self) -> str:
        return CHART_CONFIDENCE_NOTES.get(self.chart_confidence, CHART_CONFIDENCE_NOTES[CHART_PRACTICE])

    @property
    def unavailable_message(self) -> str:
        return UNAVAILABLE_MESSAGES.get(self.reason, "") if not self.available else ""

    @property
    def is_verified_harmony(self) -> bool:
        return self.chart_confidence == CHART_VERIFIED

    def section_map(self) -> dict[str, list[str]]:
        return {name: list(bars) for name, bars in self.sections}

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "identity": self.identity,
            "source_kind": self.source_kind,
            "song_title": self.song_title,
            "artist": self.artist,
            "chart_confidence": self.chart_confidence,
            "chart_structure_verified": self.chart_structure_verified,
            "concert_key": self.concert_key,
            "chart_key": self.chart_key,
            "written_key": self.written_key,
            "instrument": self.instrument,
            "meter": self.meter,
            "bpm": self.bpm,
            "style": self.style,
            "sections": [[name, list(bars)] for name, bars in self.sections],
            "fingerprint": self.fingerprint,
            "projection_fingerprint": self.projection_fingerprint,
        }


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def musical_fingerprint(
    identity: str, source_kind: str, concert_key: str, meter: str, sections: Sequence[tuple[str, Sequence[str]]]
) -> str:
    """Changes with the song, the concert Practice Key, the meter or any charted bar."""
    return _digest(
        {
            "identity": identity,
            "source": source_kind,
            "key": concert_key,
            "meter": meter,
            "sections": [[name, list(bars)] for name, bars in sections],
        }
    )


def projection_fingerprint(musical: str, *, chart_key: str, written_key: str, instrument: str) -> str:
    """Changes when only the player's projection (instrument / Written / Shape key) changes."""
    return _digest({"musical": musical, "chart": chart_key, "written": written_key, "instrument": instrument})


def unavailable(reason: str, **known: Any) -> SongCoachContext:
    return SongCoachContext(available=False, reason=reason, **known)


def build_song_coach_context(
    *,
    identity: str,
    source_kind: str,
    concert_sections: Mapping[str, Sequence[str]] | None,
    concert_key: str,
    section_order: Sequence[str] | None = None,
    record: Mapping[str, Any] | None = None,
    reference_sections: Mapping[str, Sequence[str]] | None = None,
    reference_key: str = "",
    song_title: str = "",
    artist: str = "",
    chart_key: str = "",
    written_key: str = "",
    instrument: str = "",
    meter: str = "4/4",
    bpm: int = 0,
    style: str = "default",
    jam_sections: Mapping[str, Sequence[str]] | None = None,
) -> SongCoachContext:
    """Validate the inputs and freeze them; any doubt fails closed.

    ``reference_sections`` / ``reference_key`` are the song's own chart and the key it is
    written in (Catalog). When given, ``concert_sections`` must have the same form and sit
    exactly at ``concert_key``. ``jam_sections`` is the Entry & Jam progression, which must
    never stand in for the song.
    """
    identity = _clean(identity)
    source_kind = _clean(source_kind) or SOURCE_CATALOG
    concert_key = _clean(concert_key)
    meter = _clean(meter) or "4/4"
    rec = record if isinstance(record, Mapping) else {}
    known = {
        "identity": identity,
        "source_kind": source_kind,
        "song_title": _clean(song_title) or _clean(rec.get("title")),
        "artist": _clean(artist) or _clean(rec.get("artist")),
        "chart_confidence": chart_confidence(source_kind, rec),
        "concert_key": concert_key,
        "chart_key": _clean(chart_key) or concert_key,
        "written_key": _clean(written_key),
        "instrument": _clean(instrument),
        "meter": meter,
        "bpm": int(bpm or 0),
        "style": _clean(style) or "default",
    }
    if not identity:
        return unavailable(REASON_NO_SONG, **known)
    if source_kind == SOURCE_CATALOG and _clean(rec.get("chart_status")).lower() == PLACEHOLDER_STATUS:
        return unavailable(REASON_PLACEHOLDER, **known)
    sections = clean_sections(concert_sections)
    if not any(_theory_root_pc(bar) >= 0 for bars in sections.values() for bar in bars):
        return unavailable(REASON_NO_CHORDS, **known)
    if not concert_key or _key_pc(concert_key) < 0:
        return unavailable(REASON_NO_KEY, **known)
    jam = clean_sections(jam_sections)
    if jam and jam == sections:
        return unavailable(REASON_JAM_PROGRESSION, **known)
    reference = clean_sections(reference_sections)
    structure_verified = False
    if reference:
        if not chart_structure_matches(sections, reference):
            return unavailable(REASON_CHART_OUT_OF_SYNC, **known)
        if _clean(reference_key) and not chart_is_at_key(
            sections, reference, reference_key=reference_key, concert_key=concert_key
        ):
            return unavailable(REASON_KEY_OUT_OF_SYNC, **known)
        structure_verified = True
    ordered = tuple(ordered_section_items(sections, section_order))
    musical = musical_fingerprint(identity, source_kind, concert_key, meter, ordered)
    return SongCoachContext(
        available=True,
        chart_structure_verified=structure_verified,
        sections=ordered,
        fingerprint=musical,
        projection_fingerprint=projection_fingerprint(
            musical, chart_key=known["chart_key"], written_key=known["written_key"], instrument=known["instrument"]
        ),
        **known,
    )


# --------------------------------------------------------------------------- session adapter


def source_owner(session: Mapping[str, Any]) -> str:
    """The global source owner: ``composition`` / ``custom`` / ``catalog`` (never the SBI preview)."""
    try:
        from workflow_musical_authority import (
            composition_owns_active_song_material,
            custom_owns_active_song_material,
        )
    except ImportError:
        return SOURCE_CATALOG
    if composition_owns_active_song_material(session):  # type: ignore[arg-type]
        return SOURCE_COMPOSITION
    if custom_owns_active_song_material(session):  # type: ignore[arg-type]
        return SOURCE_CUSTOM
    return SOURCE_CATALOG


def _pick_key(session: Mapping[str, Any]) -> str:
    pick = _clean(session.get("active_catalog_pick_key"))
    if pick:
        return pick
    sel = session.get("selected_song")
    return _clean(sel.get("pick_key")) if isinstance(sel, Mapping) else ""


def _is_custom_pick(pick: str) -> bool:
    return pick.startswith(("custom::", "custom\x1f"))


def _is_composition_pick(pick: str) -> bool:
    return pick.startswith(("composition::", "composition\x1f"))


def _active_custom(session: Mapping[str, Any]) -> dict[str, Any]:
    """A private copy of the live Custom progression (its helpers mutate what they get)."""
    active = session.get("cpl_active_progression")
    return copy.deepcopy(dict(active)) if isinstance(active, Mapping) and active else {}


def _active_composition(session: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from composition_session_state import get_active_document

        doc = get_active_document(session)  # type: ignore[arg-type]
    except ImportError:
        doc = None
    return copy.deepcopy(dict(doc)) if isinstance(doc, Mapping) and doc else {}


def global_song_identity(session: Mapping[str, Any], owner: str) -> str:
    """``owner|song id`` of the global active song, or "" when it cannot be named safely."""
    pick = _pick_key(session)
    if owner == SOURCE_CATALOG:
        if not pick or _is_custom_pick(pick) or _is_composition_pick(pick):
            return ""
        return f"{SOURCE_CATALOG}|{pick}"
    if owner == SOURCE_CUSTOM:
        song_id = pick if _is_custom_pick(pick) else ""
        active = _active_custom(session)
        if not song_id and active:
            try:
                from songs.music_source import custom_pick_key_for

                song_id = _clean(custom_pick_key_for(active))
            except ImportError:
                song_id = _clean(active.get("id"))
        return f"{SOURCE_CUSTOM}|{song_id}" if song_id else ""
    if owner == SOURCE_COMPOSITION:
        song_id = pick if _is_composition_pick(pick) else ""
        if not song_id:
            try:
                from composition_songs_bridge import composition_pick_key_for

                song_id = _clean(composition_pick_key_for(_active_composition(session)))
            except ImportError:
                song_id = ""
        return f"{SOURCE_COMPOSITION}|{song_id}" if song_id else ""
    return ""


def live_catalog_record(session: Mapping[str, Any]) -> dict[str, Any]:
    """``selected_song`` only when it belongs to the live catalog pick (never another song's)."""
    sel = session.get("selected_song")
    if not isinstance(sel, Mapping) or not sel:
        return {}
    pick = _pick_key(session)
    sel_pick = _clean(sel.get("pick_key"))
    if sel_pick and pick and sel_pick != pick:
        return {}
    record = dict(sel)
    # The live song blob does not carry the catalog's chart verification; read it from the
    # merged catalog row for this pick (read-only), which also reflects saved user edits.
    flags = catalog_chart_flags(pick or sel_pick)
    record.update({k: v for k, v in flags.items() if v not in (None, "")})
    return record


def catalog_chart_flags(pick: str) -> dict[str, Any]:
    """``chart_status`` / ``user_override`` of the merged catalog row for ``pick`` ({} if unknown)."""
    if not pick:
        return {}
    try:
        from song_catalog.catalog import load_song_catalog, record_for_pick_key

        row = record_for_pick_key(load_song_catalog()[3], pick)
    except Exception:
        return {}
    if not isinstance(row, Mapping):
        return {}
    return {"chart_status": row.get("chart_status"), "user_override": row.get("user_override")}


def custom_reference_chart(active: Mapping[str, Any]) -> tuple[dict[str, list[str]], str, dict[str, Any]]:
    """A Custom progression's own bars in its original key, read from a copy."""
    if not active:
        return {}, "", {}
    try:
        from custom_progression_lab import ensure_original_structure, sections_to_chord_lists
        from songs.music_source import custom_original_key
    except ImportError:
        return {}, "", {}
    struct = ensure_original_structure(copy.deepcopy(dict(active)))
    sections = clean_sections(sections_to_chord_lists(struct.get("original_sections") or {}))
    key = _clean(custom_original_key(copy.deepcopy(struct)))
    record = {
        "title": _clean(struct.get("name") or struct.get("title")),
        "artist": _clean(struct.get("artist")),
        "time_signature": _clean(struct.get("time_signature")),
        "bpm": struct.get("bpm") or 0,
    }
    return sections, key, record


def composition_reference_chart(doc: Mapping[str, Any]) -> tuple[dict[str, list[str]], str, dict[str, Any]]:
    """A Composition's own sections in its original key.

    Mirrors the section extraction of
    :func:`workflow_musical_authority.resolve_composition_concert_sections_at_practice_key`
    (one chart entry per chord, repeated labels numbered) without its Practice Key
    resolution; ``tests/test_song_coach_context.py`` pins the two together.

    Known limitation (kept deliberately): like that shared resolver, each Composition chord
    entry counts as one bar — its ``bars`` value is ignored — so Composition bar numbers can
    be shorter than the document's form. Coaching mirrors what the rest of Creative shows;
    the shared resolver is not changed here.
    """
    if not doc:
        return {}, "", {}
    try:
        from composition_document import ordered_sections
        from composition_songs_bridge import composition_home_key
    except ImportError:
        return {}, "", {}
    sections: dict[str, list[str]] = {}
    for sec in ordered_sections(dict(doc)):
        label = _clean(sec.get("label") or sec.get("name"))
        if not label:
            continue
        symbols = []
        for entry in sec.get("chords") or []:
            sym = _clean(entry.get("chord") or entry.get("symbol")) if isinstance(entry, Mapping) else _clean(entry)
            if sym:
                symbols.append(sym)
        if not symbols:
            continue
        name, suffix = label, 2
        while name in sections:
            name, suffix = f"{label} {suffix}", suffix + 1
        sections[name] = symbols
    glob = doc.get("global") if isinstance(doc.get("global"), Mapping) else {}
    record = {
        "title": _clean(doc.get("title") or glob.get("title")),
        "artist": "",
        "time_signature": _clean(glob.get("time_signature") or glob.get("meter")),
        "bpm": glob.get("bpm") or glob.get("tempo_bpm") or 0,
    }
    return sections, _clean(composition_home_key(dict(doc))), record


def song_coach_context_from_session(
    session: Mapping[str, Any],
    *,
    concert_sections: Mapping[str, Sequence[str]] | None,
    concert_key: str,
    chart_key: str = "",
    written_key: str = "",
    instrument: str = "",
    section_order: Sequence[str] | None = None,
    song_title: str = "",
    artist: str = "",
    meter: str = "",
    bpm: int = 0,
    style: str = "default",
) -> SongCoachContext:
    """Read-only snapshot for the Creative page (never writes ``session``).

    ``concert_sections`` / ``concert_key`` are what the Creative page resolved this run.
    They are accepted only when they are the global owner's own chart (same form) at
    exactly ``concert_key``. Custom and Composition charts are authoritative even when
    empty, so a leftover Catalog or Jam map can never answer for them.
    """
    owner = source_owner(session)
    identity = global_song_identity(session, owner)
    if owner == SOURCE_CATALOG:
        record = live_catalog_record(session)
        sel = session.get("selected_song")
        if identity and isinstance(sel, Mapping) and sel and not record:
            return unavailable(REASON_SONG_OUT_OF_SYNC, identity=identity, source_kind=owner)
        reference = clean_sections(record.get("sections"))
        reference_key = _clean(record.get("key") or record.get("original_key"))
        order = section_order or record.get("section_order")
    else:
        if owner == SOURCE_CUSTOM:
            reference, reference_key, record = custom_reference_chart(_active_custom(session))
        else:
            reference, reference_key, record = composition_reference_chart(_active_composition(session))
        if not reference:
            return unavailable(
                REASON_NO_CHORDS if identity else REASON_NO_SONG,
                identity=identity,
                source_kind=owner,
                chart_confidence=CHART_USER_AUTHORED,
                song_title=_clean(song_title) or _clean(record.get("title")),
            )
        order = section_order or list(reference)
    ext = record.get("extensions") if isinstance(record.get("extensions"), Mapping) else {}
    record_meter = _clean(record.get("time_signature") or record.get("meter") or ext.get("time_signature"))
    try:
        record_bpm = int(record.get("bpm") or ext.get("default_bpm") or 0)
    except (TypeError, ValueError):
        record_bpm = 0
    jam = session.get("improv_generated_sections")
    return build_song_coach_context(
        identity=identity,
        source_kind=owner,
        concert_sections=concert_sections,
        concert_key=concert_key,
        section_order=order,  # type: ignore[arg-type]
        record=record,
        reference_sections=reference,
        reference_key=reference_key,
        song_title=song_title,
        artist=artist,
        chart_key=chart_key,
        written_key=written_key,
        instrument=instrument or _clean(session.get("instrument")),
        meter=meter or record_meter or "4/4",
        bpm=bpm or record_bpm,
        style=style,
        jam_sections=jam if isinstance(jam, Mapping) else None,
    )


__all__ = [
    "CHART_CONFIDENCE_LABELS",
    "CHART_CONFIDENCE_NOTES",
    "CHART_PRACTICE",
    "CHART_USER_AUTHORED",
    "CHART_USER_EDITED",
    "CHART_VERIFIED",
    "REASON_CHART_OUT_OF_SYNC",
    "REASON_JAM_PROGRESSION",
    "REASON_KEY_OUT_OF_SYNC",
    "REASON_NO_CHORDS",
    "REASON_NO_KEY",
    "REASON_NO_SONG",
    "REASON_PLACEHOLDER",
    "REASON_SONG_OUT_OF_SYNC",
    "SOURCE_CATALOG",
    "SOURCE_COMPOSITION",
    "SOURCE_CUSTOM",
    "SongCoachContext",
    "UNAVAILABLE_MESSAGES",
    "build_song_coach_context",
    "catalog_chart_flags",
    "chart_confidence",
    "chart_is_at_key",
    "chart_structure_matches",
    "clean_sections",
    "composition_reference_chart",
    "custom_reference_chart",
    "global_song_identity",
    "is_no_chord",
    "live_catalog_record",
    "musical_fingerprint",
    "ordered_section_items",
    "projection_fingerprint",
    "song_coach_context_from_session",
    "source_owner",
]
