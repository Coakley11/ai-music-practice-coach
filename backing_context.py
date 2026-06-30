"""Canonical backing context — metadata + handoff driver for Backing Track.

Does not replace ``backing_track_state`` (canonical backing blob). Phase 1: build,
validate, invalidate, and signature helpers only — no page wiring yet.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

BACKING_CONTEXT_KEY = "backing_context"
PENDING_BACKING_CONTEXT_APPLY = "_pending_backing_context_apply"

BackingSource = Literal["regular_song", "entry_jam", "mission", "custom_progression"]

_SOURCE_LABELS: dict[BackingSource, str] = {
    "regular_song": "Regular song",
    "entry_jam": "Entry & Jam",
    "mission": "Mission",
    "custom_progression": "Custom progression",
}

_SIGNATURE_FIELDS = (
    "source",
    "bound_pick_key",
    "active_song_id",
    "key",
    "display_key",
    "concert_key",
    "chart_display_key",
    "bpm",
    "style",
    "groove",
    "mood",
    "groove_intensity",
    "difficulty",
    "meter",
    "section",
    "scope",
    "loops",
    "progression",
    "mission_id",
    "jam_id",
    "entry_mode",
    "custom_revision_id",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class BackingContext:
    source: BackingSource
    source_label: str
    active_song_id: str
    song_title: str
    key: str
    display_key: str
    concert_key: str
    bpm: int
    style: str
    groove: str
    section: str | None = None
    sections: list[str] = field(default_factory=list)
    scope: str = "Full song"
    loops: int = 2
    progression: list[str] = field(default_factory=list)
    progression_label: str = ""
    duration_bars: int | None = None
    loop: bool = True
    mission_id: str | None = None
    jam_id: str | None = None
    entry_mode: str | None = None
    custom_revision_id: str | None = None
    mode_label: str = ""
    mood: str = ""
    groove_intensity: str = ""
    difficulty: str = ""
    meter: str = "4/4"
    chart_display_key: str = ""
    section_labels: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    source_signature: str = ""
    bound_pick_key: str = ""

    def __post_init__(self) -> None:
        if not self.source_label:
            self.source_label = _SOURCE_LABELS.get(self.source, self.source.replace("_", " ").title())
        if not self.created_at:
            self.created_at = utc_now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.source_signature:
            self.source_signature = compute_source_signature(self)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> BackingContext | None:
        if not isinstance(raw, dict):
            return None
        source = str(raw.get("source") or "regular_song").strip()
        if source not in _SOURCE_LABELS:
            return None
        return cls(
            source=source,  # type: ignore[arg-type]
            source_label=str(raw.get("source_label") or ""),
            active_song_id=str(raw.get("active_song_id") or ""),
            song_title=str(raw.get("song_title") or ""),
            key=str(raw.get("key") or ""),
            display_key=str(raw.get("display_key") or ""),
            concert_key=str(raw.get("concert_key") or ""),
            bpm=int(raw.get("bpm") or 100),
            style=str(raw.get("style") or ""),
            groove=str(raw.get("groove") or ""),
            section=str(raw.get("section") or "").strip() or None,
            sections=[str(s) for s in (raw.get("sections") or []) if str(s).strip()],
            scope=str(raw.get("scope") or "Full song"),
            loops=int(raw.get("loops") or 2),
            progression=[str(c) for c in (raw.get("progression") or []) if str(c).strip()],
            progression_label=str(raw.get("progression_label") or ""),
            duration_bars=int(raw["duration_bars"]) if raw.get("duration_bars") not in (None, "") else None,
            loop=bool(raw.get("loop", True)),
            mission_id=str(raw.get("mission_id") or "").strip() or None,
            jam_id=str(raw.get("jam_id") or "").strip() or None,
            entry_mode=str(raw.get("entry_mode") or "").strip() or None,
            custom_revision_id=str(raw.get("custom_revision_id") or "").strip() or None,
            mode_label=str(raw.get("mode_label") or ""),
            mood=str(raw.get("mood") or ""),
            groove_intensity=str(raw.get("groove_intensity") or ""),
            difficulty=str(raw.get("difficulty") or ""),
            meter=str(raw.get("meter") or "4/4"),
            chart_display_key=str(raw.get("chart_display_key") or ""),
            section_labels=[str(s) for s in (raw.get("section_labels") or []) if str(s).strip()],
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
            source_signature=str(raw.get("source_signature") or ""),
            bound_pick_key=str(raw.get("bound_pick_key") or ""),
        )


def compute_source_signature(ctx: BackingContext | dict[str, Any]) -> str:
    """Deterministic hash of fields that affect backing generation."""
    if isinstance(ctx, BackingContext):
        data = ctx.to_dict()
    else:
        data = dict(ctx)
    payload = {key: data.get(key) for key in _SIGNATURE_FIELDS}
    progression = payload.get("progression")
    if isinstance(progression, list):
        payload["progression"] = "|".join(str(c) for c in progression)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def refresh_backing_context_timestamps(ctx: BackingContext) -> BackingContext:
    now = utc_now_iso()
    if not ctx.created_at:
        ctx.created_at = now
    ctx.updated_at = now
    ctx.source_signature = compute_source_signature(ctx)
    return ctx


def get_backing_context(session: dict[str, Any]) -> BackingContext | None:
    return BackingContext.from_dict(session.get(BACKING_CONTEXT_KEY))


def set_backing_context(session: dict[str, Any], ctx: BackingContext) -> None:
    session[BACKING_CONTEXT_KEY] = refresh_backing_context_timestamps(ctx).to_dict()


def clear_backing_context(session: dict[str, Any]) -> None:
    session.pop(BACKING_CONTEXT_KEY, None)


def _current_pick_key(session: dict[str, Any]) -> str:
    try:
        from active_song_state import canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            pick = str(ctx.get("pick_key") or "").strip()
            if pick:
                return pick
    except ImportError:
        pass
    return str(
        session.get("active_catalog_pick_key")
        or session.get("pick_key")
        or ""
    ).strip()


def _song_title_from_session(session: dict[str, Any]) -> str:
    title = str(session.get("song") or session.get("active_song_title") or "").strip()
    if title:
        return title
    sel = session.get("selected_song")
    if isinstance(sel, dict):
        return str(sel.get("title") or sel.get("name") or "").strip()
    return ""


def _display_keys_from_session(session: dict[str, Any]) -> tuple[str, str, str]:
    display = str(session.get("display_key") or "").strip()
    concert = str(session.get("concert_key") or session.get("original_key") or display).strip()
    key = concert or display or "C"
    return key, display or key, concert or key


def _creative_concert_keys(session: dict[str, Any]) -> tuple[str, str, str] | None:
    try:
        from creative_key_sync import creative_entry_concert_key

        creative = creative_entry_concert_key(session)
    except ImportError:
        creative = ""
    if not creative:
        return None
    return creative, creative, creative


def _resolve_chart_display_key(session: dict[str, Any], concert_key: str) -> str:
    try:
        from songs.key_state import resolve_active_musical_key

        mk = resolve_active_musical_key(session)
        chart = str(mk.chart_key or "").strip()
        if chart:
            return chart
    except Exception:
        pass
    return str(concert_key or "C").strip() or "C"


def _entry_jam_sections_dict(session: dict[str, Any], entry_mode: str) -> dict[str, list[str]]:
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
    gen = session.get("improv_generated_sections")
    if isinstance(gen, dict) and gen:
        return {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in gen.items()
            if isinstance(chords, list)
        }
    return {}


def _filter_sections_dict(
    sections: dict[str, list[str]],
    *,
    section: str | None,
    selected: list[str],
) -> dict[str, list[str]]:
    if not sections:
        return sections
    names = [str(s).strip() for s in selected if str(s).strip()]
    if names:
        return {k: v for k, v in sections.items() if k in names}
    if section and section in sections:
        return {section: sections[section]}
    return sections


def _default_bpm(session: dict[str, Any]) -> int:
    for key in ("backing_track_bpm", "active_song_bpm", "bpm"):
        try:
            return int(session.get(key) or 0) or 100
        except (TypeError, ValueError):
            continue
    return 100


def _default_groove(session: dict[str, Any]) -> str:
    return str(session.get("backing_groove_style") or session.get("backing_groove") or "Pop groove").strip()


def _backing_groove_style_from_ctx(ctx: BackingContext) -> str:
    """Map Creative style name to Backing Studio groove/style control value."""
    from songs.playback_defaults import normalize_groove_label

    style = str(ctx.style or "").strip()
    if style:
        return normalize_groove_label(style)
    groove = str(ctx.groove or "").strip()
    if groove and groove not in {"Light", "Medium", "Heavy"}:
        return normalize_groove_label(groove)
    return normalize_groove_label("Pop groove")


def flush_pending_backing_handoff_keys(
    session: dict[str, Any],
    *,
    sync_id: str = "",
) -> None:
    """Apply queued BPM/groove/meter handoff before backing widgets render."""
    from songs.bpm_state import BPM_WIDGET_KEY, PENDING_BACKING_TRACK_BPM
    from songs.playback_defaults import backing_bpm_slider_widget_key
    from songs.playback_defaults import (
        BACKING_GROOVE_KEY,
        PENDING_BACKING_GROOVE,
        _set_bpm_tracking_ids,
        normalize_groove_label,
    )

    pending_bpm = session.pop(PENDING_BACKING_TRACK_BPM, None)
    pending_groove = session.pop(PENDING_BACKING_GROOVE, None)
    pending_meter = session.pop("_pending_backing_meter", None)

    if pending_bpm is not None:
        bpm = int(pending_bpm)
        session[BPM_WIDGET_KEY] = bpm
        session["backing_track_bpm"] = bpm
        session["bpm"] = bpm
        sid = str(sync_id or session.get("_backing_trace_sync_id") or "").strip()
        if sid:
            from types import SimpleNamespace

            from songs.playback_defaults import _set_bpm_tracking_ids

            session[backing_bpm_slider_widget_key(sid)] = bpm
            _set_bpm_tracking_ids(SimpleNamespace(session_state=session), sid, bpm)

    if pending_groove is not None:
        groove = normalize_groove_label(str(pending_groove))
        session[BACKING_GROOVE_KEY] = groove
        session["backing_groove_style"] = groove

    if pending_meter is not None:
        meter = str(pending_meter).strip()
        try:
            from songs.meter_state import BACKING_METER_KEY

            session[BACKING_METER_KEY] = meter
        except ImportError:
            pass
        session["backing_time_signature"] = meter


def _default_scope(session: dict[str, Any]) -> tuple[str, str | None, list[str]]:
    scope = str(session.get("backing_track_scope") or "Full song").strip()
    section = str(session.get("backing_track_single_section") or "").strip() or None
    multi = session.get("backing_track_multi_sections")
    sections = [str(s) for s in multi if str(s).strip()] if isinstance(multi, list) else []
    return scope, section, sections


def build_regular_song_context(session: dict[str, Any]) -> BackingContext:
    pick_key = _current_pick_key(session)
    key, display_key, concert_key = _display_keys_from_session(session)
    scope, section, sections = _default_scope(session)
    return BackingContext(
        source="regular_song",
        source_label=_SOURCE_LABELS["regular_song"],
        active_song_id=pick_key,
        song_title=_song_title_from_session(session),
        key=key,
        display_key=display_key,
        concert_key=concert_key,
        bpm=_default_bpm(session),
        style="",
        groove=_default_groove(session),
        section=section,
        sections=sections,
        scope=scope,
        loops=int(session.get("backing_track_loops") or 2),
        progression=[],
        progression_label="",
        loop=True,
        bound_pick_key=pick_key,
    )


def build_entry_jam_context(session: dict[str, Any]) -> BackingContext:
    try:
        from studio_page_state import resolve_improv_song_source
    except ImportError:
        resolve_improv_song_source = lambda s: str(s.get("improv_song_source") or "Active song")  # type: ignore

    pick_key = _current_pick_key(session)
    creative_keys = _creative_concert_keys(session)
    if creative_keys:
        key, display_key, concert_key = creative_keys
    else:
        key, display_key, concert_key = _display_keys_from_session(session)
    chart_display_key = _resolve_chart_display_key(session, concert_key)
    entry_mode = str(session.get("improv_entry_mode") or "Song-Based Improvisation").strip()
    style_meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}

    if entry_mode == "Jam Session Generator":
        style = str(session.get("improv_jam_style") or style_meta.get("style") or "").strip()
        groove = str(style_meta.get("groove") or session.get("improv_groove") or _default_groove(session)).strip()
        bpm = int(session.get("improv_jam_bpm") or style_meta.get("bpm") or _default_bpm(session))
        mood = str(session.get("improv_jam_mood") or style_meta.get("mood") or "Mellow").strip()
    else:
        style = str(style_meta.get("style") or session.get("improv_style") or "").strip()
        groove = str(style_meta.get("groove") or session.get("improv_groove") or _default_groove(session)).strip()
        bpm = int(style_meta.get("bpm") or session.get("improv_style_bpm") or _default_bpm(session))
        mood = str(style_meta.get("mood") or session.get("improv_mood") or "Mellow").strip()

    groove_intensity = str(
        style_meta.get("groove_intensity") or session.get("improv_groove") or "Medium"
    ).strip()
    from songs.playback_defaults import normalize_groove_label

    backing_style = normalize_groove_label(style or "Pop groove")
    difficulty = str(
        style_meta.get("difficulty") or session.get("improv_difficulty") or "Intermediate"
    ).strip()
    meter = str(
        style_meta.get("meter") or session.get("improv_style_meter") or session.get("backing_time_signature") or "4/4"
    ).strip()
    jam_id = str(style or entry_mode).strip() or None
    mode_label = entry_mode.replace(" Mode", "").replace(" Generator", "")

    sections_dict = _entry_jam_sections_dict(session, entry_mode)
    if not sections_dict and resolve_improv_song_source(session) == "Custom progression":
        return build_custom_progression_context(session)

    progression: list[str] = []
    progression_label = ""
    section_labels = list(sections_dict.keys())
    if sections_dict:
        try:
            from improvisation_intelligence import flatten_sections

            progression = flatten_sections(sections_dict)
            first_sec = next(iter(sections_dict.keys()), "")
            progression_label = f"{style or mode_label} · {first_sec}" if first_sec else (style or mode_label)
        except ImportError:
            for chords in sections_dict.values():
                if isinstance(chords, list):
                    progression.extend(str(c) for c in chords if str(c).strip())

    scope, section, selected_sections = _default_scope(session)
    if not section:
        section = str(session.get("improv_selected_section") or session.get("II_SELECTED_SECTION") or "").strip() or None
    if selected_sections:
        sections_dict = _filter_sections_dict(sections_dict, section=section, selected=selected_sections)
        section_labels = list(sections_dict.keys())
        if sections_dict:
            try:
                from improvisation_intelligence import flatten_sections

                progression = flatten_sections(sections_dict)
            except ImportError:
                progression = [c for chs in sections_dict.values() for c in chs]

    return BackingContext(
        source="entry_jam",
        source_label=_SOURCE_LABELS["entry_jam"],
        active_song_id=pick_key,
        song_title=style or _song_title_from_session(session) or mode_label or "Style jam",
        key=key,
        display_key=display_key,
        concert_key=concert_key,
        chart_display_key=chart_display_key,
        bpm=bpm,
        style=style,
        groove=backing_style,
        mood=mood,
        groove_intensity=groove_intensity,
        difficulty=difficulty,
        meter=meter,
        mode_label=mode_label,
        section=section,
        sections=selected_sections or section_labels,
        scope=scope,
        loops=int(session.get("backing_track_loops") or 2),
        progression=progression,
        progression_label=progression_label or " · ".join(progression[:4]),
        section_labels=section_labels,
        loop=True,
        jam_id=jam_id,
        entry_mode=entry_mode,
        bound_pick_key=pick_key,
    )


def build_mission_context(session: dict[str, Any]) -> BackingContext:
    pick_key = _current_pick_key(session)
    key, display_key, concert_key = _display_keys_from_session(session)
    mission_id = str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "").strip()
    style_meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}

    progression: list[str] = []
    section = str(session.get("II_SELECTED_SECTION") or session.get("improv_selected_section") or "").strip() or None
    stored = session.get("improv_mission_progression")
    if isinstance(stored, list):
        progression = [str(c) for c in stored if str(c).strip()]
    else:
        home = session.get("home_sections") if isinstance(session.get("home_sections"), dict) else {}
        if home:
            try:
                from improvisation_intelligence import flatten_sections

                progression = flatten_sections(home, section_names=[section] if section else None)
            except ImportError:
                pass

    bpm = int(style_meta.get("bpm") or session.get("improv_style_bpm") or _default_bpm(session))
    groove = str(style_meta.get("groove") or session.get("improv_groove") or _default_groove(session)).strip()
    scope = "Single section" if section else "Full song"

    return BackingContext(
        source="mission",
        source_label=_SOURCE_LABELS["mission"],
        active_song_id=pick_key,
        song_title=_song_title_from_session(session),
        key=key,
        display_key=display_key,
        concert_key=concert_key,
        bpm=bpm,
        style=str(style_meta.get("style") or "").strip(),
        groove=groove,
        section=section,
        scope=scope,
        loops=int(session.get("backing_track_loops") or 2),
        progression=progression,
        progression_label=mission_id or "Mission",
        loop=True,
        mission_id=mission_id or None,
        bound_pick_key=pick_key,
    )


def build_custom_progression_context(session: dict[str, Any]) -> BackingContext:
    try:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            all_chords_from_lab_sections,
            ensure_original_structure,
            written_home_key,
        )
    except ImportError:
        return build_regular_song_context(session)

    active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
    name = str(active.get("name") or "Custom progression").strip()
    revision = str(active.get("id") or active.get("revision") or "").strip()
    pick_key = revision or _current_pick_key(session)
    home_key = str(written_home_key(active) or active.get("original_key_center") or "C").strip()
    display_key = str(session.get("display_key") or home_key).strip()
    sections = active.get("original_sections") if isinstance(active.get("original_sections"), dict) else {}
    progression = all_chords_from_lab_sections(sections)

    label = name
    if progression:
        label = f"{name} · {'–'.join(progression[:4])}"

    return BackingContext(
        source="custom_progression",
        source_label=_SOURCE_LABELS["custom_progression"],
        active_song_id=pick_key,
        song_title=name,
        key=home_key,
        display_key=display_key,
        concert_key=home_key,
        bpm=int(active.get("bpm") or _default_bpm(session)),
        style=str(active.get("progression_style") or "").strip(),
        groove=str(active.get("groove_style") or _default_groove(session)).strip(),
        scope=str(session.get("backing_track_scope") or "Full song"),
        loops=int(active.get("loops") or session.get("backing_track_loops") or 2),
        progression=progression,
        progression_label=label,
        loop=True,
        custom_revision_id=revision or None,
        bound_pick_key=_current_pick_key(session),
    )


def is_backing_context_valid(session: dict[str, Any], ctx: BackingContext | None = None) -> bool:
    ctx = ctx or get_backing_context(session)
    if ctx is None:
        return False
    if ctx.source == "regular_song":
        return True
    if ctx.source in {"entry_jam", "mission"}:
        if ctx.source == "mission":
            current_mission = str(session.get("improv_active_mission") or "").strip()
            if ctx.mission_id and current_mission and ctx.mission_id != current_mission:
                return False
        return True
    current_pick = _current_pick_key(session)
    if ctx.bound_pick_key and current_pick and ctx.bound_pick_key != current_pick:
        return False
    if ctx.source == "mission":
        current_mission = str(session.get("improv_active_mission") or "").strip()
        if ctx.mission_id and current_mission and ctx.mission_id != current_mission:
            return False
    if ctx.source == "custom_progression" and ctx.custom_revision_id:
        try:
            from custom_progression_lab import CPL_ACTIVE_KEY, ensure_original_structure

            active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
            revision = str(active.get("id") or active.get("revision") or "").strip()
            if revision and revision != ctx.custom_revision_id:
                return False
        except ImportError:
            pass
    return True


def invalidate_if_song_changed(session: dict[str, Any], new_pick_key: str | None = None) -> bool:
    """Clear stale Creative context when active song changes. Returns True if cleared."""
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return False
    if ctx.source in {"entry_jam", "mission"}:
        return False
    current = str(new_pick_key or _current_pick_key(session)).strip()
    if not ctx.bound_pick_key or not current:
        return False
    if ctx.bound_pick_key == current:
        return False
    clear_backing_context(session)
    return True


def invalidate_if_mission_changed(session: dict[str, Any]) -> bool:
    ctx = get_backing_context(session)
    if ctx is None or ctx.source != "mission":
        return False
    current = str(session.get("improv_active_mission") or "").strip()
    if ctx.mission_id and current and ctx.mission_id != current:
        clear_backing_context(session)
        return True
    return False


def invalidate_if_progression_changed(session: dict[str, Any]) -> bool:
    ctx = get_backing_context(session)
    if ctx is None or ctx.source != "custom_progression":
        return False
    if not is_backing_context_valid(session, ctx):
        clear_backing_context(session)
        return True
    return False


def context_is_stale(session: dict[str, Any]) -> bool:
    ctx = get_backing_context(session)
    if ctx is None:
        return False
    return not is_backing_context_valid(session, ctx)


def format_backing_context_banner(ctx: BackingContext | None) -> str:
    if ctx is None:
        return ""
    if ctx.source == "regular_song":
        parts = ["Backing source: Regular song"]
        if ctx.song_title:
            parts.append(ctx.song_title)
        if ctx.display_key:
            parts.append(ctx.display_key)
        if ctx.bpm:
            parts.append(f"{ctx.bpm} BPM")
        return " · ".join(parts)
    if ctx.source == "entry_jam":
        parts = ["Backing source: Entry & Jam"]
        if ctx.mood and ctx.style:
            parts.append(f"{ctx.mood} {ctx.style}")
        elif ctx.style:
            parts.append(ctx.style)
        concert = str(ctx.concert_key or ctx.key or ctx.display_key or "").strip()
        if concert:
            parts.append(f"Concert {concert}")
        if ctx.bpm:
            parts.append(f"{ctx.bpm} BPM")
        return " · ".join(parts)
    if ctx.source == "mission":
        label = ctx.mission_id or ctx.progression_label or "Mission"
        parts = ["Backing source: Mission", label]
        if ctx.bpm:
            parts.append(f"{ctx.bpm} BPM")
        return " · ".join(parts)
    if ctx.source == "custom_progression":
        if ctx.progression:
            prog = "–".join(ctx.progression[:4])
            return f"Backing source: Custom progression · {prog}"
        return f"Backing source: Custom progression · {ctx.song_title or 'Custom'}"
    return f"Backing source: {ctx.source_label}"


def apply_backing_context_to_session(
    session: dict[str, Any],
    ctx: BackingContext,
    *,
    st_like: Any | None = None,
    widget_safe: bool = True,
) -> None:
    """Mirror BackingContext into backing session keys.

    When ``widget_safe`` is True (default), queue pending handoff keys instead of
    writing widget-owned session keys after widgets may already exist.
    """
    from types import SimpleNamespace

    from backing_track_state import write_canonical_backing_state
    from custom_progression_lab import (
        BACKING_AUTOPLAY,
        PENDING_BACKING_LOOPS,
        PENDING_BACKING_SCOPE,
        PENDING_BACKING_SINGLE_SECTION,
    )
    from songs.bpm_state import request_backing_bpm
    from songs.key_state import BACKING_NEEDS_REGEN, request_display_key
    from songs.playback_defaults import (
        apply_backing_defaults_for_song,
        playback_song_id,
        prime_active_song_bpm,
        request_backing_groove,
    )

    st_like = st_like or SimpleNamespace(session_state=session)
    backing_style = _backing_groove_style_from_ctx(ctx)
    sync_id = backing_page_sync_id(session, song_sync_id=str(ctx.active_song_id or ""))

    if ctx.source == "custom_progression":
        try:
            from songs.music_source import set_custom_source

            set_custom_source(session)
        except ImportError:
            pass
    elif ctx.source in {"entry_jam", "mission"}:
        try:
            from studio_page_state import resolve_improv_song_source

            source = resolve_improv_song_source(session)
        except ImportError:
            source = str(session.get("improv_song_source") or "Active song")
        if source == "Custom progression":
            try:
                from songs.music_source import set_custom_source

                set_custom_source(session)
            except ImportError:
                pass
        else:
            try:
                from songs.music_source import set_catalog_source

                set_catalog_source(session)
            except ImportError:
                pass

    if ctx.display_key or ctx.concert_key:
        concert = str(ctx.concert_key or ctx.display_key or "").strip()
        if concert:
            session["concert_key"] = concert
            if ctx.chart_display_key:
                session["_creative_chart_display_key"] = str(ctx.chart_display_key).strip()
            if widget_safe:
                request_display_key(st_like, concert)
            else:
                session["display_key"] = concert

    is_custom = ctx.source == "custom_progression"
    song_id = str(ctx.active_song_id or "").strip()
    if not song_id:
        song_id = playback_song_id(
            is_custom=is_custom,
            song_title=ctx.song_title,
            song_artist="",
            custom_name=ctx.song_title if is_custom else "",
            custom_revision=str(ctx.custom_revision_id or ""),
        )

    session.pop("last_backing_defaults_song_id", None)
    if widget_safe:
        request_backing_bpm(st_like, int(ctx.bpm))
        request_backing_groove(st_like, backing_style)
    else:
        prime_active_song_bpm(st_like, sync_id=sync_id, active_song_bpm=int(ctx.bpm))
        request_backing_bpm(st_like, int(ctx.bpm))
        request_backing_groove(st_like, backing_style)
        apply_backing_defaults_for_song(
            st_like,
            song_id=sync_id,
            default_bpm=int(ctx.bpm),
            default_groove=backing_style,
            song_data={"name": ctx.song_title, "bpm": ctx.bpm} if is_custom else None,
        )
        session["backing_track_bpm"] = int(ctx.bpm)
        session["backing_groove_style"] = backing_style
        flush_pending_backing_handoff_keys(session, sync_id=sync_id)

    if ctx.section:
        session[PENDING_BACKING_SCOPE] = "Single section"
        session[PENDING_BACKING_SINGLE_SECTION] = ctx.section
        if not widget_safe:
            session["backing_track_scope"] = "Single section"
            session["backing_track_single_section"] = ctx.section
    else:
        session.pop("backing_track_single_section", None)
        session[PENDING_BACKING_SCOPE] = str(ctx.scope or "Full song")
        session.pop(PENDING_BACKING_SINGLE_SECTION, None)
        if not widget_safe:
            session["backing_track_scope"] = str(ctx.scope or "Full song")

    if widget_safe:
        session[PENDING_BACKING_LOOPS] = int(ctx.loops or 2)
    else:
        session["backing_track_loops"] = int(ctx.loops or 2)

    canonical = {
        "backing_track_bpm": int(ctx.bpm),
        "backing_groove_style": backing_style,
        "backing_time_signature": str(ctx.meter or "4/4"),
        "backing_track_scope": str(ctx.scope or "Full song"),
        "backing_track_single_section": str(ctx.section or ""),
        "backing_track_loops": int(ctx.loops or 2),
    }
    write_canonical_backing_state(
        session,
        canonical,
        reason=f"backing_context_{ctx.source}",
    )
    session[BACKING_NEEDS_REGEN] = True
    session[BACKING_AUTOPLAY] = True
    if ctx.source in {"entry_jam", "mission"} and ctx.groove_intensity:
        try:
            from harmonic_rhythm_intelligence import BACKING_HUMANIZE_LEVEL_KEY

            session[BACKING_HUMANIZE_LEVEL_KEY] = humanize_level_for_groove_intensity(ctx.groove_intensity)
        except ImportError:
            session["backing_humanize_level"] = humanize_level_for_groove_intensity(ctx.groove_intensity)
    if ctx.meter:
        if widget_safe:
            session["_pending_backing_meter"] = str(ctx.meter)
        else:
            try:
                from songs.meter_state import BACKING_METER_KEY

                session[BACKING_METER_KEY] = str(ctx.meter)
            except ImportError:
                session["backing_time_signature"] = str(ctx.meter)
    if widget_safe:
        session[PENDING_BACKING_CONTEXT_APPLY] = True


def active_creative_backing_context(session: dict[str, Any]) -> BackingContext | None:
    """Return valid non-regular backing context, or None."""
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return None
    if not is_backing_context_valid(session, ctx):
        return None
    return ctx


def sections_dict_from_backing_context(
    session: dict[str, Any],
    ctx: BackingContext | None = None,
) -> dict[str, list[str]]:
    """Chord sections in concert key for backing generation when Creative context is active."""
    ctx = ctx or active_creative_backing_context(session)
    entry_mode = str(ctx.entry_mode if ctx else session.get("improv_entry_mode") or "").strip()
    sections = _entry_jam_sections_dict(session, entry_mode)
    if not sections and ctx and ctx.progression:
        label = str(ctx.progression_label or "Creative").strip() or "Creative"
        return {label: list(ctx.progression)}
    if ctx:
        section = ctx.section
        selected = list(ctx.sections or [])
        sections = _filter_sections_dict(sections, section=section, selected=selected)
    return sections


def sections_dict_for_chart_display(
    session: dict[str, Any],
    sections_concert: dict[str, list[str]],
    *,
    concert_key: str = "",
    ctx: BackingContext | None = None,
) -> dict[str, list[str]]:
    """Transpose Creative sections to chart/shape/written display key when needed."""
    if not sections_concert:
        return sections_concert
    ctx = ctx or active_creative_backing_context(session)
    concert = str(concert_key or (ctx.concert_key if ctx else "") or session.get("concert_key") or "C").strip()
    chart = str((ctx.chart_display_key if ctx else "") or _resolve_chart_display_key(session, concert)).strip()
    if not chart or chart == concert:
        return sections_concert
    try:
        from creative_key_sync import retranspose_generated_sections

        return retranspose_generated_sections(sections_concert, from_key=concert, to_key=chart)
    except ImportError:
        return sections_concert


def humanize_level_for_groove_intensity(intensity: str) -> str:
    mapping = {"Light": "Light", "Medium": "Moderate", "Heavy": "Strong"}
    return mapping.get(str(intensity or "").strip(), "Moderate")


def flush_pending_backing_context_handoff(session: dict[str, Any]) -> bool:
    """Return True when a Creative/custom backing handoff is queued for this run."""
    return bool(session.pop(PENDING_BACKING_CONTEXT_APPLY, None))


def backing_page_sync_id(session: dict[str, Any], *, song_sync_id: str) -> str:
    """BPM/widget sync id — creative source signature when non-regular backing is active."""
    ctx = active_creative_backing_context(session)
    if ctx is None:
        return str(song_sync_id or "").strip()
    sig = str(ctx.source_signature or "").strip()
    if sig:
        return f"creative:{ctx.source}:{sig}"
    return f"creative:{ctx.source}"


def sync_creative_handoff_keys(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Read Creative widget values into canonical keys before building backing context."""
    try:
        from creative_key_sync import (
            apply_creative_concert_key,
            creative_entry_concert_key,
            sync_creative_style_jam_meta,
        )
    except ImportError:
        return
    sync_creative_style_jam_meta(session)
    key = creative_entry_concert_key(session)
    if key:
        apply_creative_concert_key(session, key, st_like=st_like)


