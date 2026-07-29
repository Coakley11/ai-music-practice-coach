"""
Music Practice Coach — low-egress mode (Streamlit secret / env).

Enable with top-level Streamlit secret or env::

    MUSIC_EGRESS_STRICT = "1"

When active, Music reduces Supabase traffic: no post-save cloud readback,
routine autosaves write disk only (cloud on explicit/page-change saves),
lazy custom-song library fetch, smaller saved-item list limits, and lighter
page snapshots in persist blobs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from suite_storage_config import _coerce_str, _mapping_get

MUSIC_EGRESS_STRICT_KEY = "MUSIC_EGRESS_STRICT"
_SESSION_FLAG = "_music_egress_strict_active"

# Session keys never written to cloud/disk persist envelopes (ephemeral / large).
_EPHEMERAL_SNAPSHOT_KEYS: frozenset[str] = frozenset(
    {
        "composer_preview_wav",
        "composer_preview_signature",
        "_last_backing_wav",
        "_last_backing_timeline",
        "last_analysis_audio",
        "mixed_track_wav",
        "multitrack_backing_music_wav",
    }
)

# Reasons that still upload full session to Supabase under strict mode.
_STRICT_CLOUD_WRITE_REASONS: frozenset[str] = frozenset(
    {
        "page_change",
        "force_autosave",
        "insight_persist",
        "analysis_complete",
        "cpl_draft_edit",
        "song_edit",
        "practice_edit",
        "backing_edit",
        "music_coach_send",
    }
)

_CUSTOM_SONG_CLOUD_MERGED_KEY = "_music_custom_song_cloud_merged"


def _truthy(value: Any) -> bool:
    return _coerce_str(value).lower() in {"1", "true", "yes", "on"}


def _from_streamlit_secrets() -> bool:
    try:
        import streamlit as st  # noqa: WPS433

        root = st.secrets
        top = _mapping_get(root, MUSIC_EGRESS_STRICT_KEY)
        if _truthy(top):
            return True
        for section_name in ("music", "suite_activity", "music_practice"):
            try:
                block = root.get(section_name)
            except Exception:
                block = None
            if block is not None and _truthy(_mapping_get(block, MUSIC_EGRESS_STRICT_KEY)):
                return True
    except Exception:
        pass
    return False


def music_egress_strict_enabled(*, st: Any | None = None) -> bool:
    """True when MUSIC_EGRESS_STRICT is set in env or Streamlit secrets."""
    if _truthy(os.environ.get(MUSIC_EGRESS_STRICT_KEY, "")):
        return True
    if _from_streamlit_secrets():
        return True
    return False


def mark_music_egress_strict_session(st: Any | None) -> bool:
    """Cache strict flag on session for diagnostics (?dev=1)."""
    active = music_egress_strict_enabled(st=st)
    if st is not None:
        try:
            st.session_state[_SESSION_FLAG] = active
        except Exception:
            pass
    return active


@dataclass(frozen=True)
class MusicEgressPolicy:
    strict: bool
    skip_cloud_readback_after_save: bool
    skip_autosave_cloud_upload: bool
    lazy_custom_song_cloud_merge: bool
    saved_items_default_limit: int


def get_music_egress_policy(*, st: Any | None = None) -> MusicEgressPolicy:
    strict = music_egress_strict_enabled(st=st)
    if not strict:
        return MusicEgressPolicy(
            strict=False,
            skip_cloud_readback_after_save=False,
            skip_autosave_cloud_upload=False,
            lazy_custom_song_cloud_merge=False,
            saved_items_default_limit=200,
        )
    return MusicEgressPolicy(
        strict=True,
        skip_cloud_readback_after_save=True,
        skip_autosave_cloud_upload=True,
        lazy_custom_song_cloud_merge=True,
        saved_items_default_limit=25,
    )


def saved_items_list_limit(*, default: int = 50, st: Any | None = None) -> int:
    policy = get_music_egress_policy(st=st)
    if not policy.strict:
        return int(default)
    return min(int(default), policy.saved_items_default_limit)


def skip_cloud_readback_after_write(app_id: str, *, st: Any | None = None) -> bool:
    if str(app_id or "").strip().lower() != "music":
        return False
    return get_music_egress_policy(st=st).skip_cloud_readback_after_save


def music_cloud_write_allowed(*, save_reason: str, st: Any | None = None) -> bool:
    """Whether a music persist path may call save_cloud_full_session."""
    policy = get_music_egress_policy(st=st)
    if not policy.strict:
        return True
    reason = str(save_reason or "autosave").strip() or "autosave"
    if reason in _STRICT_CLOUD_WRITE_REASONS:
        return True
    if policy.skip_autosave_cloud_upload and reason == "autosave":
        return False
    return True


def should_merge_custom_songs_from_cloud(session_state: dict[str, Any], *, force: bool = False) -> bool:
    """Under strict mode, custom-song cloud list loads only when forced (library UI)."""
    if force:
        return True
    policy = get_music_egress_policy()
    if not policy.lazy_custom_song_cloud_merge:
        return True
    if session_state.get(_CUSTOM_SONG_CLOUD_MERGED_KEY):
        return False
    return False


def note_custom_song_cloud_merged(session_state: dict[str, Any]) -> None:
    session_state[_CUSTOM_SONG_CLOUD_MERGED_KEY] = True


def sanitize_studio_page_snapshots_for_persist(snapshots: dict[str, Any] | None) -> dict[str, Any]:
    """Drop ephemeral/large keys from per-page snapshots before hashing or cloud upload."""
    if not isinstance(snapshots, dict):
        return {}
    if not music_egress_strict_enabled():
        return snapshots
    out: dict[str, Any] = {}
    for page_id, snap in snapshots.items():
        if not isinstance(snap, dict):
            continue
        cleaned = {k: v for k, v in snap.items() if str(k) not in _EPHEMERAL_SNAPSHOT_KEYS}
        out[str(page_id)] = cleaned
    return out


def format_music_egress_status_line(*, st: Any | None = None) -> str:
    policy = get_music_egress_policy(st=st)
    if not policy.strict:
        return "MUSIC_EGRESS_STRICT: off"
    return (
        "MUSIC_EGRESS_STRICT: **on** — lazy custom-song cloud, "
        f"saved_items≤{policy.saved_items_default_limit}, no autosave cloud, no post-save readback"
    )
