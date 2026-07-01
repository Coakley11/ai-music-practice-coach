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

BackingSource = Literal[
    "regular_song", "entry_jam", "mission", "custom_progression", "song_improv"
]

_SOURCE_LABELS: dict[BackingSource, str] = {
    "regular_song": "Catalog song",
    "entry_jam": "Entry & Jam",
    "mission": "Mission",
    "custom_progression": "Custom progression",
    "song_improv": "Song-Based Improvisation",
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
    pick = _current_pick_key(session)
    sel = session.get("selected_song")
    if not isinstance(sel, dict):
        try:
            from songs.state import SELECTED_SONG_STATE_KEY

            sel = session.get(SELECTED_SONG_STATE_KEY)
        except ImportError:
            sel = None
    if isinstance(sel, dict) and pick:
        try:
            from songs.music_source import _pick_keys_match

            if _pick_keys_match(str(sel.get("pick_key") or "").strip(), pick, session_state=session):
                title = str(sel.get("title") or sel.get("name") or "").strip()
                if title:
                    return title
        except ImportError:
            spk = str(sel.get("pick_key") or "").strip()
            if spk == pick:
                title = str(sel.get("title") or sel.get("name") or "").strip()
                if title:
                    return title
    title = str(session.get("song") or session.get("active_song_title") or "").strip()
    if title:
        return title
    if isinstance(sel, dict):
        return str(sel.get("title") or sel.get("name") or "").strip()
    return ""


def _display_keys_from_session(session: dict[str, Any]) -> tuple[str, str, str]:
    display = str(session.get("display_key") or "").strip()
    concert = str(session.get("concert_key") or session.get("original_key") or display).strip()
    key = concert or display or "C"
    return key, display or key, concert or key


def _live_backing_concert_keys(session: dict[str, Any]) -> tuple[str, str, str]:
    """Practice concert key from live sidebar/session — not stale widget/improv snapshots."""
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE, creative_entry_concert_key
        from songs.key_state import PENDING_DISPLAY_KEY

        pending = str(
            session.get(PENDING_DISPLAY_KEY)
            or session.get("_pending_display_key")
            or ""
        ).strip()
        if pending:
            return pending, pending, pending

        live = str(session.get("display_key") or "").strip()
        concert = str(session.get("concert_key") or "").strip()
        creative_sel = str(creative_entry_concert_key(session) or "").strip()
        key_source = str(session.get(CREATIVE_CONCERT_KEY_SOURCE) or "").strip()
        if live and key_source:
            practice = live
        elif creative_sel and live and live != creative_sel and not key_source:
            practice = creative_sel
        else:
            practice = live or creative_sel or concert or "C"
        practice = practice or "C"
        return practice, practice, practice
    except ImportError:
        pass
    display = str(session.get("display_key") or "").strip()
    concert = display or str(session.get("concert_key") or "").strip()
    if concert:
        return concert, display or concert, concert
    creative_keys = _creative_concert_keys(session)
    if creative_keys:
        return creative_keys
    return _display_keys_from_session(session)


def sync_improv_widgets_from_live_concert_key(session: dict[str, Any]) -> None:
    """Keep Creative improv widget keys aligned with the live Practice Concert Key."""
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not live:
        return
    entry = str(session.get("improv_entry_mode") or "").strip()
    meta = dict(session.get("improv_style_meta") or {})
    if entry == "Style Jam Mode":
        session["improv_style_key"] = live
        meta["key"] = live
    elif entry == "Jam Session Generator":
        session["improv_jam_key"] = live
        meta["key"] = live
    if meta:
        session["improv_style_meta"] = meta


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
    """Chart/shape/written display key for ``concert_key`` (not global sidebar drift)."""
    concert = str(concert_key or session.get("concert_key") or session.get("display_key") or "C").strip() or "C"
    try:
        from instrument_transposition import (
            chart_in_instrument_key,
            effective_chart_key,
            is_transposing_instrument,
        )

        inst = str(session.get("instrument") or "Piano").strip() or "Piano"
        if is_transposing_instrument(inst) and chart_in_instrument_key(session):
            chart, _mode = effective_chart_key(concert, inst, session)
            return str(chart or concert).strip() or concert
        try:
            from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

            if inst == "Guitar" and session.get(CAPO_ENABLED_KEY):
                shape = str(session.get(CAPO_SHAPE_KEY) or "").strip()
                if shape:
                    return shape
        except ImportError:
            pass
    except ImportError:
        pass
    return concert


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
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None and sess.sections:
            return {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in sess.sections.items()
                if isinstance(chords, list)
            }
    except ImportError:
        pass
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


def _canonical_active_song_bpm(session: dict[str, Any]) -> int:
    """Song-default BPM from catalog/custom metadata — not stale backing transport."""
    sel = session.get("selected_song")
    if isinstance(sel, dict) and sel:
        try:
            bpm = int(sel.get("bpm") or 0)
            if bpm > 0:
                return bpm
        except (TypeError, ValueError):
            pass
        try:
            from songs.playback_defaults import canonical_active_song_bpm

            bpm = int(canonical_active_song_bpm(sel) or 0)
            if bpm > 0:
                return bpm
        except (ImportError, TypeError, ValueError):
            pass
    active = session.get("cpl_active_progression")
    if isinstance(active, dict):
        try:
            bpm = int(active.get("bpm") or 0)
            if bpm > 0:
                return bpm
        except (TypeError, ValueError):
            pass
    return _default_bpm(session)


def _canonical_active_song_groove(session: dict[str, Any]) -> str:
    sel = session.get("selected_song")
    if isinstance(sel, dict) and sel:
        genre = str(sel.get("genre") or "").strip()
        if genre:
            try:
                from songs.playback_defaults import normalize_groove_label

                label = genre if genre.lower().endswith("groove") else f"{genre} groove"
                return normalize_groove_label(label)
            except ImportError:
                pass
        try:
            from songs.playback_defaults import default_groove_for_song, normalize_groove_label

            groove = str(
                default_groove_for_song(sel, infer_fn=lambda _rec, _fb: "Auto")
            ).strip()
            if groove and groove != "Auto":
                return normalize_groove_label(groove)
        except ImportError:
            pass
    try:
        from songs.playback_defaults import normalize_groove_label

        return normalize_groove_label("Pop groove")
    except ImportError:
        return "Pop groove"


def _default_groove(session: dict[str, Any]) -> str:
    return str(session.get("backing_groove_style") or session.get("backing_groove") or "Pop groove").strip()


def backing_page_transport_defaults(session: dict[str, Any]) -> tuple[int, str, str]:
    """BPM/groove/meter for Backing page widgets from backing_context when present."""
    ctx = get_backing_context(session)
    if ctx is not None:
        return (
            int(ctx.bpm or _default_bpm(session)),
            _backing_groove_style_from_ctx(ctx),
            str(ctx.meter or "4/4"),
        )
    return _default_bpm(session), _default_groove(session), "4/4"


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
    original_key = _original_key_for_active_song(session)
    pref = get_backing_source_preference(session)
    _, display_key, concert_key = _live_backing_concert_keys(session)
    if not concert_key:
        concert_key = display_key = original_key
    catalog_practice = False
    try:
        from music_source_ownership import intended_practice_owner

        catalog_practice = intended_practice_owner(session) == "catalog"
    except ImportError:
        pass
    if catalog_practice or pref == BACKING_PREF_CATALOG:
        bpm = _canonical_active_song_bpm(session)
        groove = _canonical_active_song_groove(session)
    else:
        bpm = _default_bpm(session)
        groove = _default_groove(session)
    scope, section, sections = _default_scope(session)
    return BackingContext(
        source="regular_song",
        source_label=_SOURCE_LABELS["regular_song"],
        active_song_id=pick_key,
        song_title=_song_title_from_session(session),
        key=original_key,
        display_key=display_key,
        concert_key=concert_key,
        bpm=bpm,
        style="",
        groove=groove,
        section=section,
        sections=sections,
        scope=scope,
        loops=int(session.get("backing_track_loops") or 2),
        progression=[],
        progression_label="",
        loop=True,
        bound_pick_key=pick_key,
    )


def _song_improv_sections_dict(session: dict[str, Any]) -> dict[str, list[str]]:
    stored = session.get("improv_song_concert_sections")
    if isinstance(stored, dict) and stored:
        return {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in stored.items()
            if isinstance(chords, list)
        }
    return {}


def build_song_improv_context(session: dict[str, Any]) -> BackingContext:
    """Backing context for Song-Based Improvisation (catalog song or custom progression)."""
    try:
        from studio_page_state import resolve_improv_song_source
    except ImportError:
        resolve_improv_song_source = lambda s: str(s.get("improv_song_source") or "Active song")  # type: ignore

    song_source = str(resolve_improv_song_source(session) or "Active song").strip()
    if song_source == "Custom progression":
        try:
            from songs.music_source import ensure_custom_progression_for_backing

            ensure_custom_progression_for_backing(session)
            from custom_progression_lab import (
                CPL_ACTIVE_KEY,
                all_chords_from_lab_sections,
                ensure_original_structure,
                written_home_key,
            )

            active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
            name = str(active.get("name") or "My Progression").strip()
            revision = str(active.get("id") or active.get("revision") or "").strip()
            try:
                from songs.music_source import custom_pick_key_for

                pick_key = custom_pick_key_for(active)
            except ImportError:
                pick_key = revision or f"custom::{name.lower().replace(' ', '-')}"
            home_key = str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C"
            _, display_key, concert_key = _live_backing_concert_keys(session)
            if not concert_key:
                concert_key = display_key = home_key
            sections_raw = active.get("original_sections") if isinstance(active.get("original_sections"), dict) else {}
            sections_dict = {
                str(sec): [str(c) for c in chords if str(c).strip()]
                for sec, chords in sections_raw.items()
                if isinstance(chords, list)
            }
            progression = all_chords_from_lab_sections(sections_raw) if sections_raw else []
            progression_label = name
            if progression:
                progression_label = f"{name} · {'–'.join(progression[:4])}"
            scope, section, selected_sections = _default_scope(session)
            return BackingContext(
                source="song_improv",
                source_label=_SOURCE_LABELS["song_improv"],
                active_song_id=pick_key,
                song_title=name,
                key=home_key,
                display_key=display_key,
                concert_key=concert_key,
                chart_display_key=_resolve_chart_display_key(session, concert_key),
                bpm=int(active.get("bpm") or _default_bpm(session)),
                style=str(active.get("progression_style") or "").strip(),
                groove=str(active.get("groove_style") or _default_groove(session)).strip(),
                section=section,
                sections=selected_sections or list(sections_dict.keys()),
                scope=scope,
                loops=int(active.get("loops") or session.get("backing_track_loops") or 2),
                progression=progression,
                progression_label=progression_label,
                section_labels=list(sections_dict.keys()),
                loop=True,
                entry_mode="Song-Based Improvisation",
                mode_label="Song-Based Improvisation",
                bound_pick_key=pick_key,
                custom_revision_id=revision or None,
            )
        except ImportError:
            pass

    pick_key = _current_pick_key(session)
    key, display_key, concert_key = _live_backing_concert_keys(session)
    chart_display_key = _resolve_chart_display_key(session, concert_key)
    scope, section, selected_sections = _default_scope(session)
    sections_dict = _song_improv_sections_dict(session)
    progression: list[str] = []
    section_labels = list(sections_dict.keys())
    if sections_dict:
        try:
            from improvisation_intelligence import flatten_sections

            progression = flatten_sections(sections_dict)
        except ImportError:
            progression = [c for chs in sections_dict.values() for c in chs if str(c).strip()]
    song_title = _song_title_from_session(session) or "Active song"
    progression_label = song_title
    if progression:
        progression_label = f"{song_title} · {'–'.join(progression[:4])}"
    return BackingContext(
        source="song_improv",
        source_label=_SOURCE_LABELS["song_improv"],
        active_song_id=pick_key,
        song_title=song_title,
        key=key,
        display_key=display_key,
        concert_key=concert_key,
        chart_display_key=chart_display_key,
        bpm=_default_bpm(session),
        style="",
        groove=_default_groove(session),
        section=section,
        sections=selected_sections or section_labels,
        scope=scope,
        loops=int(session.get("backing_track_loops") or 2),
        progression=progression,
        progression_label=progression_label,
        section_labels=section_labels,
        loop=True,
        entry_mode="Song-Based Improvisation",
        mode_label="Song-Based Improvisation",
        bound_pick_key=pick_key,
    )


def build_entry_jam_context(session: dict[str, Any]) -> BackingContext:
    try:
        from studio_page_state import resolve_improv_song_source
    except ImportError:
        resolve_improv_song_source = lambda s: str(s.get("improv_song_source") or "Active song")  # type: ignore

    pick_key = _current_pick_key(session)
    key, display_key, concert_key = _live_backing_concert_keys(session)
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

    jam_title = style or mode_label or "Style jam"
    if not style and str(resolve_improv_song_source(session) or "").strip() == "Active song":
        jam_title = _song_title_from_session(session) or jam_title
    return BackingContext(
        source="entry_jam",
        source_label=_SOURCE_LABELS["entry_jam"],
        active_song_id=pick_key,
        song_title=jam_title,
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
        from songs.music_source import custom_pick_key_for
    except ImportError:
        return build_regular_song_context(session)

    active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
    name = str(active.get("name") or "Custom progression").strip()
    revision = str(active.get("id") or active.get("revision") or "").strip()
    pick_key = custom_pick_key_for(active)
    home_key = str(written_home_key(active) or active.get("original_key_center") or "C").strip()
    _, display_key, concert_key = _live_backing_concert_keys(session)
    if not concert_key:
        concert_key = display_key = home_key
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
        concert_key=concert_key,
        bpm=int(active.get("bpm") or _default_bpm(session)),
        style=str(active.get("progression_style") or "").strip(),
        groove=str(active.get("groove_style") or _default_groove(session)).strip(),
        scope=str(session.get("backing_track_scope") or "Full song"),
        loops=int(active.get("loops") or session.get("backing_track_loops") or 2),
        progression=progression,
        progression_label=label,
        loop=True,
        custom_revision_id=revision or None,
        bound_pick_key=pick_key,
    )


def is_backing_context_valid(session: dict[str, Any], ctx: BackingContext | None = None) -> bool:
    ctx = ctx or get_backing_context(session)
    if ctx is None:
        return False
    if ctx.source == "regular_song":
        return True
    if ctx.source == "custom_progression":
        if ctx.custom_revision_id:
            try:
                from custom_progression_lab import CPL_ACTIVE_KEY, ensure_original_structure

                active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
                revision = str(active.get("id") or active.get("revision") or "").strip()
                if revision and revision != ctx.custom_revision_id:
                    return False
            except ImportError:
                pass
        return True
    if ctx.source in {"entry_jam", "mission", "song_improv"}:
        if ctx.source == "mission":
            current_mission = str(session.get("improv_active_mission") or "").strip()
            if ctx.mission_id and current_mission and ctx.mission_id != current_mission:
                return False
        current_pick = _current_pick_key(session)
        if ctx.bound_pick_key and current_pick and ctx.bound_pick_key != current_pick:
            return False
        return True
    return False


def invalidate_if_song_changed(session: dict[str, Any], new_pick_key: str | None = None) -> bool:
    """Clear stale Creative backing when active song changes. Returns True if reset."""
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return False
    current = str(new_pick_key or _current_pick_key(session)).strip()
    if not current or not ctx.bound_pick_key:
        return False
    if ctx.bound_pick_key == current:
        return False
    reset_backing_on_active_song_change(session, new_pick_key=current)
    return True


def reset_backing_on_active_song_change(
    session: dict[str, Any],
    *,
    new_pick_key: str = "",
    practice_concert_key: str = "",
) -> BackingContext:
    """Active song changed: catalog/custom regular backing owns studio; preserve creative_session."""
    _release_creative_backing_ownership(session)
    try:
        from songs.key_state import PENDING_DISPLAY_KEY
    except ImportError:
        PENDING_DISPLAY_KEY = "_pending_display_key"  # type: ignore[misc,assignment]

    pending = str(session.get(PENDING_DISPLAY_KEY) or "").strip()
    concert = str(
        practice_concert_key
        or pending
        or _original_key_for_active_song(session)
        or ""
    ).strip()
    if concert:
        _apply_original_song_display_key(session, concert)

    try:
        from songs.bpm_state import LAST_BPM_SONG

        session.pop(LAST_BPM_SONG, None)
    except ImportError:
        session.pop("_last_bpm_song", None)
    session.pop("last_backing_defaults_song_id", None)

    try:
        from songs.music_source import (
            cpl_session_is_active,
            is_custom_progression,
            set_catalog_source,
            set_custom_source,
        )

        if cpl_session_is_active(session) or is_custom_progression(session):
            set_custom_source(session)
            set_backing_source_preference(session, BACKING_PREF_CUSTOM)
            ctx = build_custom_progression_context(session)
        else:
            set_catalog_source(session)
            set_backing_source_preference(session, BACKING_PREF_CATALOG)
            ctx = build_regular_song_context(session)
    except ImportError:
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        ctx = build_regular_song_context(session)

    set_backing_context(session, ctx)
    try:
        apply_backing_context_to_session(session, ctx, widget_safe=True)
    except Exception:
        pass
    _ = new_pick_key
    return ctx


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
        parts = ["Backing source: Catalog song"]
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
    elif ctx.source in {"entry_jam", "mission", "song_improv"}:
        try:
            from studio_page_state import resolve_improv_song_source

            source = resolve_improv_song_source(session)
        except ImportError:
            source = str(session.get("improv_song_source") or "Active song")
        if ctx.source == "song_improv" or source == "Active song":
            try:
                from songs.music_source import set_catalog_source

                set_catalog_source(session)
            except ImportError:
                pass
        elif source == "Custom progression":
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
            try:
                from session_widget_safe import safe_assign_display_key

                safe_assign_display_key(session, concert, widget_safe=widget_safe, st_like=st_like)
            except ImportError:
                session["concert_key"] = concert
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


def _retranspose_sections_to_practice_key(
    session: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    practice_key: str,
    ctx: BackingContext,
) -> dict[str, list[str]]:
    """Retranspose generated jam sections when practice concert key diverges from tracker."""
    if not sections or not practice_key:
        return sections
    if ctx.source != "entry_jam":
        return sections
    entry_mode = str(ctx.entry_mode or session.get("improv_entry_mode") or "").strip()
    try:
        from creative_key_sync import IMPROV_JAM_KEY_TRACKER, IMPROV_STYLE_KEY_TRACKER, retranspose_generated_sections
    except ImportError:
        return sections
    if entry_mode == "Jam Session Generator":
        tracker = str(session.get(IMPROV_JAM_KEY_TRACKER) or session.get("improv_jam_key") or "").strip()
    else:
        tracker = str(session.get(IMPROV_STYLE_KEY_TRACKER) or session.get("improv_style_key") or "").strip()
    origin = str(tracker or ctx.concert_key or "").strip()
    if origin and origin != practice_key:
        return retranspose_generated_sections(sections, from_key=origin, to_key=practice_key)
    return sections


def sections_dict_from_backing_context(
    session: dict[str, Any],
    ctx: BackingContext | None = None,
) -> dict[str, list[str]]:
    """Chord sections in concert key for backing generation when Creative context is active."""
    ctx = ctx or active_creative_backing_context(session)
    if ctx is None:
        return {}
    practice_key = str(session.get("display_key") or ctx.concert_key or "C").strip() or "C"
    if ctx.source == "song_improv":
        sections = _song_improv_sections_dict(session)
        if not sections and ctx.progression:
            label = str(ctx.song_title or ctx.progression_label or "Song").strip() or "Song"
            sections = {label: list(ctx.progression)}
        origin = str(ctx.concert_key or ctx.display_key or "").strip()
        if sections and origin and origin != practice_key:
            try:
                from creative_key_sync import retranspose_generated_sections

                sections = retranspose_generated_sections(sections, from_key=origin, to_key=practice_key)
            except ImportError:
                pass
    else:
        entry_mode = str(ctx.entry_mode or session.get("improv_entry_mode") or "").strip()
        sections = _entry_jam_sections_dict(session, entry_mode)
        if not sections and ctx.progression:
            label = str(ctx.progression_label or "Creative").strip() or "Creative"
            sections = {label: list(ctx.progression)}
        sections = _retranspose_sections_to_practice_key(
            session,
            sections,
            practice_key=practice_key,
            ctx=ctx,
        )
    section = ctx.section
    selected = list(ctx.sections or [])
    return _filter_sections_dict(sections, section=section, selected=selected)


def refresh_backing_context_from_session(session: dict[str, Any]) -> BackingContext | None:
    """Rebuild backing context snapshot from live session state."""
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return None
    if ctx.source == "entry_jam":
        new_ctx = build_entry_jam_context(session)
    elif ctx.source == "song_improv":
        new_ctx = build_song_improv_context(session)
    elif ctx.source == "mission":
        new_ctx = build_mission_context(session)
    elif ctx.source == "custom_progression":
        new_ctx = build_custom_progression_context(session)
    else:
        return ctx
    new_ctx.created_at = ctx.created_at
    return new_ctx


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
    _ = ctx  # ctx retained for callers; chart key always comes from live session state.
    concert = str(
        concert_key
        or session.get("concert_key")
        or session.get("display_key")
        or "C"
    ).strip()
    chart = _resolve_chart_display_key(session, concert)
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
    """Return True when a Creative/custom backing handoff is queued (does not consume)."""
    return bool(session.get(PENDING_BACKING_CONTEXT_APPLY))


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
    from backing_musical_state import clear_stale_chart_session_keys
    from songs.playback_defaults import _CANONICAL_BACKING_ID_KEY

    try:
        from backing_source_navigation import snapshot_practice_source_display_key

        snapshot_practice_source_display_key(session)
    except ImportError:
        pass
    sync_creative_handoff_keys(session, st_like=st_like)
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass
    if source == "mission":
        ctx = build_mission_context(session)
    elif source == "song_improv":
        ctx = build_song_improv_context(session)
    elif source == "custom_progression":
        ctx = build_custom_progression_context(session)
    else:
        ctx = build_entry_jam_context(session)
    existing = get_backing_context(session)
    if not existing or existing.source_signature != ctx.source_signature or existing.source != ctx.source:
        session.pop(_CANONICAL_BACKING_ID_KEY, None)
    if existing and existing.source_signature == ctx.source_signature and existing.source == ctx.source:
        ctx.created_at = existing.created_at
    clear_stale_chart_session_keys(session)
    set_backing_context(session, ctx)
    apply_backing_context_to_session(session, ctx, st_like=st_like)
    set_backing_source_preference(session, BACKING_PREF_CREATIVE)
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "backing")
        save_page_snapshot(session, "creative")
    except ImportError:
        pass
    return ctx


