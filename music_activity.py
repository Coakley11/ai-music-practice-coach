"""
Command Center activity hooks — factual events only (no coaching copy).
"""

from __future__ import annotations

from typing import Any


PRACTICE_ACTIVITY_SCHEMA_VERSION = 2
_ACTIVITY_EXECUTOR = None


def _source_type(st: Any, pick_key: str = "") -> str:
    """Read the activity pick owner without mutating source state."""
    pick = str(pick_key or st.session_state.get("active_catalog_pick_key") or "").strip()
    if pick.startswith(("composition::", "composition\x1f")):
        return "composition"
    if pick.startswith(("custom::", "custom\x1f")):
        return "custom"
    try:
        from source_session_state import global_music_source_owner

        source = str(global_music_source_owner(st.session_state) or "").strip()
        if source in {"catalog", "custom", "composition"}:
            return source
    except Exception:
        pass
    pick = str(pick_key or st.session_state.get("active_catalog_pick_key") or "").strip()
    if pick.startswith("composition::"):
        return "composition"
    if pick.startswith("custom::"):
        return "custom"
    return "catalog" if pick else ""


def _key_cycling_context(st: Any) -> dict[str, Any]:
    """Return factual Key Cycling state; never project it onto Practice Key."""
    context: dict[str, Any] = {"key_cycling_active": False}
    if str(st.session_state.get("studio_page") or "") != "backing":
        return context
    try:
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_SESSIONS_KEY,
            STATUS_HELD,
            STATUS_RUNNING,
            resolve_cycle_owner,
        )

        owner = str(resolve_cycle_owner(st.session_state) or "").strip()
        sessions = st.session_state.get(BACKING_KEY_CYCLE_SESSIONS_KEY)
        raw = sessions.get(owner) if isinstance(sessions, dict) else None
        cycle = dict(raw) if isinstance(raw, dict) else {}
        active = bool(cycle.get("enabled")) and str(cycle.get("status") or "") in {
            STATUS_RUNNING,
            STATUS_HELD,
        }
        context["key_cycling_active"] = active
        if not active:
            return context
        start_key = str(cycle.get("start_cycle_key") or "").strip()
        sounding_key = str(cycle.get("current_playback_key") or "").strip()
        if start_key:
            context["key_cycling_start_key"] = start_key
        if sounding_key:
            context["key_cycling_sounding_key"] = sounding_key
    except Exception:
        pass
    return context


def _song_context(st: Any) -> dict[str, str]:
    try:
        from songs.state import build_music_local_state

        state = build_music_local_state(st)
    except Exception:
        state = {}
    title = str(
        state.get("song")
        or st.session_state.get("song")
        or ""
    ).strip()
    artist = str(state.get("artist") or "").strip()
    pick_key = str(
        state.get("pick_key")
        or st.session_state.get("active_catalog_pick_key")
        or ""
    ).strip()
    instrument = str(state.get("instrument") or st.session_state.get("instrument") or "").strip()
    display_key = str(state.get("display_key") or st.session_state.get("display_key") or "").strip()
    # A page snapshot may still contain another source's display key.
    # Reporting reads the pick-owned key; it never changes musical state.
    try:
        from songs.practice_key_state import get_practice_concert_key

        display_key = get_practice_concert_key(st.session_state, pick_key) or display_key
    except ImportError:
        pass
    source_type = _source_type(st, pick_key)
    return {
        "song": title,
        "artist": artist,
        "pick_key": pick_key,
        "source_id": pick_key,
        "source_type": source_type,
        "instrument": instrument,
        "display_key": display_key,
        "practice_key": display_key,
    }


def _practice_session_summary(metrics: dict[str, Any]) -> str:
    song = str(metrics.get("song") or "song").strip() or "song"
    instrument = str(metrics.get("instrument") or "").strip()
    practice_key = str(metrics.get("practice_key") or "").strip()
    summary = f"Practiced {song}"
    if instrument:
        summary += f" on {instrument}"
    if metrics.get("key_cycling_active"):
        summary += " with Key Cycling"
        start_key = str(metrics.get("key_cycling_start_key") or practice_key).strip()
        if start_key:
            summary += f", starting in {start_key}"
    elif practice_key:
        summary += f" in {practice_key}"
    return summary


