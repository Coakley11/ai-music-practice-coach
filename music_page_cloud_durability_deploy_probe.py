"""Standalone dev deploy probe for page cloud durability diagnostics (?dev=1).

Does not import music_phase1_write_journal or music_page_cloud_durability_trace at module load.
"""

from __future__ import annotations

import importlib
from typing import Any

# Bump suffix `-v1` when probe UI changes; bump commit segment when shipping visibility fixes.
PAGE_CLOUD_DURABILITY_DEPLOY_MARKER = "PAGE_CLOUD_DURABILITY_DEPLOY: e199c14-v1"


def _dev_enabled(st: Any) -> bool:
    try:
        ss = st.session_state
    except Exception:
        return False
    if ss.get("developer_mode"):
        return True
    try:
        raw = st.query_params.get("dev")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}
    except Exception:
        return False


def _import_probe(module_name: str, *, attr: str | None = None) -> dict[str, Any]:
    try:
        mod = importlib.import_module(module_name)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if attr:
        fn = getattr(mod, attr, None)
        if not callable(fn):
            return {"ok": False, "error": f"{module_name}.{attr} missing or not callable"}
    return {"ok": True, "error": None}


def build_deploy_probe_payload() -> dict[str, Any]:
    from suite_deploy_marker import resolve_git_branch, resolve_git_commit_short

    commit = resolve_git_commit_short()
    branch = resolve_git_branch()
    durability = _import_probe("music_page_cloud_durability_trace")
    journal = _import_probe("music_phase1_write_journal")
    journal_render = _import_probe(
        "music_phase1_write_journal", attr="render_phase1_write_journal_expander"
    )
    marker_commit = ""
    if ":" in PAGE_CLOUD_DURABILITY_DEPLOY_MARKER:
        tail = PAGE_CLOUD_DURABILITY_DEPLOY_MARKER.split(":", 1)[1].strip()
        marker_commit = tail.split("-", 1)[0].strip()
    commit_matches_marker = bool(
        marker_commit and commit not in ("unknown", "") and marker_commit == commit
    )
    return {
        "deploy_marker": PAGE_CLOUD_DURABILITY_DEPLOY_MARKER,
        "deployed_commit": commit,
        "deployed_branch": branch,
        "marker_commit_segment": marker_commit or None,
        "deployed_commit_matches_marker": commit_matches_marker,
        "durability_module_import": durability,
        "journal_module_import": journal,
        "journal_renderer_import": journal_render,
    }


def render_page_cloud_durability_deploy_sidebar(st: Any) -> None:
    if not _dev_enabled(st):
        return
    payload = build_deploy_probe_payload()
    st.sidebar.markdown(f"**`{PAGE_CLOUD_DURABILITY_DEPLOY_MARKER}`**")
    st.sidebar.caption(f"deployed_branch: `{payload['deployed_branch']}`")
    st.sidebar.caption(f"deployed_commit: `{payload['deployed_commit']}`")
    if payload.get("marker_commit_segment"):
        match = payload.get("deployed_commit_matches_marker")
        st.sidebar.caption(
            f"marker vs live commit: `{'match' if match else 'MISMATCH — redeploy or stale build'}`"
        )
    for label, block in (
        ("durability module", payload["durability_module_import"]),
        ("journal module", payload["journal_module_import"]),
        ("journal renderer", payload["journal_renderer_import"]),
    ):
        ok = bool(block.get("ok"))
        st.sidebar.caption(f"{label} import: `{'ok' if ok else 'FAILED'}`")
        if not ok and block.get("error"):
            st.sidebar.error(f"{label}: {block['error']}")


__all__ = [
    "PAGE_CLOUD_DURABILITY_DEPLOY_MARKER",
    "build_deploy_probe_payload",
    "render_page_cloud_durability_deploy_sidebar",
]