BACKING_SOURCE_PREFERENCE_KEY = "_backing_source_preference"
BACKING_PREF_CATALOG = "catalog"
BACKING_PREF_CUSTOM = "custom"
BACKING_PREF_CREATIVE = "creative"


def set_backing_source_preference(session: dict[str, Any], preference: str) -> None:
    session[BACKING_SOURCE_PREFERENCE_KEY] = str(preference or "").strip()


def get_backing_source_preference(session: dict[str, Any]) -> str:
    return str(session.get(BACKING_SOURCE_PREFERENCE_KEY) or "").strip()


def clear_backing_source_preference(session: dict[str, Any]) -> None:
    session.pop(BACKING_SOURCE_PREFERENCE_KEY, None)


def catalog_or_custom_backing_is_authoritative(session: dict[str, Any]) -> bool:
    """True when catalog or custom practice owns key/progression (Creative must not reclaim)."""
    try:
        from music_source_ownership import intended_practice_owner

        practice = intended_practice_owner(session)
        if practice in {"catalog", "custom"}:
            return True
    except ImportError:
        pass
    pref = get_backing_source_preference(session)
    if pref in {BACKING_PREF_CATALOG, BACKING_PREF_CUSTOM}:
        return True
    ctx = get_backing_context(session)
    return ctx is not None and ctx.source in {"regular_song", "custom_progression"}


