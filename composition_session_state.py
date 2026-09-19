"""Session keys and persistence helpers for Composition Studio."""

from __future__ import annotations

import copy
from typing import Any

from composition_document import deep_copy_document, ensure_workflow, touch_composition

COMPOSER_ACTIVE_KEY = "composer_active_document"
COMPOSER_LIBRARY_KEY = "composer_saved_compositions"
COMPOSER_NEEDS_SEED_KEY = "composer_needs_seed"
COMPOSER_ACTIVE_SECTION_KEY = "composer_active_section_id"
COMPOSER_FOCUS_LANE_KEY = "composer_focus_lane"
COMPOSER_PREVIEW_WAV_KEY = "composer_preview_wav"
COMPOSER_PREVIEW_SIG_KEY = "composer_preview_signature"
COMPOSER_SNAPSHOT_STAMP_KEY = "composer_snapshot_stamp"
# Last explicit/implicit library upsert metadata for UI feedback.
COMPOSER_LAST_LIBRARY_SAVE_KEY = "_composer_last_library_save"
# IDs that have received an explicit "Save to Composition Library" click.
COMPOSER_EXPLICIT_LIBRARY_SAVE_IDS_KEY = "_composer_explicit_library_save_ids"

COMPOSER_WIDGET_SCALAR_KEYS: frozenset[str] = frozenset(
    {
        COMPOSER_ACTIVE_KEY,
        COMPOSER_LIBRARY_KEY,
        COMPOSER_NEEDS_SEED_KEY,
        COMPOSER_ACTIVE_SECTION_KEY,
        COMPOSER_FOCUS_LANE_KEY,
        COMPOSER_PREVIEW_WAV_KEY,
        COMPOSER_PREVIEW_SIG_KEY,
        COMPOSER_SNAPSHOT_STAMP_KEY,
    }
)

COMPOSER_WIDGET_PREFIXES: tuple[str, ...] = ("composer_pending_chord_",)


def init_composer_page_state(session_state: dict) -> None:
    session_state.setdefault(COMPOSER_LIBRARY_KEY, {})
    session_state.setdefault(COMPOSER_FOCUS_LANE_KEY, "chords")
    if COMPOSER_ACTIVE_KEY not in session_state:
        session_state[COMPOSER_NEEDS_SEED_KEY] = True


def get_active_document(session_state: dict) -> dict[str, Any] | None:
    doc = session_state.get(COMPOSER_ACTIVE_KEY)
    return doc if isinstance(doc, dict) else None


def set_active_document(
    session_state: dict,
    doc: dict[str, Any],
    *,
    clear_preview: bool = False,
    checkpoint: bool = True,
) -> None:
    """Install the active Composition document.

    ``clear_preview`` defaults to False so routine saves do not wipe an in-progress
    harmony/melody audition. Pass True when loading a different song or starting over.

    ``checkpoint`` syncs the durable composition workspace blob (reboot draft).
    """
    prepared = touch_composition(deep_copy_document(doc))
    ensure_workflow(prepared)
    session_state[COMPOSER_ACTIVE_KEY] = prepared
    session_state[COMPOSER_NEEDS_SEED_KEY] = False
    if clear_preview:
        from composition_preview import invalidate_composer_preview

        invalidate_composer_preview(session_state)
    session_state.pop(COMPOSER_SNAPSHOT_STAMP_KEY, None)
    if checkpoint:
        try:
            from composition_workspace_state_persistence import checkpoint_composition_workspace

            checkpoint_composition_workspace(session_state, reason="composer_edit", force_disk=False)
        except ImportError:
            pass