def _workflow_resume_key(st: Any, ctx: dict[str, str]) -> str:
    page = str(st.session_state.get("studio_page") or "practice").strip()
    pick = str(ctx.get("pick_key") or "").strip()
    if page == "backing":
        return f"backing:{pick}" if pick else "backing:"
    return f"song:{pick}" if pick else ""


def _workflow_page_label(st: Any) -> str:
    page = str(st.session_state.get("studio_page") or "practice").strip()
    return {
        "practice": "practice",
        "backing": "backing",
        "picker": "picker",
        "analysis": "recording",
        "log": "Practice Log",
    }.get(page, page or "practice")


def _record(
    event: str,
    *,
    st: Any,
    page: str = "",
    metrics: dict[str, Any] | None = None,
    summary: str = "",
    resume_key: str = "",
    resume_title: str = "",
    resume_subtitle: str = "",
    resume_kind: str = "",
    sync_continue_card: bool = False,
    background: bool = False,
) -> None:
    try:
        from music_resume_payload import (
            build_music_resume_payload,
            continue_card_subtitle,
            continue_card_title,
            legacy_resume_key_for_payload,
        )

        payload = build_music_resume_payload(
            st.session_state,
            kind=resume_kind or None,
            st=st,
        )
        if metrics and metrics.get("practice_context_id"):
            payload.update({k: metrics.get(k) for k in ("source_type", "source_id", "practice_context_id")})
            payload["display_key"] = metrics.get("practice_key") or ""
            payload["pick_key"] = metrics.get("source_id") or ""
        card_title = resume_title or continue_card_title(payload)
        card_subtitle = resume_subtitle or continue_card_subtitle(payload)
        card_key = resume_key or legacy_resume_key_for_payload(payload)
    except Exception:
        payload = {}
        card_title = resume_title
        card_subtitle = resume_subtitle
        card_key = resume_key

    try:
        ctx = _song_context(st)
        merged = {**ctx, **(metrics or {})}
        merged.setdefault("studio_page", str(st.session_state.get("studio_page") or ""))
        merged.setdefault(
            "practice_focus_section",
            str(st.session_state.get("practice_focus_section") or ""),
        )
        if payload:
            merged.setdefault("resume_kind", payload.get("resume_kind"))
            merged["resume_payload"] = payload
            merged.setdefault("workspace_id", payload.get("workspace_id"))
        page_resolved = page or _workflow_page_label(st)
        if not card_key:
            card_key = _workflow_resume_key(st, ctx)
        if not card_title and ctx.get("song"):
            card_title = f"Continue: {ctx['song']}"
        if not card_subtitle:
            parts = [
                str(ctx.get("display_key") or "").strip(),
                str(ctx.get("instrument") or "").strip(),
                page_resolved,
            ]
            card_subtitle = " · ".join(p for p in parts if p) or str(ctx.get("artist") or "")
        local_state = None
        try:
            from songs.state import build_music_local_state

            local_state = build_music_local_state(st)
        except Exception:
            pass
        record_kwargs = dict(
            page=page or str(st.session_state.get("studio_page") or ""),
            metrics=merged, summary=summary, resume_key=card_key,
            resume_title=card_title, resume_subtitle=card_subtitle,
            local_state=None if merged.get("practice_context_id") else local_state,
        )
        if background:
            submit_activity_snapshot(event, record_kwargs, payload if sync_continue_card else {})
        else:
            _persist_activity(event, record_kwargs, payload if sync_continue_card else {})
    except Exception:
        pass


def submit_activity_snapshot(event: str, kwargs: dict[str, Any], payload: dict[str, Any] | None = None) -> None:
    """Queue a copied event; background reporting never receives live Music state."""
    from concurrent.futures import ThreadPoolExecutor
    from copy import deepcopy
    global _ACTIVITY_EXECUTOR
    if _ACTIVITY_EXECUTOR is None:
        _ACTIVITY_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="music-activity")
    _ACTIVITY_EXECUTOR.submit(_persist_activity, event, deepcopy(kwargs), deepcopy(payload or {}))


def _persist_activity(event: str, kwargs: dict[str, Any], payload: dict[str, Any]) -> None:
    try:
        from suite_activity_client import record_activity
        record_activity("music", event, **kwargs)
    except Exception:
        pass
    if payload:
        try:
            from music_command_center import upsert_music_continue_card
            upsert_music_continue_card(payload)
        except Exception:
            pass