def open_backing_from_creative(
    session: dict[str, Any],
    *,
    source: BackingSource,
    st_like: Any | None = None,
) -> BackingContext:
    """Build, store, and apply Creative backing context."""
    sync_creative_handoff_keys(session, st_like=st_like)
    if source == "mission":
        ctx = build_mission_context(session)
    else:
        ctx = build_entry_jam_context(session)
    existing = get_backing_context(session)
    if existing and existing.source_signature == ctx.source_signature and existing.source == ctx.source:
        ctx.created_at = existing.created_at
    set_backing_context(session, ctx)
    apply_backing_context_to_session(session, ctx, st_like=st_like)
    return ctx


def restore_regular_song_backing(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext:
    """Clear Creative/custom override and restore active song backing."""
    clear_backing_context(session)
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE

        session.pop(CREATIVE_CONCERT_KEY_SOURCE, None)
    except ImportError:
        session.pop("_creative_concert_key_source", None)
    session.pop("_creative_chart_display_key", None)
    ctx = build_regular_song_context(session)
    set_backing_context(session, ctx)
    apply_backing_context_to_session(session, ctx, st_like=st_like)
    return ctx


def reconcile_backing_context_on_backing_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Re-sync valid Creative/custom context after backing page song-default logic."""
    ctx = active_creative_backing_context(session)
    if ctx is None:
        flush_pending_backing_handoff_keys(
            session,
            sync_id=str(session.get("_backing_trace_sync_id") or ""),
        )
        return
    apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=False)
    flush_pending_backing_handoff_keys(
        session,
        sync_id=backing_page_sync_id(session, song_sync_id=str(ctx.active_song_id or "")),
    )


__all__ = [
    "BACKING_CONTEXT_KEY",
    "BackingContext",
    "BackingSource",
    "build_custom_progression_context",
    "build_entry_jam_context",
    "build_mission_context",
    "build_regular_song_context",
    "clear_backing_context",
    "compute_source_signature",
    "context_is_stale",
    "get_backing_context",
    "invalidate_if_mission_changed",
    "invalidate_if_progression_changed",
    "invalidate_if_song_changed",
    "is_backing_context_valid",
    "refresh_backing_context_timestamps",
    "apply_backing_context_to_session",
    "active_creative_backing_context",
    "sections_dict_from_backing_context",
    "sections_dict_for_chart_display",
    "humanize_level_for_groove_intensity",
    "flush_pending_backing_context_handoff",
    "flush_pending_backing_handoff_keys",
    "_backing_groove_style_from_ctx",
    "format_backing_context_banner",
    "backing_page_sync_id",
    "sync_creative_handoff_keys",
    "open_backing_from_creative",
    "PENDING_BACKING_CONTEXT_APPLY",
    "reconcile_backing_context_on_backing_page",
    "restore_regular_song_backing",
]
