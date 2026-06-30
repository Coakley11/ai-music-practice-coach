"""Canonical Creative workflow session — durable across navigation, refresh, and cloud restore."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

CREATIVE_SESSION_KEY = "creative_session"

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


def creative_session_is_active(session: dict[str, Any]) -> bool:
    """True when a standalone Creative jam workflow should own key/BPM state."""
    sess = get_creative_session(session)
    if sess is None:
        return False
    if sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
        return bool(sess.sections) or bool(sess.style)
    if sess.tool_type == "song_based_improvisation":
        return bool(sess.sections)
    if sess.tool_type == "mission":
        return bool(sess.mission_id)
    return False


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


def sync_creative_session_from_session(session: dict[str, Any]) -> CreativeSession | None:
    """Capture live Creative widget state into the canonical session object."""
    entry = str(session.get("improv_entry_mode") or "").strip()
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
            sections=_sections_from_session(session, entry),
        )
        set_creative_session(session, sess)
        return sess

    tool = _ENTRY_MODE_TO_TOOL.get(entry)
    if not tool:
        return None

    meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}
    if entry == "Jam Session Generator":
        style = str(session.get("improv_jam_style") or meta.get("style") or "").strip()
        concert = str(session.get("improv_jam_key") or meta.get("key") or "C").strip()
        bpm = int(session.get("improv_jam_bpm") or meta.get("bpm") or 110)
        mood = str(session.get("improv_jam_mood") or meta.get("mood") or "Mellow").strip()
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

    sections = _sections_from_session(session, entry)
    if not sections and not style and entry not in {"Song-Based Improvisation"}:
        return get_creative_session(session)

    if tool in {"entry_style_jam", "jam_session_generator"}:
        display = concert
    else:
        display = str(session.get("display_key") or concert).strip() or concert

    existing = CreativeSession.from_dict(session.get(CREATIVE_SESSION_KEY)) if session.get(CREATIVE_SESSION_KEY) else None
    sess = CreativeSession(
        session_id=existing.session_id if existing else "",
        tool_type=tool,
        entry_mode=entry,
        song_source=str(session.get("improv_song_source") or "Active song"),
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

    _set("improv_entry_mode", sess.entry_mode)
    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY
    except ImportError:
        CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY = "creative_improv_intelligence_tab"  # type: ignore[misc,assignment]
    saved_tab = str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or sess.intelligence_tab or "").strip()
    tab = _normalize_improv_intelligence_tab(saved_tab or sess.intelligence_tab)
    if widget_safe:
        if not session.get("_improv_tab_user_touched"):
            session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = tab
    else:
        _set("improv_intelligence_tab", tab)
        _set("creative_improv_intelligence_tab", tab)
    _set("creative_lab_analysis_mode", "Improvisation Intelligence")
    _set("creative_lab_last_mode", "Improvisation Intelligence")
    _set("improv_song_source", sess.song_source)

    concert = str(sess.concert_key or sess.display_key or "C").strip() or "C"
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


def hydrate_creative_session_for_page(session: dict[str, Any]) -> None:
    """Apply persisted Creative session to widgets at page entry (after cloud restore)."""
    sess = get_creative_session(session)
    if sess is not None and creative_session_is_active(session):
        apply_creative_session_to_session(session, sess, widget_safe=True)
        return
    if str(session.get("improv_entry_mode") or "").strip():
        sync_creative_session_from_session(session)


def hydrate_creative_session_after_restore(session: dict[str, Any]) -> bool:
    """Re-apply persisted Creative session after cloud/disk restore. Returns True if applied."""
    sess = get_creative_session(session)
    if sess is None or not creative_session_is_active(session):
        return False
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
    """Sections for backing playback — Creative session first, then backing_context."""
    sess = get_creative_session(session)
    if sess and sess.sections:
        practice = str(session.get("display_key") or sess.concert_key or "C").strip() or "C"
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
    """Temporary deploy/state path visibility for Creative session debugging."""
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
    "CreativeSession",
    "CreativeToolType",
    "apply_creative_session_to_session",
    "clear_creative_session",
    "compute_creative_session_signature",
    "creative_session_is_active",
    "get_creative_session",
    "hydrate_creative_session_for_page",
    "hydrate_creative_session_after_restore",
    "sync_creative_session_before_persist",
    "migrate_legacy_creative_session",
    "render_creative_session_diagnostic",
    "resolve_creative_backing_sections",
    "set_creative_session",
    "sync_creative_session_from_session",
]