def ctx_is_stale_creative_for_practice(session: dict[str, Any], ctx: BackingContext | None) -> bool:
    """True when live catalog/custom practice should replace a Creative backing_context."""
    if ctx is not None and ctx.source in {"regular_song", "custom_progression"}:
        return False
    try:
        from music_source_ownership import intended_practice_owner

        practice = intended_practice_owner(session)
        if practice is None:
            return False
        if practice == "catalog":
            return ctx is None or ctx.source != "regular_song"
        if practice == "custom":
            return ctx is None or ctx.source != "custom_progression"
    except ImportError:
        pass
    try:
        from songs.music_source import (
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        if (
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        ):
            return True
    except ImportError:
        pass
    if get_backing_source_preference(session) in {BACKING_PREF_CATALOG, BACKING_PREF_CUSTOM}:
        return True
    return False


def open_live_practice_backing(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext | None:
    """Rebuild backing_context from the live catalog/custom practice source."""
    try:
        from backing_source_navigation import open_backing_for_practice_source

        return open_backing_for_practice_source(session, st_like=st_like)
    except ImportError:
        return None


def _release_creative_backing_ownership(session: dict[str, Any]) -> None:
    """Suspend live Creative backing widgets; preserve creative_session blob for later return."""
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass
    _detach_creative_backing_from_session(session)
    for key in (
        "improv_entry_mode",
        "improv_generated_sections",
        "improv_jam_session",
        "improv_song_concert_sections",
        "improv_style_meta",
        "improv_style",
        "improv_jam_style",
        "improv_mood",
        "improv_difficulty",
        "improv_groove",
        "improv_jam_mood",
        "improv_song_source",
        "improv_style_bpm",
        "improv_jam_bpm",
        "improv_style_key",
        "improv_jam_key",
        "improv_style_meter",
    ):
        session.pop(key, None)
    try:
        from studio_page_state import CREATIVE_BACKING_SONG_SOURCE_KEY, PENDING_IMPROV_SONG_SOURCE

        session.pop(CREATIVE_BACKING_SONG_SOURCE_KEY, None)
        session.pop(PENDING_IMPROV_SONG_SOURCE, None)
    except ImportError:
        pass


def _detach_creative_backing_from_session(session: dict[str, Any]) -> None:
    """Stop live Creative widgets from polluting catalog/custom backing (preserve creative_session)."""
    session.pop("_backing_creative_chart_sections", None)
    session.pop(PENDING_BACKING_CONTEXT_APPLY, None)
    try:
        from creative_key_sync import (
            IMPROV_JAM_KEY_TRACKER,
            IMPROV_STYLE_KEY_TRACKER,
            PENDING_IMPROV_JAM_KEY,
            PENDING_IMPROV_STYLE_KEY,
        )
    except ImportError:
        IMPROV_STYLE_KEY_TRACKER = "_improv_style_key_tracker"  # type: ignore[misc,assignment]
        IMPROV_JAM_KEY_TRACKER = "_improv_jam_key_tracker"  # type: ignore[misc,assignment]
        PENDING_IMPROV_STYLE_KEY = "_pending_improv_style_key"  # type: ignore[misc,assignment]
        PENDING_IMPROV_JAM_KEY = "_pending_improv_jam_key"  # type: ignore[misc,assignment]
    for key in (
        IMPROV_STYLE_KEY_TRACKER,
        IMPROV_JAM_KEY_TRACKER,
        PENDING_IMPROV_STYLE_KEY,
        PENDING_IMPROV_JAM_KEY,
        "_creative_chart_display_key",
    ):
        session.pop(key, None)
    try:
        from studio_cache import invalidate_session_cache

        invalidate_session_cache(session, "chart_bundle")
    except Exception:
        pass


def _original_key_for_active_song(session: dict[str, Any]) -> str:
    """Catalog/custom original key for the active practice song."""
    sel = session.get("selected_song")
    if isinstance(sel, dict):
        key = str(sel.get("key") or "").strip()
        if key:
            return key
    try:
        from active_song_state import canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            key = str(ctx.get("original_key") or ctx.get("key") or "").strip()
            if key:
                return key
    except ImportError:
        pass
    return str(session.get("original_key") or "C").strip() or "C"


def _apply_original_song_display_key(
    session: dict[str, Any],
    original_key: str,
    *,
    st_like: Any | None = None,
) -> None:
    key = str(original_key or "C").strip() or "C"
    try:
        from session_widget_safe import safe_assign_display_key

        safe_assign_display_key(session, key, widget_safe=True, st_like=st_like)
    except ImportError:
        session["concert_key"] = key
        session["display_key"] = key
        session["_pending_display_key"] = key
    try:
        from backing_source_navigation import PRACTICE_SOURCE_DISPLAY_KEY, PRACTICE_SOURCE_PICK_KEY

        session[PRACTICE_SOURCE_DISPLAY_KEY] = key
        session[PRACTICE_SOURCE_PICK_KEY] = str(session.get("active_catalog_pick_key") or "").strip()
    except ImportError:
        pass


def restore_regular_song_backing(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext:
    """Clear Creative/custom override and restore active catalog song backing."""
    clear_backing_context(session)
    _release_creative_backing_ownership(session)
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE

        session.pop(CREATIVE_CONCERT_KEY_SOURCE, None)
    except ImportError:
        session.pop("_creative_concert_key_source", None)
    try:
        from songs.music_source import (
            activate_catalog_pick_for_backing,
            ensure_custom_progression_for_backing,
            resolve_last_catalog_pick_key,
            set_catalog_source,
        )

        set_catalog_source(session)
    except ImportError:
        activate_catalog_pick_for_backing = None  # type: ignore[misc,assignment]
        ensure_custom_progression_for_backing = None  # type: ignore[misc,assignment]
        resolve_last_catalog_pick_key = None  # type: ignore[misc,assignment]
        try:
            from songs.music_source import set_catalog_source

            set_catalog_source(session)
        except ImportError:
            pass
    pick_key = ""
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        live_pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
        if live_pick and not live_pick.startswith("custom::"):
            pick_key = live_pick
    except ImportError:
        pass
    if not pick_key and resolve_last_catalog_pick_key is not None:
        pick_key = resolve_last_catalog_pick_key(session)
    if activate_catalog_pick_for_backing is not None:
        original = activate_catalog_pick_for_backing(session, pick_key, st_like=st_like)
    else:
        original = _original_key_for_active_song(session)
    _apply_original_song_display_key(session, original, st_like=st_like)
    set_backing_source_preference(session, BACKING_PREF_CATALOG)
    ctx = build_regular_song_context(session)
    set_backing_context(session, ctx)
    apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=True)
    try:
        from songs.key_state import BACKING_NEEDS_REGEN

        session[BACKING_NEEDS_REGEN] = True
    except ImportError:
        pass
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "backing")
    except ImportError:
        pass
    return ctx


def restore_custom_song_backing(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext:
    """Clear Creative/catalog override and restore active custom progression backing."""
    clear_backing_context(session)
    _release_creative_backing_ownership(session)
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE

        session.pop(CREATIVE_CONCERT_KEY_SOURCE, None)
    except ImportError:
        session.pop("_creative_concert_key_source", None)
    try:
        from songs.music_source import ensure_custom_progression_for_backing

        original = ensure_custom_progression_for_backing(session)
    except ImportError:
        original = ""
        try:
            from songs.music_source import cpl_session_is_active, set_custom_source

            if cpl_session_is_active(session):
                set_custom_source(session)
        except ImportError:
            pass
    ctx = build_custom_progression_context(session)
    concert = str(original or ctx.concert_key or ctx.display_key or ctx.key or "").strip()
    if concert:
        _apply_original_song_display_key(session, concert, st_like=st_like)
    set_backing_source_preference(session, BACKING_PREF_CUSTOM)
    set_backing_context(session, ctx)
    apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=True)
    try:
        from songs.key_state import BACKING_NEEDS_REGEN

        session[BACKING_NEEDS_REGEN] = True
    except ImportError:
        pass
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "backing")
    except ImportError:
        pass
    return ctx