def save_document_to_library(
    session_state: dict,
    doc: dict[str, Any] | None = None,
    *,
    force_disk: bool = False,
    reason: str = "library_save",
    explicit: bool = False,
) -> dict[str, Any]:
    """Upsert the active Composition into the canonical library by stable UUID.

    Session ``composer_saved_compositions`` and durable
    ``composition_workspace_state.library`` stay mirrored. Does not mint a new id.
    Incomplete lyrics/review do not block save.

    ``explicit=True`` marks a user-facing Save to Composition Library action
    (affects first-save vs update confirmation copy).
    """
    active = doc or get_active_document(session_state)
    if not active:
        session_state[COMPOSER_LAST_LIBRARY_SAVE_KEY] = {"ok": False, "reason": "missing_document"}
        return {}
    lib = session_state.setdefault(COMPOSER_LIBRARY_KEY, {})
    if not isinstance(lib, dict):
        lib = {}
        session_state[COMPOSER_LIBRARY_KEY] = lib
    sid = str(active.get("id") or "").strip()
    if not sid:
        session_state[COMPOSER_LAST_LIBRARY_SAVE_KEY] = {"ok": False, "reason": "missing_id"}
        return active

    prior = lib.get(sid) if isinstance(lib.get(sid), dict) else None
    raw_explicit = session_state.get(COMPOSER_EXPLICIT_LIBRARY_SAVE_IDS_KEY) or []
    if isinstance(raw_explicit, set):
        explicit_ids = {str(x) for x in raw_explicit if str(x).strip()}
    elif isinstance(raw_explicit, (list, tuple)):
        explicit_ids = {str(x) for x in raw_explicit if str(x).strip()}
    else:
        explicit_ids = set()
    # User-facing first vs update: first *explicit* library save for this id.
    was_explicitly_saved = sid in explicit_ids
    is_update = bool(prior is not None) if not explicit else was_explicitly_saved
    prior_created = str((prior or {}).get("created_at") or active.get("created_at") or "").strip()

    prepared = deep_copy_document(active)
    # Keep draft/in-progress when Guided Path is incomplete; never invent "ready".
    status = str(prepared.get("status") or "").strip().lower()
    if status in ("", "new"):
        prepared["status"] = "draft"
    if prior_created:
        prepared["created_at"] = prior_created
    prepared = touch_composition(prepared)
    lib[sid] = prepared

    # Keep audition audio across saves — only replace the active document copy.
    # Skip nested checkpoint; we mirror the workspace library explicitly below.
    set_active_document(session_state, lib[sid], clear_preview=False, checkpoint=False)
    try:
        from composition_workspace_state_persistence import checkpoint_composition_workspace

        checkpoint_composition_workspace(
            session_state,
            reason=reason,
            force_disk=bool(force_disk),
        )
    except ImportError:
        pass

    if explicit:
        explicit_ids.add(sid)
        # Persist as a list so workspace/JSON envelopes stay serializable.
        session_state[COMPOSER_EXPLICIT_LIBRARY_SAVE_IDS_KEY] = sorted(explicit_ids)

    ws = session_state.get("composition_workspace_state")
    ws_lib = ws.get("library") if isinstance(ws, dict) else None
    mirrored = isinstance(ws_lib, dict) and sid in ws_lib
    session_state[COMPOSER_LAST_LIBRARY_SAVE_KEY] = {
        "ok": True,
        "is_update": is_update,
        "id": sid,
        "explicit": bool(explicit),
        "workspace_mirrored": mirrored,
        "updated_at": str(prepared.get("updated_at") or ""),
        "created_at": str(prepared.get("created_at") or ""),
    }
    return lib[sid]


def last_library_save_meta(session_state: dict) -> dict[str, Any]:
    meta = session_state.get(COMPOSER_LAST_LIBRARY_SAVE_KEY)
    return dict(meta) if isinstance(meta, dict) else {}


def library_save_success_message(session_state: dict) -> str:
    """User-facing confirmation after a successful library upsert."""
    meta = last_library_save_meta(session_state)
    if not meta.get("ok"):
        return ""
    if meta.get("is_update"):
        return "Composition Library updated."
    return "Saved to Composition Library."


def list_library_documents(session_state: dict) -> list[dict[str, Any]]:
    lib = session_state.get(COMPOSER_LIBRARY_KEY) or {}
    if not isinstance(lib, dict):
        return []
    rows = [v for v in lib.values() if isinstance(v, dict)]
    rows.sort(key=lambda d: str(d.get("updated_at") or d.get("created_at") or ""), reverse=True)
    return rows


def load_library_document(session_state: dict, doc_id: str) -> dict[str, Any] | None:
    lib = session_state.get(COMPOSER_LIBRARY_KEY) or {}
    if not isinstance(lib, dict):
        return None
    doc = lib.get(doc_id)
    if not isinstance(doc, dict):
        return None
    set_active_document(session_state, doc, clear_preview=True, checkpoint=True)
    sec_order = list((doc.get("form") or {}).get("section_order") or [])
    if sec_order:
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = sec_order[0]
    try:
        from composition_workspace_state_persistence import checkpoint_composition_workspace

        checkpoint_composition_workspace(session_state, reason="composer_edit", force_disk=True)
    except ImportError:
        pass
    return doc


def delete_library_document(session_state: dict, doc_id: str) -> None:
    lib = session_state.get(COMPOSER_LIBRARY_KEY) or {}
    if isinstance(lib, dict):
        lib.pop(doc_id, None)
    active = get_active_document(session_state)
    if active and str(active.get("id") or "") == doc_id:
        session_state.pop(COMPOSER_ACTIVE_KEY, None)
        session_state[COMPOSER_NEEDS_SEED_KEY] = True
    try:
        from composition_workspace_state_persistence import checkpoint_composition_workspace

        checkpoint_composition_workspace(session_state, reason="composer_edit", force_disk=True)
    except ImportError:
        pass


def export_composer_widget_state(session_state: dict) -> dict[str, Any]:
    """Session export for page snapshots — excludes ephemeral preview audio."""
    out: dict[str, Any] = {}
    for key in COMPOSER_WIDGET_SCALAR_KEYS:
        if key in (COMPOSER_PREVIEW_WAV_KEY, COMPOSER_PREVIEW_SIG_KEY):
            continue
        if key in session_state:
            out[key] = copy.deepcopy(session_state[key])
    for key in list(session_state.keys()):
        sk = str(key)
        if any(sk.startswith(p) for p in COMPOSER_WIDGET_PREFIXES):
            out[sk] = copy.deepcopy(session_state[key])
    return out


def import_composer_widget_state(session_state: dict, blob: dict[str, Any]) -> None:
    if not isinstance(blob, dict):
        return
    for key, val in blob.items():
        session_state[str(key)] = copy.deepcopy(val)
