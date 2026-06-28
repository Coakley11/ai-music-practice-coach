"""Workspace-scoped paths for Music user-owned files (practice log, charts, uploads history)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from suite_workspace import DATA_DIR, DEFAULT_WORKSPACE_ID, normalize_workspace_id, resolve_workspace_id, workspace_dir

# logical key → (filename under workspace dir, legacy paths to migrate for Daniel)
_WORKSPACE_FILES: dict[str, tuple[str, tuple[Path, ...]]] = {
    "practice_history": (
        "practice_history.json",
        (Path("practice_history.json"), DATA_DIR / "practice_history.json"),
    ),
    "user_chart_overrides": (
        "user_chart_overrides.json",
        (DATA_DIR / "user_chart_overrides.json",),
    ),
    "user_song_content": (
        "user_song_content.json",
        (DATA_DIR / "user_song_content.json",),
    ),
    "ai_performance_history": (
        "ai_performance_history.json",
        (Path("ai_performance_history.json"),),
    ),
    "analysis_history": (
        "analysis_history.json",
        (Path("analysis_history.json"),),
    ),
    "mission_analysis_history": (
        "mission_analysis_history.json",
        (Path("mission_analysis_history.json"),),
    ),
    "analysis_last_session": (
        "analysis_last_session.json",
        (Path("analysis_last_session.json"),),
    ),
    "media_catalog": (
        "media_catalog.json",
        (),
    ),
}
_migrated_keys: set[str] = set()


def workspace_media_dir(workspace_id: str | None = None) -> Path:
    """Workspace-scoped media root (recordings, future multitrack blobs)."""
    from suite_workspace import workspace_dir

    ws = normalize_workspace_id(
        workspace_id if workspace_id not in (None, "") else resolve_workspace_id()
    )
    return workspace_dir(ws) / "media"


def music_data_path(file_key: str, workspace_id: str | None = None) -> Path:
    """Return ``data/workspaces/{profile}/{filename}``; migrate Daniel legacy files once."""
    spec = _WORKSPACE_FILES.get(str(file_key or "").strip())
    if not spec:
        raise KeyError(f"unknown music workspace file key: {file_key!r}")
    filename, legacy_paths = spec
    ws = normalize_workspace_id(
        workspace_id if workspace_id not in (None, "") else resolve_workspace_id()
    )
    target = workspace_dir(ws) / filename
    if ws == DEFAULT_WORKSPACE_ID and file_key not in _migrated_keys:
        _migrate_legacy_to_workspace(target, legacy_paths)
        _migrated_keys.add(file_key)
    return target


def _migrate_legacy_to_workspace(target: Path, legacy_paths: tuple[Path, ...]) -> None:
    if target.is_file():
        return
    for legacy in legacy_paths:
        if not legacy.is_file():
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
            return
        except OSError:
            continue


def workspace_persistence_context(*, st: Any | None = None) -> dict[str, str]:
    """Diagnostic bundle for traces (active profile + content paths)."""
    try:
        from suite_workspace import get_active_workspace_id, workspace_persistence_meta

        ws = get_active_workspace_id(st)
        meta = workspace_persistence_meta("music", st=st, workspace_id=ws)
    except Exception:
        ws = resolve_workspace_id()
        meta = {"active_workspace_id": ws, "cloud_app_key": "", "local_state_path": ""}
    return {
        **meta,
        "practice_history_path": str(music_data_path("practice_history", ws)),
        "chart_overrides_path": str(music_data_path("user_chart_overrides", ws)),
        "song_content_path": str(music_data_path("user_song_content", ws)),
        "performance_history_path": str(music_data_path("ai_performance_history", ws)),
    }
