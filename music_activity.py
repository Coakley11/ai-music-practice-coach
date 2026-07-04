"""
Command Center activity hooks — factual events only (no coaching copy).
"""

from __future__ import annotations

from typing import Any


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
    return {
        "song": title,
        "artist": artist,
        "pick_key": pick_key,
        "instrument": instrument,
        "display_key": display_key,
    }


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
        card_title = resume_title or continue_card_title(payload)
        card_subtitle = resume_subtitle or continue_card_subtitle(payload)
        card_key = resume_key or legacy_resume_key_for_payload(payload)
    except Exception:
        payload = {}
        card_title = resume_title
        card_subtitle = resume_subtitle
        card_key = resume_key

    try:
        from suite_activity_client import record_activity

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
        record_activity(
            "music",
            event,
            page=page or str(st.session_state.get("studio_page") or ""),
            metrics=merged,
            summary=summary,
            resume_key=card_key,
            resume_title=card_title,
            resume_subtitle=card_subtitle,
            local_state=local_state,
        )
        if sync_continue_card and payload:
            try:
                from music_command_center import upsert_music_continue_card

                upsert_music_continue_card(payload)
            except Exception:
                pass
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


def log_studio_page_entered(st: Any, page_id: str) -> None:
    """Log meaningful studio page work — practice, backing, recording, etc."""
    page = str(page_id or "").strip()
    if page not in {"practice", "backing", "picker", "analysis", "log"}:
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
    event = "video_uploaded" if media_type == "video" else "audio_uploaded"
    ctx = _song_context(st)
    song = ctx.get("song") or "recording"
    kind = "performance video" if event == "video_uploaded" else "audio recording"
    _record(
        event,
        st=st,
        page=page,
        metrics={
            "media_type": media_type,
            "filename": filename,
            "upload_kind": kind,
        },
        summary=f"Uploaded {kind} for {song}",
        resume_title=f"Continue: {song}",
        resume_subtitle="Review upload",
    )


def log_recording_reviewed(st: Any, *, page: str = "Recording Analysis") -> None:
    ctx = _song_context(st)
    song = ctx.get("song") or "recording"
    _record(
        "recording_reviewed",
        st=st,
        page=page,
        metrics={"song": song, "artist": ctx.get("artist", "")},
        summary=f"Reviewed recording for {song}",
    )


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
