"""
Music Command Center integration — Continue cards and App Directory workstreams.

Continue cards restore a specific task via ``music_resume_payload``.
Workstream cards open Music to the current workspace without forcing stale song state.
"""

from __future__ import annotations

from typing import Any

from music_resume_payload import (
    MUSIC_WORKSTREAM_KINDS,
    WORKSTREAM_LABELS,
    WORKSTREAM_PAGE,
    build_music_resume_payload,
    continue_card_subtitle,
    continue_card_title,
    filter_payloads_for_workspace,
    legacy_resume_key_for_payload,
    normalize_resume_kind,
    normalize_workspace_id,
    payload_workspace_matches,
    resume_key_for_payload,
)

__all__ = (
    "MUSIC_WORKSTREAM_KINDS",
    "build_continue_card",
    "build_workstream_card",
    "build_workstream_cards",
    "filter_continue_cards_for_workspace",
    "record_and_sync_continue_card",
    "sync_music_continue_card",
    "upsert_music_continue_card",
    "workstream_entry_url",
)


def build_continue_card(
    payload: dict[str, Any],
    *,
    base_url: str = "",
) -> dict[str, Any]:
    """Structured Continue card for Command Center top section."""
    kind = normalize_resume_kind(str(payload.get("resume_kind") or ""))
    item_key = resume_key_for_payload(payload)
    title = continue_card_title(payload)
    subtitle = continue_card_subtitle(payload)
    action_url = _continue_action_url(payload, base_url=base_url)
    return {
        "card_type": "continue",
        "resume_kind": kind,
        "workspace_id": normalize_workspace_id(str(payload.get("workspace_id") or "")),
        "item_key": item_key,
        "title": title,
        "subtitle": subtitle,
        "action_url": action_url,
        "resume_key": legacy_resume_key_for_payload(payload),
        "payload": dict(payload),
    }


def _continue_action_url(payload: dict[str, Any], *, base_url: str = "") -> str:
    try:
        from suite_deep_links import build_music_continue_url

        return build_music_continue_url(payload, base_url=base_url)
    except Exception:
        return ""


def workstream_entry_url(
    workstream_kind: str,
    *,
    workspace_id: str = "",
    base_url: str = "",
) -> str:
    """Soft Music entry — page only, no stale pick_key or resume payload."""
    kind = str(workstream_kind or "").strip().lower()
    page = WORKSTREAM_PAGE.get(kind, "practice")
    ws = normalize_workspace_id(workspace_id)
    try:
        from suite_deep_links import build_music_workstream_url

        return build_music_workstream_url(page, workspace_id=ws, base_url=base_url)
    except Exception:
        return ""


def build_workstream_card(
    workstream_kind: str,
    *,
    workspace_id: str,
    summary: str = "",
    base_url: str = "",
) -> dict[str, Any]:
    """App Directory card — general workspace entry, not task-specific restore."""
    kind = str(workstream_kind or "").strip().lower()
    label = WORKSTREAM_LABELS.get(kind, kind.replace("_", " ").title())
    page = WORKSTREAM_PAGE.get(kind, "practice")
    ws = normalize_workspace_id(workspace_id)
    subtitle = str(summary or "").strip() or f"Open {label} in your Music workspace"
    return {
        "card_type": "workstream",
        "workstream_kind": kind,
        "workspace_id": ws,
        "title": label,
        "subtitle": subtitle,
        "action_url": workstream_entry_url(kind, workspace_id=ws, base_url=base_url),
        "studio_page": page,
        "item_key": f"music:workstream:{kind}",
    }


def build_workstream_cards(
    *,
    workspace_id: str,
    summaries: dict[str, str] | None = None,
    base_url: str = "",
) -> list[dict[str, Any]]:
    """Default App Directory workstream row for a workspace."""
    ws = normalize_workspace_id(workspace_id)
    sums = dict(summaries or {})
    return [
        build_workstream_card(kind, workspace_id=ws, summary=sums.get(kind, ""), base_url=base_url)
        for kind in MUSIC_WORKSTREAM_KINDS
    ]


def filter_continue_cards_for_workspace(
    cards: list[dict[str, Any]],
    workspace_id: str,
) -> list[dict[str, Any]]:
    """Drop Continue cards that belong to another workspace (coakley11 vs daniel)."""
    ws = normalize_workspace_id(workspace_id)
    out: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_ws = normalize_workspace_id(str(card.get("workspace_id") or ""))
        payload = card.get("payload")
        if isinstance(payload, dict) and payload.get("workspace_id"):
            if not payload_workspace_matches(payload, ws):
                continue
        elif card_ws and card_ws != ws:
            continue
        out.append(card)
    return out


