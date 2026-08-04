"""Dedupe page snapshot saves and cloud-adjacent writes within one Streamlit rerun."""

from __future__ import annotations

import hashlib
import json
from typing import Any

_SNAPSHOT_FP_RUN_KEY = "_page_snapshot_fp_this_run"
_NAV_SAVE_COUNT_KEY = "_page_snapshot_save_count_run"


def _snapshot_fingerprint(session: dict[str, Any], page_id: str) -> str:
    try:
        from studio_page_persistence import capture_page_snapshot

        snap = capture_page_snapshot(session, page_id)
        raw = json.dumps(snap, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:20]
    except Exception:
        return ""


def save_page_snapshot_deduped(session: dict[str, Any], page_id: str) -> bool:
    """
    Persist page-local snapshot only when content changed this rerun.

    Returns True if a save was performed.
    """
    pid = str(page_id or "").strip()
    if not pid:
        return False
    fp = _snapshot_fingerprint(session, pid)
    store = session.setdefault(_SNAPSHOT_FP_RUN_KEY, {})
    if isinstance(store, dict) and store.get(pid) == fp and fp:
        try:
            from music_dev_nav import dev_count

            dev_count(session, "page_snapshot_save_skipped")
        except ImportError:
            pass
        return False
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, pid)
    except ImportError:
        return False
    if isinstance(store, dict):
        store[pid] = fp
    counts = session.setdefault(_NAV_SAVE_COUNT_KEY, {})
    if isinstance(counts, dict):
        counts[pid] = int(counts.get(pid) or 0) + 1
    try:
        from music_dev_nav import dev_count

        dev_count(session, "page_snapshot_save")
    except ImportError:
        pass
    return True


__all__ = ["save_page_snapshot_deduped"]
