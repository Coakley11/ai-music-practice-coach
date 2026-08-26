"""Canonical backing context — metadata + handoff driver for Backing Track.

Does not replace ``backing_track_state`` (canonical backing blob). Phase 1: build,
validate, invalidate, and signature helpers only — no page wiring yet.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

BACKING_CONTEXT_KEY = "backing_context"
BACKING_SESSION_LAUNCH_ID_BLOB_KEY = "backing_session_launch_id"
PENDING_BACKING_CONTEXT_APPLY = "_pending_backing_context_apply"
BACKING_CTX_TRANSPORT_APPLIED_SIG = "_backing_ctx_transport_applied_sig"
_CREATIVE_RETURN_ROUTE_ARG_UNSET: Any = object()

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


def _catalog_groove_label_leak(label: str, style: str) -> bool:
    g = str(label or "").strip().lower()
    st = str(style or "").strip().lower()
    if not g:
        return False
    if "jewish" in g and "jewish" not in st:
        return True
    return g in {"jewish ballad", "jewish hora", "jewish groove"} and g not in st


def _entry_jam_rhythm_groove_label(style: str, snap_groove: str = "") -> str:
    """Rhythm feel for UI — not catalog default_groove or play-intensity labels."""
    groove = str(snap_groove or "").strip()
    if groove and _catalog_groove_label_leak(groove, style):
        groove = ""
    try:
        from backing_musical_profile import normalize_backing_play_intensity

        if groove and normalize_backing_play_intensity(groove).lower() == groove.lower():
            if groove.lower() in {"light", "medium", "heavy"}:
                groove = ""
    except ImportError:
        pass
    if not groove:
        try:
            from backing_style_recipes import resolve_feel_for_style

            groove = str(resolve_feel_for_style(style, "") or "").strip()
        except ImportError:
            groove = ""
    if groove and _catalog_groove_label_leak(groove, style):
        return ""
    return groove

# Source identity only — never include editable play-session knobs (BPM, style,
# meter, sections) or player-facing Practice/Shape projection fields. Changing an
# override must not look like a new Backing source.
_SIGNATURE_FIELDS = (
    "source",
    "bound_pick_key",
    "active_song_id",
    "mission_id",
    "jam_id",
    "entry_mode",
    "custom_revision_id",
    # Generated recipe identity when jam_id is empty (Style Jam / Jam Generator).
    "mood",
    "difficulty",
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


def signature_field_values(ctx: BackingContext | dict[str, Any]) -> dict[str, Any]:
    """Values participating in ``source_signature`` (for diagnostics)."""
    if isinstance(ctx, BackingContext):
        data = ctx.to_dict()
    else:
        data = dict(ctx)
    out: dict[str, Any] = {}
    for key in _SIGNATURE_FIELDS:
        val = data.get(key)
        if key == "progression" and isinstance(val, list):
            val = "|".join(str(c) for c in val)
        out[key] = val
    return out


def diff_source_signature_fields(
    prev_blob: dict[str, Any],
    ctx: BackingContext,
) -> list[str]:
    """Field names whose signature inputs differ between stored blob and new ctx."""
    old = signature_field_values(prev_blob)
    new = signature_field_values(ctx)
    changed: list[str] = []
    for key in _SIGNATURE_FIELDS:
        if old.get(key) != new.get(key):
            changed.append(str(key))
    return changed


def _infer_set_backing_context_caller() -> str:
    import inspect

    for frame_info in inspect.stack()[2:10]:
        mod = str(frame_info.frame.f_globals.get("__name__") or "")
        func = str(frame_info.function or "")
        if mod == __name__ and func == "set_backing_context":
            continue
        if func in {"set_backing_context", "_infer_set_backing_context_caller"}:
            continue
        mod_short = mod.rsplit(".", 1)[-1] if mod else "unknown"
        return f"{mod_short}:{func}"
    return "set_backing_context"


def refresh_backing_context_timestamps(ctx: BackingContext) -> BackingContext:
    now = utc_now_iso()
    if not ctx.created_at:
        ctx.created_at = now
    ctx.updated_at = now
    ctx.source_signature = compute_source_signature(ctx)
    return ctx


def get_backing_context(session: dict[str, Any]) -> BackingContext | None:
    return BackingContext.from_dict(session.get(BACKING_CONTEXT_KEY))


def set_backing_context(
    session: dict[str, Any],
    ctx: BackingContext,
    *,
    creative_return_route: dict[str, Any] | Any = _CREATIVE_RETURN_ROUTE_ARG_UNSET,
    trace_caller: str = "",
) -> None:
    prev_blob = session.get(BACKING_CONTEXT_KEY)
    prev_route = prev_blob.get("creative_return_route") if isinstance(prev_blob, dict) else None
    prev_mission_dest = (
        prev_blob.get("mission_return_destination") if isinstance(prev_blob, dict) else None
    )
    prev_launch_id = (
        str(prev_blob.get(BACKING_SESSION_LAUNCH_ID_BLOB_KEY) or "").strip()
        if isinstance(prev_blob, dict)
        else ""
    )
    try:
        prev_src = str(prev_blob.get("source") or "").strip() if isinstance(prev_blob, dict) else ""
        new_src = str(getattr(ctx, "source", "") or "").strip()
        if prev_src == "mission" and new_src and new_src != "mission":
            from mission_pk_reclaim_trace import note_mission_pk_reclaim

            note_mission_pk_reclaim(
                session,
                writer="set_backing_context:mission→other",
                extra={
                    "new_source": new_src,
                    "trace_caller": str(trace_caller or ""),
                },
            )
    except Exception:
        pass
    explicit_route_arg_present = creative_return_route is not _CREATIVE_RETURN_ROUTE_ARG_UNSET
    payload = refresh_backing_context_timestamps(ctx).to_dict()
    preservation_reason = "no_previous_route"
    signature_fields_changed: list[str] = []
    if isinstance(prev_blob, dict):
        signature_fields_changed = diff_source_signature_fields(prev_blob, ctx)
    prev_sig = str(prev_blob.get("source_signature") or "").strip() if isinstance(prev_blob, dict) else ""
    new_sig = str(payload.get("source_signature") or "").strip()

    if explicit_route_arg_present and isinstance(creative_return_route, dict):
        payload["creative_return_route"] = dict(creative_return_route)
        # Same source identity + existing play session: keep launch_id so ephemeral
        # Current BPM/style/meter overrides survive Mission/Jam re-open / refresh.
        same_identity = bool(
            prev_sig
            and new_sig
            and prev_sig == new_sig
            and str(prev_blob.get("source") or "") == str(payload.get("source") or "")
            and prev_launch_id
        ) if isinstance(prev_blob, dict) else False
        if same_identity:
            payload[BACKING_SESSION_LAUNCH_ID_BLOB_KEY] = prev_launch_id
            preservation_reason = "explicit_route_same_signature"
        else:
            payload[BACKING_SESSION_LAUNCH_ID_BLOB_KEY] = uuid.uuid4().hex
            preservation_reason = "explicit_new_route"
    elif isinstance(prev_blob, dict):
        # New source identity (signature/source change) always starts a new
        # Backing play session — never reuse prior launch_id / ephemeral knobs.
        signature_changed = bool(prev_sig and new_sig and prev_sig != new_sig)
        source_changed = str(prev_blob.get("source") or "") != str(payload.get("source") or "")
        if signature_changed or source_changed:
            payload[BACKING_SESSION_LAUNCH_ID_BLOB_KEY] = uuid.uuid4().hex
            preservation_reason = "new_launch_on_signature_change"
        elif prev_launch_id:
            payload[BACKING_SESSION_LAUNCH_ID_BLOB_KEY] = prev_launch_id
        if (
            not signature_changed
            and not source_changed
            and isinstance(prev_route, dict)
            and prev_launch_id
        ):
            payload["creative_return_route"] = dict(prev_route)
            preservation_reason = "preserved_same_launch_id"
        elif isinstance(prev_route, dict) and not signature_changed and not source_changed:
            if not prev_sig:
                preservation_reason = "previous_signature_missing"
            elif not new_sig:
                preservation_reason = "new_signature_missing"
            else:
                payload["creative_return_route"] = dict(prev_route)
                preservation_reason = "preserved_same_signature"
        if (
            isinstance(prev_mission_dest, dict)
            and str(prev_mission_dest.get("mission_id") or "").strip()
        ):
            payload["mission_return_destination"] = copy.deepcopy(prev_mission_dest)
    session[BACKING_CONTEXT_KEY] = payload
    try:
        src = str(getattr(ctx, "source", "") or payload.get("source") or "").strip()
        if src:
            session["_last_valid_backing_source"] = src
    except Exception:
        pass
    new_route = payload.get("creative_return_route")
    caller = str(trace_caller or "").strip() or _infer_set_backing_context_caller()
    try:
        from creative_return_trace import trace_set_backing_context

        trace_set_backing_context(
            session,
            caller=caller,
            prev_route=prev_route,
            new_route=new_route,
            ctx_source=str(ctx.source or ""),
            ctx_signature=str(ctx.source_signature or ""),
            prev_blob=prev_blob,
            new_blob=payload,
            preservation_reason=preservation_reason,
            explicit_route_arg_present=explicit_route_arg_present,
            extra={
                "prev_source_signature": prev_sig,
                "new_source_signature": new_sig,
                "backing_session_launch_id": str(payload.get(BACKING_SESSION_LAUNCH_ID_BLOB_KEY) or ""),
                "prev_backing_session_launch_id": prev_launch_id,
                "signature_fields_changed": signature_fields_changed,
            },
        )
    except ImportError:
        pass


def clear_backing_context(session: dict[str, Any]) -> None:
    prev_blob = session.get(BACKING_CONTEXT_KEY)
    try:
        from creative_return_trace import trace_direct_backing_context_write

        trace_direct_backing_context_write(
            session,
            source="clear_backing_context",
            prev_blob=prev_blob,
            new_blob=None,
        )
    except ImportError:
        pass
    session.pop(BACKING_CONTEXT_KEY, None)
    session.pop(BACKING_CTX_TRANSPORT_APPLIED_SIG, None)


def _current_pick_key(session: dict[str, Any]) -> str:
    """Live catalog pick — prefer session pick over stale canonical ACTIVE_SONG_STATE.

    E4 split-brain: canonical meta / identity lagged on Love Story while
    ``active_catalog_pick_key`` already moved to Country Roads.
    """
    live = str(session.get("active_catalog_pick_key") or "").strip()
    if not live:
        sel = session.get("selected_song")
        if not isinstance(sel, dict):
            try:
                from songs.state import SELECTED_SONG_STATE_KEY

                sel = session.get(SELECTED_SONG_STATE_KEY)
            except ImportError:
                sel = None
        if isinstance(sel, dict):
            live = str(sel.get("pick_key") or "").strip()
    if live:
        return live
    try:
        from active_song_state import canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            pick = str(ctx.get("pick_key") or "").strip()
            if pick:
                return pick
    except ImportError:
        pass
    return str(session.get("pick_key") or "").strip()


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


def _fixed_practice_key_for_context(
    session: dict[str, Any],
    ctx: BackingContext,
    fallback: str = "",
) -> str:
    try:
        from workflow_key_identity import (
            fixed_practice_key_projection_blocked,
            resolve_practice_key_identity_for_ui,
        )

        if fixed_practice_key_projection_blocked(session):
            ident = resolve_practice_key_identity_for_ui(session)
            if ident is not None:
                return ident.practice_key_token
            fb = str(fallback or ctx.concert_key or ctx.display_key or "").strip()
            if fb:
                return fb
    except ImportError:
        pass
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            original = str(ctx.key or fallback or ctx.concert_key or ctx.display_key or "C").strip() or "C"
            return resolve_practice_concert_key_for_song(session, original, fallback=fallback or original)
    except ImportError:
        pass
    return str(fallback or ctx.concert_key or ctx.display_key or ctx.key or "C").strip() or "C"


def _live_backing_concert_keys(session: dict[str, Any]) -> tuple[str, str, str]:
    """Practice concert key from live sidebar/session — not stale widget/improv snapshots."""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source == "custom_progression":
            live = str(session.get("display_key") or "").strip()
            concert = str(
                session.get("concert_key") or live or ctx.concert_key or ctx.key or ""
            ).strip()
            practice = live or concert or str(ctx.concert_key or ctx.key or "C").strip() or "C"
            practice = _fixed_practice_key_for_context(session, ctx, practice)
            return practice, practice, practice
    except ImportError:
        pass
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE, creative_entry_concert_key
        from songs.key_state import PENDING_DISPLAY_KEY

        pending = str(
            session.get(PENDING_DISPLAY_KEY)
            or session.get("_pending_display_key")
            or ""
        ).strip()
        jam_owns = False
        try:
            from workflow_key_identity import generated_workflow_owns_practice_key

            jam_owns = bool(generated_workflow_owns_practice_key(session))
        except ImportError:
            jam_owns = False
        if pending and not jam_owns:
            return pending, pending, pending

        live = str(session.get("display_key") or "").strip()
        concert = str(session.get("concert_key") or "").strip()
        creative_sel = str(creative_entry_concert_key(session) or "").strip()
        key_source = str(session.get(CREATIVE_CONCERT_KEY_SOURCE) or "").strip()
        try:
            from backing_context import active_creative_backing_context

            creative_ctx = active_creative_backing_context(session)
        except ImportError:
            creative_ctx = None
        if creative_ctx is not None:
            ctx_concert = str(getattr(creative_ctx, "concert_key", "") or "").strip()
            if key_source == "backing_sidebar" and live:
                if not creative_sel or live == creative_sel or live == ctx_concert:
                    practice = live
                else:
                    practice = creative_sel
            elif creative_sel:
                practice = creative_sel
            elif live:
                practice = live
            else:
                practice = ctx_concert or concert or "C"
        else:
            practice = live or concert or "C"
        practice = practice or "C"
        try:
            from backing_context import get_backing_context

            _ctx_fix = creative_ctx or get_backing_context(session)
            if _ctx_fix is not None:
                practice = _fixed_practice_key_for_context(session, _ctx_fix, practice)
        except ImportError:
            pass
        return practice, practice, practice
    except ImportError:
        pass
    display = str(session.get("display_key") or "").strip()
    concert = display or str(session.get("concert_key") or "").strip()
    if concert:
        practice = concert
        try:
            from backing_context import get_backing_context

            _ctx_fix = get_backing_context(session)
            if _ctx_fix is not None:
                practice = _fixed_practice_key_for_context(session, _ctx_fix, practice)
        except ImportError:
            pass
        return practice, display or practice, practice
    creative_keys = _creative_concert_keys(session)
    if creative_keys:
        return creative_keys
    return _display_keys_from_session(session)


def sync_improv_widgets_from_live_concert_key(session: dict[str, Any]) -> None:
    """Keep generated-jam widgets aligned with the generated session — never song display_key."""
    try:
        from generated_workflow_projection import project_generated_owner_from_active_blob

        if project_generated_owner_from_active_blob(session, writer="sync_improv_widgets"):
            return
    except ImportError:
        pass
    try:
        from workflow_key_identity import generated_workflow_owns_practice_key, resolve_active_workflow_key_identity

        if generated_workflow_owns_practice_key(session):
            ident = resolve_active_workflow_key_identity(session)
            if ident is not None:
                live = ident.practice_key_token
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
                return
    except ImportError:
        pass


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
                    try:
                        from guitar_capo import shape_chart_key_for_concert

                        return shape_chart_key_for_concert(concert, shape)
                    except ImportError:
                        return shape
        except ImportError:
            pass
    except ImportError:
        pass
    return concert


def _entry_jam_sections_dict(session: dict[str, Any], entry_mode: str) -> dict[str, list[str]]:
    mode = str(entry_mode or "").strip()
    if mode == "Jam Session Generator":
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict):
            raw = jam.get("sections")
            if isinstance(raw, dict) and raw:
                return {
                    str(name): [str(c) for c in chords if str(c).strip()]
                    for name, chords in raw.items()
                    if isinstance(chords, list)
                }
        return {}
    if mode == "Style Jam Mode":
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
            if sess is not None and sess.tool_type == "entry_style_jam" and sess.sections:
                return {
                    str(name): [str(c) for c in chords if str(c).strip()]
                    for name, chords in sess.sections.items()
                    if isinstance(chords, list)
                }
        except ImportError:
            pass
        return {}
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
    try:
        from songs.music_source import catalog_transport_bpm_for_pick

        pick = str(session.get("active_catalog_pick_key") or "").strip()
        if not pick:
            sel = session.get("selected_song")
            if isinstance(sel, dict):
                pick = str(sel.get("pick_key") or "").strip()
        if pick and not pick.startswith("custom::"):
            row_bpm = catalog_transport_bpm_for_pick(session, pick)
            if row_bpm > 0:
                return row_bpm
    except ImportError:
        pass
    return 100


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
    """BPM/groove/meter for Backing page widgets from backing_context when present.

    Returned BPM is the *current* session tempo (slider / play-session).
    Immutable catalog default must be read via ``catalog_transport_bpm_for_pick``.
    """
    canonical_bpm = _canonical_active_song_bpm(session)
    ctx = get_backing_context(session)
    ctx_source = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
    # Catalog pick BPM is a separate owner — never authoritative for generated/
    # Mission/SBI source defaults merely because an active song also exists.
    if ctx_source not in {"entry_jam", "mission", "song_improv"}:
        try:
            from songs.music_source import catalog_transport_bpm_for_pick

            pick = _current_pick_key(session)
            cat = catalog_transport_bpm_for_pick(session, pick) if pick else 0
            if cat > 0:
                canonical_bpm = cat
        except ImportError:
            pass
    if ctx is None:
        return canonical_bpm, _default_groove(session), "4/4"
    try:
        from backing_play_session import effective_backing_play_overrides, play_session_blocks_canonical_seed

        if play_session_blocks_canonical_seed(session):
            ov = effective_backing_play_overrides(session)
            bpm = int(ov.get("bpm") or session.get("backing_track_bpm") or ctx.bpm or canonical_bpm)
            groove = str(ov.get("groove") or _backing_groove_style_from_ctx(ctx))
            meter = str(ov.get("meter") or ctx.meter or "4/4")
            return bpm, groove, meter
    except ImportError:
        pass
    if ctx_source in {"entry_jam", "song_improv", "mission"}:
        live_bpm = int(session.get("backing_track_bpm") or session.get("bpm") or 0)
        source_bpm = int(ctx.bpm or 0)
        if ctx_source == "entry_jam" and source_bpm <= 0:
            try:
                from backing_play_session import _generated_source_bpm

                source_bpm = int(_generated_source_bpm(session, ctx) or 0)
            except ImportError:
                pass
        if live_bpm > 0 and source_bpm > 0 and live_bpm != source_bpm:
            # Leftover catalog domain (96) must not outrank sealed generated source.
            try:
                from songs.music_source import catalog_transport_bpm_for_pick

                pick = _current_pick_key(session)
                cat = catalog_transport_bpm_for_pick(session, pick) if pick else 0
            except Exception:
                cat = 0
            if cat > 0 and int(live_bpm) == int(cat) and ctx_source == "entry_jam":
                live_bpm = 0
        if live_bpm > 0:
            return (
                live_bpm,
                _backing_groove_style_from_ctx(ctx),
                str(ctx.meter or "4/4"),
            )
        return (
            int(source_bpm or canonical_bpm),
            _backing_groove_style_from_ctx(ctx),
            str(ctx.meter or "4/4"),
        )
    live_bpm = int(session.get("backing_track_bpm") or session.get("bpm") or 0)
    ctx_bpm = int(ctx.bpm or 0)
    # Leftover play-session BPM that only echoes a stale ctx (song change /
    # prior source) must not outrank the live catalog original.
    if (
        canonical_bpm > 0
        and live_bpm > 0
        and live_bpm != canonical_bpm
        and (ctx_bpm <= 0 or live_bpm == ctx_bpm)
    ):
        live_bpm = 0
    if live_bpm > 0:
        use_bpm = live_bpm
    elif canonical_bpm > 0:
        use_bpm = canonical_bpm
    elif ctx_bpm > 0:
        use_bpm = ctx_bpm
    else:
        use_bpm = canonical_bpm
    return (
        use_bpm,
        _backing_groove_style_from_ctx(ctx),
        str(ctx.meter or "4/4"),
    )


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

    skip_bpm = skip_groove = skip_meter = False
    try:
        from backing_play_session import backing_play_session_has_override, play_session_blocks_canonical_seed

        if play_session_blocks_canonical_seed(session):
            skip_bpm = backing_play_session_has_override(session, "bpm")
            skip_groove = backing_play_session_has_override(session, "groove")
            skip_meter = backing_play_session_has_override(session, "meter")
    except ImportError:
        pass

    pending_bpm = session.pop(PENDING_BACKING_TRACK_BPM, None)
    pending_groove = session.pop(PENDING_BACKING_GROOVE, None)
    pending_meter = session.pop("_pending_backing_meter", None)
    if skip_bpm:
        pending_bpm = None
    if skip_groove:
        pending_groove = None
    if skip_meter:
        pending_meter = None

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
        # Immutable catalog/source default — never overwrite with session slider.
        catalog_bpm = _canonical_active_song_bpm(session)
        try:
            from songs.music_source import catalog_transport_bpm_for_pick

            pick = _current_pick_key(session)
            cat = catalog_transport_bpm_for_pick(session, pick) if pick else 0
            if cat > 0:
                catalog_bpm = cat
        except ImportError:
            pass
        groove = _canonical_active_song_groove(session)
        # Source/default BPM only — Current play-session BPM lives in play session / widgets.
        bpm = int(catalog_bpm or 100)
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
    """Full catalog/custom song sections — never Entry Jam generated maps or one-chord mission slices."""
    try:
        from workflow_musical_authority import (
            custom_owns_active_song_material,
            resolve_custom_concert_sections_at_practice_key,
        )

        if custom_owns_active_song_material(session):
            custom_secs = resolve_custom_concert_sections_at_practice_key(session)
            if custom_secs:
                return custom_secs
    except ImportError:
        pass
    try:
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        synced = sync_song_improv_sections_to_practice_key(session)
        if isinstance(synced, dict) and synced:
            cleaned = {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in synced.items()
                if isinstance(chords, list)
            }
            if sum(len(v) for v in cleaned.values()) > 0:
                return cleaned
    except ImportError:
        pass
    stored = session.get("improv_song_concert_sections")
    if isinstance(stored, dict) and stored:
        flat_count = sum(len(v) for v in stored.values() if isinstance(v, list))
        if flat_count > 1:
            cleaned = {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in stored.items()
                if isinstance(chords, list)
            }
            orig = ""
            sel = session.get("selected_song")
            if isinstance(sel, dict):
                orig = str(sel.get("key") or "").strip()
            dest = ""
            try:
                from music_workflow_pending_song_practice_key_edit import overlay_destination_practice_key

                dest = overlay_destination_practice_key(session)
            except ImportError:
                dest = str(session.get("display_key") or "")
            first = ""
            for chs in cleaned.values():
                if chs:
                    first = str(chs[0] or "").strip()
                    if first:
                        break
            keep = True
            if first and (dest or orig):
                try:
                    from music_theory import normalize_root, split_chord

                    first_root = normalize_root(split_chord(first)[0])
                    orig_root = normalize_root(split_chord(orig)[0]) if orig else ""
                    dest_root = normalize_root(split_chord(dest or orig)[0]) if (dest or orig) else ""
                    # Concert-pitch cache is only valid at the *practice* destination.
                    # Keeping catalog-original pitch (first == orig, dest != orig) while
                    # Practice Key has moved causes Guitar Shape projection to apply the
                    # shape interval to the wrong pitch class (e.g. Bm + Dm→Em → C#m).
                    if dest_root and first_root:
                        keep = first_root == dest_root
                    elif orig_root and first_root and first_root != orig_root:
                        keep = False
                except ImportError:
                    keep = True
            if keep:
                return cleaned
    home = session.get("home_sections")
    if isinstance(home, dict) and home:
        return {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in home.items()
            if isinstance(chords, list)
        }
    try:
        from songs.music_source import resolve_catalog_song_for_pick

        pick_key = _current_pick_key(session)
        selected, _ok = resolve_catalog_song_for_pick(session, pick_key)
        if isinstance(selected, dict):
            sec = selected.get("sections")
            if isinstance(sec, dict) and sec:
                return {
                    str(name): [str(c) for c in chords if str(c).strip()]
                    for name, chords in sec.items()
                    if isinstance(chords, list)
                }
    except ImportError:
        pass
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

            ensure_custom_progression_for_backing(session, promote_to_global_active=False)
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
            # Custom SBI Backing must use Custom sticky PK — never Catalog display_key.
            display_key = home_key
            concert_key = home_key
            try:
                from songs.practice_key_state import get_practice_concert_key

                sticky = str(
                    get_practice_concert_key(session, pick_key, default=home_key) or ""
                ).strip()
                if sticky:
                    display_key = concert_key = sticky
            except Exception:
                pass
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
    try:
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        sync_song_improv_sections_to_practice_key(session)
    except ImportError:
        pass
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


def _entry_jam_context_from_owner_snapshot(
    session: dict[str, Any],
    snap: Any,
) -> BackingContext:
    from generated_workflow_artifact import GeneratedWorkflowArtifactSnapshot, concert_key_from_snapshot

    if not isinstance(snap, GeneratedWorkflowArtifactSnapshot):
        snap = GeneratedWorkflowArtifactSnapshot.from_dict(snap)
    if snap is None:
        return build_entry_jam_context(session)
    entry_mode = str(snap.entry_mode or "").strip() or "Style Jam Mode"
    concert_key = concert_key_from_snapshot(snap)
    try:
        from musical_context_coherence import (
            GENERATED_OWNERS,
            CreativeBackingHandoffBlocked,
            raise_coherence_handoff_blocked,
            resolve_coherent_musical_context,
            validate_coherent_musical_context,
            validate_generated_snapshot_coherence,
        )

        owner = str(snap.workflow_owner or "")
        coherent = resolve_coherent_musical_context(
            session, prefer_owners=(owner,) if owner in GENERATED_OWNERS else None
        )
        if coherent is not None:
            snap_v = validate_coherent_musical_context(coherent)
        else:
            prog = list(snap.progression or [])
            if not prog and snap.section_map:
                try:
                    from improvisation_intelligence import flatten_sections

                    prog = flatten_sections(snap.section_map)
                except ImportError:
                    prog = [c for chs in snap.section_map.values() for c in chs if str(c).strip()]
            snap_v = validate_generated_snapshot_coherence(
                practice_tonic=str(snap.practice_tonic or "C"),
                practice_mode=str(snap.practice_mode or "major"),
                progression=prog,
                style_id=str(snap.style or ""),
                mood=str(snap.mood or "Mellow"),
                owner=owner or "jam_session_generator",
            )
        if snap_v:
            raise_coherence_handoff_blocked(session, snap_v)
    except CreativeBackingHandoffBlocked:
        raise
    except ImportError:
        pass
    key = display_key = concert_key
    chart_display_key = _resolve_chart_display_key(session, concert_key)
    style = str(snap.style or "").strip() or "Jazz Swing"
    difficulty = str(snap.level or session.get("improv_difficulty") or "Intermediate").strip()
    from backing_musical_profile import normalize_backing_play_intensity
    from songs.playback_defaults import normalize_groove_label

    rhythm_groove = _entry_jam_rhythm_groove_label(style, str(snap.groove or ""))
    backing_style = normalize_groove_label(style or "Pop groove")
    groove_intensity = normalize_backing_play_intensity(str(snap.intensity or ""), difficulty=difficulty)
    bpm = int(snap.bpm or 110)
    mood = str(snap.mood or "Mellow").strip()
    meter = str(snap.meter or "4/4").strip()
    import hashlib

    jam_id = hashlib.sha256(
        f"{snap.workflow_owner}|{snap.artifact_id}|{snap.artifact_revision}|{snap.control_fingerprint}".encode()
    ).hexdigest()[:12]
    mode_label = entry_mode.replace(" Mode", "").replace(" Generator", "")
    sections_dict = copy.deepcopy(snap.section_map)
    progression = list(snap.progression or [])
    if not progression and sections_dict:
        try:
            from improvisation_intelligence import flatten_sections

            progression = flatten_sections(sections_dict)
        except ImportError:
            progression = [c for chs in sections_dict.values() for c in chs]
    section_labels = list(sections_dict.keys())
    progression_label = section_labels[0] if section_labels else style
    scope = str(snap.selected_scope or "Full song")
    section = None
    selected_sections = list(snap.selected_section_ids or section_labels)
    jam_title = style or mode_label or "Style jam"
    gen_song_id = f"generated::{entry_mode}::{snap.artifact_id or jam_id}"
    return BackingContext(
        source="entry_jam",
        source_label=_SOURCE_LABELS["entry_jam"],
        active_song_id=gen_song_id,
        song_title=jam_title,
        key=key,
        display_key=display_key,
        concert_key=concert_key,
        chart_display_key=chart_display_key,
        bpm=bpm,
        style=style,
        groove=rhythm_groove or backing_style,
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
        bound_pick_key="",
    )


def build_entry_jam_context(session: dict[str, Any]) -> BackingContext:
    try:
        from generated_workflow_artifact import (
            BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY,
            WorkflowOwnerIntegrityError,
            WORKFLOW_OWNER_INTEGRITY_FAILURE,
            WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY,
            detect_cross_owner_handoff_fields,
            peek_backing_owner_artifact_snapshot,
            validate_owner_artifact_snapshot,
        )

        snap = peek_backing_owner_artifact_snapshot(session)
        if snap is not None:
            violations = validate_owner_artifact_snapshot(snap)
            violations.extend(detect_cross_owner_handoff_fields(session, snap))
            if not violations:
                return _entry_jam_context_from_owner_snapshot(session, snap)
            session[WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY] = "\n".join(violations)
            raise WorkflowOwnerIntegrityError(violations[0] if violations else WORKFLOW_OWNER_INTEGRITY_FAILURE)
    except ImportError:
        pass
    except WorkflowOwnerIntegrityError:
        raise
    try:
        from studio_page_state import resolve_improv_song_source
    except ImportError:
        resolve_improv_song_source = lambda s: str(s.get("improv_song_source") or "Active song")  # type: ignore

    pick_key = _current_pick_key(session)
    try:
        from backing_source_navigation import resolve_entry_jam_entry_mode

        entry_mode = resolve_entry_jam_entry_mode(session)
    except ImportError:
        entry_mode = str(session.get("improv_entry_mode") or "Style Jam Mode").strip()
        if entry_mode == "Song-Based Improvisation":
            entry_mode = "Style Jam Mode"

    key, display_key, concert_key = _live_backing_concert_keys(session)
    sections_dict: dict[str, list[str]] = {}
    used_coherent_generated = False
    if entry_mode in {"Style Jam Mode", "Jam Session Generator"}:
        try:
            from musical_context_coherence import (
                GENERATED_OWNERS,
                CreativeBackingHandoffBlocked,
                raise_coherence_handoff_blocked,
                resolve_coherent_musical_context,
                validate_coherent_musical_context,
            )

            coherent = resolve_coherent_musical_context(session, prefer_owners=tuple(GENERATED_OWNERS))
            if coherent is not None:
                coherence_v = validate_coherent_musical_context(coherent)
                if coherence_v:
                    raise_coherence_handoff_blocked(session, coherence_v)
                key = display_key = concert_key = coherent.key_token
                sections_dict = copy.deepcopy(coherent.section_map)
                used_coherent_generated = True
        except CreativeBackingHandoffBlocked:
            raise
        except ImportError:
            pass

    if not used_coherent_generated:
        try:
            from creative_key_sync import creative_entry_concert_key

            creative_sel = str(creative_entry_concert_key(session) or "").strip()
            if entry_mode in {"Style Jam Mode", "Jam Session Generator"}:
                jam_key = ""
                if entry_mode == "Style Jam Mode":
                    jam_key = str(session.get("improv_style_key") or creative_sel or "").strip()
                else:
                    jam_key = str(session.get("improv_jam_key") or creative_sel or "").strip()
                if jam_key:
                    key = display_key = concert_key = jam_key
        except ImportError:
            pass
    chart_display_key = _resolve_chart_display_key(session, concert_key)
    style_meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}
    if entry_mode == "Jam Session Generator":
        style = str(session.get("improv_jam_style") or style_meta.get("style") or "Jazz Swing").strip() or "Jazz Swing"
        groove = str(session.get("improv_groove") or style_meta.get("groove") or style).strip()
        bpm = int(session.get("improv_jam_bpm") or style_meta.get("bpm") or 110)
        mood = str(session.get("improv_jam_mood") or style_meta.get("mood") or "Mellow").strip()
    else:
        style = str(session.get("improv_style") or style_meta.get("style") or "").strip() or "Jazz Swing"
        groove = str(session.get("improv_groove") or style_meta.get("groove") or style).strip()
        bpm = int(session.get("improv_style_bpm") or style_meta.get("bpm") or 110)
        mood = str(session.get("improv_mood") or style_meta.get("mood") or "Mellow").strip()
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        owner = str(ptr.workflow_owner or "") if ptr else ""
        if owner in {"style_jam", "jam_session_generator"}:
            blob = get_workflow_blob(session, owner, str(ptr.workflow_session_id or ""))
            if blob is not None and int(getattr(blob, "tempo_bpm", 0) or 0) > 0:
                bpm = int(blob.tempo_bpm)
            if blob is not None:
                if str(blob.style or "").strip():
                    style = str(blob.style).strip()
                if str(blob.mood or "").strip():
                    mood = str(blob.mood).strip()
                if str(blob.groove or "").strip():
                    groove = str(blob.groove).strip()
    except ImportError:
        pass

    groove_intensity = str(
        session.get("improv_groove") or style_meta.get("groove") or style_meta.get("groove_intensity") or "Medium"
    ).strip()
    from backing_musical_profile import normalize_backing_play_intensity
    from songs.playback_defaults import normalize_groove_label

    difficulty = str(session.get("improv_difficulty") or style_meta.get("difficulty") or "Intermediate").strip()
    groove_intensity = normalize_backing_play_intensity(groove_intensity, difficulty=difficulty)
    if _catalog_groove_label_leak(groove_intensity, style):
        groove_intensity = normalize_backing_play_intensity("", difficulty=difficulty)
    rhythm_groove = _entry_jam_rhythm_groove_label(
        style,
        str(session.get("improv_groove") or groove if entry_mode == "Jam Session Generator" else session.get("improv_groove") or ""),
    )
    backing_style = normalize_groove_label(style or "Pop groove")
    meter = str(
        session.get("improv_style_meter") or session.get("backing_time_signature") or "4/4"
    ).strip()
    import hashlib

    jam_id = hashlib.sha256(f"{entry_mode}|{style}|{concert_key}".encode()).hexdigest()[:12]
    mode_label = entry_mode.replace(" Mode", "").replace(" Generator", "")

    if not used_coherent_generated:
        sections_dict = _entry_jam_sections_dict(session, entry_mode)

    progression: list[str] = []
    progression_label = ""
    section_labels = list(sections_dict.keys())
    if sections_dict:
        try:
            from improvisation_intelligence import flatten_sections

            progression = flatten_sections(sections_dict)
            first_sec = next(iter(sections_dict.keys()), "")
            progression_label = first_sec if first_sec else (style or mode_label)
        except ImportError:
            for chords in sections_dict.values():
                if isinstance(chords, list):
                    progression.extend(str(c) for c in chords if str(c).strip())

    scope, section, selected_sections = _default_scope(session)
    try:
        import hashlib

        from backing_workflow_context import backing_scope_for_workflow

        wf: str = (
            "jam_session_generator"
            if entry_mode == "Jam Session Generator"
            else ("style_jam" if entry_mode == "Style Jam Mode" else "entry_jam")
        )
        fp_src = f"{wf}|{style}|{entry_mode}|{'/'.join(sorted(sections_dict.keys()))}"
        fp = hashlib.sha256(fp_src.encode()).hexdigest()[:16]
        scope, section, selected_sections = backing_scope_for_workflow(
            session,
            workflow_type=wf,  # type: ignore[arg-type]
            context_fingerprint=fp,
        )
    except ImportError:
        pass
    if not section and scope not in {"Full song", "Mission chord"}:
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
    gen_song_id = f"generated::{entry_mode}::{jam_id}"
    if (
        entry_mode in {"Style Jam Mode", "Jam Session Generator"}
        and progression
        and not used_coherent_generated
    ):
        try:
            from musical_context_coherence import (
                CreativeBackingHandoffBlocked,
                infer_major_tonic_from_progression,
                raise_coherence_handoff_blocked,
                validate_hybrid_generated_session_split,
            )

            hybrid_v = validate_hybrid_generated_session_split(
                session,
                declared_key=concert_key,
                progression=progression,
                style_id=style,
            )
            if hybrid_v:
                try:
                    from creative_key_sync import retranspose_generated_sections
                    from music_theory import normalize_root, semitone_distance, split_chord

                    inferred = infer_major_tonic_from_progression(progression)
                    if inferred and concert_key:
                        inf_root = normalize_root(split_chord(inferred)[0])
                        dest_root = normalize_root(split_chord(str(concert_key))[0])
                        if inf_root and dest_root and semitone_distance(inf_root, dest_root) != 0:
                            sections_dict = retranspose_generated_sections(
                                sections_dict,
                                from_key=inferred,
                                to_key=str(concert_key),
                            )
                            try:
                                from improvisation_intelligence import flatten_sections

                                progression = flatten_sections(sections_dict)
                            except ImportError:
                                progression = [
                                    str(c)
                                    for chs in sections_dict.values()
                                    if isinstance(chs, list)
                                    for c in chs
                                    if str(c).strip()
                                ]
                            hybrid_v = validate_hybrid_generated_session_split(
                                session,
                                declared_key=concert_key,
                                progression=progression,
                                style_id=style,
                            )
                except ImportError:
                    pass
            if hybrid_v:
                raise_coherence_handoff_blocked(session, hybrid_v)
        except CreativeBackingHandoffBlocked:
            raise
        except ImportError:
            pass
    return BackingContext(
        source="entry_jam",
        source_label=_SOURCE_LABELS["entry_jam"],
        active_song_id=gen_song_id,
        song_title=jam_title,
        key=key,
        display_key=display_key,
        concert_key=concert_key,
        chart_display_key=chart_display_key,
        bpm=bpm,
        style=style,
        groove=rhythm_groove or backing_style,
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
        bound_pick_key="" if entry_mode in {"Style Jam Mode", "Jam Session Generator"} else pick_key,
    )


def build_mission_context(session: dict[str, Any]) -> BackingContext:
    try:
        from mission_song_backing_style import sync_mission_style_from_song

        sync_mission_style_from_song(session)
    except ImportError:
        pass
    pick_key = _current_pick_key(session)
    key, display_key, concert_key = _display_keys_from_session(session)
    chart_display_key = _resolve_chart_display_key(session, concert_key)
    mission_id = str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "").strip()
    style_meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}

    chords_flat = session.get("improv_mission_chord_options")
    idx = int(session.get("ii_selected_chord_index") or session.get("II_SELECTED_CHORD_INDEX") or 0)
    target_chord = ""
    if isinstance(chords_flat, list) and chords_flat:
        idx = max(0, min(idx, len(chords_flat) - 1))
        target_chord = str(chords_flat[idx] or "").strip()
    if not target_chord:
        target_chord = str(session.get("ii_selected_chord") or session.get("II_SELECTED_CHORD") or "").strip()

    # Keep canonical concert identity for theory; player-facing progression for
    # Mission Backing display must follow the preserved Instrument/Shape context.
    canonical_target = target_chord
    try:
        from creative_chord_selection_authority import read_authoritative_mission_chord_selection

        auth_ch, _auth_sec, _auth_idx = read_authoritative_mission_chord_selection(session)
        if auth_ch:
            canonical_target = str(auth_ch).strip() or canonical_target
    except ImportError:
        pass
    try:
        from effective_practice_context import musician_facing_chart_key, musician_facing_chord

        concert = str(
            session.get("concert_key")
            or session.get("display_key")
            or concert_key
            or ""
        ).strip()
        chart = musician_facing_chart_key(session, concert) if concert else ""
        src = canonical_target or target_chord
        if concert and chart and src:
            target_chord = musician_facing_chord(src, concert_key=concert, chart_key=chart)
    except ImportError:
        pass
    if canonical_target:
        session["_mission_backing_canonical_chord"] = canonical_target

    section = str(
        session.get("ii_selected_section")
        or session.get("II_SELECTED_SECTION")
        or session.get("improv_selected_section")
        or ""
    ).strip() or None

    progression: list[str] = []
    if target_chord:
        progression = [target_chord]
        session["improv_mission_progression"] = progression
    else:
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
    style = str(style_meta.get("style") or session.get("improv_style") or "").strip()
    meter = str(
        style_meta.get("meter") or session.get("improv_style_meter") or session.get("backing_time_signature") or "4/4"
    ).strip()
    scope = "Mission chord"
    section_label = section or (f"Chord · {target_chord}" if target_chord else "Mission")
    loops = int(session.get("backing_track_loops") or session.get("improv_mission_loops") or 4)
    song_title = _song_title_from_session(session)
    if target_chord and section:
        progression_label = f"{section} · {target_chord}"
    elif target_chord:
        progression_label = target_chord
    else:
        progression_label = mission_id or "Mission"

    try:
        from musical_context_authority import resolve_authoritative_practice_key

        pk = resolve_authoritative_practice_key(session)
        practice_token = pk.practice_key_token
        if practice_token:
            key = practice_token
            display_key = practice_token
            concert_key = practice_token
            chart_display_key = _resolve_chart_display_key(session, concert_key)
    except ImportError:
        pass

    return BackingContext(
        source="mission",
        source_label="Mission Backing Jam",
        active_song_id=pick_key,
        song_title=song_title,
        key=key,
        display_key=display_key,
        concert_key=concert_key,
        chart_display_key=chart_display_key,
        bpm=bpm,
        style=style,
        groove=groove,
        meter=meter,
        section=section_label,
        scope=scope,
        loops=loops,
        progression=progression,
        progression_label=progression_label,
        loop=True,
        mission_id=mission_id or None,
        bound_pick_key=pick_key,
    )


def _custom_progression_sections_at_concert_key(
    session: dict[str, Any],
    *,
    concert_key: str = "",
    active: dict[str, Any] | None = None,
) -> tuple[dict[str, list[str]], list[str]]:
    """CPL section dict and flat progression in the current practice concert key."""
    try:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            all_chords_from_lab_sections,
            display_sections_for_key,
            ensure_original_structure,
            sections_to_chord_lists,
            written_home_key,
        )
    except ImportError:
        return {}, []

    active = ensure_original_structure(active or session.get(CPL_ACTIVE_KEY) or {})
    practice = str(
        concert_key or session.get("display_key") or session.get("concert_key") or ""
    ).strip()
    if not practice:
        practice = str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C"
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            original = str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C"
            practice = resolve_practice_concert_key_for_song(session, original, fallback=practice)
    except ImportError:
        pass
    transposed = display_sections_for_key(active, practice)
    sections = sections_to_chord_lists(transposed)
    progression = all_chords_from_lab_sections(transposed)
    return sections, progression


def build_custom_progression_context(session: dict[str, Any]) -> BackingContext:
    try:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
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
    has_live_concert_key = bool(
        str(
            session.get("display_key")
            or session.get("concert_key")
            or session.get("_pending_display_key")
            or ""
        ).strip()
    )
    _, display_key, concert_key = _live_backing_concert_keys(session)
    if not has_live_concert_key:
        concert_key = display_key = home_key
    elif not concert_key:
        concert_key = display_key = home_key
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            concert_key = display_key = resolve_practice_concert_key_for_song(
                session,
                home_key,
                pick_key=pick_key,
                fallback=concert_key or display_key or home_key,
            )
    except ImportError:
        pass
    sections, progression = _custom_progression_sections_at_concert_key(
        session,
        concert_key=concert_key,
        active=active,
    )

    label = name
    if progression:
        label = f"{name} · {'–'.join(progression[:4])}"

    default_bpm = int(active.get("bpm") or _default_bpm(session))
    try:
        from songs.practice_key_state import resolve_source_bpm_for_pick

        bpm = resolve_source_bpm_for_pick(session, pick_key, default_bpm=default_bpm)
    except ImportError:
        bpm = default_bpm

    return BackingContext(
        source="custom_progression",
        source_label=_SOURCE_LABELS["custom_progression"],
        active_song_id=pick_key,
        song_title=name,
        key=home_key,
        display_key=display_key,
        concert_key=concert_key,
        bpm=bpm,
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
        # Song-change must invalidate stale catalog Backing (E2/E4).
        current_pick = _current_pick_key(session)
        bound = str(ctx.bound_pick_key or ctx.active_song_id or "").strip()
        if bound and current_pick:
            try:
                from songs.music_source import _pick_keys_match

                if not _pick_keys_match(bound, current_pick, session_state=session):
                    return False
            except ImportError:
                if bound != current_pick:
                    return False
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
        bound = str(ctx.bound_pick_key or "").strip()
        # Custom SBI (and custom-bound specialized overlays) may temporarily bind to
        # custom:: while Global Active Catalog remains a different song. That is not
        # invalid — validate against CPL revision, not catalog pick identity.
        custom_overlay = bool(ctx.custom_revision_id) or bound.lower().startswith("custom")
        if custom_overlay:
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
        current_pick = _current_pick_key(session)
        if bound and current_pick:
            try:
                from songs.music_source import _pick_keys_match

                if not _pick_keys_match(bound, current_pick, session_state=session):
                    return False
            except ImportError:
                if bound != current_pick:
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
    # Explicit Mission/SBI/Jam Backing visit must survive sticky/identity restore and
    # Practice Key mutation. Workspace restore under Custom GA must not reclaim.
    # Do not require studio_page==backing — post-nav restore often runs before page
    # widgets hydrate, and that is exactly when Custom reclaim was winning.
    handoff = str(session.get("_backing_explicit_handoff_source") or "").strip()
    if handoff in {"mission", "song_improv", "entry_jam"} and not session.get(
        "_backing_released_specialized_context"
    ):
        existing = get_backing_context(session)
        if existing is not None and str(getattr(existing, "source", "") or "") == handoff:
            try:
                from mission_pk_reclaim_trace import note_mission_pk_reclaim

                note_mission_pk_reclaim(
                    session,
                    writer="reset_backing_on_active_song_change:skipped_specialized",
                    extra={"handoff": handoff, "new_pick_key": str(new_pick_key or "")},
                )
            except ImportError:
                pass
            return existing
        # Ctx briefly cleared during restore — reopen specialized, never Custom.
        try:
            from mission_pk_reclaim_trace import note_mission_pk_reclaim

            note_mission_pk_reclaim(
                session,
                writer="reset_backing_on_active_song_change:reopen_specialized",
                extra={"handoff": handoff, "had_ctx": existing is not None},
            )
        except ImportError:
            pass
        try:
            from music_source_ownership import (
                activate_entry_jam_ownership,
                activate_mission_ownership,
                activate_sbi_ownership,
            )

            if handoff == "mission":
                reopened = activate_mission_ownership(session)
            elif handoff == "song_improv":
                reopened = activate_sbi_ownership(session)
            else:
                reopened = activate_entry_jam_ownership(session)
            if reopened is not None:
                return reopened
        except ImportError:
            pass
        if existing is not None:
            return existing
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
            USER_CATALOG_SOURCE_CHOICE_KEY,
            cpl_session_is_active,
            is_custom_progression,
            set_catalog_source,
            set_custom_source,
        )

        pick = str(new_pick_key or _current_pick_key(session) or "").strip()
        catalog_pick = bool(pick and not pick.startswith("custom::"))
        user_chose_catalog = bool(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        if catalog_pick or user_chose_catalog or (
            not cpl_session_is_active(session) and not is_custom_progression(session)
        ):
            set_catalog_source(session)
            set_backing_source_preference(session, BACKING_PREF_CATALOG)
            ctx = build_regular_song_context(session)
        else:
            set_custom_source(session)
            set_backing_source_preference(session, BACKING_PREF_CUSTOM)
            ctx = build_custom_progression_context(session)
    except ImportError:
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        ctx = build_regular_song_context(session)

    set_backing_context(session, ctx, trace_caller="backing_context:reset_backing_on_active_song_change")
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


def format_backing_context_banner(
    ctx: BackingContext | None,
    *,
    practice_concert_key: str = "",
    applied_bpm: int | None = None,
) -> str:
    if ctx is None:
        return ""
    resolved_concert = str(practice_concert_key or "").strip()
    try:
        bpm_display = int(applied_bpm) if applied_bpm is not None else int(ctx.bpm or 0)
    except (TypeError, ValueError):
        bpm_display = int(ctx.bpm or 0)
    if ctx.source == "regular_song":
        parts = ["Backing source: Catalog song"]
        if ctx.song_title:
            parts.append(ctx.song_title)
        concert = resolved_concert or str(ctx.display_key or "").strip()
        if concert:
            parts.append(concert)
        if bpm_display:
            parts.append(f"{bpm_display} BPM")
        return " · ".join(parts)
    if ctx.source == "entry_jam":
        parts = ["Backing source: Entry & Jam"]
        if ctx.mood and ctx.style:
            parts.append(f"{ctx.mood} {ctx.style}")
        elif ctx.style:
            parts.append(ctx.style)
        concert = resolved_concert or str(ctx.concert_key or ctx.key or ctx.display_key or "").strip()
        if concert:
            parts.append(f"Concert {concert}")
        if bpm_display:
            parts.append(f"{bpm_display} BPM")
        return " · ".join(parts)
    if ctx.source == "mission":
        parts = ["Creative Backing Jam · Mission"]
        if ctx.song_title:
            parts.append(ctx.song_title)
        if ctx.section:
            parts.append(ctx.section)
        if ctx.progression:
            parts.append(ctx.progression[0])
        elif ctx.progression_label:
            parts.append(ctx.progression_label)
        concert = resolved_concert or str(ctx.concert_key or ctx.display_key or "").strip()
        if concert:
            parts.append(f"Concert {concert}")
        if bpm_display:
            parts.append(f"{bpm_display} BPM")
        return " · ".join(parts)
    if ctx.source == "custom_progression":
        title = str(ctx.song_title or "").strip()
        if title:
            return f"Backing source: Custom progression · {title}"
        if ctx.progression:
            prog = "–".join(ctx.progression[:4])
            return f"Backing source: Custom progression · {prog}"
        return "Backing source: Custom progression · Custom"
    return f"Backing source: {ctx.source_label}"


def apply_backing_context_to_session(
    session: dict[str, Any],
    ctx: BackingContext,
    *,
    st_like: Any | None = None,
    widget_safe: bool = True,
    apply_transport_bpm: bool | None = None,
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

    sig = str(ctx.source_signature or "").strip()
    transport_already = str(session.get(BACKING_CTX_TRANSPORT_APPLIED_SIG) or "").strip() == sig
    if apply_transport_bpm is None:
        apply_transport_bpm = not transport_already
    if apply_transport_bpm and ctx.source in {"entry_jam", "mission", "song_improv"}:
        session[BACKING_CTX_TRANSPORT_APPLIED_SIG] = sig

    if ctx.source == "custom_progression":
        try:
            from songs.music_source import set_custom_source

            set_custom_source(session)
        except ImportError:
            pass
    # Creative specialized backing (entry_jam / mission / song_improv) must not flip
    # Global Catalog/Custom ownership. SBI Active/Custom are preview/handoff only (H5).

    if ctx.display_key or ctx.concert_key:
        concert = str(ctx.concert_key or ctx.display_key or "").strip()
        concert = _fixed_practice_key_for_context(session, ctx, concert)
        try:
            from workflow_key_identity import generated_workflow_owns_practice_key, resolve_practice_key_identity_for_ui

            if generated_workflow_owns_practice_key(session) or str(ctx.source or "") in {
                "entry_jam",
                "mission",
                "song_improv",
            }:
                ident = resolve_practice_key_identity_for_ui(session)
                if ident is not None:
                    concert = ident.practice_key_token
        except ImportError:
            pass
        # Regular catalog Backing must never demote the active-source sticky Practice Key
        # back to a stale sealed ctx concert key (H2: Shape C#m must not fall to Bm).
        if str(ctx.source or "") == "regular_song":
            try:
                from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

                pick = str(
                    resolve_practice_source_pick(session)
                    or getattr(ctx, "bound_pick_key", "")
                    or session.get("active_catalog_pick_key")
                    or ""
                ).strip()
                sticky = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
                if sticky:
                    concert = sticky
            except ImportError:
                pass
        jam_ctx = str(ctx.source or "") == "entry_jam"
        # song_improv / mission backing seals must never overwrite the sidebar Practice Key.
        # Live identity (display_key / practice store) owns Practice Key; backing only consumes it.
        backing_must_not_own_practice_key = str(ctx.source or "") in {"song_improv", "mission"}
        if concert and not jam_ctx and not backing_must_not_own_practice_key:
            try:
                from session_widget_safe import safe_assign_display_key

                safe_assign_display_key(session, concert, widget_safe=widget_safe, st_like=st_like)
            except ImportError:
                session["concert_key"] = concert
                if widget_safe:
                    request_display_key(st_like, concert)
                else:
                    session["display_key"] = concert
            # Keep sealed regular_song ctx aligned with sticky Practice Key.
            if str(ctx.source or "") == "regular_song" and concert:
                try:
                    if str(ctx.concert_key or "") != concert or str(ctx.display_key or "") != concert:
                        ctx.concert_key = concert
                        ctx.display_key = concert
                        set_backing_context(session, ctx)
                except Exception:
                    pass
        elif concert and not jam_ctx and backing_must_not_own_practice_key:
            # Keep concert_key aligned for transport only when live practice already matches.
            live = str(session.get("display_key") or session.get("concert_key") or "").strip()
            if live:
                session["concert_key"] = live
            elif concert:
                session["concert_key"] = concert
        elif concert and jam_ctx:
            try:
                from session_widget_safe import safe_session_assign

                entry = str(ctx.entry_mode or session.get("improv_entry_mode") or "").strip()
                if entry == "Jam Session Generator":
                    safe_session_assign(session, "improv_jam_key", concert, widget_safe=widget_safe)
                else:
                    safe_session_assign(session, "improv_style_key", concert, widget_safe=widget_safe)
            except ImportError:
                entry = str(ctx.entry_mode or session.get("improv_entry_mode") or "").strip()
                if entry == "Jam Session Generator":
                    session["improv_jam_key"] = concert
                else:
                    session["improv_style_key"] = concert

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
    skip_transport = False
    try:
        from backing_play_session import play_session_blocks_canonical_seed

        skip_transport = bool(play_session_blocks_canonical_seed(session))
    except ImportError:
        skip_transport = False

    if apply_transport_bpm and not skip_transport:
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
    elif widget_safe and not skip_transport:
        request_backing_groove(st_like, backing_style)

    if skip_transport:
        pass
    elif ctx.section:
        session[PENDING_BACKING_SCOPE] = "Single section"
        session[PENDING_BACKING_SINGLE_SECTION] = ctx.section
        if not widget_safe:
            session["backing_track_scope"] = "Single section"
            session["backing_track_single_section"] = ctx.section
    else:
        preserve_scope = False
        scope_filters: dict[str, Any] = {}
        try:
            from backing_track_state import canonical_backing_filters, gather_backing_filters, is_backing_user_dirty

            if is_backing_user_dirty(session):
                preserve_scope = True
                scope_filters = gather_backing_filters(session) or canonical_backing_filters(session) or {}
        except ImportError:
            pass
        if preserve_scope and scope_filters.get("backing_track_scope"):
            session.pop("backing_track_single_section", None)
            session[PENDING_BACKING_SCOPE] = str(scope_filters.get("backing_track_scope") or "Full song")
            session.pop(PENDING_BACKING_SINGLE_SECTION, None)
            if not widget_safe:
                session["backing_track_scope"] = str(scope_filters.get("backing_track_scope") or "Full song")
                sec = str(scope_filters.get("backing_track_single_section") or "").strip()
                if sec:
                    session["backing_track_single_section"] = sec
                multi = scope_filters.get("backing_track_multi_sections")
                if isinstance(multi, list) and multi:
                    session["backing_track_multi_sections"] = list(multi)
        else:
            session.pop("backing_track_single_section", None)
            session[PENDING_BACKING_SCOPE] = str(ctx.scope or "Full song")
            session.pop(PENDING_BACKING_SINGLE_SECTION, None)
            if not widget_safe:
                session["backing_track_scope"] = str(ctx.scope or "Full song")

    if skip_transport:
        pass
    elif widget_safe:
        session[PENDING_BACKING_LOOPS] = int(ctx.loops or 2)
    else:
        session["backing_track_loops"] = int(ctx.loops or 2)

    if not skip_transport:
        applied_bpm = int(ctx.bpm or 0)
        preserve_live_bpm = False
        try:
            from backing_play_session import (
                backing_play_session_has_override,
                current_backing_play_bpm,
                play_session_blocks_canonical_seed,
            )

            preserve_live_bpm = bool(
                play_session_blocks_canonical_seed(session)
                or backing_play_session_has_override(session, "bpm")
            )
            live_slider = int(current_backing_play_bpm(session, default=0, sync_id=str(sync_id or "")) or 0)
            if live_slider > 0 and applied_bpm > 0 and live_slider != applied_bpm:
                preserve_live_bpm = True
        except ImportError:
            preserve_live_bpm = False
        if apply_transport_bpm and applied_bpm > 0 and not preserve_live_bpm:
            session["backing_track_bpm"] = applied_bpm
            session["bpm"] = applied_bpm
            try:
                from songs.bpm_state import BPM_WIDGET_KEY

                session[BPM_WIDGET_KEY] = applied_bpm
            except ImportError:
                pass
            try:
                from songs.playback_defaults import seed_backing_bpm_slider_before_widget

                seed_backing_bpm_slider_before_widget(
                    session, sync_id=str(sync_id or ""), bpm=applied_bpm
                )
            except ImportError:
                pass
        canonical = {
            "backing_track_bpm": int(
                session.get("backing_track_bpm") or applied_bpm or ctx.bpm or 100
            ),
            "backing_groove_style": backing_style,
            "backing_time_signature": str(ctx.meter or "4/4"),
            "backing_track_scope": str(session.get("backing_track_scope") or ctx.scope or "Full song"),
            "backing_track_single_section": str(
                session.get("backing_track_single_section") or ctx.section or ""
            ),
            "backing_track_loops": int(ctx.loops or 2),
        }
        multi = session.get("backing_track_multi_sections")
        if isinstance(multi, list) and multi:
            canonical["backing_track_multi_sections"] = list(multi)
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
    if ctx.meter and not skip_transport:
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


def sync_live_keys_from_backing_context(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    widget_safe: bool = True,
) -> str:
    """Align display_key, concert_key, and pending with active Creative/custom backing.

    Mission / SBI Backing are subordinate to the live Practice Key. Sealed context
    must never push an older Dm over a user Em (Pass 8 Mission B regression).
    """
    ctx = get_backing_context(session)
    if ctx is None:
        return ""
    if ctx.source not in {"entry_jam", "song_improv", "mission", "custom_progression"}:
        return ""
    concert = str(ctx.concert_key or ctx.display_key or ctx.key or "").strip()
    concert = _fixed_practice_key_for_context(session, ctx, concert)
    if not concert:
        return ""
    if ctx.source == "entry_jam":
        entry = str(ctx.entry_mode or session.get("improv_entry_mode") or "").strip()
        try:
            from session_widget_safe import safe_session_assign

            if entry == "Style Jam Mode":
                safe_session_assign(session, "improv_style_key", concert, widget_safe=widget_safe)
            elif entry == "Jam Session Generator":
                safe_session_assign(session, "improv_jam_key", concert, widget_safe=widget_safe)
        except ImportError:
            if entry == "Style Jam Mode":
                session["improv_style_key"] = concert
            elif entry == "Jam Session Generator":
                session["improv_jam_key"] = concert
        return concert
    # Mission / SBI: live Practice Key owns; sealed ctx only follows.
    if ctx.source in {"mission", "song_improv"}:
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        pending = ""
        try:
            from music_workflow_pending_song_practice_key_edit import pending_selected_practice_key_token

            pending = str(pending_selected_practice_key_token(session) or "").strip()
        except ImportError:
            pending = str(session.get("_pending_display_key") or "").strip()
        protect = pending or live
        if protect:
            session["concert_key"] = protect
            try:
                from music_source_ownership import trace_practice_key_owner

                trace_practice_key_owner(
                    session,
                    phase="sync_live_keys_skip_sealed_mission_sbi",
                    extra={
                        "sealed": concert,
                        "protect": protect,
                        "source": ctx.source,
                        "reason": "live_practice_key_outranks_sealed_ctx",
                    },
                )
            except ImportError:
                pass
            return protect
    try:
        from session_widget_safe import (
            safe_assign_display_key,
            widgets_likely_instantiated,
        )

        locked = widget_safe and widgets_likely_instantiated(session)
        if not locked:
            from songs.key_state import PENDING_DISPLAY_KEY

            session.pop(PENDING_DISPLAY_KEY, None)
            session["display_key"] = concert
            session["concert_key"] = concert
        else:
            safe_assign_display_key(session, concert, widget_safe=True, st_like=st_like)
    except ImportError:
        from songs.key_state import PENDING_DISPLAY_KEY

        session["concert_key"] = concert
        session[PENDING_DISPLAY_KEY] = concert
        if not widget_safe:
            session["display_key"] = concert
    return concert


_CREATIVE_BACKING_SOURCES = frozenset({"entry_jam", "song_improv", "mission"})


def active_creative_backing_context(session: dict[str, Any]) -> BackingContext | None:
    """Return valid Creative (entry_jam/song_improv/mission) backing context, or None."""
    ctx = get_backing_context(session)
    if ctx is None or ctx.source not in _CREATIVE_BACKING_SOURCES:
        return None
    if not is_backing_context_valid(session, ctx):
        return None
    return ctx


def creative_backing_card_context(session: dict[str, Any]) -> BackingContext | None:
    """Return backing_context when the visible card should use the Creative template."""
    return active_creative_backing_context(session)


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
    practice_key = str(ctx.concert_key or session.get("display_key") or "C").strip() or "C"
    if ctx.source == "entry_jam":
        try:
            from workflow_key_identity import resolve_active_workflow_key_identity

            ident = resolve_active_workflow_key_identity(session)
            if ident is not None:
                practice_key = ident.practice_key_token
        except ImportError:
            practice_key = str(
                session.get("improv_style_key")
                or session.get("improv_jam_key")
                or ctx.concert_key
                or "C"
            ).strip() or "C"
    practice_key = _fixed_practice_key_for_context(session, ctx, practice_key)
    if ctx.source == "song_improv":
        # Custom SBI must use CPL / LAST_CUSTOM sections — never catalog Shape charts
        # via sync_song_improv_sections_to_practice_key (screenshot My Progression / Shape bleed).
        use_custom_sbi = False
        try:
            from songs.practice_key_state import sbi_uses_custom_progression_preview

            use_custom_sbi = bool(
                sbi_uses_custom_progression_preview(session)
                or str(getattr(ctx, "active_song_id", "") or "").startswith("custom::")
                or getattr(ctx, "custom_revision_id", None)
            )
        except ImportError:
            use_custom_sbi = bool(
                str(getattr(ctx, "active_song_id", "") or "").startswith("custom::")
                or getattr(ctx, "custom_revision_id", None)
            )
        if use_custom_sbi:
            sections, _ = _custom_progression_sections_at_concert_key(
                session, concert_key=practice_key
            )
            if not sections and ctx.progression:
                label = str(ctx.song_title or ctx.progression_label or "Custom").strip() or "Custom"
                sections = {label: list(ctx.progression)}
        else:
            # sync_song_improv_sections_to_practice_key already returns Practice-Key pitch.
            # Never retranspose again using sealed ctx.key (catalog original) — that yields
            # Dm→Fm when Practice is Dm and original was Bm.
            try:
                from workflow_musical_authority import sync_song_improv_sections_to_practice_key

                sections = sync_song_improv_sections_to_practice_key(session) or _song_improv_sections_dict(
                    session
                )
            except ImportError:
                sections = _song_improv_sections_dict(session)
            if not sections and ctx.progression:
                label = str(ctx.song_title or ctx.progression_label or "Song").strip() or "Song"
                sections = {label: list(ctx.progression)}
    elif ctx.source == "custom_progression":
        sections, _ = _custom_progression_sections_at_concert_key(session, concert_key=practice_key)
        if not sections and ctx.progression:
            label = str(ctx.song_title or ctx.progression_label or "Custom").strip() or "Custom"
            sections = {label: list(ctx.progression)}
    elif ctx.source == "mission":
        label = str(ctx.section or ctx.progression_label or "Mission").strip() or "Mission"
        sections: dict[str, list[str]] = {}
        chords = list(ctx.progression or [])
        if chords:
            sections = {label: chords}
        elif ctx.progression:
            sections = {label: list(ctx.progression)}
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


def sync_regular_song_backing_context_keys(session: dict[str, Any]) -> None:
    """Keep catalog backing_context concert keys aligned with live practice state."""
    ctx = get_backing_context(session)
    if ctx is None or ctx.source != "regular_song":
        return
    practice = ""
    try:
        from backing_musical_state import resolve_current_backing_musical_state

        practice = str(resolve_current_backing_musical_state(session).practice_concert_key or "").strip()
    except ImportError:
        pass
    if not practice:
        _, _, practice = _live_backing_concert_keys(session)
    practice = str(practice or "").strip()
    if not practice:
        return
    if str(ctx.display_key or "").strip() == practice and str(ctx.concert_key or "").strip() == practice:
        return
    ctx.display_key = practice
    ctx.concert_key = practice
    set_backing_context(session, ctx, trace_caller="backing_context:sync_regular_song_backing_context_keys")


def refresh_backing_context_from_session(session: dict[str, Any]) -> BackingContext | None:
    """Rebuild backing context snapshot from live session state.

    Source rebuilds (CPL / catalog / generator) refresh progression identity, but
    CURRENT Backing play-session transport (BPM / style / meter / loop / scope)
    must survive refresh and reboot. Only an expired play session yields to
    source defaults (true leave → later return).
    """
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
    try:
        from backing_play_session import (
            apply_current_play_session_to_backing_context,
            recover_play_session_overrides_from_backing_context,
        )

        # Ensure empty reminted bags recover visit transport from sealed ctx first.
        recover_play_session_overrides_from_backing_context(session)
        new_ctx = apply_current_play_session_to_backing_context(
            session, new_ctx, previous=ctx
        )
    except ImportError:
        pass
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


def backing_page_sync_id(session: dict[str, Any], *, song_sync_id: str = "") -> str:
    """Stable BPM/widget sync id for one backing source identity.

    Must not include live BPM (or the full source signature, which hashes BPM).
    A BPM-in-id slider remounts on every tempo edit and snaps back to source BPM.
    """
    ctx = get_backing_context(session)
    if ctx is not None and ctx.source == "custom_progression":
        sig = str(ctx.custom_revision_id or ctx.bound_pick_key or "").strip()
        if sig:
            return f"custom:{sig}"
        active_id = str(ctx.active_song_id or "").strip()
        return f"custom:{active_id or 'progression'}"
    ctx = active_creative_backing_context(session)
    if ctx is None:
        return str(song_sync_id or "").strip()
    source = str(ctx.source or "").strip() or "creative"
    identity = ""
    if source == "entry_jam":
        # Never use catalog bound_pick_key — that remounted the Jam slider onto
        # Shape-of-You 96. Prefer launch_id (stable for one Backing play session)
        # over jam_id — style-label churn reminted jam_id and snapped TEMPO to 98
        # while Current stayed 111 after refresh.
        launch = ""
        try:
            from backing_play_session import BACKING_PLAY_SESSION_KEY

            bag = session.get(BACKING_PLAY_SESSION_KEY)
            if isinstance(bag, dict):
                launch = str(bag.get("launch_id") or "").strip()
        except Exception:
            launch = ""
        if not launch:
            try:
                raw = session.get(BACKING_CONTEXT_KEY)
                if isinstance(raw, dict):
                    launch = str(raw.get(BACKING_SESSION_LAUNCH_ID_BLOB_KEY) or "").strip()
            except Exception:
                launch = ""
        identity = str(
            launch
            or getattr(ctx, "jam_id", None)
            or getattr(ctx, "active_song_id", None)
            or getattr(ctx, "entry_mode", None)
            or source
        ).strip()
    else:
        identity = str(
            ctx.bound_pick_key
            or ctx.mission_id
            or ctx.active_song_id
            or ctx.entry_mode
            or source
        ).strip()
    return f"creative:{source}:{identity}"


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


def creative_specialized_backing_handoff_ready(
    session: dict[str, Any],
    *,
    creative_source: str,
) -> tuple[bool, str]:
    """True when open_backing_from_creative sealed a valid specialized BackingContext."""
    try:
        from musical_context_coherence import (
            MUSICAL_CONTEXT_COHERENCE_BLOCK_KEY,
            clear_coherence_handoff_block,
            resolve_coherent_musical_context,
            validate_coherent_musical_context,
        )

        block = session.get(MUSICAL_CONTEXT_COHERENCE_BLOCK_KEY)
        ctx = get_backing_context(session)
        if ctx is not None and creative_source == "entry_jam":
            prog = list(getattr(ctx, "progression", None) or [])
            coherent = resolve_coherent_musical_context(session)
            coherence_v: list[str] = []
            if coherent is not None:
                coherence_v = validate_coherent_musical_context(coherent)
            if prog and not coherence_v:
                clear_coherence_handoff_block(session)
                block = None
        if isinstance(block, dict) and block.get("blocked"):
            return False, "coherence_blocked"
    except ImportError:
        pass
    ctx = get_backing_context(session)
    if ctx is None:
        return False, "missing_backing_context"
    src = str(getattr(ctx, "source", "") or "").strip()
    if creative_source == "entry_jam":
        if src != "entry_jam":
            return False, f"unexpected_source:{src or 'empty'}"
        prog = list(getattr(ctx, "progression", None) or [])
        if not prog:
            return False, "empty_progression"
    elif creative_source == "mission" and src != "mission":
        return False, f"unexpected_source:{src or 'empty'}"
    elif creative_source == "song_improv" and src != "song_improv":
        return False, f"unexpected_source:{src or 'empty'}"
    elif creative_source == "custom_progression" and src != "custom_progression":
        return False, f"unexpected_source:{src or 'empty'}"
    return True, "ok"


def open_backing_from_creative(
    session: dict[str, Any],
    *,
    source: BackingSource,
    st_like: Any | None = None,
    skip_workflow_activation: bool = False,
) -> BackingContext:
    """Build, store, and apply Creative backing context."""
    from backing_musical_state import clear_stale_chart_session_keys
    from songs.playback_defaults import _CANONICAL_BACKING_ID_KEY

    try:
        from creative_source_ownership_contract import stamp_explicit_backing_handoff

        stamp_explicit_backing_handoff(session, str(source))
    except ImportError:
        session["_backing_explicit_handoff_source"] = str(source)
        session["_backing_explicit_handoff_epoch"] = int(session.get("_backing_explicit_handoff_epoch") or 0) + 1

    # Instrument is user-owned — capture before any hydrate and restore after.
    _preserved_instrument = str(session.get("instrument") or "").strip()
    _preserved_level = str(session.get("level") or "").strip()
    _preserved_focus = str(session.get("focus") or "").strip()
    try:
        from backing_source_navigation import snapshot_practice_source_display_key

        snapshot_practice_source_display_key(session)
    except ImportError:
        pass
    try:
        from songs.music_source import snapshot_catalog_before_creative

        snapshot_catalog_before_creative(session, refresh_if_pick_changed=True)
    except ImportError:
        pass
    try:
        from backing_creative_return_route import read_live_creative_surface_at_backing_launch

        _launch_tab, _launch_entry = read_live_creative_surface_at_backing_launch(session)
        if _launch_entry in ("Style Jam Mode", "Jam Session Generator"):
            session["_backing_handoff_entry_mode"] = _launch_entry
    except ImportError:
        _launch_tab, _launch_entry = "", ""
    try:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE

        session.pop(CREATIVE_CONCERT_KEY_SOURCE, None)
    except ImportError:
        pass
    sync_creative_handoff_keys(session, st_like=st_like)
    if str(source) == "entry_jam":
        try:
            from improv_jam_session_projection import sync_improv_jam_session_from_active_blob

            sync_improv_jam_session_from_active_blob(
                session, writer="open_backing_from_creative", phase="pre_build"
            )
        except ImportError:
            pass
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass
    if not _launch_tab or not _launch_entry:
        try:
            from backing_creative_return_route import read_live_creative_surface_at_backing_launch

            late_tab, late_entry = read_live_creative_surface_at_backing_launch(session)
            _launch_tab = _launch_tab or late_tab
            _launch_entry = _launch_entry or late_entry
        except ImportError:
            pass
    try:
        from backing_session_route import on_creative_backing_handoff

        on_creative_backing_handoff(session, source=str(source))
    except ImportError:
        pass
    if source == "song_improv":
        try:
            from mission_workflow_context import _deactivate_entry_jam_transient_for_missions

            _deactivate_entry_jam_transient_for_missions(session)
        except ImportError:
            pass
    if source == "mission":
        ctx = build_mission_context(session)
    elif source == "song_improv":
        ctx = build_song_improv_context(session)
    elif source == "custom_progression":
        ctx = build_custom_progression_context(session)
    else:
        if str(source) == "entry_jam":
            try:
                from generated_workflow_artifact import seal_backing_handoff_snapshot_for_creative_open
                from generated_workflow_artifact import WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY
                from musical_context_coherence import CreativeBackingHandoffBlocked

                sealed = seal_backing_handoff_snapshot_for_creative_open(session)
                if not sealed:
                    msg = str(session.get(WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY) or "").strip()
                    if not msg:
                        msg = "Specialized backing handoff could not seal the generated artifact snapshot."
                    raise CreativeBackingHandoffBlocked(msg)
            except ImportError:
                pass
        try:
            from musical_context_coherence import CreativeBackingHandoffBlocked

            ctx = build_entry_jam_context(session)
        except CreativeBackingHandoffBlocked:
            raise
    try:
        from workflow_musical_authority import validate_workflow_consistency, workflow_type_from_backing_source
        from music_workflow_activation import activate_workflow_simple
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        entry_for_wf = str(getattr(ctx, "entry_mode", "") or session.get("improv_entry_mode") or "")
        launch_wf = workflow_type_from_backing_source(
            str(ctx.source or source),
            entry_mode=entry_for_wf,
        )
        ptr = get_active_workflow_pointer(session)
        if (
            ptr
            and ptr.workflow_owner in {"jam_session_generator", "style_jam"}
            and str(source) in {"entry_jam", ""}
            and str(getattr(ctx, "source", "") or "") == "entry_jam"
            and (
                not launch_wf
                or str(ptr.workflow_owner) == str(launch_wf)
            )
        ):
            launch_wf = str(ptr.workflow_owner)
        session["_backing_launch_workflow"] = launch_wf
        owner = str(launch_wf)
        if source == "mission":
            owner = "mission_jam"
        elif source == "song_improv":
            owner = "song_based_improvisation"
        elif source == "custom_progression":
            owner = "regular_custom_backing"
        elif str(ctx.source or "") == "entry_jam":
            owner = launch_wf if launch_wf in {"style_jam", "jam_session_generator"} else "entry_jam"
        else:
            owner = "regular_catalog_backing"
        if not skip_workflow_activation and ptr and owner in {"jam_session_generator", "style_jam"}:
            if (
                str(ptr.workflow_owner or "") == owner
                and get_workflow_blob(session, str(ptr.workflow_owner), str(ptr.workflow_session_id or "")) is not None
            ):
                skip_workflow_activation = True
        if not skip_workflow_activation:
            activate_workflow_simple(
                session,
                owner,
                activation_source="open_backing_from_creative",
                page_route="backing",
                return_route="creative",
                navigation_intent="backing_open",
                persist_policy="durable_handoff",
            )
        validate_workflow_consistency(session, ctx)
    except ImportError:
        try:
            from workflow_musical_authority import validate_workflow_consistency, workflow_type_from_backing_source

            launch_wf = workflow_type_from_backing_source(
                str(ctx.source or source),
                entry_mode=str(getattr(ctx, "entry_mode", "") or session.get("improv_entry_mode") or ""),
            )
            session["_backing_launch_workflow"] = launch_wf
            validate_workflow_consistency(session, ctx)
        except ImportError:
            pass
    try:
        from generated_jam_key_context import activate_generated_jam_key_ownership

        if source in {"entry_jam"} or str(ctx.source or "") == "entry_jam":
            activate_generated_jam_key_ownership(session, entry_mode=str(ctx.entry_mode or ""))
    except ImportError:
        pass
    existing = get_backing_context(session)
    if not existing or existing.source_signature != ctx.source_signature or existing.source != ctx.source:
        session.pop(_CANONICAL_BACKING_ID_KEY, None)
        session.pop(BACKING_CTX_TRANSPORT_APPLIED_SIG, None)
    if existing and existing.source_signature == ctx.source_signature and existing.source == ctx.source:
        ctx.created_at = existing.created_at
    clear_stale_chart_session_keys(session)
    launch_wf = str(session.get("_backing_launch_workflow") or "").strip()
    owner = launch_wf or "style_jam"
    if source == "mission":
        owner = "mission_jam"
    elif source == "song_improv":
        owner = "song_based_improvisation"
    elif source == "custom_progression":
        owner = "regular_custom_backing"
    elif str(ctx.source or "") == "entry_jam":
        owner = launch_wf if launch_wf in {"style_jam", "jam_session_generator"} else "style_jam"
    creative_return_route = None
    try:
        from backing_creative_return_route import capture_creative_return_route_at_backing_launch

        creative_return_route = capture_creative_return_route_at_backing_launch(
            session,
            backing_source=str(ctx.source or source),
            workflow_owner=owner,
            launch_tab=_launch_tab,
            launch_entry=_launch_entry,
            ctx=ctx,
        )
    except ImportError:
        pass
    set_backing_context(
        session,
        ctx,
        creative_return_route=creative_return_route,
        trace_caller="open_backing_from_creative",
    )
    try:
        from backing_source_navigation import (
            mark_specialized_backing_handoff_entry,
            stamp_backing_restore_anchor,
        )

        # Anchor restore eligibility to the active catalog/custom source epoch.
        stamp_backing_restore_anchor(session)
        mark_specialized_backing_handoff_entry(session)
    except ImportError:
        pass
    # New Creative → Backing play session: Current BPM must initialize from the
    # generated/source BPM (e.g. Style Jam 130 / Jam 98), not a stale prior
    # play-session override or catalog slider (95).
    try:
        from backing_play_session import expire_backing_play_session
        from songs.playback_defaults import seed_backing_bpm_slider_before_widget

        same_sig = bool(
            existing
            and existing.source_signature == ctx.source_signature
            and existing.source == ctx.source
        )
        prev_prog = list(getattr(existing, "progression", None) or []) if existing else []
        new_prog = list(getattr(ctx, "progression", None) or [])
        new_bpm = int(getattr(ctx, "bpm", 0) or 0)
        # Note: Style/Jam may mint a new jam_id on rebuild — do not treat jam_id
        # alone as a new play source (that wiped Current BPM on same-jam reopen).
        identity_shift = bool(
            not existing
            or str(existing.source or "") != str(ctx.source or "")
            or str(getattr(existing, "mission_id", "") or "") != str(getattr(ctx, "mission_id", "") or "")
            or str(getattr(existing, "entry_mode", "") or "") != str(getattr(ctx, "entry_mode", "") or "")
            or prev_prog != new_prog
        )
        # New generated jam with a different SOURCE default BPM must seed Current
        # even when source_signature no longer hashes BPM.
        source_default_bpm_changed = False
        try:
            from backing_play_session import get_backing_play_session

            ps = get_backing_play_session(session)
            prev_default = int(((ps or {}).get("defaults") or {}).get("bpm") or 0)
            if new_bpm > 0 and prev_default > 0 and int(new_bpm) != int(prev_default):
                source_default_bpm_changed = True
            elif new_bpm > 0 and existing is not None:
                prev_ctx_bpm = int(getattr(existing, "bpm", 0) or 0)
                if prev_ctx_bpm > 0 and int(new_bpm) != int(prev_ctx_bpm):
                    source_default_bpm_changed = True
        except ImportError:
            source_default_bpm_changed = False
        try:
            from backing_play_session import (
                apply_backing_play_session_to_widgets,
                backing_play_session_has_override,
            )

            has_bpm_override = backing_play_session_has_override(session, "bpm")
        except ImportError:
            apply_backing_play_session_to_widgets = None  # type: ignore[assignment]
            has_bpm_override = False

        if (
            source_default_bpm_changed
            or (not same_sig and identity_shift)
            or (not same_sig and not has_bpm_override)
        ):
            # New generated/source identity (or first open): initialize from source BPM.
            expire_backing_play_session(session)
            source_bpm = new_bpm
            if source_bpm > 0:
                sync_id = ""
                try:
                    sync_id = str(backing_page_sync_id(session, song_sync_id=str(ctx.active_song_id or "")) or "")
                except Exception:
                    sync_id = ""
                if not sync_id:
                    sync_id = str(
                        session.get("_active_bpm_sync_id")
                        or session.get("_backing_trace_sync_id")
                        or getattr(ctx, "source_signature", "")
                        or ""
                    ).strip()
                seed_backing_bpm_slider_before_widget(session, sync_id=sync_id, bpm=source_bpm)
        elif has_bpm_override and apply_backing_play_session_to_widgets is not None:
            # Same play identity (or signature churn): keep Current override BPM.
            apply_backing_play_session_to_widgets(session)
        # Same play-session / active override: never reseed Current BPM from source.
    except ImportError:
        pass
    try:
        from musical_context_coherence import clear_coherence_handoff_block

        clear_coherence_handoff_block(session)
    except ImportError:
        session.pop("_musical_context_coherence_handoff_block", None)
    try:
        from creative_return_trace import trace_backing_launch

        trace_backing_launch(
            session,
            launch_tab=_launch_tab,
            launch_entry=_launch_entry,
            sealed_route=creative_return_route,
            backing_source=str(ctx.source or source),
        )
    except ImportError:
        pass
    if source == "mission":
        try:
            from mission_practice_context import (
                MISSION_BACKING_SOUNDING_CHORD_KEY,
                MISSION_EXACT_BACKING_ARMED_KEY,
                ensure_mission_practice_context,
                seal_recording_context,
            )

            if ctx.progression:
                session[MISSION_BACKING_SOUNDING_CHORD_KEY] = str(ctx.progression[0] or "").strip()
            session[MISSION_EXACT_BACKING_ARMED_KEY] = True
            ensure_mission_practice_context(session, force=True)
            seal_recording_context(session, association="mission_backing_jam")
        except ImportError:
            pass
    if existing and existing.source_signature == ctx.source_signature and existing.source == ctx.source:
        apply_backing_context_to_session(
            session,
            ctx,
            st_like=st_like,
            apply_transport_bpm=False,
        )
    else:
        # Signature churn with an active play-session BPM override must not
        # reseal Current BPM from source (Style/Jam refresh / same jam reopen).
        skip_transport = False
        try:
            from backing_play_session import backing_play_session_has_override

            skip_transport = bool(
                backing_play_session_has_override(session, "bpm")
                and not (
                    not existing
                    or str(existing.source or "") != str(ctx.source or "")
                    or str(getattr(existing, "mission_id", "") or "") != str(getattr(ctx, "mission_id", "") or "")
                    or str(getattr(existing, "entry_mode", "") or "") != str(getattr(ctx, "entry_mode", "") or "")
                    or (
                        int(getattr(existing, "bpm", 0) or 0) > 0
                        and int(getattr(ctx, "bpm", 0) or 0) > 0
                        and int(existing.bpm) != int(ctx.bpm)
                    )
                    or list(getattr(existing, "progression", None) or []) != list(getattr(ctx, "progression", None) or [])
                )
            )
        except ImportError:
            skip_transport = False
        apply_backing_context_to_session(
            session,
            ctx,
            st_like=st_like,
            apply_transport_bpm=not skip_transport,
        )
        if skip_transport:
            try:
                from backing_play_session import apply_backing_play_session_to_widgets

                apply_backing_play_session_to_widgets(session)
            except ImportError:
                pass
    set_backing_source_preference(session, BACKING_PREF_CREATIVE)
    sync_live_keys_from_backing_context(session, st_like=st_like)
    try:
        from backing_workflow_context import sync_backing_workflow_envelope

        sync_backing_workflow_envelope(session, ctx)
    except ImportError:
        pass
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "backing")
        save_page_snapshot(session, "creative")
    except ImportError:
        pass
    # Restore user-owned instrument/level/focus if any hydrate path overwrote them.
    if _preserved_instrument:
        live = str(session.get("instrument") or "").strip()
        if live != _preserved_instrument:
            try:
                from practice_setup_globals import set_active_instrument

                set_active_instrument(
                    session,
                    _preserved_instrument,
                    source="open_backing_preserve_instrument",
                )
            except ImportError:
                session["instrument"] = _preserved_instrument
    if _preserved_level and not str(session.get("level") or "").strip():
        session["level"] = _preserved_level
    if _preserved_focus and not str(session.get("focus") or "").strip():
        session["focus"] = _preserved_focus
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


def creative_nested_backing_should_override_catalog(
    session: dict[str, Any],
) -> bool:
    """True when reboot/hydrate must rebuild Creative SBI/Mission/Jam over a stale catalog ctx.

    Contract: refresh/reboot keeps the same nested Backing visit. A persisted
    ``regular_song`` blob must not win when Creative still owns Song-Based /
    Mission / Entry Jam and the user is on the Backing page.
    """
    if session.get("_backing_released_specialized_context"):
        return False
    if int(session.get("_force_catalog_backing_after_use_catalog") or 0) > 0:
        return False
    page = str(session.get("studio_page") or "").strip()
    if page != "backing":
        return False
    handoff = str(session.get("_backing_explicit_handoff_source") or "").strip()
    if handoff in {"song_improv", "mission", "entry_jam"}:
        return True
    try:
        from creative_workspace_state_persistence import CREATIVE_WORKSPACE_STATE_KEY

        cw = session.get(CREATIVE_WORKSPACE_STATE_KEY)
        cw = cw if isinstance(cw, dict) else {}
    except ImportError:
        cw = {}
    entry = str(
        session.get("improv_entry_mode") or cw.get("improv_entry_mode") or ""
    ).strip()
    tab = str(
        session.get("improv_intelligence_tab")
        or cw.get("improv_intelligence_tab")
        or ""
    ).strip()
    if "Song-Based" in entry or tab in {"Entry & Jam", "Entry and Jam"}:
        return True
    if tab == "Missions" or "mission" in entry.lower():
        return True
    if tab in {"Entry & Jam", "Entry and Jam"} and (
        "Jam" in entry or "Style" in entry
    ):
        return True
    try:
        from creative_session_state import creative_session_is_active, get_creative_session

        if creative_session_is_active(session):
            sess = get_creative_session(session)
            tool = str(getattr(sess, "tool_type", "") or "") if sess is not None else ""
            if tool in {
                "song_based_improvisation",
                "mission",
                "entry_jam",
                "jam_generator",
                "style_jam",
            }:
                return True
    except ImportError:
        pass
    return False


def catalog_or_custom_backing_is_authoritative(session: dict[str, Any]) -> bool:
    """True when catalog or custom practice owns key/progression (Creative must not reclaim)."""
    if creative_nested_backing_should_override_catalog(session):
        return False
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
    src = str(getattr(ctx, "source", "") or "") if ctx is not None else ""
    specialized = {"mission", "song_improv", "entry_jam"}
    # Explicit Creative → Backing handoff outranks Global Active source type.
    # Custom GA must not reclaim Mission/SBI/Jam that was just opened from Creative.
    handoff = str(session.get("_backing_explicit_handoff_source") or "").strip()
    if (
        handoff in specialized
        and src == handoff
        and not session.get("_backing_released_specialized_context")
    ):
        return False
    # Use raw practice owner — intentional Creative/Mission must not hide an
    # explicit Songs Catalog/Custom switch (H9: Custom Active + sealed Mission).
    try:
        from music_source_ownership import _raw_practice_owner

        raw = _raw_practice_owner(session)
        if raw == "custom":
            # Custom SBI uses CPL under song_improv — not a stale Mission overlay.
            if (
                src == "song_improv"
                and not session.get("_backing_released_specialized_context")
                and (
                    bool(getattr(ctx, "custom_revision_id", None))
                    or str(getattr(ctx, "bound_pick_key", "") or "").lower().startswith("custom")
                )
            ):
                return False
            # Explicit Mission/Jam under Custom GA already returned False above.
            # Leftover sealed Mission without handoff remains stale (H9).
            return ctx is None or src != "custom_progression"
        if raw == "catalog":
            # Catalog Global Active still allows intentional Mission/SBI/Jam overlay
            # unless specialized ownership was explicitly released.
            if session.get("_backing_released_specialized_context"):
                return ctx is None or src != "regular_song"
            if src in specialized:
                return False
            # No specialized overlay — catalog practice should own Backing.
            return ctx is None
        # raw is None / unknown — do not call intended_practice_owner here.
        # That helper calls intentional_creative_backing_active → this function (re-entry).
    except ImportError:
        pass
    try:
        from songs.music_source import (
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        # CPL active during Custom SBI is expected — do not treat as stale reclaim.
        if src == "song_improv" and (
            bool(getattr(ctx, "custom_revision_id", None))
            or str(getattr(ctx, "bound_pick_key", "") or "").lower().startswith("custom")
        ):
            return False
        if (
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        ):
            return True
    except ImportError:
        pass
    if get_backing_source_preference(session) in {BACKING_PREF_CATALOG, BACKING_PREF_CUSTOM}:
        if src in specialized and not session.get("_backing_released_specialized_context"):
            return False
        return True
    return False


def open_live_practice_backing(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext | None:
    """Rebuild backing_context from the live catalog/custom practice source."""
    try:
        from mission_pk_reclaim_trace import note_mission_pk_reclaim

        note_mission_pk_reclaim(session, writer="open_live_practice_backing")
    except ImportError:
        pass
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


def _apply_practice_display_key(
    session: dict[str, Any],
    practice_key: str,
    *,
    st_like: Any | None = None,
) -> None:
    """Apply saved practice concert key without resetting to catalog/custom original."""
    key = str(practice_key or "C").strip() or "C"
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
    """Clear Creative/custom override and restore active catalog song backing.

    Ordinary Backing reruns that are already on this catalog pick must NOT expire
    the play session — that reminted Current BPM from source default (110→96).
    """
    from types import SimpleNamespace

    from songs.key_state import invalidate_backing_cache
    from songs.music_source import activate_catalog_song_for_backing, resolve_catalog_pick_for_backing_restore

    existing_ctx = get_backing_context(session)
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    ctx_pick = ""
    if existing_ctx is not None:
        ctx_pick = str(
            getattr(existing_ctx, "bound_pick_key", "")
            or getattr(existing_ctx, "active_song_id", "")
            or ""
        ).strip()
    already_same_catalog = (
        existing_ctx is not None
        and str(getattr(existing_ctx, "source", "") or "") == "regular_song"
        and bool(pick)
        and ctx_pick == pick
    )
    keep_play_session = False
    if already_same_catalog:
        try:
            from backing_play_session import (
                BACKING_PLAY_SESSION_EXPIRED_KEY,
                get_backing_play_session,
            )

            ps = get_backing_play_session(session)
            expired = bool(session.get(BACKING_PLAY_SESSION_EXPIRED_KEY)) or bool((ps or {}).get("expired"))
            keep_play_session = bool(ps) and not expired
        except ImportError:
            keep_play_session = False

    if not keep_play_session:
        try:
            from backing_play_session import expire_backing_play_session

            expire_backing_play_session(session)
        except ImportError:
            pass
    try:
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
    except Exception:
        pass

    reason = "creative_to_catalog"
    try:
        from backing_source_navigation import BACKING_INTENT_SWITCH_CATALOG, peek_key_transition_intent

        intent = peek_key_transition_intent(session)
        if intent == BACKING_INTENT_SWITCH_CATALOG:
            reason = "switch_to_catalog_backing"
    except ImportError:
        pass
    try:
        from songs.music_source import cpl_session_is_active, is_custom_progression

        if is_custom_progression(session) or cpl_session_is_active(session):
            reason = "switch_to_catalog_backing"
    except ImportError:
        pass
    try:
        from backing_source_navigation import BACKING_INTENT_CREATIVE_TO_CATALOG, set_key_transition_intent

        if reason == "switch_to_catalog_backing":
            set_key_transition_intent(session, BACKING_INTENT_SWITCH_CATALOG)
        else:
            set_key_transition_intent(session, BACKING_INTENT_CREATIVE_TO_CATALOG)
    except ImportError:
        pass
    clear_backing_context(session)
    try:
        from generated_jam_key_context import deactivate_generated_jam_key_ownership

        deactivate_generated_jam_key_ownership(session, pre_widget=True)
    except ImportError:
        pass
    try:
        from music_workflow_song_practice import (
            reconcile_practice_key_after_active_source_change,
            resolve_song_practice_key_token,
        )
        from songs.practice_key_state import get_practice_concert_key

        pick = str(session.get("active_catalog_pick_key") or "").strip()
        saved = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
        live_dk = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if not saved and live_dk:
            try:
                from songs.practice_key_state import set_practice_concert_key

                set_practice_concert_key(session, live_dk, pick_key=pick)
                saved = live_dk
            except Exception:
                saved = live_dk
        if reason == "switch_to_catalog_backing" and pick:
            # Same Global Active catalog pick with sticky PK: keep it.
            # Only force Original Key when this pick has no sticky override yet.
            if saved:
                song_tok = saved
                try:
                    from session_widget_safe import safe_assign_display_key

                    safe_assign_display_key(session, song_tok, widget_safe=True, st_like=st_like)
                except ImportError:
                    session["_pending_display_key"] = song_tok
                    session["concert_key"] = song_tok
            else:
                sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
                prev_pick = ""
                try:
                    from songs.music_source import _LAST_ACTIVE_PICK_KEY

                    prev_pick = str(session.get(_LAST_ACTIVE_PICK_KEY) or "").strip()
                except ImportError:
                    prev_pick = ""
                song_tok = reconcile_practice_key_after_active_source_change(
                    session,
                    pick_key=pick,
                    original_key=str((sel or {}).get("key") or ""),
                    previous_pick_key=prev_pick,
                    source="restore_regular_song_backing",
                )
        else:
            song_tok = saved or live_dk or str(resolve_song_practice_key_token(session) or "").strip()
            try:
                from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, shape_chart_key_for_concert, shape_tonic_only

                if session.get(CAPO_ENABLED_KEY):
                    shape = shape_tonic_only(str(session.get(CAPO_SHAPE_KEY) or ""))
                    # Capo Shape must never become Practice Key.
                    if saved and shape:
                        chart = shape_chart_key_for_concert(saved, shape)
                        if song_tok == chart and song_tok != saved:
                            song_tok = saved
                    # Capo is player context: keep the live song Practice Key when it
                    # still matches the active catalog song original. Stale sealed
                    # Roads PK (A) must not win while Love Story (C) is active.
                    sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
                    sel_key = str((sel or {}).get("key") or "").strip()
                    if live_dk and sel_key:
                        try:
                            from music_theory import split_key_center

                            live_t, _ = split_key_center(live_dk)
                            sel_t, _ = split_key_center(sel_key)
                            if live_t and sel_t and live_t == sel_t:
                                song_tok = live_dk
                        except ImportError:
                            if live_dk == sel_key:
                                song_tok = live_dk
            except ImportError:
                pass
            if song_tok:
                try:
                    from session_widget_safe import safe_assign_display_key

                    safe_assign_display_key(session, song_tok, widget_safe=True, st_like=st_like)
                except ImportError:
                    session["_pending_display_key"] = song_tok
                    session["concert_key"] = song_tok
                try:
                    from music_workflow_song_practice import ensure_song_practice_blob_for_active_song

                    orig = ""
                    selected = session.get("selected_song")
                    if isinstance(selected, dict):
                        orig = str(selected.get("key") or "")
                    ensure_song_practice_blob_for_active_song(
                        session, practice_key=song_tok, original_key=orig
                    )
                except ImportError:
                    pass
    except ImportError:
        pass
    try:
        from music_workflow_activation import activate_workflow_simple

        activate_workflow_simple(
            session,
            "song_based_improvisation",
            activation_source="restore_regular_song_backing",
            return_route="backing",
        )
    except ImportError:
        pass
    try:
        from music_source_ownership import _release_creative_transport_authority

        _release_creative_transport_authority(session)
    except ImportError:
        _release_creative_backing_ownership(session)
        try:
            from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE

            session.pop(CREATIVE_CONCERT_KEY_SOURCE, None)
        except ImportError:
            session.pop("_creative_concert_key_source", None)
    st = st_like or SimpleNamespace(session_state=session)
    pick_key = resolve_catalog_pick_for_backing_restore(session, reason=reason)
    ctx = activate_catalog_song_for_backing(
        st,
        pick_key,
        reason=reason,
        invalidate_backing=invalidate_backing_cache,
    )
    if ctx is not None:
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
    set_backing_source_preference(session, BACKING_PREF_CATALOG)
    ctx = build_regular_song_context(session)
    set_backing_context(session, ctx, trace_caller="backing_context:restore_regular_song_backing")
    apply_backing_context_to_session(session, ctx, st_like=st, widget_safe=True)
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "backing")
    except ImportError:
        pass
    return ctx


def restore_custom_song_backing(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext:
    """Clear Creative/catalog override and restore active custom progression backing."""
    try:
        from mission_pk_reclaim_trace import note_mission_pk_reclaim

        note_mission_pk_reclaim(session, writer="restore_custom_song_backing")
    except ImportError:
        pass
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
    try:
        from songs.practice_key_state import resolve_practice_concert_key_for_pick, resolve_practice_source_pick

        pick = resolve_practice_source_pick(session)
        concert = resolve_practice_concert_key_for_pick(
            session,
            pick,
            original_key=str(original or ctx.concert_key or ctx.key or ""),
        )
    except ImportError:
        concert = str(original or ctx.concert_key or ctx.display_key or ctx.key or "").strip()
    if concert:
        _apply_practice_display_key(session, concert, st_like=st_like)
    set_backing_source_preference(session, BACKING_PREF_CUSTOM)
    set_backing_context(session, ctx, trace_caller="backing_context:restore_custom_song_backing")
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
    sig = str(ctx.source_signature or "").strip()
    seeded = str(session.get(BACKING_CTX_TRANSPORT_APPLIED_SIG) or "").strip() == sig
    try:
        from backing_play_session import play_session_blocks_canonical_seed

        if play_session_blocks_canonical_seed(session):
            return
    except ImportError:
        pass
    if seeded:
        return
    request_backing_bpm(st_like, int(ctx.bpm))
    request_backing_groove(st_like, backing_style)
    if ctx.meter:
        session["_pending_backing_meter"] = str(ctx.meter)
    session[BACKING_CTX_TRANSPORT_APPLIED_SIG] = sig


def ensure_backing_context_from_creative_session(session: dict[str, Any]) -> BackingContext | None:
    """Create or refresh backing_context from the canonical Creative session when missing."""
    if catalog_or_custom_backing_is_authoritative(session):
        return get_backing_context(session)
    existing = get_backing_context(session)
    if existing is not None and existing.source in {"regular_song", "custom_progression"}:
        # Stale catalog/custom blob after reboot must yield to nested Creative SBI/Mission.
        if not creative_nested_backing_should_override_catalog(session):
            return existing
        clear_backing_context(session)
        existing = None
    if existing is not None and existing.source != "regular_song" and is_backing_context_valid(session, existing):
        # Last valid Mission/Jam session owns key/progression. Do not rebuild from
        # leftover live display_key (e.g. catalog C) on refresh or Upload return.
        return existing
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
        set_backing_context(session, ctx, trace_caller="ensure_backing_context_from_creative_session:build")
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
    if ctx is not None and ctx.source == "regular_song":
        if creative_nested_backing_should_override_catalog(session):
            clear_backing_context(session)
            ensure_backing_context_from_creative_session(session)
            ctx = get_backing_context(session)
        else:
            return
    if ctx is None:
        return
    if not is_backing_context_valid(session, ctx):
        # Do not leave nested Creative Backing empty after a false-invalid clear —
        # rebuild specialized ownership when Creative still owns the visit.
        if creative_nested_backing_should_override_catalog(session):
            clear_backing_context(session)
            ensure_backing_context_from_creative_session(session)
            ctx = get_backing_context(session)
            if ctx is None or not is_backing_context_valid(session, ctx):
                return
        else:
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
    if concert and ctx.source != "entry_jam":
        # Mission / SBI sealed keys must not overwrite a live Practice Key after restore.
        if ctx.source in {"mission", "song_improv"}:
            live = str(session.get("display_key") or session.get("concert_key") or "").strip()
            if live:
                session["concert_key"] = live
            else:
                session["concert_key"] = concert
                try:
                    from session_widget_safe import safe_assign_display_key

                    safe_assign_display_key(session, concert, widget_safe=False)
                except ImportError:
                    session["display_key"] = concert
                    session["_pending_display_key"] = concert
        else:
            session["concert_key"] = concert
            try:
                from session_widget_safe import safe_assign_display_key

                safe_assign_display_key(session, concert, widget_safe=False)
            except ImportError:
                session["display_key"] = concert
                session["_pending_display_key"] = concert
    sync_improv_widgets_from_live_concert_key(session)
    session[PENDING_BACKING_CONTEXT_APPLY] = True
    if ctx.source == "mission":
        try:
            from mission_return_destination import (
                rehydrate_mission_return_destination_from_backing_context,
            )

            rehydrate_mission_return_destination_from_backing_context(session)
        except ImportError:
            pass


def reconcile_backing_context_on_backing_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Re-sync valid Creative/custom context after backing page song-default logic."""
    # After explicit Use catalog, do not let ownership reconcile reclaim Custom.
    if int(session.get("_force_catalog_backing_after_use_catalog") or 0) > 0:
        try:
            from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

            session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        except ImportError:
            pass
        try:
            set_backing_source_preference(session, BACKING_PREF_CATALOG)
            restore_regular_song_backing(session, st_like=st_like)
        except Exception:
            pass
        return
    try:
        from creative_return_trace import emit_creative_return_trace

        emit_creative_return_trace(session, "RECONCILE_BACKING_PAGE_START")
    except ImportError:
        pass
    try:
        from music_source_ownership import intentional_creative_backing_active, reconcile_source_ownership

        if not intentional_creative_backing_active(session):
            try:
                from mission_pk_reclaim_trace import note_mission_pk_reclaim

                note_mission_pk_reclaim(
                    session,
                    writer="reconcile_backing_page:not_intentional",
                )
            except ImportError:
                pass
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
            try:
                from mission_pk_reclaim_trace import note_mission_pk_reclaim

                note_mission_pk_reclaim(
                    session,
                    writer="reconcile_backing_page:stale_creative",
                    extra={"stale_src": str(getattr(ctx, "source", "") or "")},
                )
            except ImportError:
                pass
            open_live_practice_backing(session, st_like=st_like)
            ctx = get_backing_context(session)
            pref = get_backing_source_preference(session)
    except ImportError:
        pass

    if ctx is not None and ctx.source == "regular_song":
        try:
            from music_source_ownership import catalog_identity_aligns, rebuild_catalog_backing_from_canonical_pick
            from songs.practice_key_state import get_practice_concert_key

            pick = str(session.get("active_catalog_pick_key") or "").strip()
            sticky = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
            live_dk = str(session.get("display_key") or session.get("concert_key") or "").strip()
            want = sticky or live_dk
            ctx_key = str(getattr(ctx, "concert_key", "") or getattr(ctx, "display_key", "") or "").strip()
            need_pk_heal = bool(want and ctx_key and want != ctx_key)
            if (not catalog_identity_aligns(session)) or need_pk_heal:
                # Identity / sticky-PK heal — never reset BPM mid-session
                # (BPM/style/meter are temporary play overrides; PK is song-owned sticky).
                rebuild_catalog_backing_from_canonical_pick(
                    session,
                    st_like=st_like,
                    reset_to_original=False,
                    force_bpm_reset=False,
                )
                ctx = get_backing_context(session)
        except ImportError:
            pass
        _sync_sidebar_to_ctx(ctx)
        flush_pending_backing_handoff_keys(
            session,
            sync_id=str(session.get("_backing_trace_sync_id") or ""),
        )
        return
    if ctx is not None and ctx.source == "custom_progression":
        set_backing_source_preference(session, BACKING_PREF_CUSTOM)
        refreshed = refresh_backing_context_from_session(session)
        if refreshed is not None:
            set_backing_context(session, refreshed, trace_caller="reconcile_backing_page:custom_progression_refresh")
        flush_pending_backing_handoff_keys(
            session,
            sync_id=str(session.get("_backing_trace_sync_id") or ""),
        )
        return
    if pref in {BACKING_PREF_CATALOG, BACKING_PREF_CUSTOM}:
        if ctx is not None and ctx.source == "regular_song":
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
            set_backing_context(session, refreshed, trace_caller="reconcile_backing_page:creative_refresh")
            ctx = refreshed
        if pending_apply:
            seeded = (
                str(session.get(BACKING_CTX_TRANSPORT_APPLIED_SIG) or "").strip()
                == str(ctx.source_signature or "").strip()
            )
            apply_backing_context_to_session(
                session,
                ctx,
                st_like=st_like,
                widget_safe=True,
                apply_transport_bpm=not seeded,
            )
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
    "creative_backing_card_context",
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
    "sync_live_keys_from_backing_context",
    "creative_specialized_backing_handoff_ready",
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