def _sync_creative_backing_transport_handoff(
    session: dict[str, Any],
    ctx: BackingContext,
    *,
    st_like: Any | None = None,
) -> None:
    """Queue BPM/groove/meter from refreshed context without overwriting practice key."""
    from types import SimpleNamespace

    from songs.bpm_state import request_backing_bpm
    from songs.playback_defaults import request_backing_groove

    st_like = st_like or SimpleNamespace(session_state=session)
    backing_style = _backing_groove_style_from_ctx(ctx)
    request_backing_bpm(st_like, int(ctx.bpm))
    request_backing_groove(st_like, backing_style)
    if ctx.meter:
        session["_pending_backing_meter"] = str(ctx.meter)


def ensure_backing_context_from_creative_session(session: dict[str, Any]) -> BackingContext | None:
    """Create or refresh backing_context from the canonical Creative session when missing."""
    if catalog_or_custom_backing_is_authoritative(session):
        return get_backing_context(session)
    existing = get_backing_context(session)
    if existing is not None and existing.source in {"regular_song", "custom_progression"}:
        return existing
    if existing is not None and existing.source != "regular_song" and is_backing_context_valid(session, existing):
        refreshed = refresh_backing_context_from_session(session)
        if refreshed is not None:
            set_backing_context(session, refreshed)
        return refreshed or existing
    try:
        from creative_session_state import creative_session_is_active, get_creative_session

        if not creative_session_is_active(session):
            return existing
        sess = get_creative_session(session)
        if sess is None:
            return existing
        if sess.tool_type == "mission":
            ctx = build_mission_context(session)
        elif sess.tool_type == "song_based_improvisation":
            ctx = build_song_improv_context(session)
        elif sess.tool_type == "custom_progression":
            ctx = build_custom_progression_context(session)
        else:
            ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        return ctx
    except ImportError:
        return existing