def log_display_key_changed(
    st: Any,
    *,
    display_key: str,
    previous_key: str = "",
) -> None:
    ctx = _song_context(st)
    song = ctx.get("song") or "song"
    prev = previous_key or str(st.session_state.get("_activity_last_logged_display_key") or "")
    if prev == display_key:
        return
    st.session_state["_activity_last_logged_display_key"] = display_key
    summary = f"Changed {song} to {display_key}"
    if prev:
        summary = f"Changed {song} from {prev} to {display_key}"
    _record(
        "display_key_changed",
        st=st,
        metrics={
            "display_key": display_key,
            "previous_key": prev,
            "original_key": str(st.session_state.get("original_key") or ""),
        },
        summary=summary,
    )


def log_instrument_changed(
    st: Any,
    *,
    instrument: str,
    previous: str = "",
) -> None:
    inst = str(instrument or "").strip()
    if not inst:
        return
    prev = str(previous or st.session_state.get("_activity_last_logged_instrument") or "").strip()
    if prev == inst:
        return
    st.session_state["_activity_last_logged_instrument"] = inst
    ctx = _song_context(st)
    song = ctx.get("song") or "song"
    _record(
        "instrument_changed",
        st=st,
        metrics={"instrument": inst, "previous_instrument": prev},
        summary=f"Switched {song} to {inst}",
    )


def log_practice_session_started(
    st: Any,
    *,
    backing_active: bool = False,
    practice_mode: str = "",
    background: bool = False,
) -> bool:
    """Emit one meaningful session-start event for the current musical owner.

    The signature is session-local rerun protection. It deliberately uses the
    canonical Practice Key separately from any temporary Key Cycling pitch.
    """
    ctx = _song_context(st)
    if not ctx.get("song"):
        return False
    mode = str(
        practice_mode
        or st.session_state.get("last_practice_mode")
        or st.session_state.get("focus")
        or ""
    ).strip()
    metrics: dict[str, Any] = {
        "activity_schema_version": PRACTICE_ACTIVITY_SCHEMA_VERSION,
        "activity_type": "practice_session_started",
        "source_type": ctx.get("source_type", ""),
        "source_id": ctx.get("source_id", ""),
        "practice_key": ctx.get("practice_key", ""),
        "practice_mode": mode,
        "backing_active": bool(backing_active),
        **_key_cycling_context(st),
    }
    # A practice context spans transport churn. Only semantic upgrades emit.
    signature = tuple(ctx.get(k, "") for k in (
        "source_type", "source_id", "song", "instrument", "practice_key"
    ))
    signature += (str(st.session_state.get("_suite_active_workspace_id") or ""),)
    flag = "_activity_practice_context"
    prior = st.session_state.get(flag)
    prior = prior if isinstance(prior, dict) and prior.get("signature") == signature else {}
    import uuid
    metrics["practice_context_id"] = prior.get("id") or uuid.uuid4().hex
    # A stopped cycle / later rerun cannot erase work already observed.
    old = prior.get("metrics") or {}
    for name in ("backing_active", "key_cycling_active"):
        metrics[name] = bool(metrics.get(name) or old.get(name))
    if old.get("key_cycling_start_key"):
        metrics["key_cycling_start_key"] = old["key_cycling_start_key"]
    meaningful = (metrics["backing_active"], metrics["key_cycling_active"])
    if prior and prior.get("meaningful") == meaningful:
        return False
    metrics["practice_context_revision"] = int(prior.get("revision") or 0) + 1
    st.session_state[flag] = {
        "revision": metrics["practice_context_revision"],
        "id": metrics["practice_context_id"], "signature": signature,
        "meaningful": meaningful, "metrics": dict(metrics),
    }
    _record(
        "practice_session_started",
        st=st,
        page="Backing Track Studio" if backing_active else "Practice",
        metrics=metrics,
        summary=_practice_session_summary({**ctx, **metrics}),
        resume_kind="backing" if backing_active else "practice",
        sync_continue_card=True,
        background=background,
    )
    return True


