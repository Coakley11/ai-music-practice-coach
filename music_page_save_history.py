"""Ordered history of page-bearing cloud/disk saves (?dev=1)."""

from __future__ import annotations

from typing import Any

PAGE_SAVE_HISTORY_KEY = "_music_page_save_history"
PAGE_SAVE_HISTORY_MAX = 40


def record_page_bearing_save(
    session: dict[str, Any],
    *,
    reason: str,
    run_seq: int | None = None,
    pages: dict[str, Any] | None = None,
    cloud_confirmed: Any = None,
    confirmed_revision: Any = None,
    writer: str = "",
) -> None:
    hist = session.get(PAGE_SAVE_HISTORY_KEY)
    if not isinstance(hist, list):
        hist = []
    entry: dict[str, Any] = {
        "reason": str(reason or "").strip() or "unknown",
        "run_seq": run_seq if run_seq is not None else session.get("_script_run_seq"),
        "writer": writer,
        "session_studio_page": session.get("studio_page"),
        "cloud_confirmed": cloud_confirmed,
        "confirmed_revision": confirmed_revision,
    }
    if isinstance(pages, dict):
        entry.update(pages)
    hist.append(entry)
    if len(hist) > PAGE_SAVE_HISTORY_MAX:
        del hist[: len(hist) - PAGE_SAVE_HISTORY_MAX]
    session[PAGE_SAVE_HISTORY_KEY] = hist


def record_page_click_save_diagnostics(
    session: dict[str, Any],
    *,
    clicked_page: str,
    page_change_origin: str,
    stamp_trace: dict[str, Any] | None = None,
    cloud_confirmed: Any = None,
    confirmed_revision: Any = None,
) -> None:
    try:
        from music_studio_page_diagnostics import record_studio_page_diag

        fields: dict[str, Any] = {
            "clicked_page": clicked_page,
            "page_change_origin": page_change_origin,
            "canonical_page_after_click": clicked_page,
            "session_page_after_click": session.get("studio_page"),
            "page_change_cloud_confirmed": cloud_confirmed,
            "confirmed_revision": confirmed_revision,
        }
        if isinstance(stamp_trace, dict):
            for key in (
                "save_payload_core_page",
                "save_payload_session_page",
                "save_payload_workspace_page",
                "save_payload_studio_nav_page",
                "final_payload_studio_page",
                "cloud_write_studio_page",
            ):
                if stamp_trace.get(key) is not None:
                    fields[f"page_saved_{key.replace('save_payload_', '')}"] = stamp_trace.get(key)
                    if key.startswith("save_payload_"):
                        short = key.replace("save_payload_", "")
                        fields[f"save_{short}"] = stamp_trace.get(key)
        record_studio_page_diag(session, **fields)
    except ImportError:
        pass


__all__ = [
    "PAGE_SAVE_HISTORY_KEY",
    "record_page_bearing_save",
    "record_page_click_save_diagnostics",
]
