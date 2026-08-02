"""Dev-facing studio page restore / navigation diagnostics (?dev=1)."""

from __future__ import annotations

from typing import Any

STUDIO_PAGE_DIAG_KEY = "_music_studio_page_restore_diag"


def record_studio_page_diag(session: dict[str, Any], **fields: Any) -> None:
    diag = session.get(STUDIO_PAGE_DIAG_KEY)
    if not isinstance(diag, dict):
        diag = {}
    diag.update({k: v for k, v in fields.items() if v is not None})
    session[STUDIO_PAGE_DIAG_KEY] = diag


def collect_studio_page_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    diag = session.get(STUDIO_PAGE_DIAG_KEY)
    base = dict(diag) if isinstance(diag, dict) else {}
    try:
        from music_startup_save_suppression import get_page_change_origin

        base.setdefault("page_change_origin", get_page_change_origin(session))
    except ImportError:
        pass
    try:
        from studio_nav_state import canonical_studio_page

        base.setdefault("canonical_studio_page_before_widgets", canonical_studio_page(session))
    except ImportError:
        pass
    base.setdefault("hydrated_studio_page", session.get("_music_hydrated_studio_page"))
    base.setdefault("final_rendered_page", str(session.get("studio_page") or "").strip() or None)
    base.setdefault(
        "page_restore_overwrite_source",
        session.get("_suite_page_overwrite_source") or session.get("_page_restore_overwrite_source"),
    )
    tx = session.get("_music_workspace_save_transaction")
    if isinstance(tx, dict):
        base.setdefault("page_change_save_requested", tx.get("force_save_requested"))
        base.setdefault("page_change_cloud_confirmed", session.get("_suite_persist_last_save_cloud"))
    return base


__all__ = [
    "STUDIO_PAGE_DIAG_KEY",
    "collect_studio_page_diagnostics",
    "record_studio_page_diag",
]