def hydrate_backing_context_after_restore(session: dict[str, Any]) -> None:
    """Re-apply persisted Creative/custom backing_context after cloud or disk restore."""
    try:
        from creative_session_state import hydrate_creative_session_after_restore

        hydrate_creative_session_after_restore(session)
    except ImportError:
        pass
    ensure_backing_context_from_creative_session(session)
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return
    if not is_backing_context_valid(session, ctx):
        clear_backing_context(session)
        return
    try:
        from backing_source_navigation import restore_session_widgets_from_backing_context

        restore_session_widgets_from_backing_context(session, ctx)
    except ImportError:
        pass
    concert = str(
        ctx.concert_key or ctx.display_key or ctx.key or session.get("display_key") or ""
    ).strip()
    if concert:
        session["concert_key"] = concert
        try:
            from creative_session_state import creative_session_is_active, get_creative_session

            if creative_session_is_active(session):
                sess = get_creative_session(session)
                creative_key = str((sess.concert_key if sess else "") or concert).strip() or concert
                try:
                    from session_widget_safe import safe_assign_display_key

                    safe_assign_display_key(session, creative_key, widget_safe=False)
                except ImportError:
                    session["display_key"] = creative_key
                    session["_pending_display_key"] = creative_key
            else:
                session["display_key"] = concert
        except ImportError:
            session["display_key"] = concert
        sync_improv_widgets_from_live_concert_key(session)
    refreshed = refresh_backing_context_from_session(session)
    if refreshed is not None:
        set_backing_context(session, refreshed)
    session[PENDING_BACKING_CONTEXT_APPLY] = True


