"""Canonical Creative workflow session — durable across navigation, refresh, and cloud restore."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

CREATIVE_SESSION_KEY = "creative_session"
JAM_SESSION_GENERATE_GUARD_KEY = "_jam_session_generate_guard"
JAM_CAPTURE_STAGING_KEY = "_jam_capture_staging"

CreativeToolType = Literal[
    "entry_style_jam",
    "jam_session_generator",
    "song_based_improvisation",
    "mission",
    "custom_progression",
]

_ENTRY_MODE_TO_TOOL: dict[str, CreativeToolType] = {
    "Style Jam Mode": "entry_style_jam",
    "Jam Session Generator": "jam_session_generator",
    "Song-Based Improvisation": "song_based_improvisation",
}

_TOOL_TO_ENTRY_MODE: dict[CreativeToolType, str] = {
    "entry_style_jam": "Style Jam Mode",
    "jam_session_generator": "Jam Session Generator",
    "song_based_improvisation": "Song-Based Improvisation",
}


def _normalize_improv_intelligence_tab(tab: str) -> str:
    """Clamp persisted tab names to the live Improvisation Intelligence radio set."""
    try:
        from studio_page_state import IMPROV_TAB_NAMES
    except ImportError:
        IMPROV_TAB_NAMES = ("Entry & Jam", "Missions")  # type: ignore[misc,assignment]
    text = str(tab or "").strip()
    return text if text in IMPROV_TAB_NAMES else IMPROV_TAB_NAMES[0]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CreativeSession:
    """Single source of truth for the active Creative editing / jam workflow."""

    session_id: str
    tool_type: CreativeToolType
    entry_mode: str
    song_source: str = "Active song"
    concert_key: str = "C"
    display_key: str = ""
    instrument: str = ""
    style: str = ""
    mood: str = "Mellow"
    groove_intensity: str = "Medium"
    difficulty: str = "Intermediate"
    bpm: int = 110
    meter: str = "4/4"
    sections: dict[str, list[str]] = field(default_factory=dict)
    selected_section: str = ""
    mission_id: str = ""
    bound_song_id: str = ""
    intelligence_tab: str = "Entry & Jam"
    updated_at: str = ""
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = uuid.uuid4().hex[:16]
        if not self.entry_mode:
            self.entry_mode = _TOOL_TO_ENTRY_MODE.get(self.tool_type, "Style Jam Mode")
        if not self.display_key:
            self.display_key = self.concert_key or "C"
        if not self.updated_at:
            self.updated_at = utc_now_iso()
        if not self.signature:
            self.signature = compute_creative_session_signature(self)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> CreativeSession | None:
        if not isinstance(raw, dict):
            return None
        tool = str(raw.get("tool_type") or "").strip()
        if tool not in _TOOL_TO_ENTRY_MODE:
            entry = str(raw.get("entry_mode") or "").strip()
            tool = _ENTRY_MODE_TO_TOOL.get(entry, "")
        if not tool:
            return None
        sections_raw = raw.get("sections")
        sections: dict[str, list[str]] = {}
        if isinstance(sections_raw, dict):
            sections = {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in sections_raw.items()
                if isinstance(chords, list)
            }
        return cls(
            session_id=str(raw.get("session_id") or ""),
            tool_type=tool,  # type: ignore[arg-type]
            entry_mode=str(raw.get("entry_mode") or _TOOL_TO_ENTRY_MODE.get(tool, "")),
            song_source=str(raw.get("song_source") or "Active song"),
            concert_key=str(raw.get("concert_key") or "C"),
            display_key=str(raw.get("display_key") or raw.get("concert_key") or "C"),
            instrument=str(raw.get("instrument") or ""),
            style=str(raw.get("style") or ""),
            mood=str(raw.get("mood") or "Mellow"),
            groove_intensity=str(raw.get("groove_intensity") or "Medium"),
            difficulty=str(raw.get("difficulty") or "Intermediate"),
            bpm=int(raw.get("bpm") or 110),
            meter=str(raw.get("meter") or "4/4"),
            sections=sections,
            selected_section=str(raw.get("selected_section") or ""),
            mission_id=str(raw.get("mission_id") or ""),
            bound_song_id=str(raw.get("bound_song_id") or ""),
            intelligence_tab=str(raw.get("intelligence_tab") or "Entry & Jam"),
            updated_at=str(raw.get("updated_at") or ""),
            signature=str(raw.get("signature") or ""),
        )


def compute_creative_session_signature(sess: CreativeSession | dict[str, Any]) -> str:
    data = sess.to_dict() if isinstance(sess, CreativeSession) else dict(sess)
    payload = {
        "tool_type": data.get("tool_type"),
        "entry_mode": data.get("entry_mode"),
        "concert_key": data.get("concert_key"),
        "style": data.get("style"),
        "bpm": data.get("bpm"),
        "meter": data.get("meter"),
        "mission_id": data.get("mission_id"),
    }
    sections = data.get("sections")
    if isinstance(sections, dict):
        payload["sections"] = "|".join(
            f"{k}:{','.join(str(c) for c in v)}"
            for k, v in sections.items()
            if isinstance(v, list)
        )
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def get_creative_session(session: dict[str, Any], *, allow_migrate: bool = True) -> CreativeSession | None:
    raw = session.get(CREATIVE_SESSION_KEY)
    if raw is not None:
        return CreativeSession.from_dict(raw)
    if not allow_migrate:
        return None
    migrated = migrate_legacy_creative_session(session)
    if migrated is not None:
        set_creative_session(session, migrated)
        return migrated
    return None


def set_creative_session(session: dict[str, Any], sess: CreativeSession) -> None:
    sess.updated_at = utc_now_iso()
    sess.signature = compute_creative_session_signature(sess)
    session[CREATIVE_SESSION_KEY] = sess.to_dict()


def clear_creative_session(session: dict[str, Any]) -> None:
    session.pop(CREATIVE_SESSION_KEY, None)


def _creative_session_blob_has_workflow(sess: CreativeSession) -> bool:
    if sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
        return bool(sess.sections) or bool(sess.style)
    if sess.tool_type == "song_based_improvisation":
        return bool(sess.sections)
    if sess.tool_type == "mission":
        return bool(sess.mission_id)
    return False


def creative_session_is_active(session: dict[str, Any]) -> bool:
    """True when a standalone Creative jam workflow should own key/BPM state."""
    sess = get_creative_session(session)
    if sess is None:
        return False
    if not _creative_session_blob_has_workflow(sess):
        return False
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "creative" and sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
        return True
    try:
        from backing_context import catalog_or_custom_backing_is_authoritative

        if catalog_or_custom_backing_is_authoritative(session):
            return False
    except ImportError:
        pass
    return True


def _mission_sections_from_session(session: dict[str, Any]) -> dict[str, list[str]]:
    """Single-chord loop for the active mission tile (not the full song form)."""
    try:
        from backing_context import build_mission_context

        ctx = build_mission_context(session)
        if ctx.progression:
            label = str(ctx.section or ctx.progression_label or "Mission").strip() or "Mission"
            return {label: list(ctx.progression)}
    except ImportError:
        pass
    chord = str(session.get("ii_selected_chord") or "").strip()
    section = str(session.get("ii_selected_section") or "Mission").strip() or "Mission"
    if chord:
        return {section: [chord]}
    return {}


def _sections_from_session(session: dict[str, Any], entry_mode: str) -> dict[str, list[str]]:
    if entry_mode == "Jam Session Generator":
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict):
            raw = jam.get("sections")
            if isinstance(raw, dict) and raw:
                return {
                    str(name): [str(c) for c in chords if str(c).strip()]
                    for name, chords in raw.items()
                    if isinstance(chords, list)
                }
    if entry_mode == "Song-Based Improvisation":
        stored = session.get("improv_song_concert_sections")
        if isinstance(stored, dict) and stored:
            return {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in stored.items()
                if isinstance(chords, list)
            }
    gen = session.get("improv_generated_sections")
    if isinstance(gen, dict) and gen:
        return {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in gen.items()
            if isinstance(chords, list)
        }
    return {}


def _live_jam_session_fields(session: dict[str, Any]) -> tuple[str, str, int, str]:
    """Read Jam Session Generator widget values, honoring pending hydrates when locked."""
    staging = session.get(JAM_CAPTURE_STAGING_KEY)
    if isinstance(staging, dict):
        try:
            bpm = int(staging.get("bpm") or 110)
        except (TypeError, ValueError):
            bpm = 110
        return (
            str(staging.get("style") or "").strip(),
            str(staging.get("concert_key") or "C").strip() or "C",
            bpm,
            str(staging.get("mood") or "Mellow").strip() or "Mellow",
        )
    try:
        from session_widget_safe import (
            PENDING_IMPROV_JAM_BPM_KEY,
            PENDING_IMPROV_JAM_KEY,
            PENDING_IMPROV_JAM_MOOD_KEY,
            PENDING_IMPROV_JAM_STYLE_KEY,
        )
    except ImportError:
        PENDING_IMPROV_JAM_KEY = "_pending_improv_jam_key"  # type: ignore[misc,assignment]
        PENDING_IMPROV_JAM_BPM_KEY = "_pending_improv_jam_bpm"  # type: ignore[misc,assignment]
        PENDING_IMPROV_JAM_MOOD_KEY = "_pending_improv_jam_mood"  # type: ignore[misc,assignment]
        PENDING_IMPROV_JAM_STYLE_KEY = "_pending_improv_jam_style"  # type: ignore[misc,assignment]
    style = str(session.get(PENDING_IMPROV_JAM_STYLE_KEY) or session.get("improv_jam_style") or "").strip()
    concert = str(session.get("improv_jam_key") or "").strip()
    pending_key = session.get(PENDING_IMPROV_JAM_KEY)
    if pending_key is not None:
        concert = str(pending_key).strip() or concert
    bpm_raw = session.get(PENDING_IMPROV_JAM_BPM_KEY)
    if bpm_raw is None:
        bpm_raw = session.get("improv_jam_bpm")
    try:
        bpm = int(bpm_raw or 110)
    except (TypeError, ValueError):
        bpm = 110
    mood = str(session.get(PENDING_IMPROV_JAM_MOOD_KEY) or session.get("improv_jam_mood") or "Mellow").strip()
    return style, concert or "C", bpm, mood or "Mellow"


def capture_jam_session_generator_state(
    session: dict[str, Any],
    *,
    ensemble: str,
    style: str,
    concert_key: str,
    bpm: int,
    mood: str,
    jam_session: dict[str, Any],
    st_like: Any | None = None,
) -> CreativeSession | None:
    """Persist live Jam Session Generator widget values before rerun/hydrate can clobber them."""
    try:
        from songs.music_source import snapshot_catalog_before_creative

        snapshot_catalog_before_creative(session, refresh_if_pick_changed=True)
    except ImportError:
        pass
    k = str(concert_key or "C").strip() or "C"
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            k = resolve_practice_concert_key_for_song(session, "C", fallback=k)
    except ImportError:
        pass
    style_name = str(style or "").strip()
    mood_name = str(mood or "Mellow").strip() or "Mellow"
    tempo = int(bpm)

    ensemble_name = str(ensemble or "").strip() or "Jazz trio"
    session[JAM_CAPTURE_STAGING_KEY] = {
        "ensemble": ensemble_name,
        "style": style_name,
        "concert_key": k,
        "bpm": tempo,
        "mood": mood_name,
        "entry_mode": "Jam Session Generator",
    }
    session["improv_jam_session"] = jam_session

    try:
        from session_widget_safe import safe_session_assign

        safe_session_assign(
            session, "improv_entry_mode", "Jam Session Generator", widget_safe=True
        )
        safe_session_assign(session, "improv_ensemble", ensemble_name, widget_safe=True)
        safe_session_assign(session, "improv_jam_style", style_name, widget_safe=True)
        safe_session_assign(session, "improv_jam_key", k, widget_safe=True)
        safe_session_assign(session, "improv_jam_bpm", tempo, widget_safe=True)
        safe_session_assign(session, "improv_jam_mood", mood_name, widget_safe=True)
    except ImportError:
        if not session.get("_streamlit_widgets_locked_this_run"):
            session["improv_entry_mode"] = "Jam Session Generator"
            session["improv_ensemble"] = ensemble_name
            session["improv_jam_style"] = style_name
            session["improv_jam_key"] = k
            session["improv_jam_bpm"] = tempo
            session["improv_jam_mood"] = mood_name

    session["improv_style_meta"] = {
        "style": style_name,
        "bpm": tempo,
        "groove": str(session.get("improv_groove") or "Medium").strip(),
        "groove_intensity": str(session.get("improv_groove") or "Medium").strip(),
        "key": k,
        "mood": mood_name,
        "difficulty": str(session.get("improv_difficulty") or "Intermediate").strip(),
        "meter": str(session.get("improv_style_meter") or session.get("backing_time_signature") or "4/4").strip(),
        "entry_mode": "Jam Session Generator",
    }

    try:
        from creative_key_sync import IMPROV_JAM_KEY_TRACKER, apply_creative_concert_key

        apply_creative_concert_key(
            session, k, st_like=st_like, source="creative_jam_session"
        )
        session[IMPROV_JAM_KEY_TRACKER] = k
    except ImportError:
        pass

    try:
        from session_widget_safe import safe_session_assign

        safe_session_assign(
            session, "improv_entry_mode", "Jam Session Generator", widget_safe=True
        )
        safe_session_assign(session, "improv_ensemble", ensemble_name, widget_safe=True)
        safe_session_assign(session, "improv_jam_style", style_name, widget_safe=True)
        safe_session_assign(session, "improv_jam_key", k, widget_safe=True)
        safe_session_assign(session, "improv_jam_bpm", tempo, widget_safe=True)
        safe_session_assign(session, "improv_jam_mood", mood_name, widget_safe=True)
    except ImportError:
        pass

    session[JAM_SESSION_GENERATE_GUARD_KEY] = True
    page = str(session.get("studio_page") or "").strip().lower()
    if page:
        session[f"_creative_session_hydrated_{page}"] = True

    sess = sync_creative_session_from_session(session)
    session.pop(JAM_CAPTURE_STAGING_KEY, None)
    return sess


def sync_creative_session_from_session(session: dict[str, Any]) -> CreativeSession | None:
    """Capture live Creative widget state into the canonical session object."""
    try:
        from session_widget_safe import PENDING_IMPROV_ENTRY_MODE_KEY
        from studio_page_state import IMPROV_ENTRY_MODES

        pending_entry = str(session.get(PENDING_IMPROV_ENTRY_MODE_KEY) or "").strip()
    except ImportError:
        pending_entry = str(session.get("_pending_improv_entry_mode") or "").strip()
        IMPROV_ENTRY_MODES = ("Song-Based Improvisation", "Style Jam Mode", "Jam Session Generator")
    entry = str(session.get("improv_entry_mode") or "").strip()
    if pending_entry in IMPROV_ENTRY_MODES:
        entry = pending_entry
    elif not entry:
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict) and jam.get("sections"):
            entry = "Jam Session Generator"
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or "Entry & Jam"
    ).strip()
    if tab == "Missions":
        mission_id = str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "").strip()
        if not mission_id:
            return None
        meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}
        concert = str(
            session.get("display_key") or session.get("concert_key") or meta.get("key") or "C"
        ).strip()
        existing = CreativeSession.from_dict(session.get(CREATIVE_SESSION_KEY)) if session.get(CREATIVE_SESSION_KEY) else None
        sess = CreativeSession(
            session_id=existing.session_id if existing else "",
            tool_type="mission",
            entry_mode="Song-Based Improvisation",
            concert_key=concert,
            display_key=concert,
            instrument=str(session.get("instrument") or ""),
            style=str(meta.get("style") or ""),
            bpm=int(meta.get("bpm") or session.get("improv_style_bpm") or 110),
            meter=str(meta.get("meter") or "4/4"),
            mission_id=mission_id,
            intelligence_tab="Missions",
            sections=_mission_sections_from_session(session),
        )
        set_creative_session(session, sess)
        return sess

    tool = _ENTRY_MODE_TO_TOOL.get(entry)
    if not tool:
        return None

    meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}
    if entry == "Jam Session Generator":
        style, concert, bpm, mood = _live_jam_session_fields(session)
    elif entry == "Song-Based Improvisation":
        style = ""
        concert = str(session.get("display_key") or session.get("concert_key") or "C").strip()
        bpm = int(session.get("improv_style_bpm") or meta.get("bpm") or session.get("bpm") or 110)
        mood = str(session.get("improv_mood") or "Mellow").strip()
    else:
        style = str(session.get("improv_style") or meta.get("style") or "").strip()
        concert = str(session.get("improv_style_key") or meta.get("key") or "C").strip()
        bpm = int(session.get("improv_style_bpm") or meta.get("bpm") or 110)
        mood = str(session.get("improv_mood") or meta.get("mood") or "Mellow").strip()
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            fixed_original = "C" if tool in {"entry_style_jam", "jam_session_generator"} else concert
            concert = resolve_practice_concert_key_for_song(session, fixed_original, fallback=concert)
    except ImportError:
        pass

    sections = _sections_from_session(session, entry)
    if not sections and not style and entry not in {"Song-Based Improvisation"}:
        return get_creative_session(session)

    if tool in {"entry_style_jam", "jam_session_generator"}:
        display = concert
    else:
        display = str(session.get("display_key") or concert).strip() or concert

    try:
        from source_session_state import get_sbi_preview_source

        song_src = get_sbi_preview_source(session)
    except ImportError:
        song_src = str(session.get("improv_song_source") or "Active song")
    existing = CreativeSession.from_dict(session.get(CREATIVE_SESSION_KEY)) if session.get(CREATIVE_SESSION_KEY) else None
    sess = CreativeSession(
        session_id=existing.session_id if existing else "",
        tool_type=tool,
        entry_mode=entry,
        song_source=song_src,
        concert_key=concert,
        display_key=display,
        instrument=str(session.get("instrument") or ""),
        style=style,
        mood=mood,
        groove_intensity=str(
            meta.get("groove_intensity") or session.get("improv_groove") or "Medium"
        ).strip(),
        difficulty=str(meta.get("difficulty") or session.get("improv_difficulty") or "Intermediate").strip(),
        bpm=bpm,
        meter=str(meta.get("meter") or session.get("improv_style_meter") or "4/4").strip(),
        sections=sections,
        selected_section=str(
            session.get("improv_selected_section") or session.get("II_SELECTED_SECTION") or ""
        ).strip(),
        intelligence_tab=_normalize_improv_intelligence_tab(tab),
    )
    set_creative_session(session, sess)
    return sess


def apply_creative_session_to_session(
    session: dict[str, Any],
    sess: CreativeSession,
    *,
    widget_safe: bool | None = None,
) -> None:
    """Project canonical Creative session into legacy improv_* widget keys."""
    if widget_safe is None:
        try:
            from session_widget_safe import widgets_likely_instantiated

            widget_safe = widgets_likely_instantiated(session)
        except ImportError:
            widget_safe = False

    try:
        from session_widget_safe import safe_assign_display_key, safe_session_assign
    except ImportError:
        safe_assign_display_key = None  # type: ignore[assignment,misc]
        safe_session_assign = None  # type: ignore[assignment,misc]

    def _set(key: str, value: Any) -> None:
        if safe_session_assign is not None:
            safe_session_assign(session, key, value, widget_safe=widget_safe)
        else:
            session[key] = value

    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY, IMPROV_ENTRY_MODES
    except ImportError:
        CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY = "creative_improv_intelligence_tab"  # type: ignore[misc,assignment]
        IMPROV_ENTRY_MODES = ("Song-Based Improvisation", "Style Jam Mode", "Jam Session Generator")
    live_entry = str(session.get("improv_entry_mode") or "").strip()
    if widget_safe and session.get("_improv_tab_user_touched") and live_entry in IMPROV_ENTRY_MODES:
        pass  # keep user-selected entry mode on the radio widget
    else:
        _set("improv_entry_mode", sess.entry_mode)
    saved_tab = str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or sess.intelligence_tab or "").strip()
    tab = _normalize_improv_intelligence_tab(saved_tab or sess.intelligence_tab)
    if widget_safe:
        if not session.get("_improv_tab_user_touched"):
            session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = tab
            _set("improv_intelligence_tab", tab)
    else:
        _set("improv_intelligence_tab", tab)
        _set("creative_improv_intelligence_tab", tab)
    _set("creative_lab_analysis_mode", "Improvisation Intelligence")
    _set("creative_lab_last_mode", "Improvisation Intelligence")
    _set("improv_song_source", sess.song_source)
    try:
        from source_session_state import set_sbi_preview_source

        set_sbi_preview_source(session, sess.song_source)
    except ImportError:
        pass

    concert = str(sess.concert_key or sess.display_key or "C").strip() or "C"
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            fixed_original = "C" if sess.tool_type in {"entry_style_jam", "jam_session_generator"} else concert
            concert = resolve_practice_concert_key_for_song(session, fixed_original, fallback=concert)
            sess.concert_key = concert
    except ImportError:
        pass
    if sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
        display = concert
    else:
        display = str(sess.display_key or concert).strip() or concert
    if safe_assign_display_key is not None:
        safe_assign_display_key(session, display, widget_safe=widget_safe)
    else:
        session["concert_key"] = concert
        session["display_key"] = display
        session["_pending_display_key"] = display

    if sess.instrument:
        _set("instrument", sess.instrument)

    if sess.tool_type == "mission":
        session["improv_active_mission"] = sess.mission_id
        session["improv_mission_pick"] = sess.mission_id
    elif sess.tool_type == "jam_session_generator":
        _set("improv_jam_style", sess.style)
        if widget_safe:
            try:
                from creative_key_sync import PENDING_IMPROV_JAM_KEY

                session[PENDING_IMPROV_JAM_KEY] = concert
            except ImportError:
                session["_pending_improv_jam_key"] = concert
        else:
            _set("improv_jam_key", concert)
        _set("improv_jam_bpm", int(sess.bpm))
        _set("improv_jam_mood", sess.mood)
        if sess.sections:
            jam = dict(session.get("improv_jam_session") or {})
            if not isinstance(jam, dict):
                jam = {}
            jam["sections"] = {k: list(v) for k, v in sess.sections.items()}
            session["improv_jam_session"] = jam
    elif sess.tool_type == "song_based_improvisation":
        if sess.sections:
            session["improv_song_concert_sections"] = {k: list(v) for k, v in sess.sections.items()}
    else:
        _set("improv_style", sess.style)
        if widget_safe:
            try:
                from creative_key_sync import PENDING_IMPROV_STYLE_KEY

                session[PENDING_IMPROV_STYLE_KEY] = concert
            except ImportError:
                session["_pending_improv_style_key"] = concert
        else:
            _set("improv_style_key", concert)
        _set("improv_style_bpm", int(sess.bpm))
        _set("improv_mood", sess.mood)
        _set("improv_groove", sess.groove_intensity)
        _set("improv_difficulty", sess.difficulty)
        _set("improv_style_meter", sess.meter)
        if sess.sections:
            session["improv_generated_sections"] = {k: list(v) for k, v in sess.sections.items()}

    session["improv_style_meta"] = {
        "style": sess.style,
        "bpm": int(sess.bpm),
        "groove": sess.groove_intensity,
        "groove_intensity": sess.groove_intensity,
        "key": concert,
        "mood": sess.mood,
        "difficulty": sess.difficulty,
        "meter": sess.meter,
        "entry_mode": sess.entry_mode,
    }
    if sess.selected_section:
        session["improv_selected_section"] = sess.selected_section
        session["II_SELECTED_SECTION"] = sess.selected_section


def migrate_legacy_creative_session(session: dict[str, Any]) -> CreativeSession | None:
    """Build a CreativeSession from legacy improv_* keys when none is persisted."""
    if session.get(CREATIVE_SESSION_KEY):
        return CreativeSession.from_dict(session.get(CREATIVE_SESSION_KEY))
    entry = str(session.get("improv_entry_mode") or "").strip()
    if not entry:
        return None
    tool = _ENTRY_MODE_TO_TOOL.get(entry)
    tab = str(session.get("improv_intelligence_tab") or "Entry & Jam").strip()
    if tab == "Missions":
        tool = "mission"
    if not tool:
        return None
    sections = _sections_from_session(session, entry)
    meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}
    if entry == "Jam Session Generator":
        style = str(session.get("improv_jam_style") or meta.get("style") or "").strip()
        concert = str(session.get("improv_jam_key") or meta.get("key") or "C").strip()
        bpm = int(session.get("improv_jam_bpm") or meta.get("bpm") or 110)
        mood = str(session.get("improv_jam_mood") or meta.get("mood") or "Mellow").strip()
    elif entry == "Song-Based Improvisation":
        style = ""
        concert = str(session.get("display_key") or session.get("concert_key") or "C").strip()
        bpm = int(session.get("improv_style_bpm") or meta.get("bpm") or 110)
        mood = str(session.get("improv_mood") or "Mellow").strip()
    else:
        style = str(session.get("improv_style") or meta.get("style") or "").strip()
        concert = str(session.get("improv_style_key") or meta.get("key") or "C").strip()
        bpm = int(session.get("improv_style_bpm") or meta.get("bpm") or 110)
        mood = str(session.get("improv_mood") or meta.get("mood") or "Mellow").strip()
    if not sections and not style and tool not in {"song_based_improvisation", "mission"}:
        return None
    display = concert if tool in {"entry_style_jam", "jam_session_generator"} else (
        str(session.get("display_key") or concert).strip() or concert
    )
    return CreativeSession(
        session_id="",
        tool_type=tool,
        entry_mode=entry,
        song_source=str(session.get("improv_song_source") or "Active song"),
        concert_key=concert,
        display_key=display,
        instrument=str(session.get("instrument") or ""),
        style=style,
        mood=mood,
        groove_intensity=str(meta.get("groove_intensity") or session.get("improv_groove") or "Medium").strip(),
        difficulty=str(meta.get("difficulty") or session.get("improv_difficulty") or "Intermediate").strip(),
        bpm=bpm,
        meter=str(meta.get("meter") or session.get("improv_style_meter") or "4/4").strip(),
        sections=sections,
        mission_id=str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "").strip(),
        intelligence_tab=_normalize_improv_intelligence_tab(tab),
    )


def sync_creative_session_before_persist(session: dict[str, Any]) -> CreativeSession | None:
    """Capture live Creative widget state immediately before disk/cloud save."""
    entry = str(session.get("improv_entry_mode") or "").strip()
    if not entry and not session.get(CREATIVE_SESSION_KEY):
        return None
    return sync_creative_session_from_session(session)


def merge_live_key_into_creative_session(session: dict[str, Any]) -> None:
    """Adopt live practice concert key into canonical Creative session before page hydrate."""
    page = str(session.get("studio_page") or "").strip().lower()
    sess = get_creative_session(session)
    if sess is not None and page == "creative" and sess.tool_type in {
        "entry_style_jam",
        "jam_session_generator",
    }:
        return
    try:
        from music_theory import key_is_minor
    except ImportError:
        key_is_minor = lambda _k: False  # type: ignore[assignment,misc]
    if sess is None or not creative_session_is_active(session):
        return
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not live:
        return
    if sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
        try:
            from creative_key_sync import (
                PENDING_IMPROV_JAM_KEY,
                PENDING_IMPROV_STYLE_KEY,
                to_major_key_preserve_spelling,
            )
        except ImportError:
            PENDING_IMPROV_STYLE_KEY = "_pending_improv_style_key"  # type: ignore[misc,assignment]
            PENDING_IMPROV_JAM_KEY = "_pending_improv_jam_key"  # type: ignore[misc,assignment]
            to_major_key_preserve_spelling = lambda k: k  # type: ignore[assignment,misc]
        saved_major = to_major_key_preserve_spelling(str(sess.concert_key or "C"))
        if key_is_minor(live):
            live = saved_major
        else:
            live = to_major_key_preserve_spelling(live)
        if sess.tool_type == "entry_style_jam":
            session[PENDING_IMPROV_STYLE_KEY] = live
        else:
            session[PENDING_IMPROV_JAM_KEY] = live
    if live != sess.concert_key or live != sess.display_key:
        sess.concert_key = live
        sess.display_key = live
        set_creative_session(session, sess)


def hydrate_creative_session_for_page(session: dict[str, Any]) -> None:
    """Apply persisted Creative session to widgets at page entry (after cloud restore)."""
    page = str(session.get("studio_page") or "").strip().lower()
    hydrate_flag = f"_creative_session_hydrated_{page}"
    if session.get(hydrate_flag):
        return
    if session.pop(JAM_SESSION_GENERATE_GUARD_KEY, False):
        sync_creative_session_from_session(session)
        session[hydrate_flag] = True
        return
    try:
        from backing_source_navigation import (
            CREATIVE_RESTORE_FROM_BACKING_KEY,
            rehydrate_creative_from_backing_context,
        )

        if session.pop(CREATIVE_RESTORE_FROM_BACKING_KEY, False):
            rehydrate_creative_from_backing_context(session)
            return
    except ImportError:
        pass
    sess = get_creative_session(session)
    page = str(session.get("studio_page") or "").strip().lower()
    should_apply = sess is not None and creative_session_is_active(session)
    if (
        page == "creative"
        and sess is not None
        and sess.tool_type in {"entry_style_jam", "jam_session_generator", "song_based_improvisation"}
    ):
        should_apply = True
    if page == "creative" and session.get("_improv_tab_user_touched"):
        should_apply = False
    if should_apply and sess is not None:
        apply_creative_session_to_session(session, sess, widget_safe=True)
        session[hydrate_flag] = True
        return
    merge_live_key_into_creative_session(session)
    sess = get_creative_session(session)
    should_apply = sess is not None and creative_session_is_active(session)
    if (
        sess is not None
        and page == "creative"
        and not should_apply
        and (sess.sections or sess.style)
        and not session.get("_improv_tab_user_touched")
    ):
        should_apply = True
        try:
            from backing_context import BACKING_PREF_CREATIVE, set_backing_source_preference

            set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        except ImportError:
            pass
    if should_apply and sess is not None:
        apply_creative_session_to_session(session, sess, widget_safe=True)
        session[hydrate_flag] = True
        return
    if str(session.get("improv_entry_mode") or "").strip():
        sync_creative_session_from_session(session)
    session[hydrate_flag] = True


def hydrate_creative_session_after_restore(session: dict[str, Any]) -> bool:
    """Re-apply persisted Creative session after cloud/disk restore. Returns True if applied."""
    page = str(session.get("studio_page") or "").strip().lower()
    sess = get_creative_session(session)
    if sess is None:
        return False
    if page == "creative" and sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
        apply_creative_session_to_session(session, sess, widget_safe=False)
        return True
    if not creative_session_is_active(session):
        return False
    try:
        from backing_context import catalog_or_custom_backing_is_authoritative

        if catalog_or_custom_backing_is_authoritative(session):
            return False
    except ImportError:
        pass
    apply_creative_session_to_session(session, sess, widget_safe=False)
    try:
        from backing_context import (
            PENDING_BACKING_CONTEXT_APPLY,
            ensure_backing_context_from_creative_session,
        )

        ensure_backing_context_from_creative_session(session)
        session[PENDING_BACKING_CONTEXT_APPLY] = True
    except ImportError:
        pass
    return True


def resolve_creative_backing_sections(session: dict[str, Any]) -> dict[str, list[str]]:
    """Sections for backing playback — only when Creative/custom backing is active."""
    try:
        from backing_context import active_creative_backing_context, get_backing_context, sections_dict_from_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source == "regular_song":
            return {}
        mission_ctx = active_creative_backing_context(session)
        if mission_ctx is not None and mission_ctx.source == "mission":
            sections = sections_dict_from_backing_context(session, mission_ctx)
            if sections:
                return sections
        if active_creative_backing_context(session) is None:
            return {}
    except ImportError:
        pass
    sess = get_creative_session(session)
    if sess and sess.sections:
        practice = str(session.get("display_key") or sess.concert_key or "C").strip() or "C"
        try:
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

            if is_fixed_practice_key_mode(session):
                original = "C" if sess.tool_type in {"entry_style_jam", "jam_session_generator"} else str(sess.concert_key or practice)
                practice = resolve_practice_concert_key_for_song(session, original, fallback=practice)
        except ImportError:
            pass
        origin = str(sess.concert_key or "C").strip()
        if origin and practice != origin:
            try:
                from creative_key_sync import retranspose_generated_sections

                return retranspose_generated_sections(sess.sections, from_key=origin, to_key=practice)
            except ImportError:
                pass
        return dict(sess.sections)
    try:
        from backing_context import active_creative_backing_context, sections_dict_from_backing_context

        ctx = active_creative_backing_context(session)
        if ctx is not None:
            sections = sections_dict_from_backing_context(session, ctx)
            if sections:
                return sections
    except ImportError:
        pass
    return _sections_from_session(session, str(session.get("improv_entry_mode") or ""))


def render_creative_session_diagnostic(st: Any, session: dict[str, Any]) -> None:
    """Deploy/state path visibility — developer mode only."""
    try:
        from music_dev_ui import music_dev_mode_enabled
    except ImportError:
        try:
            from suite_workspace import is_developer_mode_enabled

            if not is_developer_mode_enabled(st=st):
                return
        except ImportError:
            if not st.session_state.get("developer_mode"):
                return
    else:
        if not music_dev_mode_enabled(st=st):
            return
    try:
        from suite_deploy_probe import deploy_info
    except ImportError:
        deploy_info = lambda: {"commit": "unknown"}  # type: ignore[misc, assignment]
    deploy = deploy_info()
    commit = str(deploy.get("commit") or "unknown").strip()[:12]
    sess = get_creative_session(session)
    if sess is None:
        summary = "no creative_session"
    else:
        sec_count = len(sess.sections or {})
        summary = (
            f"{sess.tool_type} · {sess.entry_mode} · key {sess.concert_key} · "
            f"bpm {sess.bpm} · {sec_count} section(s)"
        )
    active = creative_session_is_active(session)
    ctx_src = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_src = f" · backing={ctx.source}"
    except ImportError:
        pass
    st.caption(
        f"State · commit `{commit}` · creative_session: {summary} · active={active}{ctx_src}"
    )


__all__ = [
    "CREATIVE_SESSION_KEY",
    "JAM_SESSION_GENERATE_GUARD_KEY",
    "JAM_CAPTURE_STAGING_KEY",
    "CreativeSession",
    "CreativeToolType",
    "apply_creative_session_to_session",
    "capture_jam_session_generator_state",
    "clear_creative_session",
    "compute_creative_session_signature",
    "creative_session_is_active",
    "get_creative_session",
    "hydrate_creative_session_for_page",
    "hydrate_creative_session_after_restore",
    "sync_creative_session_before_persist",
    "merge_live_key_into_creative_session",
    "migrate_legacy_creative_session",
    "render_creative_session_diagnostic",
    "resolve_creative_backing_sections",
    "set_creative_session",
    "sync_creative_session_from_session",
]