def _resume_upsert_succeeded(result: Any) -> bool:
    if isinstance(result, dict):
        return str(result.get("write_mode") or "") not in {"", "skipped"}
    return bool(result)


def upsert_music_continue_card(payload: dict[str, Any], *, base_url: str = "") -> bool:
    """Write one Continue card to suite_resume_items (workspace-scoped cloud app key)."""
    card = build_continue_card(payload, base_url=base_url)
    item_key = str(card.get("item_key") or "").strip()
    title = str(card.get("title") or "").strip()
    if not item_key or not title:
        return False
    ws = normalize_workspace_id(str(payload.get("workspace_id") or ""))
    try:
        from suite_workspace import scoped_cloud_app_id

        storage_app = scoped_cloud_app_id("music", ws)
    except ImportError:
        storage_app = "music"
    subtitle = str(card.get("subtitle") or "")
    action_url = str(card.get("action_url") or "")
    for mod_name in ("suite_storage_supabase", "suite_storage"):
        try:
            mod = __import__(mod_name, fromlist=["upsert_resume_item"])
            result = mod.upsert_resume_item(
                storage_app,
                item_key,
                title=title,
                subtitle=subtitle,
                action_url=action_url,
            )
            if _resume_upsert_succeeded(result):
                return True
        except Exception:
            continue
    return False


def sync_music_continue_card(
    st: Any,
    *,
    kind: str | None = None,
    base_url: str = "",
) -> bool:
    """Build payload from session and upsert the matching Continue card."""
    session = st.session_state if hasattr(st, "session_state") else st
    payload = build_music_resume_payload(session, kind=kind, st=st if hasattr(st, "session_state") else None)
    return upsert_music_continue_card(payload, base_url=base_url)


def record_and_sync_continue_card(
    st: Any,
    event: str,
    *,
    kind: str | None = None,
    metrics: dict[str, Any] | None = None,
    page: str = "",
    summary: str = "",
) -> None:
    """Record activity + upsert Continue card with workspace-tagged payload."""
    session = st.session_state if hasattr(st, "session_state") else st
    payload = build_music_resume_payload(session, kind=kind, st=st if hasattr(st, "session_state") else st)
    merged_metrics = {**(metrics or {}), "resume_kind": payload.get("resume_kind"), "resume_payload": payload}
    try:
        from suite_activity_audit import prepare_activity_metrics

        merged_metrics = prepare_activity_metrics("music", merged_metrics)
    except ImportError:
        merged_metrics.setdefault("workspace_id", payload.get("workspace_id"))
    try:
        from suite_activity_client import record_activity

        record_activity(
            "music",
            event,
            page=page or str(session.get("studio_page") or ""),
            metrics=merged_metrics,
            summary=summary,
            resume_key=legacy_resume_key_for_payload(payload),
            resume_title=continue_card_title(payload),
            resume_subtitle=continue_card_subtitle(payload),
            action_url=_continue_action_url(payload),
        )
    except Exception:
        pass
    upsert_music_continue_card(payload)


def summarize_workstreams_from_payloads(
    payloads: list[dict[str, Any]],
    *,
    workspace_id: str,
) -> dict[str, str]:
    """Short summaries for App Directory subtitles from recent task payloads."""
    scoped = filter_payloads_for_workspace(payloads, workspace_id)
    sums: dict[str, str] = {}
    for payload in scoped:
        kind = normalize_resume_kind(str(payload.get("resume_kind") or ""))
        song = str(payload.get("song") or "").strip()
        if kind == "practice" and song:
            sums.setdefault("song_practice", f"Recent: {song}")
        elif kind == "backing":
            style = str(payload.get("style") or "Backing").strip()
            sums.setdefault("backing", f"Recent backing: {style}")
        elif kind == "creative":
            style = str(payload.get("improv_style_key") or "Creative").strip()
            sums.setdefault("creative", f"Recent lab: {style}")
        elif kind == "multitrack":
            title = str(payload.get("multitrack_title") or song or "session").strip()
            sums.setdefault("multitrack", f"Recent session: {title}")
        elif kind == "tone":
            dk = str(payload.get("display_key") or "").strip()
            sums.setdefault("tone", f"Recent tone work: {dk}" if dk else "Tone / tuner practice")
        elif kind in {"upload", "analysis"}:
            label = str(payload.get("upload_label") or song or "uploads").strip()
            sums.setdefault("upload", f"Recent upload: {label}")
    return sums