def reconcile_backing_context_on_backing_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Re-sync valid Creative/custom context after backing page song-default logic."""
    try:
        from music_source_ownership import reconcile_source_ownership

        reconcile_source_ownership(session, st_like=st_like)
    except ImportError:
        pass
    ctx = get_backing_context(session)
    pref = get_backing_source_preference(session)

    def _sync_sidebar_to_ctx(context: BackingContext | None) -> None:
        if context is None:
            return
        concert = str(
            context.concert_key or context.display_key or context.key or ""
        ).strip()
        if not concert:
            return
        try:
            from session_widget_safe import safe_assign_display_key

            safe_assign_display_key(session, concert, widget_safe=True, st_like=st_like)
        except ImportError:
            session["concert_key"] = concert
            session["_pending_display_key"] = concert

    try:
        from backing_context import ctx_is_stale_creative_for_practice, open_live_practice_backing

        if ctx_is_stale_creative_for_practice(session, ctx):
            open_live_practice_backing(session, st_like=st_like)
            ctx = get_backing_context(session)
            pref = get_backing_source_preference(session)
    except ImportError:
        pass

    if ctx is not None and ctx.source == "regular_song":
        _sync_sidebar_to_ctx(ctx)
        flush_pending_backing_handoff_keys(
            session,
            sync_id=str(session.get("_backing_trace_sync_id") or ""),
        )
        return
    if ctx is not None and ctx.source == "custom_progression":
        set_backing_source_preference(session, BACKING_PREF_CUSTOM)
        _sync_sidebar_to_ctx(ctx)
        flush_pending_backing_handoff_keys(
            session,
            sync_id=str(session.get("_backing_trace_sync_id") or ""),
        )
        return
    if pref in {BACKING_PREF_CATALOG, BACKING_PREF_CUSTOM}:
        _sync_sidebar_to_ctx(ctx)
        flush_pending_backing_handoff_keys(
            session,
            sync_id=str(session.get("_backing_trace_sync_id") or ""),
        )
        return
    if ctx is None:
        ctx = ensure_backing_context_from_creative_session(session)
    if ctx is not None and ctx.source != "regular_song" and is_backing_context_valid(session, ctx):
        sync_improv_widgets_from_live_concert_key(session)
        pending_apply = bool(session.get(PENDING_BACKING_CONTEXT_APPLY))
        refreshed = refresh_backing_context_from_session(session)
        if refreshed is not None:
            set_backing_context(session, refreshed)
            ctx = refreshed
        if pending_apply:
            apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=True)
            session.pop(PENDING_BACKING_CONTEXT_APPLY, None)
        else:
            _sync_creative_backing_transport_handoff(session, ctx, st_like=st_like)
        flush_pending_backing_handoff_keys(
            session,
            sync_id=backing_page_sync_id(session, song_sync_id=str(ctx.active_song_id or "")),
        )
        return
    flush_pending_backing_handoff_keys(
        session,
        sync_id=str(session.get("_backing_trace_sync_id") or ""),
    )


__all__ = [
    "BACKING_CONTEXT_KEY",
    "BackingContext",
    "BackingSource",
    "build_custom_progression_context",
    "build_entry_jam_context",
    "build_mission_context",
    "build_song_improv_context",
    "build_regular_song_context",
    "clear_backing_context",
    "compute_source_signature",
    "context_is_stale",
    "get_backing_context",
    "invalidate_if_mission_changed",
    "invalidate_if_progression_changed",
    "invalidate_if_song_changed",
    "reset_backing_on_active_song_change",
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
    "backing_page_transport_defaults",
    "sync_creative_handoff_keys",
    "open_backing_from_creative",
    "ensure_backing_context_from_creative_session",
    "PENDING_BACKING_CONTEXT_APPLY",
    "refresh_backing_context_from_session",
    "reconcile_backing_context_on_backing_page",
    "hydrate_backing_context_after_restore",
    "restore_regular_song_backing",
    "BACKING_PREF_CATALOG",
    "BACKING_PREF_CREATIVE",
    "BACKING_PREF_CUSTOM",
    "BACKING_SOURCE_PREFERENCE_KEY",
    "clear_backing_source_preference",
    "catalog_or_custom_backing_is_authoritative",
    "ctx_is_stale_creative_for_practice",
    "open_live_practice_backing",
    "get_backing_source_preference",
    "set_backing_source_preference",
    "restore_custom_song_backing",
    "sync_improv_widgets_from_live_concert_key",
    "_live_backing_concert_keys",
]