def log_studio_page_entered(st: Any, page_id: str) -> None:
    """Log meaningful studio page work — practice, backing, recording, etc."""
    page = str(page_id or "").strip()
    if page not in {"practice", "backing", "picker", "analysis", "log"}:
        return
    if page == "practice":
        log_practice_session_started(st)
        return
    flag = f"_activity_logged_page::{page}"
    ctx = _song_context(st)
    song = ctx.get("song") or ""
    if not song:
        return
    sig = (
        page,
        str(ctx.get("pick_key") or ""),
        str(ctx.get("display_key") or ""),
        str(ctx.get("instrument") or ""),
    )
    if st.session_state.get(flag) == sig:
        return
    st.session_state[flag] = sig
    label = {
        "practice": "Practice",
        "backing": "Backing Track Studio",
        "analysis": "Recording Analysis",
        "log": "Practice Log",
        "picker": "Song Selection",
    }.get(page, page)
    _record(
        "studio_page_entered",
        st=st,
        page=label,
        metrics={"studio_page": page},
        summary=f"Working on {song} — {label}",
        sync_continue_card=True,
    )


def log_media_upload(
    st: Any,
    *,
    media_type: str,
    filename: str = "",
    page: str = "Recording Analysis",
) -> None:
    if page == "Multitrack":
        # P2 workflows retain their existing activity path in this slice.
        ctx = _song_context(st)
        title = ctx.get("song") or "recording"
        _record("audio_uploaded", st=st, page=page,
                metrics={"media_type": media_type, "filename": filename, "upload_kind": "audio recording"},
                summary=f"Uploaded audio recording for {title}",
                resume_title=f"Continue: {title}", resume_subtitle="Review upload")
        return
    try:
        from recording_activity import capture_upload, report_recording_fact
        context = capture_upload(st.session_state, filename=filename)
        report_recording_fact(st, "video_uploaded" if media_type == "video" else "audio_uploaded",
                              context, page=page, media_type=media_type)
    except Exception:
        pass


def log_recording_reviewed(st: Any, *, page: str = "Recording Analysis") -> None:
    try:
        from recording_activity import report_recording_fact
        # The take snapshot captured at upload owns review identity.
        context = st.session_state.get("_activity_recording_context") or {}
        if context:
            report_recording_fact(st, "recording_reviewed", context, page=page)
    except Exception:
        pass


def log_backing_track_started(st: Any, *, bpm: int, loops: int, scope: str = "") -> None:
    ctx = _song_context(st)
    song = ctx.get("song") or "song"
    _record(
        "backing_track_started",
        st=st,
        page="Backing Track Studio",
        metrics={"bpm": bpm, "loops": loops, "scope": scope},
        summary=f"Started backing track for {song}",
        resume_kind="backing",
        sync_continue_card=True,
    )


def log_backing_track_completed(st: Any, *, bpm: int, loops: int, scope: str = "") -> None:
    ctx = _song_context(st)
    song = ctx.get("song") or "song"
    _record(
        "backing_track_completed",
        st=st,
        page="Backing Track Studio",
        metrics={"bpm": bpm, "loops": loops, "scope": scope},
        summary=f"Completed backing track session for {song}",
        resume_kind="backing",
        sync_continue_card=True,
    )


def observe_backing_practice(st: Any) -> bool:
    """Called for a playable audio mount with explicit transport permission.

    Never called for generated/prepared WAVs. Failure cannot escape to audio.
    Counts/duration are deliberately omitted: a mount is not a completed pass.
    """
    try:
        from backing_transport_intent import playback_allowed
        if not playback_allowed(st.session_state):
            return False
        from backing_key_cycle import resolve_cycle_owner, current_backing_owner_practice_key
        owner = resolve_cycle_owner(st.session_state)
        if owner not in {"catalog", "custom", "composition"}:
            return False  # Creative-local owners need their own audited schema.
        ctx = _song_context(st)
        if ctx.get("source_type") != owner or not ctx.get("source_id"):
            return False
        pick = str(ctx["source_id"])
        pick_owner = "custom" if pick.startswith("custom::") else (
            "composition" if pick.startswith("composition::") else "catalog"
        )
        if pick_owner != owner:
            return False
        # Owner canonical resolver never reads the temporary sounding key.
        canonical = current_backing_owner_practice_key(st.session_state)
        from types import SimpleNamespace
        snapshot = dict(st.session_state)
        snapshot["display_key"] = canonical
        proxy = SimpleNamespace(session_state=snapshot)
        emitted = log_practice_session_started(proxy, backing_active=True, background=True)
        if "_activity_practice_context" in snapshot:
            st.session_state["_activity_practice_context"] = snapshot["_activity_practice_context"]
        return emitted
    except Exception:
        return False
