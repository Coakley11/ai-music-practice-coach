"""Active music source: catalog song vs custom progression (shared session contract)."""

from __future__ import annotations

from typing import Any, Callable

ACTIVE_MUSIC_SOURCE_KEY = "active_music_source"
SOURCE_CATALOG = "catalog_song"
SOURCE_CUSTOM = "custom_progression"
SOURCE_COMPOSITION = "composition_song"
_LAST_SOURCE_KEY = "_last_active_music_source"
_LAST_ACTIVE_PICK_KEY = "_last_active_pick_key_for_reset"
PENDING_CUSTOM_ACTIVE_SONG_KEY = "_pending_custom_active_song_activation"
PENDING_CUSTOM_LIBRARY_ACTION_KEY = "_pending_custom_library_action"
SONG_PICKER_SOURCE_CATALOG = "Song Selection (catalog song)"
SONG_PICKER_SOURCE_CUSTOM = "Use Custom Progression / Create Your Own Song"
SONG_PICKER_SOURCE_COMPOSITION = "Composition"


def song_picker_composition_option_label() -> str:
    """Radio option text for Composition (must match widget value exactly)."""
    try:
        from music_feature_icons import FEATURE_ICONS

        return f"{FEATURE_ICONS.get('composition', '🪶')} Composition"
    except ImportError:
        return "🪶 Composition"


def picker_choice_is_composition(choice: str) -> bool:
    text = str(choice or "").strip()
    return text == SONG_PICKER_SOURCE_COMPOSITION or "Composition" in text

SONG_PICKER_ACTIVE_SOURCE_KEY = "song_picker_active_source"
PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY = "_pending_song_picker_active_source"
LAST_CATALOG_STATE_KEY = "_last_catalog_song_state"
LAST_CUSTOM_STATE_KEY = "_last_custom_song_state"
CATALOG_BEFORE_CUSTOM_KEY = "_catalog_before_custom_state"
PENDING_CATALOG_FROM_PICKER_KEY = "_pending_catalog_from_picker_switch"
CATALOG_BEFORE_CREATIVE_KEY = "_catalog_before_creative_state"
CATALOG_RESTORE_PIN_KEY = "_catalog_restore_pin_pick"
PENDING_PREVIOUS_CATALOG_RESTORE_KEY = "_pending_previous_catalog_restore"
USER_CATALOG_SOURCE_CHOICE_KEY = "_user_chose_catalog_music_source"
# Deterministic commit stamp for Songs radio / source selection. Outranks a
# stale composition:: / custom:: pick during the same rerun and after refresh.
EXPLICIT_MUSIC_SOURCE_CHOICE_KEY = "explicit_music_source_choice"
EXPLICIT_MUSIC_SOURCE_SEQ_KEY = "_explicit_music_source_seq"
CATALOG_RECENT_PICK_KEYS = "catalog_recent_pick_keys"
CUSTOM_RECENT_ACTIVE_NAMES_KEY = "custom_recent_active_names"


def ensure_active_music_source(session_state: dict[str, Any]) -> None:
    session_state.setdefault(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)


def explicit_music_source_choice(session_state: dict[str, Any]) -> str:
    """Last explicit Catalog/Custom/Composition selection (empty when unset)."""
    raw = str(session_state.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY) or "").strip()
    if raw in {SOURCE_CATALOG, SOURCE_CUSTOM, SOURCE_COMPOSITION}:
        return raw
    return ""


def is_custom_progression(session_state: dict[str, Any]) -> bool:
    return session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CUSTOM


def is_composition_song(session_state: dict[str, Any]) -> bool:
    return session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_COMPOSITION


def _pick_looks_composition(pick_key: str) -> bool:
    return str(pick_key or "").strip().startswith("composition::")



def clear_composition_one_shot_nav_flags(session_state: dict[str, Any]) -> None:
    """Drop Composition hub/backing one-shots after an explicit non-Composition choice.

    Must not run after a Composition hub Backing ``on_click`` in the same script
    run — reconcile / ``set_custom_source`` otherwise pops ``composition_hub_backing``
    and ``_composition_hub_backing_clicked`` before ``st.button`` body can navigate.
    """
    if session_state.get("_composition_hub_backing_clicked") or session_state.get(
        "_composition_hub_backing_pending"
    ):
        return
    for key in (
        "_force_composition_backing_open",
        "_composition_hub_backing_clicked",
        "_composition_hub_backing_pending",
        "_composition_hub_promote_token",
        "_composition_hub_promote_error",
        "_composition_hub_outer_error",
        "_composition_radio_ensure_error",
        "_composition_ensure_ok",
        "_composition_ensure_commit_error",
        "composition_hub_backing",
        "composition_hub_practice",
        "composition_hub_edit",
    ):
        session_state.pop(key, None)


def commit_explicit_music_source_choice(
    session_state: dict[str, Any],
    source: str,
    *,
    clear_composition_oneshots: bool | None = None,
) -> None:
    """Single commit point for an explicit Songs source selection.

    Must run before ownership reconcile / open-backing / hub promote so a
    newer radio choice cannot lose to a stale pick or Composition one-shot.
    """
    src = str(source or "").strip()
    if src not in {SOURCE_CATALOG, SOURCE_CUSTOM, SOURCE_COMPOSITION}:
        return
    session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = src
    try:
        seq = int(session_state.get(EXPLICIT_MUSIC_SOURCE_SEQ_KEY) or 0)
    except (TypeError, ValueError):
        seq = 0
    session_state[EXPLICIT_MUSIC_SOURCE_SEQ_KEY] = seq + 1
    if src == SOURCE_CATALOG:
        session_state[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    else:
        session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
    if clear_composition_oneshots is None:
        clear_composition_oneshots = src != SOURCE_COMPOSITION
    if clear_composition_oneshots:
        # Mid-run reconcile / set_custom must not drop an in-flight Composition
        # hub Backing ``on_click`` (same contract as
        # ``clear_composition_one_shot_nav_flags``). Intentional Catalog/Custom
        # *radio* leave paths pop the click/pending flags before calling commit.
        if session_state.get("_composition_hub_backing_clicked") or session_state.get(
            "_composition_hub_backing_pending"
        ):
            clear_composition_one_shot_nav_flags(session_state)
        else:
            session_state.pop("_composition_hub_backing_clicked", None)
            session_state.pop("_force_composition_backing_open", None)
            session_state.pop("_composition_hub_backing_pending", None)
            clear_composition_one_shot_nav_flags(session_state)


def composition_song_is_active(session_state: dict[str, Any]) -> bool:
    """True when a Composition document is the active song."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CATALOG:
        return False
    # Live Songs radio wins before the explicit stamp — a stale Custom stamp
    # must not block Composition after the radio has already moved.
    if picker_composition_mode(session_state):
        return True
    if picker_custom_progression_mode(session_state):
        return False
    explicit = explicit_music_source_choice(session_state)
    if explicit in {SOURCE_CATALOG, SOURCE_CUSTOM}:
        return False
    if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CUSTOM:
        return False
    if explicit == SOURCE_COMPOSITION:
        return True
    # Composition pick/meta must win even when ACTIVE_MUSIC_SOURCE still lags on
    # Custom after Songs → Composition (sidebar/Backing otherwise stay Custom).
    if is_composition_song(session_state):
        return True
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if _pick_looks_composition(pick_key):
        return True
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict):
        if str(meta.get("music_source") or "") == SOURCE_COMPOSITION:
            return True
        if _pick_looks_composition(str(meta.get("pick_key") or "")):
            return True
    if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CUSTOM:
        return False
    return False


def custom_progression_is_active(session_state: dict[str, Any]) -> bool:
    """True when Custom Progression is the active song (session or canonical blob)."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CATALOG:
        return False
    # Live Composition radio outranks a lingering Custom stamp/pick.
    if picker_composition_mode(session_state):
        return False
    explicit = explicit_music_source_choice(session_state)
    if explicit == SOURCE_CATALOG:
        return False
    if explicit == SOURCE_COMPOSITION:
        return False
    if composition_song_is_active(session_state):
        return False
    if explicit == SOURCE_CUSTOM or is_custom_progression(session_state):
        return True
    if picker_custom_progression_mode(session_state):
        return True
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick_key.startswith("custom::"):
        return True
    if _pick_looks_composition(pick_key):
        return False
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict):
        if str(meta.get("music_source") or "") == SOURCE_COMPOSITION:
            return False
        if str(meta.get("music_source") or "") == SOURCE_CUSTOM:
            return True
        if str(meta.get("pick_key") or "").strip().startswith("custom::"):
            return True
    return False


def source_ownership_snapshot(session_state: dict[str, Any]) -> dict[str, Any]:
    """Before/after transition capture for ownership race diagnosis."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    meta = session_state.get("active_song_state")
    meta_src = ""
    meta_pick = ""
    if isinstance(meta, dict):
        meta_src = str(meta.get("music_source") or "").strip()
        meta_pick = str(meta.get("pick_key") or "").strip()
    pref = ""
    try:
        from backing_context import get_backing_source_preference

        pref = str(get_backing_source_preference(session_state) or "").strip()
    except Exception:
        pref = str(session_state.get("_backing_source_preference") or "").strip()
    return {
        "radio": str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip(),
        "explicit": explicit_music_source_choice(session_state),
        "explicit_seq": int(session_state.get(EXPLICIT_MUSIC_SOURCE_SEQ_KEY) or 0),
        "active_music_source": str(session_state.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip(),
        "pick": pick,
        "meta_source": meta_src,
        "meta_pick": meta_pick,
        "user_catalog_choice": bool(session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY)),
        "force_composition_backing": bool(
            session_state.get("_force_composition_backing_open")
        ),
        "hub_backing_pending": bool(
            session_state.get("_composition_hub_backing_pending")
        ),
        "hub_promote_token": str(
            session_state.get("_composition_hub_promote_token") or ""
        ).strip(),
        "backing_pref": pref,
        "composition_active": bool(composition_song_is_active(session_state)),
        "custom_active": bool(custom_progression_is_active(session_state)),
    }


def picker_custom_progression_mode(session_state: dict[str, Any]) -> bool:
    """True when the Songs page radio is on Custom Progression."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if "Composition" in choice:
        return False
    return choice == SONG_PICKER_SOURCE_CUSTOM or choice.startswith("Use Custom")


def picker_composition_mode(session_state: dict[str, Any]) -> bool:
    """True when the Songs page radio is on Composition."""
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    return picker_choice_is_composition(choice)


def songs_hub_custom_backing_selected(session_state: dict[str, Any]) -> bool:
    """Live Songs hub: Custom owns the next hub Backing navigation."""
    explicit = explicit_music_source_choice(session_state)
    if explicit == SOURCE_CUSTOM:
        return True
    if explicit == SOURCE_CATALOG or session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if explicit == SOURCE_COMPOSITION:
        return False
    if picker_custom_progression_mode(session_state):
        return True
    return custom_progression_is_active(session_state)


def songs_hub_catalog_backing_selected(session_state: dict[str, Any]) -> bool:
    """Live Songs hub: Catalog owns the next hub Backing navigation."""
    if songs_hub_custom_backing_selected(session_state):
        return False
    explicit = explicit_music_source_choice(session_state)
    if explicit == SOURCE_CATALOG or session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return True
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    return choice == SONG_PICKER_SOURCE_CATALOG


def songs_hub_composition_backing_selected(session_state: dict[str, Any]) -> bool:
    """Live Songs hub: Composition owns the next hub Backing navigation."""
    if songs_hub_custom_backing_selected(session_state):
        return False
    if songs_hub_catalog_backing_selected(session_state):
        return False
    return composition_song_is_active(session_state) or picker_composition_mode(session_state)


def cpl_session_is_active(session_state: dict[str, Any]) -> bool:
    """True when the loaded song is a Custom Progression (for key display/sync)."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if composition_song_is_active(session_state) or picker_composition_mode(session_state):
        return False
    if is_custom_progression(session_state):
        return True
    if picker_custom_progression_mode(session_state):
        return True
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if _pick_looks_composition(pick_key):
        return False
    if pick_key.startswith("custom::"):
        return True
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_CUSTOM:
        return True
    if isinstance(meta, dict):
        meta_pick = str(meta.get("pick_key") or "").strip()
        if meta_pick.startswith("custom::"):
            return True
    return False


def reconcile_music_picker_source_widget(session_state: dict[str, Any]) -> bool:
    """Align Songs page source radio with active song + active_music_source.

    Explicit radio / ``explicit_music_source_choice`` outrank a stale pick so
    hydration cannot overwrite a newer selection in the same rerun.
    """
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    try:
        from music_restore_phase import music_restore_phase_complete

        phase_done = music_restore_phase_complete(session_state)
    except ImportError:
        phase_done = False

    # Live widget value — checked directly because ``picker_custom_progression_mode``
    # returns False while ``USER_CATALOG`` is set (intentional for hub/nav vetoes).
    # That veto must not reset a live Custom/Composition radio back to Catalog.
    choice_live = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    live_custom = choice_live == SONG_PICKER_SOURCE_CUSTOM or choice_live.startswith(
        "Use Custom"
    )
    live_composition = picker_choice_is_composition(choice_live)

    # Trust an in-progress Songs radio selection before pick-based reclaim.
    if live_custom or picker_custom_progression_mode(session_state):
        changed = False
        if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
            session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
            changed = True
        if explicit_music_source_choice(session_state) != SOURCE_CUSTOM:
            commit_explicit_music_source_choice(session_state, SOURCE_CUSTOM)
            changed = True
        else:
            clear_composition_one_shot_nav_flags(session_state)
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CUSTOM:
            set_custom_source(session_state)
            changed = True
        return changed
    if live_composition or picker_composition_mode(session_state):
        changed = False
        if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
            session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
            changed = True
        if explicit_music_source_choice(session_state) != SOURCE_COMPOSITION:
            commit_explicit_music_source_choice(
                session_state,
                SOURCE_COMPOSITION,
                clear_composition_oneshots=False,
            )
            changed = True
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_COMPOSITION:
            session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
            changed = True
        return changed

    if phase_done and session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        expected = SONG_PICKER_SOURCE_CATALOG
        current = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
        changed = False
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
            set_catalog_source(session_state)
            changed = True
        if explicit_music_source_choice(session_state) != SOURCE_CATALOG:
            commit_explicit_music_source_choice(session_state, SOURCE_CATALOG)
            changed = True
        if current != expected:
            _assign_song_picker_source_widget(session_state, expected)
            changed = True
        return changed

    explicit = explicit_music_source_choice(session_state)
    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if explicit == SOURCE_CUSTOM:
        composition_active = False
        custom_active = True
    elif explicit == SOURCE_COMPOSITION:
        composition_active = True
        custom_active = False
    elif explicit == SOURCE_CATALOG:
        composition_active = False
        custom_active = False
    else:
        composition_active = composition_song_is_active(session_state)
        custom_active = custom_progression_is_active(session_state)
    if composition_active:
        expected = song_picker_composition_option_label()
    elif custom_active:
        expected = SONG_PICKER_SOURCE_CUSTOM
    else:
        expected = SONG_PICKER_SOURCE_CATALOG
    current = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    changed = False

    # Live Catalog radio commits Catalog ownership immediately. Defer only the
    # catalog *song* restore when pick still looks custom/composition — never
    # leave a full rerun with Catalog radio + Custom/Composition hub.
    if current == SONG_PICKER_SOURCE_CATALOG:
        if explicit_music_source_choice(session_state) != SOURCE_CATALOG:
            commit_explicit_music_source_choice(session_state, SOURCE_CATALOG)
            changed = True
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
            set_catalog_source(session_state)
            changed = True
        if pick_key.startswith("custom::") or _pick_looks_composition(pick_key):
            session_state[PENDING_CATALOG_FROM_PICKER_KEY] = True
        return changed

    if composition_active:
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_COMPOSITION:
            session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
            changed = True
    elif custom_active:
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CUSTOM:
            session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
            changed = True
    elif pick_key and not pick_key.startswith("custom::") and not _pick_looks_composition(pick_key):
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
            set_catalog_source(session_state)
            changed = True

    if current != expected:
        _assign_song_picker_source_widget(session_state, expected)
        changed = True
    return changed


def ensure_active_music_source_from_canonical(session_state: dict[str, Any]) -> None:
    """After cloud/local restore, align session source flag with canonical custom songs."""
    if is_custom_progression(session_state):
        if not explicit_music_source_choice(session_state):
            session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_CUSTOM
        return
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        if not explicit_music_source_choice(session_state):
            session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_CATALOG
        return
    if is_composition_song(session_state):
        if not explicit_music_source_choice(session_state):
            session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_COMPOSITION
        return
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY
        from music_restore_phase import authoritative_restore_in_progress
    except ImportError:
        return
    if not authoritative_restore_in_progress(session_state):
        return
    meta = session_state.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_CUSTOM:
        session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
        if not explicit_music_source_choice(session_state):
            session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_CUSTOM
    elif isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_COMPOSITION:
        session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
        if not explicit_music_source_choice(session_state):
            session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_COMPOSITION


def hydrate_explicit_music_source_from_active(session_state: dict[str, Any]) -> None:
    """After disk restore, seed the explicit stamp from persisted active source.

    Prevents pick-based reclaim from Composition on refresh when Custom was
    saved but the stamp key was absent from older workspace files.
    """
    if explicit_music_source_choice(session_state):
        return
    src = str(session_state.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip()
    if src in {SOURCE_CATALOG, SOURCE_CUSTOM, SOURCE_COMPOSITION}:
        session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = src
        if src == SOURCE_CATALOG:
            session_state[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        else:
            session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)


def set_catalog_source(session_state: dict[str, Any]) -> None:
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
    try:
        from source_session_state import sync_catalog_session

        sync_catalog_session(session_state)
    except ImportError:
        pass


def restore_catalog_identity_from_snapshot(
    session_state: dict[str, Any],
    *,
    snap_key: str = CATALOG_BEFORE_CUSTOM_KEY,
) -> bool:
    """Restore catalog pick/title when global identity was polluted by a custom preview."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick and not pick.startswith("custom::"):
        sel = session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict) and str(sel.get("title") or "").strip():
            return False
    raw = session_state.get(snap_key)
    if not isinstance(raw, dict):
        raw = session_state.get(LAST_CATALOG_STATE_KEY)
    if not isinstance(raw, dict):
        return False
    snap_pick = str(raw.get("pick_key") or "").strip()
    if not snap_pick or snap_pick.startswith("custom::"):
        return False
    raw_sel = raw.get("selected_song")
    selected = dict(raw_sel) if isinstance(raw_sel, dict) else {}
    if not selected:
        return False
    _sync_catalog_session_surface_keys(
        session_state,
        pick_key=snap_pick,
        selected_song=selected,
    )
    pin_catalog_pick_aliases(session_state)
    session_state[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    try:
        from active_song_state import clear_active_song_local_edit

        clear_active_song_local_edit(session_state)
    except ImportError:
        session_state.pop("_active_song_locally_dirty", None)
    return True


def _catalog_snapshot_from_session(session_state: dict[str, Any]) -> dict[str, Any] | None:
    """Build a catalog song snapshot from the current session selection."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    sel = session_state.get(SELECTED_SONG_STATE_KEY)
    if not isinstance(sel, dict):
        return None
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY) or sel.get("pick_key") or ""
    ).strip()
    if not pick_key or pick_key.startswith("custom::"):
        return None
    original_key = str(sel.get("key") or "C").strip() or "C"
    display_key = str(session_state.get("display_key") or original_key).strip() or original_key
    return {
        "pick_key": pick_key,
        "selected_song": dict(sel),
        "original_key": original_key,
        "display_key": display_key,
    }


def snapshot_catalog_before_custom(session_state: dict[str, Any]) -> None:
    """Remember the active catalog song before entering Custom Progression."""
    if is_custom_progression(session_state):
        return
    snap = _catalog_snapshot_from_session(session_state)
    if snap:
        session_state[CATALOG_BEFORE_CUSTOM_KEY] = snap
        session_state[LAST_CATALOG_STATE_KEY] = dict(snap)


def _custom_snapshot_from_session(session_state: dict[str, Any]) -> dict[str, Any] | None:
    """Snapshot the active custom progression for catalog ↔ custom switching."""
    import copy

    try:
        from custom_progression_lab import cpl_active_from_session, ensure_original_structure
    except ImportError:
        return None
    active = ensure_original_structure(cpl_active_from_session(session_state))
    name = str(active.get("name") or "").strip()
    if not name:
        return None
    return {"name": name, "active": copy.deepcopy(active)}


def snapshot_last_custom_state(session_state: dict[str, Any]) -> None:
    """Remember the active custom song before leaving Custom Progression."""
    if not is_custom_progression(session_state) and not custom_progression_is_active(session_state):
        return
    snap = _custom_snapshot_from_session(session_state)
    if snap:
        session_state[LAST_CUSTOM_STATE_KEY] = snap


def snapshot_catalog_before_creative(
    session_state: dict[str, Any],
    *,
    refresh_if_pick_changed: bool = False,
) -> None:
    """Remember the active catalog song before entering Creative/Jam backing."""
    if is_custom_progression(session_state):
        return
    snap = _catalog_snapshot_from_session(session_state)
    if not snap:
        return
    existing = session_state.get(CATALOG_BEFORE_CREATIVE_KEY)
    if isinstance(existing, dict) and str(existing.get("pick_key") or "").strip():
        if not refresh_if_pick_changed:
            return
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        live_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
        existing_pick = str(existing.get("pick_key") or "").strip()
        if live_pick and existing_pick and _pick_keys_match(
            existing_pick, live_pick, session_state=session_state
        ):
            return
    session_state[CATALOG_BEFORE_CREATIVE_KEY] = snap
    try:
        from source_session_state import sync_catalog_session

        sync_catalog_session(session_state)
    except ImportError:
        pass
    write_creative_catalog_guard_diag(
        session_state,
        catalog_snapshot_before_creative=str(snap.get("pick_key") or "").strip(),
        last_catalog_song_writer="snapshot_catalog_before_creative",
    )


def peek_catalog_restore_pin(session_state: dict[str, Any]) -> str:
    """Pinned catalog pick from a recent Use Catalog Song Backing restore."""
    return str(session_state.get(CATALOG_RESTORE_PIN_KEY) or "").strip()


def pin_catalog_restore_identity(
    session_state: dict[str, Any],
    pick_key: str,
    selected_song: dict[str, Any] | None = None,
    *,
    writer: str = "catalog_restore",
) -> None:
    """Atomically pin restored catalog identity so reconcile cannot fall back to stale picks."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    pick_key = str(pick_key or "").strip()
    if not pick_key or pick_key.startswith("custom::"):
        return
    session_state[CATALOG_RESTORE_PIN_KEY] = pick_key
    session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key
    if isinstance(selected_song, dict) and selected_song:
        session_state[SELECTED_SONG_STATE_KEY] = dict(selected_song)
        title = str(selected_song.get("title") or "").strip()
        if title:
            session_state["song"] = title
            session_state["active_song_title"] = title
    pin_catalog_pick_aliases(session_state)
    catalog = session_state.get("_reconcile_song_picker_catalog")
    if isinstance(catalog, dict):
        try:
            from songs.state import sync_catalog_pick_identity

            sync_catalog_pick_identity(session_state, pick_key, catalog)
        except Exception:
            pass
    try:
        from active_song_state import clear_active_song_local_edit

        clear_active_song_local_edit(session_state)
    except ImportError:
        session_state.pop("_active_song_locally_dirty", None)
    snap = _catalog_snapshot_from_session(session_state)
    if snap:
        session_state[LAST_CATALOG_STATE_KEY] = snap
    try:
        from music_source_ownership import write_catalog_restore_diag

        write_catalog_restore_diag(
            session_state,
            catalog_restore_pin_pick=pick_key,
            catalog_restore_pin_writer=writer,
        )
    except ImportError:
        pass


def write_creative_catalog_guard_diag(session_state: dict[str, Any], **fields: Any) -> None:
    """Dev trace for Creative edits that must not mutate catalog ownership."""
    blob = dict(session_state.get("_creative_catalog_guard_diag") or {})
    blob.update(fields)
    session_state["_creative_catalog_guard_diag"] = blob
    if "last_catalog_song_writer" in fields:
        session_state["last_catalog_song_writer"] = str(fields.get("last_catalog_song_writer") or "").strip()


def pin_catalog_pick_aliases(session_state: dict[str, Any]) -> str:
    """Align stale picker dropdown aliases with the live catalog pick on Creative."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, PENDING_MATCHING_SONG_DROPDOWN, SELECTED_SONG_STATE_KEY

    pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if not pick:
        sel = session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict):
            pick = str(sel.get("pick_key") or "").strip()
    if pick and not pick.startswith("custom::"):
        session_state[PENDING_MATCHING_SONG_DROPDOWN] = pick
        session_state["matching_song_dropdown"] = pick
        session_state["_master_song_pick_key"] = pick
    return pick


def restore_frozen_catalog_pick_if_mutated(
    session_state: dict[str, Any],
    before_pick: str,
    *,
    writer: str,
) -> bool:
    """Restore catalog pick when Creative widget edits incorrectly changed it."""
    try:
        from creative_key_sync import is_creative_catalog_pick_frozen
    except ImportError:
        is_creative_catalog_pick_frozen = lambda _s: False  # type: ignore[assignment,misc]
    if not is_creative_catalog_pick_frozen(session_state):
        return False
    snap = session_state.get(CATALOG_BEFORE_CREATIVE_KEY)
    snap_pick = ""
    if isinstance(snap, dict):
        snap_pick = str(snap.get("pick_key") or "").strip()
    target_pick = str(before_pick or snap_pick or "").strip()
    if not target_pick:
        return False
    current = str(session_state.get("active_catalog_pick_key") or "").strip()
    if current == target_pick:
        return False
    catalog = session_state.get("_reconcile_song_picker_catalog")
    if isinstance(catalog, dict):
        from songs.state import sync_catalog_pick_identity

        sync_catalog_pick_identity(session_state, target_pick, catalog)
    elif isinstance(snap, dict) and snap_pick == target_pick:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        session_state[ACTIVE_CATALOG_PICK_KEY] = target_pick
        raw_sel = snap.get("selected_song")
        if isinstance(raw_sel, dict) and raw_sel:
            session_state[SELECTED_SONG_STATE_KEY] = dict(raw_sel)
            title = str(raw_sel.get("title") or "").strip()
            if title:
                session_state["song"] = title
                session_state["active_song_title"] = title
        pin_catalog_pick_aliases(session_state)
    else:
        from songs.state import SELECTED_SONG_STATE_KEY

        session_state["active_catalog_pick_key"] = target_pick
        sel = session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict) and _pick_keys_match(
            str(sel.get("pick_key") or "").strip(),
            target_pick,
            session_state=session_state,
        ):
            title = str(sel.get("title") or "").strip()
            if title:
                session_state["song"] = title
                session_state["active_song_title"] = title
        pin_catalog_pick_aliases(session_state)
    write_creative_catalog_guard_diag(
        session_state,
        last_catalog_song_writer=f"restored_after_{writer}",
    )
    return True


def set_custom_source(session_state: dict[str, Any]) -> None:
    snapshot_catalog_before_custom(session_state)
    session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
    if explicit_music_source_choice(session_state) != SOURCE_CUSTOM:
        # Soft-align stamp without bumping seq when already Custom (restore).
        session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_CUSTOM
    clear_composition_one_shot_nav_flags(session_state)
    try:
        from source_session_state import sync_catalog_session, sync_custom_session

        sync_catalog_session(session_state)
        sync_custom_session(session_state)
    except ImportError:
        pass
    try:
        from custom_progression_lab import CPL_LAST_DISPLAY_KEY

        live = str(
            session_state.get("display_key") or session_state.get("concert_key") or ""
        ).strip()
        if live:
            session_state.setdefault(CPL_LAST_DISPLAY_KEY, live)
    except ImportError:
        pass


def music_picker_shows_custom_hub(session_state: dict[str, Any]) -> bool:
    """True when the Song Selection UI should show the custom library, not catalog."""
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if choice == SONG_PICKER_SOURCE_CATALOG:
        return False
    if picker_composition_mode(session_state):
        return False
    if choice.startswith("Use Custom"):
        return True
    # Live Catalog radio already handled; never show Custom hub from a stale pick
    # while the user has stamped Catalog.
    if explicit_music_source_choice(session_state) == SOURCE_CATALOG:
        return False
    return custom_progression_is_active(session_state)


def music_picker_shows_composition_hub(session_state: dict[str, Any]) -> bool:
    """True when Song Selection should show the Composition Songs library."""
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if choice == SONG_PICKER_SOURCE_CATALOG:
        return False
    if picker_custom_progression_mode(session_state) or choice.startswith("Use Custom"):
        return False
    if explicit_music_source_choice(session_state) == SOURCE_CATALOG:
        return False
    if picker_composition_mode(session_state):
        return True
    return composition_song_is_active(session_state)


def _expected_song_picker_source(session_state: dict[str, Any]) -> str:
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return SONG_PICKER_SOURCE_CATALOG
    if picker_custom_progression_mode(session_state):
        return SONG_PICKER_SOURCE_CUSTOM
    if picker_composition_mode(session_state):
        return song_picker_composition_option_label()
    if composition_song_is_active(session_state) or is_composition_song(session_state):
        return song_picker_composition_option_label()
    if is_custom_progression(session_state):
        return SONG_PICKER_SOURCE_CUSTOM
    return SONG_PICKER_SOURCE_CATALOG


def assign_song_picker_source_widget(
    session_state: dict[str, Any],
    value: str,
    *,
    widget_safe: bool = True,
) -> None:
    """Public wrapper for Songs source radio assignment."""
    _assign_song_picker_source_widget(session_state, value, widget_safe=widget_safe)


def _assign_song_picker_source_widget(
    session_state: dict[str, Any],
    value: str,
    *,
    widget_safe: bool = True,
) -> None:
    try:
        from session_widget_safe import safe_session_assign

        safe_session_assign(
            session_state,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            value,
            widget_safe=widget_safe,
        )
    except ImportError:
        session_state[SONG_PICKER_ACTIVE_SOURCE_KEY] = value


def sync_song_picker_source_widget(
    session_state: dict[str, Any],
    *,
    force: bool = False,
    widget_safe: bool = True,
) -> None:
    """Align Song Selection source radio with active_music_source (init or forced promotion only)."""
    if force:
        # Forced realign must follow ownership stamps, not the stale live radio
        # (Custom radio + catalog active_music_source after Catalog restore).
        active = str(session_state.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip()
        if (
            active in {SOURCE_CATALOG, "catalog", "regular_song"}
            or session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY)
        ):
            expected = SONG_PICKER_SOURCE_CATALOG
        elif active == SOURCE_CUSTOM:
            expected = SONG_PICKER_SOURCE_CUSTOM
        elif active == SOURCE_COMPOSITION:
            expected = song_picker_composition_option_label()
        else:
            expected = _expected_song_picker_source(session_state)
    else:
        expected = _expected_song_picker_source(session_state)
    current = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if not force:
        if current:
            return
        if current == expected:
            return
    elif current == expected:
        return
    _assign_song_picker_source_widget(session_state, expected, widget_safe=widget_safe)


def snapshot_current_catalog_state(session_state: dict[str, Any]) -> None:
    """Remember the active catalog song before switching to another catalog song."""
    if is_custom_progression(session_state):
        return
    try:
        from creative_key_sync import is_creative_catalog_pick_frozen

        if is_creative_catalog_pick_frozen(session_state):
            write_creative_catalog_guard_diag(
                session_state,
                last_catalog_song_writer="snapshot_current_catalog_state_blocked",
            )
            return
    except ImportError:
        pass
    snap = _catalog_snapshot_from_session(session_state)
    if snap:
        session_state[LAST_CATALOG_STATE_KEY] = snap
        write_creative_catalog_guard_diag(
            session_state,
            last_catalog_song_writer="snapshot_current_catalog_state",
        )


def push_catalog_recent_pick_key(session_state: dict[str, Any], pick_key: str) -> None:
    """Track recent catalog picks for Load last song / quick switch."""
    pk = str(pick_key or "").strip()
    if not pk or pk.startswith("custom::"):
        return
    recent = [k for k in (session_state.get(CATALOG_RECENT_PICK_KEYS) or []) if str(k).strip() != pk]
    recent.insert(0, pk)
    session_state[CATALOG_RECENT_PICK_KEYS] = recent[:5]


def _catalog_snapshot_for_pick_key(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> dict[str, Any] | None:
    """Build a catalog snapshot for a pick key (for recent-list fallback)."""
    pk = str(pick_key or "").strip()
    if not pk or pk.startswith("custom::"):
        return None
    for snap_key in (LAST_CATALOG_STATE_KEY, CATALOG_BEFORE_CUSTOM_KEY):
        raw = session_state.get(snap_key)
        if not isinstance(raw, dict):
            continue
        if str(raw.get("pick_key") or "").strip() == pk:
            return dict(raw)
    try:
        selected, original_key = resolve_catalog_song_for_pick(
            session_state,
            pk,
            song_picker_catalog=song_picker_catalog,
        )
    except Exception:
        return None
    if not selected:
        return None
    display_key = str(session_state.get("display_key") or original_key).strip() or original_key
    return {
        "pick_key": pk,
        "selected_song": dict(selected),
        "original_key": original_key,
        "display_key": display_key,
    }


def previous_catalog_snapshot(session_state: dict[str, Any]) -> dict[str, Any] | None:
    """Previous catalog song snapshot when it differs from the active catalog pick."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    current_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    snap = session_state.get(LAST_CATALOG_STATE_KEY)
    if isinstance(snap, dict):
        prev_pick = str(snap.get("pick_key") or "").strip()
        if prev_pick and not prev_pick.startswith("custom::") and prev_pick != current_pick:
            return snap
    for pick_key in session_state.get(CATALOG_RECENT_PICK_KEYS) or []:
        pk = str(pick_key or "").strip()
        if not pk or pk.startswith("custom::") or pk == current_pick:
            continue
        built = _catalog_snapshot_for_pick_key(session_state, pk)
        if built is not None:
            return built
    return None


def save_last_catalog_snapshot(session_state: dict[str, Any]) -> None:
    """Backward-compatible alias for snapshot_current_catalog_state."""
    snapshot_current_catalog_state(session_state)


def queue_previous_catalog_restore(st: Any) -> None:
    """Queue previous-catalog restore for before-widget application on the next rerun."""
    st.session_state[PENDING_PREVIOUS_CATALOG_RESTORE_KEY] = True


def apply_pending_previous_catalog_restore_before_widgets(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Apply queued previous-catalog restore before sidebar/global widgets render."""
    if not st.session_state.pop(PENDING_PREVIOUS_CATALOG_RESTORE_KEY, None):
        return False
    return restore_previous_catalog_song(
        st,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
        invalidate_backing=invalidate_backing,
    )


def restore_previous_catalog_song(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Restore the previous catalog song (browser-back style shortcut)."""
    snap = previous_catalog_snapshot(st.session_state)
    if not snap:
        return False
    pick_key = str(snap.get("pick_key") or "").strip()
    if not pick_key or pick_key.startswith("custom::"):
        return False
    ctx = activate_catalog_song_for_backing(
        st,
        pick_key,
        reason="previous_catalog_restore",
        invalidate_backing=invalidate_backing,
        song_picker_catalog=song_picker_catalog,
    )
    return ctx is not None


def restore_last_catalog_active_song(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Restore the catalog song active before Custom Progression mode."""
    session = st.session_state
    snap = session.get(CATALOG_BEFORE_CUSTOM_KEY) or session.get(LAST_CATALOG_STATE_KEY)
    if not isinstance(snap, dict) or not snap.get("pick_key"):
        return False
    pick_key = str(snap.get("pick_key") or "").strip()
    if not pick_key or pick_key.startswith("custom::"):
        return False
    ctx = activate_catalog_song_for_backing(
        st,
        pick_key,
        reason="last_catalog_restore",
        invalidate_backing=invalidate_backing,
        song_picker_catalog=song_picker_catalog,
    )
    return ctx is not None


def commit_catalog_active_song(
    st: Any,
    *,
    pick_key: str,
    selected_song: dict[str, Any],
    original_key: str,
    display_key: str,
    invalidate_backing,
    reason: str = "catalog_restore",
) -> None:
    """Promote a catalog song to the global active song and canonical blob."""
    from active_song_state import write_canonical_active_song_state
    from songs.playback_defaults import (
        active_song_sync_id,
        canonical_active_song_bpm,
        default_groove_for_song,
        get_song_default_meter,
        playback_song_id,
    )
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    session = st.session_state
    session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    set_catalog_source(session)
    pick_key = str(pick_key or "").strip()
    selected_song = dict(selected_song)
    _sync_catalog_session_surface_keys(session, pick_key=pick_key, selected_song=selected_song)
    original_key = str(original_key or selected_song.get("key") or "C").strip() or "C"
    display_key = str(display_key or original_key).strip() or original_key
    _reset_reasons = (
        "catalog_source_switch",
        "creative_to_catalog",
        "switch_to_catalog_backing",
        "last_catalog_restore",
        "previous_catalog_restore",
        "song_pick",
        "catalog_pick",
    )
    if reason in _reset_reasons:
        # Explicit Catalog source/song selection → original key (never restore
        # a previously modified Practice Key for this pick).
        try:
            from songs.practice_key_state import reset_practice_key_to_original_on_source_switch

            display_key = reset_practice_key_to_original_on_source_switch(
                session,
                pick_key=pick_key,
                original_key=original_key,
            )
        except ImportError:
            display_key = original_key
    lib_record = dict(selected_song)
    default_bpm = canonical_active_song_bpm(lib_record)
    default_groove = default_groove_for_song(lib_record, infer_fn=lambda _rec, _fb: "Auto")
    default_meter = get_song_default_meter(lib_record)
    _pid = playback_song_id(
        is_custom=False,
        song_title=str(selected_song.get("title") or ""),
        song_artist=str(selected_song.get("artist") or ""),
    )
    sync_id = active_song_sync_id(pick_key=str(pick_key or "").strip(), playback_song_id=_pid, is_custom=False)
    on_active_song_identity_changed(
        st,
        pick_key=str(pick_key or "").strip(),
        title=str(selected_song.get("title") or ""),
        artist=str(selected_song.get("artist") or ""),
        original_key=original_key,
        is_custom=False,
        sync_id=sync_id,
        default_bpm=default_bpm,
        default_groove=default_groove,
        default_meter=default_meter,
        display_key=display_key,
        song_data=lib_record,
        invalidate_backing=invalidate_backing,
        force_reset=reason
        in (
            "catalog_source_switch",
            "creative_to_catalog",
            "switch_to_catalog_backing",
            "last_catalog_restore",
            "previous_catalog_restore",
            "song_pick",
            "catalog_pick",
        ),
    )
    sync_song_picker_source_widget(session, force=True)
    note_active_source_change(st, invalidate_backing=invalidate_backing)
    ctx = {
        "pick_key": str(pick_key or "").strip(),
        "display_key": str(display_key or original_key).strip() or original_key,
        "instrument": str(session.get("instrument") or "").strip(),
        "level": str(session.get("level") or "").strip(),
        "focus": str(session.get("focus") or "").strip(),
        "selected_song": dict(selected_song),
        "music_source": SOURCE_CATALOG,
    }
    write_canonical_active_song_state(
        session,
        ctx,
        reason=reason,
        local_edit=True,
        mutate_display_key=False,
    )
    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st, save_reason="music_source_switch")
    except TypeError:
        try:
            from songs.state import persist_music_local_state

            # Older persist_music_local_state(**extra) signature — stash reason
            # on session for flush paths that read it.
            st.session_state["_music_persist_save_reason"] = "music_source_switch"
            persist_music_local_state(st)
        except ImportError:
            pass
    except ImportError:
        pass
    push_catalog_recent_pick_key(session, pick_key)
    pin_catalog_restore_identity(
        session,
        pick_key,
        selected_song,
        writer=reason,
    )


def switch_to_catalog_from_custom(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Leave Custom/Composition for the last catalog song (or current catalog pick)."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, apply_pick_key, first_valid_pick_key

    session = st.session_state
    leaving_creative = (
        is_custom_progression(session)
        or custom_progression_is_active(session)
        or composition_song_is_active(session)
        or is_composition_song(session)
        or str(session.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip()
        in {SOURCE_CUSTOM, SOURCE_COMPOSITION}
        or str(session.get(ACTIVE_CATALOG_PICK_KEY) or "")
        .strip()
        .startswith(("custom::", "composition::"))
    )
    if not leaving_creative:
        return False
    if is_custom_progression(session) or custom_progression_is_active(session):
        snapshot_last_custom_state(session)
    session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    # Drop Composition force-open so Songs→Backing cannot rebuild Composition.
    session.pop("_composition_hub_backing_clicked", None)
    session.pop("_composition_hub_backing_pending", None)
    clear_composition_one_shot_nav_flags(session)

    def _try_restore_from_snap(snap: dict[str, Any]) -> bool:
        pick_key = str(snap.get("pick_key") or "").strip()
        if not pick_key or pick_key.startswith("custom::"):
            return False
        selected = dict(snap.get("selected_song") or {})
        original_key = str(snap.get("original_key") or selected.get("key") or "C").strip() or "C"
        # Stale snap display_key (e.g. prior Custom E) must not win on catalog restore.
        display_key = original_key
        data = apply_pick_key(
            st,
            pick_key,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
        )
        if not data:
            return False
        selected.setdefault("title", str(data.get("title") or ""))
        selected.setdefault("artist", str(data.get("artist") or ""))
        selected.setdefault("key", str(data.get("key") or original_key))
        selected["pick_key"] = pick_key
        commit_catalog_active_song(
            st,
            pick_key=pick_key,
            selected_song=selected,
            original_key=original_key,
            display_key=display_key,
            invalidate_backing=invalidate_backing,
            reason="last_catalog_restore",
        )
        return True

    for snap_key in (LAST_CATALOG_STATE_KEY, CATALOG_BEFORE_CUSTOM_KEY):
        snap = session.get(snap_key)
        if isinstance(snap, dict) and _try_restore_from_snap(snap):
            return True

    for pick_key in session.get(CATALOG_RECENT_PICK_KEYS) or []:
        pk = str(pick_key or "").strip()
        if not pk or pk.startswith("custom::"):
            continue
        if _try_restore_from_snap({"pick_key": pk, "selected_song": {}, "original_key": "C", "display_key": "C"}):
            return True

    pick_key = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick_key and not pick_key.startswith("custom::"):
        data = apply_pick_key(
            st,
            pick_key,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
        )
        if data:
            original_key = str(data.get("key") or "C").strip() or "C"
            display_key = original_key
            commit_catalog_active_song(
                st,
                pick_key=pick_key,
                selected_song={
                    "pick_key": pick_key,
                    "title": str(data.get("title") or ""),
                    "artist": str(data.get("artist") or ""),
                    "key": original_key,
                },
                original_key=original_key,
                display_key=display_key,
                invalidate_backing=invalidate_backing,
                reason="catalog_source_switch",
            )
            return True

    fallback = first_valid_pick_key(song_picker_catalog)
    if fallback and _try_restore_from_snap(
        {"pick_key": fallback, "selected_song": {}, "original_key": "C", "display_key": "C"}
    ):
        return True

    set_catalog_source(session)
    sync_song_picker_source_widget(session, force=True)
    note_active_source_change(st, invalidate_backing=invalidate_backing)
    return True


def restore_last_custom_active_song(
    st: Any,
    *,
    invalidate_backing,
    reset_practice_to_original: bool = False,
) -> bool:
    """Restore the last custom progression when returning from catalog."""
    session = st.session_state
    snap = session.get(LAST_CUSTOM_STATE_KEY)
    if isinstance(snap, dict) and isinstance(snap.get("active"), dict):
        commit_custom_active_song(
            st,
            dict(snap["active"]),
            invalidate_backing=invalidate_backing,
            reset_practice_to_original=reset_practice_to_original,
        )
        return True
    try:
        from custom_progression_lab import cpl_active_from_session

        active = cpl_active_from_session(session)
        if str(active.get("name") or "").strip():
            commit_custom_active_song(
                st,
                active,
                invalidate_backing=invalidate_backing,
                reset_practice_to_original=reset_practice_to_original,
            )
            return True
    except Exception:
        pass
    return False


def apply_pending_catalog_from_picker_before_widgets(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> bool:
    """Apply catalog restore when the picker radio shows catalog while custom is still active."""
    if not st.session_state.pop(PENDING_CATALOG_FROM_PICKER_KEY, None):
        return False
    return switch_to_catalog_from_custom(
        st,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
        invalidate_backing=invalidate_backing,
    )


def ensure_composition_owns_active_song(
    st: Any,
    *,
    invalidate_backing=None,
) -> dict[str, Any] | None:
    """Make Composition the global active owner with generic ``My Composition`` / C.

    Safe to call from the Songs radio callback or Composition hub when the
    radio is on Composition but Catalog/Custom still owns the active song.
    """
    from composition_songs_bridge import (
        commit_composition_active_song,
        ensure_composition_library_hydrated,
        ensure_generic_composition_document,
        mark_composition_songs_source_ready,
        set_composition_source,
    )

    session = st.session_state
    # Explicit Songs radio switch sets this oneshot. Refresh / hub promote must
    # preserve a saved Composition Practice Key (same-source persistence).
    reset_pk = bool(session.pop("_composition_reset_practice_on_ensure", False))
    commit_explicit_music_source_choice(
        session,
        SOURCE_COMPOSITION,
        clear_composition_oneshots=False,
    )
    session.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
    ensure_composition_library_hydrated(session)
    mark_composition_songs_source_ready(session)
    set_composition_source(session)
    doc = ensure_generic_composition_document(session)
    try:
        commit_composition_active_song(
            st,
            doc,
            invalidate_backing=invalidate_backing,
            reset_practice_to_original=reset_pk,
        )
    except Exception as exc:
        # Keep source flag + doc even if identity commit fails mid-flight.
        session["_composition_ensure_commit_error"] = f"{type(exc).__name__}: {exc}"
        # Still stamp composition:: ownership so hub ready cannot stall on custom::.
        try:
            from composition_songs_bridge import (
                composition_pick_key_for,
                composition_selected_song_record,
            )
            from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

            selected = composition_selected_song_record(doc)
            pick_key = str(
                selected.get("pick_key") or composition_pick_key_for(doc) or ""
            ).strip()
            if pick_key:
                session[ACTIVE_CATALOG_PICK_KEY] = pick_key
                session[SELECTED_SONG_STATE_KEY] = selected
        except Exception:
            pass
        # Do not re-raise: ownership stamp above is enough for hub readiness;
        # key hydration retries on the next pre-widget rerun.
    _assign_song_picker_source_widget(
        session,
        song_picker_composition_option_label(),
    )
    # Final ownership guard — Custom refresh leftovers must never stick.
    try:
        from composition_songs_bridge import (
            composition_pick_key_for,
            composition_selected_song_record,
        )
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        live_pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
        if not live_pick.startswith("composition::"):
            selected = composition_selected_song_record(doc)
            pick_key = str(
                selected.get("pick_key") or composition_pick_key_for(doc) or ""
            ).strip()
            if pick_key:
                session[ACTIVE_CATALOG_PICK_KEY] = pick_key
                session[SELECTED_SONG_STATE_KEY] = selected
                session["_composition_ensure_forced_pick"] = pick_key
    except Exception:
        pass
    session.pop("_composition_ensure_commit_error", None)
    session["_composition_ensure_ok"] = {
        "pick": str(session.get("active_catalog_pick_key") or ""),
        "source": str(session.get(ACTIVE_MUSIC_SOURCE_KEY) or ""),
        "active": bool(composition_song_is_active(session)),
    }
    return doc


def on_song_picker_source_change(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> None:
    """Radio callback: switch catalog ↔ custom ↔ composition without post-render loops."""
    choice = str(st.session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if "Composition" in choice:
        # Commit stamp first so the same-rerun reconcile / open-backing cannot
        # reclaim Custom from a stale custom:: pick.
        commit_explicit_music_source_choice(
            st.session_state,
            SOURCE_COMPOSITION,
            clear_composition_oneshots=False,
        )
        # Mark explicit radio switch so ensure resets Practice Key to original.
        # Hub promote / refresh must not set this flag (same-source preserve).
        prior_pick = str(st.session_state.get("active_catalog_pick_key") or "").strip()
        if prior_pick and not prior_pick.startswith("composition::"):
            st.session_state["_composition_reset_practice_on_ensure"] = True
        try:
            ensure_composition_owns_active_song(
                st,
                invalidate_backing=invalidate_backing,
            )
        except Exception as exc:
            # Still force the widget label; hub promote retries ownership.
            st.session_state["_composition_radio_ensure_error"] = (
                f"{type(exc).__name__}: {exc}"
            )
            try:
                _assign_song_picker_source_widget(
                    st.session_state,
                    song_picker_composition_option_label(),
                )
            except Exception:
                pass
        else:
            st.session_state.pop("_composition_radio_ensure_error", None)
        st.rerun()
        return
    if choice.startswith("Use Custom"):
        # Intentional leave Composition — drop leftover/in-flight hub Backing
        # one-shots before commit so mid-run preserve cannot keep force-open.
        st.session_state.pop("_composition_hub_backing_clicked", None)
        st.session_state.pop("_force_composition_backing_open", None)
        st.session_state.pop("_composition_hub_backing_pending", None)
        commit_explicit_music_source_choice(st.session_state, SOURCE_CUSTOM)
        try:
            from custom_progression_lab import cpl_active_from_session

            set_custom_source(st.session_state)
            # Explicit radio → Custom: reset Practice Key to this progression's original.
            if not restore_last_custom_active_song(
                st,
                invalidate_backing=invalidate_backing,
                reset_practice_to_original=True,
            ):
                commit_custom_active_song(
                    st,
                    cpl_active_from_session(st.session_state),
                    invalidate_backing=invalidate_backing,
                    reset_practice_to_original=True,
                )
            else:
                # restore already committed; force a second persist if pick
                # still looks non-custom (defensive against partial restores).
                pick = str(st.session_state.get("active_catalog_pick_key") or "").strip()
                if not pick.startswith("custom::"):
                    commit_custom_active_song(
                        st,
                        cpl_active_from_session(st.session_state),
                        invalidate_backing=invalidate_backing,
                        reset_practice_to_original=True,
                    )
        except Exception:
            try:
                from custom_progression_lab import cpl_active_from_session

                set_custom_source(st.session_state)
                commit_custom_active_song(
                    st,
                    cpl_active_from_session(st.session_state),
                    invalidate_backing=invalidate_backing,
                    reset_practice_to_original=True,
                )
            except Exception:
                try:
                    from custom_progression_lab import cpl_active_from_session

                    queue_custom_active_song_activation(
                        st, cpl_active_from_session(st.session_state)
                    )
                except Exception:
                    pass
        st.rerun()
        return
    # Catalog — stamp before leaving_non_catalog detection so composition_active
    # does not stay True from a stale composition:: pick.
    # Intentional leave Composition — drop leftover/in-flight hub Backing one-shots
    # before commit (mid-run preserve must not keep force-open across Catalog radio).
    st.session_state.pop("_composition_hub_backing_clicked", None)
    st.session_state.pop("_force_composition_backing_open", None)
    st.session_state.pop("_composition_hub_backing_pending", None)
    commit_explicit_music_source_choice(st.session_state, SOURCE_CATALOG)
    leaving_non_catalog = (
        is_custom_progression(st.session_state)
        or custom_progression_is_active(st.session_state)
        or composition_song_is_active(st.session_state)
        or is_composition_song(st.session_state)
        or str(st.session_state.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip()
        in {SOURCE_CUSTOM, SOURCE_COMPOSITION}
        or str(st.session_state.get("active_catalog_pick_key") or "")
        .strip()
        .startswith(("custom::", "composition::"))
    )
    if leaving_non_catalog:
        switch_to_catalog_from_custom(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
            invalidate_backing=invalidate_backing,
        )
        st.rerun()


def reconcile_picker_music_source(session_state: dict[str, Any]) -> bool:
    """Align active source with Songs page picker widget before widgets render."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    page = str(
        session_state.get("studio_page") or session_state.get("page") or ""
    ).strip()
    if page != "picker":
        return reconcile_music_picker_source_widget(session_state)

    explicit = explicit_music_source_choice(session_state)
    choice_live = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    live_catalog_radio = choice_live == SONG_PICKER_SOURCE_CATALOG or (
        bool(choice_live)
        and choice_live.startswith("Song Selection")
        and "Composition" not in choice_live
    )
    live_custom_radio = choice_live.startswith("Use Custom")
    live_composition_radio = picker_choice_is_composition(choice_live)

    # Explicit Composition/Custom stamps outrank a stale catalog radio restored
    # from disk after reload (Composition refresh → Songs must not mount catalog hub).
    # Never reclaim Composition when the user explicitly chose Catalog or Custom.
    # Never overwrite a live Catalog/Custom radio while the Composition stamp still
    # lags one rerun (Composition → Catalog / Custom switch).
    if (
        not live_catalog_radio
        and not live_custom_radio
        and (
            explicit == SOURCE_COMPOSITION
            or (
                composition_song_is_active(session_state)
                and explicit not in (SOURCE_CATALOG, SOURCE_CUSTOM)
            )
        )
    ):
        session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
        if not picker_composition_mode(session_state):
            commit_explicit_music_source_choice(
                session_state,
                SOURCE_COMPOSITION,
                clear_composition_oneshots=False,
            )
            sync_song_picker_source_widget(session_state, force=True)
            return True
    if (
        not live_catalog_radio
        and not live_composition_radio
        and (
            explicit == SOURCE_CUSTOM
            or (
                custom_progression_is_active(session_state)
                and explicit not in (SOURCE_CATALOG, SOURCE_COMPOSITION)
            )
        )
    ):
        session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
        if not picker_custom_progression_mode(session_state):
            commit_explicit_music_source_choice(session_state, SOURCE_CUSTOM)
            set_custom_source(session_state)
            sync_song_picker_source_widget(session_state, force=True)
            return True

    # Live radio click with lagging explicit stamp — finish the switch.
    if live_catalog_radio and explicit != SOURCE_CATALOG:
        commit_explicit_music_source_choice(session_state, SOURCE_CATALOG)
        set_catalog_source(session_state)
        session_state[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        session_state[PENDING_CATALOG_FROM_PICKER_KEY] = True
        return True
    if live_custom_radio and explicit != SOURCE_CUSTOM:
        commit_explicit_music_source_choice(session_state, SOURCE_CUSTOM)
        set_custom_source(session_state)
        sync_song_picker_source_widget(session_state, force=True)
        return True
    if live_composition_radio and explicit != SOURCE_COMPOSITION:
        commit_explicit_music_source_choice(
            session_state,
            SOURCE_COMPOSITION,
            clear_composition_oneshots=False,
        )
        session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
        sync_song_picker_source_widget(session_state, force=True)
        return True

    user_catalog = bool(session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY))
    pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if explicit == SOURCE_CATALOG or user_catalog:
        choice_now = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
        # Live widget outranks a stale catalog stamp (USER_CATALOG blocks mode helpers).
        if picker_choice_is_composition(choice_now) or choice_now.startswith("Use Custom"):
            session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
            return reconcile_music_picker_source_widget(session_state)
        # Live Composition/Custom radio outranks a stale catalog stamp from disk
        # restore (reload after Composition refresh must not mount the catalog hub).
        if picker_composition_mode(session_state) or picker_custom_progression_mode(
            session_state
        ):
            return reconcile_music_picker_source_widget(session_state)
        # Catalog Backing → Songs can leave a stale composition:: pick or
        # Composition radio while explicit stamp is still Catalog.
        if (
            pick.startswith(("composition::", "custom::"))
            or composition_song_is_active(session_state)
            or is_composition_song(session_state)
            or custom_progression_is_active(session_state)
        ):
            commit_explicit_music_source_choice(session_state, SOURCE_CATALOG)
            set_catalog_source(session_state)
            sync_song_picker_source_widget(session_state, force=True)
            session_state[PENDING_CATALOG_FROM_PICKER_KEY] = True
            return True

    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if choice.startswith("Use Custom") and not is_custom_progression(session_state):
        commit_explicit_music_source_choice(session_state, SOURCE_CUSTOM)
        set_custom_source(session_state)
        _assign_song_picker_source_widget(session_state, SONG_PICKER_SOURCE_CUSTOM)
        return True
    if picker_choice_is_composition(choice) and not is_composition_song(session_state):
        commit_explicit_music_source_choice(
            session_state,
            SOURCE_COMPOSITION,
            clear_composition_oneshots=False,
        )
        session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
        _assign_song_picker_source_widget(
            session_state,
            song_picker_composition_option_label(),
        )
        return True
    return reconcile_music_picker_source_widget(session_state)


def custom_original_key(active: dict[str, Any]) -> str:
    """User-chosen CPL original key (never inferred from chord analysis)."""
    from custom_progression_lab import cpl_draft_written_key, ensure_original_structure

    return cpl_draft_written_key(ensure_original_structure(active))


def _catalog_original_key_for_session(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
) -> str:
    """Original/home key from active pick identity — not a stale card record."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    selected = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY)
        or selected.get("pick_key")
        or ""
    ).strip()
    selected_pick = str(selected.get("pick_key") or "").strip()
    if pick_key and selected_pick == pick_key and selected.get("key"):
        return str(selected.get("key") or "C").strip() or "C"
    record = rec or {}
    if record.get("key"):
        return str(record.get("key") or "C").strip() or "C"
    return str(selected.get("key") or "C").strip() or "C"


def resolve_active_song_keys(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
) -> tuple[str, str, str | None]:
    """Single source of truth: original, display/practice, optional written chart key."""
    from songs.key_state import get_authoritative_display_key, trace_display_key_surface

    if cpl_session_is_active(session_state):
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            default_active_progression,
            ensure_original_structure,
        )

        active = ensure_original_structure(
            session_state.get(CPL_ACTIVE_KEY) or default_active_progression()
        )
        original = custom_original_key(active)
        display = get_authoritative_display_key(
            session_state,
            original_key=original,
            surface="song_card",
        )
    else:
        original = _catalog_original_key_for_session(session_state, rec)
        display = get_authoritative_display_key(
            session_state,
            original_key=original,
            surface="song_card",
        )
    trace_display_key_surface(
        session_state,
        "song_card",
        display,
        source="resolve_active_song_keys",
    )
    from instrument_transposition import (
        chart_in_instrument_key,
        effective_chart_key,
        is_transposing_instrument,
    )

    written: str | None = None
    inst = str(session_state.get("instrument") or "Piano")
    if is_transposing_instrument(inst) and chart_in_instrument_key(session_state):
        chart_k, _ = effective_chart_key(display, inst, session_state)
        written = chart_k
    return original, display, written


def active_song_key_pair(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Original key and Practice / Concert key for Active Song cards.

    For chart/coach/analysis surfaces use ``resolve_active_musical_key()`` instead
    (written or guitar shape key when those modes are active).
    """
    original, display, _written = resolve_active_song_keys(session_state, rec)
    return original, display


def active_song_musical_key(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
    *,
    instrument: str | None = None,
    surface: str = "song_card",
) -> str:
    """Chart/analysis key honoring written-instrument and guitar capo shape modes."""
    from songs.key_state import resolve_active_musical_key

    return resolve_active_musical_key(
        session_state,
        rec=rec,
        instrument=instrument,
        surface=surface,
    ).chart_key


def active_song_written_chart_key(
    session_state: dict[str, Any],
    *,
    display_key: str | None = None,
) -> str | None:
    """Written/shape chart key for cards — transposing instrument or guitar capo shape."""
    from instrument_transposition import (
        chart_in_instrument_key,
        effective_chart_key,
        is_transposing_instrument,
    )

    _, display = active_song_key_pair(session_state)
    concert = str(display_key or display or "C").strip() or "C"
    inst = str(session_state.get("instrument") or "Piano")
    if is_transposing_instrument(inst) and chart_in_instrument_key(session_state):
        chart_k, _ = effective_chart_key(concert, inst, session_state)
        return chart_k
    try:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        if inst == "Guitar" and session_state.get(CAPO_ENABLED_KEY):
            shape = str(session_state.get(CAPO_SHAPE_KEY) or "").strip()
            if shape:
                return shape
    except ImportError:
        pass
    return None


def note_active_source_change(st: Any, *, invalidate_backing) -> bool:
    """Invalidate backing/chart caches when active song source or pick changes."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    from .playback_defaults import reset_playback_song_tracking

    session_state = st.session_state
    current_source = session_state.get(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)
    previous_source = session_state.get(_LAST_SOURCE_KEY)
    current_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    previous_pick = session_state.get(_LAST_ACTIVE_PICK_KEY)

    session_state[_LAST_SOURCE_KEY] = current_source
    session_state[_LAST_ACTIVE_PICK_KEY] = current_pick

    source_changed = previous_source is not None and previous_source != current_source
    pick_changed = previous_pick is not None and previous_pick != current_pick
    if source_changed or pick_changed:
        reset_playback_song_tracking(st)
        invalidate_backing(st)
        try:
            from studio_cache import invalidate_session_cache

            invalidate_session_cache(session_state, "chart_bundle")
        except Exception:
            pass
        return True
    return False


ACTIVE_SONG_IDENTITY_KEY = "_active_song_identity"
PREVIOUS_ACTIVE_SONG_IDENTITY_KEY = "_previous_active_song_identity"
SONG_IDENTITY_DIAG_KEY = "_song_identity_diag"


def compute_active_song_identity(
    *,
    pick_key: str = "",
    title: str = "",
    artist: str = "",
    original_key: str = "",
    is_custom: bool = False,
    custom_revision: str = "",
) -> str:
    """Stable identity string for catalog pick_key or custom progression revision."""
    pk = str(pick_key or "").strip()
    if is_custom or pk.startswith("custom::"):
        rev = str(custom_revision or "").strip()
        if rev:
            return f"cpl::{rev}"
        if pk:
            return f"cpl::{pk}"
        return f"cpl::{title}|{artist}|{original_key}"
    if pk:
        return f"pk::{pk}"
    return f"cat::{title}|{artist}|{original_key}"


def on_active_song_identity_changed(
    st: Any,
    *,
    pick_key: str,
    title: str,
    artist: str,
    original_key: str,
    is_custom: bool,
    sync_id: str,
    default_bpm: int,
    default_groove: str,
    default_meter: str,
    display_key: str | None = None,
    custom_revision: str = "",
    song_data: dict[str, Any] | None = None,
    invalidate_backing,
    force_reset: bool = False,
) -> bool:
    """Reset display key and backing defaults when the active song identity changes.

    Must run before widget-bound session keys (``display_key``, BPM slider, etc.)
    are instantiated for the rerun.
    """
    from songs.key_state import apply_display_key_for_active_song, song_display_identity
    from songs.playback_defaults import (
        canonicalize_backing_defaults_for_song,
        prime_active_song_bpm,
        reset_playback_song_tracking,
    )

    session = st.session_state
    new_identity = compute_active_song_identity(
        pick_key=pick_key,
        title=title,
        artist=artist,
        original_key=original_key,
        is_custom=is_custom,
        custom_revision=custom_revision,
    )
    prev_identity = session.get(ACTIVE_SONG_IDENTITY_KEY)
    session[PREVIOUS_ACTIVE_SONG_IDENTITY_KEY] = prev_identity
    identity_changed = force_reset or (
        prev_identity is not None and prev_identity != new_identity
    )

    if identity_changed:
        try:
            from songs.key_state import PENDING_DISPLAY_KEY

            session.pop(PENDING_DISPLAY_KEY, None)
        except ImportError:
            pass
        try:
            from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY

            session.pop(DISPLAY_KEY_CHANGE_SOURCE_KEY, None)
        except ImportError:
            pass
        target_display = str(display_key if display_key is not None else original_key).strip() or original_key
        if display_key is None:
            try:
                from practice_key_mode import resolve_practice_concert_key_for_song

                target_display = resolve_practice_concert_key_for_song(
                    session,
                    original_key,
                    pick_key=pick_key,
                    fallback=target_display,
                )
            except ImportError:
                pass
        song_identity = song_display_identity(title, artist, original_key, pick_key=pick_key)
        apply_display_key_for_active_song(
            st,
            original_key,
            song_identity,
            pending_key=target_display,
        )
        try:
            from session_widget_safe import reconcile_practice_key_fields

            reconcile_practice_key_fields(session, authoritative=target_display)
        except ImportError:
            pass
        try:
            from backing_source_navigation import PRACTICE_SOURCE_DISPLAY_KEY, PRACTICE_SOURCE_PICK_KEY

            session[PRACTICE_SOURCE_DISPLAY_KEY] = target_display
            session[PRACTICE_SOURCE_PICK_KEY] = pick_key
        except ImportError:
            pass
        reset_playback_song_tracking(st)
        invalidate_backing(st)
        try:
            from songs.bpm_state import LAST_BPM_SONG

            session.pop(LAST_BPM_SONG, None)
        except ImportError:
            session.pop("_last_bpm_song", None)
        session.pop("last_backing_defaults_song_id", None)
        try:
            from studio_cache import invalidate_session_cache

            invalidate_session_cache(session, "chart_bundle")
        except Exception:
            pass
        prime_active_song_bpm(st, sync_id=sync_id, active_song_bpm=int(default_bpm))
        canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=int(default_bpm),
            active_song_groove=str(default_groove),
            active_song_meter=str(default_meter),
        )

    if identity_changed:
        try:
            from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY

            session.pop(DISPLAY_KEY_OWNER_IDENTITY_KEY, None)
        except ImportError:
            pass

    session[ACTIVE_SONG_IDENTITY_KEY] = new_identity
    try:
        from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY

        last_change_source = session.get(DISPLAY_KEY_CHANGE_SOURCE_KEY)
    except ImportError:
        last_change_source = None
    session[SONG_IDENTITY_DIAG_KEY] = {
        "active_song_id": new_identity,
        "active_song_identity": new_identity,
        "previous_active_song_identity": prev_identity,
        "active_music_source": SOURCE_CUSTOM if is_custom else SOURCE_CATALOG,
        "song_source": SOURCE_CUSTOM if is_custom else SOURCE_CATALOG,
        "pick_key": pick_key,
        "original_key": original_key,
        "practice_display_key": session.get("display_key"),
        "display_key": session.get("display_key"),
        "last_song_change_source": last_change_source,
        "default_bpm": default_bpm,
        "backing_bpm": session.get("backing_track_bpm"),
        "default_style": default_groove,
        "backing_groove": session.get("backing_groove_style"),
        "default_meter": default_meter,
        "backing_meter": session.get("backing_time_signature"),
        "identity_changed": identity_changed,
    }
    if identity_changed:
        try:
            from backing_context import reset_backing_on_active_song_change

            reset_backing_on_active_song_change(
                session,
                new_pick_key=pick_key,
                practice_concert_key=target_display,
            )
        except ImportError:
            pass
    return identity_changed


def active_source_labels(
    session_state: dict[str, Any],
    *,
    catalog_title: str,
    catalog_artist: str,
    custom_name: str,
) -> tuple[str, str]:
    """Return ``(source_kind, source_detail)`` for the sidebar active-source banner.

    Composition detail comes from the Composition document — never a leftover
    Custom/Catalog title such as ``My Progression``.
    """
    if composition_song_is_active(session_state) or is_composition_song(session_state):
        title = ""
        try:
            from composition_session_state import get_active_document
            from composition_songs_bridge import (
                composition_title,
                ensure_generic_composition_document,
                find_composition_document,
            )

            doc = get_active_document(session_state)
            if not isinstance(doc, dict):
                pick = str(session_state.get("active_catalog_pick_key") or "").strip()
                doc = find_composition_document(session_state, pick) if pick else None
            if not isinstance(doc, dict):
                doc = ensure_generic_composition_document(session_state)
            title = composition_title(doc) if isinstance(doc, dict) else ""
        except Exception:
            title = ""
        if not title:
            sel = session_state.get("selected_song")
            if isinstance(sel, dict) and sel.get("is_composition"):
                title = str(sel.get("title") or "").strip()
        return "Composition", title or "My Composition"
    if is_custom_progression(session_state) or custom_progression_is_active(session_state):
        return "Custom Progression", str(custom_name or "Custom Progression")
    title = str(catalog_title or "").strip()
    artist = str(catalog_artist or "").strip()
    detail = f"{title} — {artist}".strip(" —") if title or artist else ""
    return "Song", detail


def _parse_legacy_active_source_markdown(text: str) -> tuple[str, str]:
    """Older builds returned one markdown string (``Song Picker — title — artist``)."""
    raw = str(text or "").replace("**", "").strip()
    if raw.lower().startswith("active source:"):
        raw = raw.split(":", 1)[1].strip()
    parts = [p.strip() for p in raw.split("—") if p.strip()]
    if not parts:
        return "Song", ""
    kind = parts[0].replace("Song Picker", "Song").strip() or "Song"
    detail = " — ".join(parts[1:]) if len(parts) > 1 else ""
    return kind, detail


def unpack_active_source_banner(result: Any) -> tuple[str, str]:
    """Normalize banner return value to exactly ``(kind, detail)``."""
    if isinstance(result, tuple):
        if len(result) >= 2:
            return str(result[0]), str(result[1])
        if len(result) == 1:
            return str(result[0]), ""
        return "Song", ""
    if isinstance(result, str):
        return _parse_legacy_active_source_markdown(result)
    if result is None:
        return "Song", ""
    return "Song", str(result)


def active_source_banner(
    session_state: dict[str, Any],
    *,
    catalog_title: str,
    catalog_artist: str,
    custom_name: str,
) -> tuple[str, str]:
    """Return ``(source_kind, source_detail)`` — always a 2-tuple (never markdown)."""
    kind, detail = active_source_labels(
        session_state,
        catalog_title=catalog_title,
        catalog_artist=catalog_artist,
        custom_name=custom_name,
    )
    return (str(kind), str(detail))


def display_key_context(
    session_state: dict[str, Any],
    *,
    catalog_song_data: dict[str, Any],
    cpl_active_key: str,
) -> tuple[str, tuple]:
    """Original/home key and identity tuple for the global display-key widget."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    # Composition must resolve before Custom/CPL leftovers — a lingering
    # custom:: pick or CPL blob must not own the Practice Key identity.
    if (
        composition_song_is_active(session_state)
        or is_composition_song(session_state)
        or picker_composition_mode(session_state)
        or explicit_music_source_choice(session_state) == SOURCE_COMPOSITION
    ):
        from songs.key_state import song_display_identity

        home = "C"
        title = "My Composition"
        pick_key = str(
            session_state.get(ACTIVE_CATALOG_PICK_KEY)
            or (session_state.get(SELECTED_SONG_STATE_KEY) or {}).get("pick_key")
            or ""
        ).strip()
        try:
            from composition_session_state import get_active_document
            from composition_songs_bridge import (
                composition_home_key,
                composition_pick_key_for,
                composition_title,
                ensure_generic_composition_document,
                find_composition_document,
            )

            doc = get_active_document(session_state)
            if not isinstance(doc, dict) and pick_key.startswith("composition::"):
                doc = find_composition_document(session_state, pick_key)
            if not isinstance(doc, dict):
                doc = ensure_generic_composition_document(session_state)
            home = composition_home_key(doc)
            title = composition_title(doc)
            pick_key = composition_pick_key_for(doc) or pick_key
        except Exception:
            pass
        return home, song_display_identity(
            str(title),
            "Composition",
            home,
            pick_key=pick_key,
        )

    if custom_progression_is_active(session_state) or cpl_session_is_active(session_state):
        from custom_progression_lab import (
            default_active_progression,
            ensure_original_structure,
        )

        ensure_custom_active_song_identity(session_state, cpl_active_key=cpl_active_key)
        active = ensure_original_structure(
            session_state.get(cpl_active_key) or default_active_progression()
        )
        home = custom_original_key(active)
        title = active.get("name", "Custom Progression")
        pick_key = str(
            session_state.get(ACTIVE_CATALOG_PICK_KEY)
            or (session_state.get(SELECTED_SONG_STATE_KEY) or {}).get("pick_key")
            or ""
        ).strip()
        from songs.key_state import song_display_identity

        return home, song_display_identity(
            str(title),
            "Custom progression",
            home,
            pick_key=pick_key,
        )

    original = catalog_song_data.get("key", "C")
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY)
        or (session_state.get(SELECTED_SONG_STATE_KEY) or {}).get("pick_key")
        or ""
    ).strip()
    from songs.key_state import song_display_identity

    return original, song_display_identity(
        str(catalog_song_data.get("title") or ""),
        str(catalog_song_data.get("artist") or ""),
        str(original),
        pick_key=pick_key,
    )


def custom_pick_key_for(active: dict[str, Any]) -> str:
    """Stable session pick_key for a custom progression (not a catalog pk:: id)."""
    title = str(active.get("name") or "My Progression").strip() or "My Progression"
    rev = str(active.get("id") or "").strip()
    if rev:
        return f"custom::{rev}"
    safe = title.replace(":", "_").replace("/", "_")[:80]
    return f"custom::{safe}"


def _custom_pick_key_suffix(pick_key: str) -> str:
    return str(pick_key or "").strip().removeprefix("custom::").strip()


def _title_from_custom_blob(blob: dict[str, Any], store_name: str = "") -> tuple[str, str]:
    title = str(blob.get("name") or store_name or "").strip()
    artist = str(blob.get("artist") or "Your progression").strip() or "Your progression"
    return title, artist


def custom_display_title_for_pick_key(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    fallback_title: str = "",
    cpl_active_key: str = "cpl_active_progression",
    cpl_saved_key: str = "cpl_saved_progressions",
) -> str:
    """User-facing title for a custom song (never an internal id/code)."""
    from custom_progression_lab import default_active_progression, ensure_original_structure
    from songs.state import SELECTED_SONG_STATE_KEY

    pk = str(pick_key or "").strip()
    fb = str(fallback_title or "").strip()
    if not pk.startswith("custom::"):
        return fb
    suffix = _custom_pick_key_suffix(pk)
    if fb and not fb.startswith("custom::") and fb != suffix:
        return fb

    sel = session_state.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict) and str(sel.get("pick_key") or "").strip() == pk:
        title = str(sel.get("title") or "").strip()
        if title and title != suffix:
            return title

    active = ensure_original_structure(
        session_state.get(cpl_active_key) or default_active_progression()
    )
    active_id = str(active.get("id") or "").strip()
    active_name = str(active.get("name") or "").strip()
    if active_id and suffix == active_id and active_name:
        return active_name
    if active_name and suffix == active_name.replace(":", "_").replace("/", "_")[:80]:
        return active_name

    saved = session_state.get(cpl_saved_key) or {}
    if isinstance(saved, dict):
        for store_name, blob in saved.items():
            if not isinstance(blob, dict):
                continue
            blob_id = str(blob.get("id") or "").strip()
            blob_name = str(blob.get("name") or store_name).strip()
            if suffix and (suffix == blob_id or suffix == blob_name or suffix == store_name):
                return blob_name or store_name

    meta = session_state.get("active_song_state")
    if isinstance(meta, dict) and str(meta.get("pick_key") or "").strip() == pk:
        title = str(meta.get("custom_progression_name") or meta.get("title") or "").strip()
        if title and title != suffix:
            return title

    if suffix and " " in suffix.replace("_", " "):
        return suffix.replace("_", " ")
    return active_name or fb or "My Progression"


def custom_display_artist_for_pick_key(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    fallback_artist: str = "",
    cpl_active_key: str = "cpl_active_progression",
    cpl_saved_key: str = "cpl_saved_progressions",
) -> str:
    """User-facing artist for a custom song pick_key."""
    from custom_progression_lab import default_active_progression, ensure_original_structure

    pk = str(pick_key or "").strip()
    fb = str(fallback_artist or "").strip() or "Your progression"
    if not pk.startswith("custom::"):
        return fb
    suffix = _custom_pick_key_suffix(pk)

    active = ensure_original_structure(
        session_state.get(cpl_active_key) or default_active_progression()
    )
    active_id = str(active.get("id") or "").strip()
    if active_id and suffix == active_id:
        return str(active.get("artist") or fb).strip() or fb

    saved = session_state.get(cpl_saved_key) or {}
    if isinstance(saved, dict):
        for store_name, blob in saved.items():
            if not isinstance(blob, dict):
                continue
            blob_id = str(blob.get("id") or "").strip()
            blob_name = str(blob.get("name") or store_name).strip()
            if suffix and (suffix == blob_id or suffix == blob_name or suffix == store_name):
                return _title_from_custom_blob(blob, store_name)[1]

    return fb


def _push_recent_custom_name(session_state: dict[str, Any], name: str) -> None:
    label = str(name or "").strip()
    if not label:
        return
    recent = [
        str(n).strip()
        for n in (session_state.get(CUSTOM_RECENT_ACTIVE_NAMES_KEY) or [])
        if str(n).strip()
    ]
    if label in recent:
        recent.remove(label)
    recent.insert(0, label)
    session_state[CUSTOM_RECENT_ACTIVE_NAMES_KEY] = recent[:8]


def custom_song_data_from_active(active: dict[str, Any]) -> dict[str, Any]:
    """Catalog-shaped song row for charts/backing when Custom Progression is active."""
    from custom_progression_lab import (
        cpl_draft_written_key,
        ensure_original_structure,
        sections_to_chord_lists,
    )

    active = ensure_original_structure(active)
    title = str(active.get("name") or "My Progression")
    home_key = cpl_draft_written_key(active)
    artist = str(active.get("artist") or "").strip()
    sections = sections_to_chord_lists(active.get("original_sections") or {})
    style = str(active.get("progression_style") or "Custom")
    bpm = int(active.get("bpm") or 100)
    groove = str(active.get("groove_style") or "Auto")
    meter = str(active.get("time_signature") or "4/4")
    return {
        "title": title,
        "artist": artist or "Your progression",
        "genre": "Custom",
        "key": home_key,
        "sections": sections,
        "chart_versions": {
            "Beginner": sections,
            "Intermediate": sections,
            "Advanced": sections,
        },
        "chart_status": "custom",
        "extensions": {
            "default_bpm": bpm,
            "default_groove": groove,
            "time_signature": meter,
            "arrangement_notes": f"Custom progression — {style} feel",
        },
    }


def custom_song_context_from_session(
    session_state: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
) -> tuple[str, str, dict[str, Any]]:
    """Return (genre, title, song_data) for an active Custom Progression song."""
    from custom_progression_lab import default_active_progression, ensure_original_structure

    active = ensure_original_structure(
        session_state.get(cpl_active_key) or default_active_progression()
    )
    song_data = custom_song_data_from_active(active)
    return "Custom", str(song_data.get("title") or "My Progression"), song_data


def composition_song_context_from_session(
    session_state: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    """Return (genre, title, song_data) for the active Composition document.

    Never returns Custom/Catalog leftovers by title matching.
    """
    from composition_session_state import get_active_document
    from composition_songs_bridge import (
        composition_as_chart_active,
        composition_home_key,
        composition_title,
        ensure_generic_composition_document,
        find_composition_document,
    )

    pick = str(session_state.get("active_catalog_pick_key") or "").strip()
    doc = get_active_document(session_state)
    if not isinstance(doc, dict) and pick.startswith("composition::"):
        doc = find_composition_document(session_state, pick)
    if not isinstance(doc, dict):
        doc = ensure_generic_composition_document(session_state)
    title = composition_title(doc)
    try:
        song_data = composition_as_chart_active(doc)
    except Exception:
        song_data = {
            "title": title,
            "artist": "Composition",
            "key": composition_home_key(doc),
            "source": SOURCE_COMPOSITION,
            "is_composition": True,
        }
    if not isinstance(song_data, dict):
        song_data = {}
    song_data = dict(song_data)
    if "title" not in song_data and song_data.get("name"):
        song_data["title"] = song_data["name"]
    song_data.setdefault("title", title)
    song_data.setdefault("artist", "Composition")
    song_data.setdefault("key", composition_home_key(doc))
    song_data["source"] = SOURCE_COMPOSITION
    song_data["is_composition"] = True
    song_data["is_custom"] = False
    return "Composition", title, song_data


def custom_selected_song_record(active: dict[str, Any]) -> dict[str, Any]:
    """Sidebar/global ``selected_song`` shape for an active custom progression."""
    from custom_progression_lab import ensure_original_structure

    active = ensure_original_structure(active)
    home_key = custom_original_key(active)
    title = str(active.get("name") or "My Progression").strip() or "My Progression"
    artist = str(active.get("artist") or "Your progression").strip() or "Your progression"
    pick_key = custom_pick_key_for(active)
    return {
        "pick_key": pick_key,
        "title": title,
        "artist": artist,
        "key": home_key,
        "source": SOURCE_CUSTOM,
        "is_custom": True,
    }


def ensure_custom_active_song_identity(
    session_state: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
) -> dict[str, Any] | None:
    """Sync CPL pick_key, selected_song, and active identity before key widgets resolve."""
    if not cpl_session_is_active(session_state):
        return None
    try:
        from custom_progression_lab import default_active_progression, ensure_original_structure
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        return None

    active_raw = session_state.get(cpl_active_key)
    if active_raw is None:
        selected = session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(selected, dict) and str(selected.get("pick_key") or "").strip():
            return selected
        return None

    active = ensure_original_structure(active_raw or default_active_progression())
    selected = custom_selected_song_record(active)
    pick_key = str(selected.get("pick_key") or "").strip()
    existing_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if not existing_pick.startswith("custom::"):
        selected_state = session_state.get(SELECTED_SONG_STATE_KEY) or {}
        existing_pick = str(selected_state.get("pick_key") or "").strip()
    if not existing_pick.startswith("custom::"):
        try:
            from active_song_state import ACTIVE_SONG_STATE_KEY

            meta = session_state.get(ACTIVE_SONG_STATE_KEY)
            if isinstance(meta, dict):
                existing_pick = str(meta.get("pick_key") or "").strip()
        except ImportError:
            pass
    if existing_pick.startswith("custom::"):
        pick_key = existing_pick
        selected = {**selected, "pick_key": pick_key}
    if pick_key:
        session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key
    session_state[SELECTED_SONG_STATE_KEY] = selected
    identity = compute_active_song_identity(
        pick_key=pick_key,
        title=str(selected.get("title") or ""),
        artist=str(selected.get("artist") or ""),
        original_key=str(selected.get("key") or "C"),
        is_custom=True,
        custom_revision=str(active.get("id") or ""),
    )
    session_state[ACTIVE_SONG_IDENTITY_KEY] = identity
    return selected


def resolve_active_song_identity(
    session_state: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
) -> str:
    """Recompute stable identity for display-key ownership (CPL-aware)."""
    try:
        from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY
    except ImportError:
        DISPLAY_KEY_OWNER_IDENTITY_KEY = "_display_key_owner_identity"

    owner = str(session_state.get(DISPLAY_KEY_OWNER_IDENTITY_KEY) or "").strip()
    cached = str(session_state.get(ACTIVE_SONG_IDENTITY_KEY) or "").strip()
    if owner and cached and owner == cached:
        return cached

    if cpl_session_is_active(session_state):
        ensure_custom_active_song_identity(session_state, cpl_active_key=cpl_active_key)
        identity = str(session_state.get(ACTIVE_SONG_IDENTITY_KEY) or "").strip()
        if identity:
            return identity
        try:
            from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
        except ImportError:
            return cached
        selected = session_state.get(SELECTED_SONG_STATE_KEY) or {}
        pick_key = str(
            session_state.get(ACTIVE_CATALOG_PICK_KEY) or selected.get("pick_key") or ""
        ).strip()
        return compute_active_song_identity(
            pick_key=pick_key,
            title=str(selected.get("title") or ""),
            artist=str(selected.get("artist") or ""),
            original_key=str(selected.get("key") or "C"),
            is_custom=True,
            custom_revision="",
        )

    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        return cached

    selected = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY) or selected.get("pick_key") or ""
    ).strip()
    return compute_active_song_identity(
        pick_key=pick_key,
        title=str(selected.get("title") or ""),
        artist=str(selected.get("artist") or ""),
        original_key=str(selected.get("key") or "C"),
        is_custom=False,
    )


def queue_custom_active_song_activation(
    st: Any,
    active: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
    toast_title: str | None = None,
) -> None:
    """Queue CPL activation for the next run (before sidebar/global widgets render)."""
    from custom_progression_lab import ensure_all_cpl_sections, ensure_original_structure

    session = st.session_state
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active
    payload: dict[str, Any] = {"cpl_active_key": cpl_active_key}
    if toast_title:
        payload["toast_title"] = str(toast_title).strip()
    session[PENDING_CUSTOM_ACTIVE_SONG_KEY] = payload


def queue_custom_library_action(
    st: Any,
    *,
    name: str = "",
    action: str = "activate",
) -> None:
    """Queue saved custom song load/activate/edit for before-widget application."""
    payload: dict[str, Any] = {"action": str(action or "activate").strip()}
    label = str(name or "").strip()
    if label:
        payload["name"] = label
    st.session_state[PENDING_CUSTOM_LIBRARY_ACTION_KEY] = payload


def apply_pending_custom_library_action_before_widgets(
    st: Any,
    *,
    invalidate_backing,
) -> bool:
    """Load a saved custom song (or reseed active) before sidebar/global widgets render."""
    session = st.session_state
    pending = session.pop(PENDING_CUSTOM_LIBRARY_ACTION_KEY, None)
    if not isinstance(pending, dict):
        return False
    action = str(pending.get("action") or "activate").strip()
    from custom_progression_lab import (
        CPL_SAVED_KEY,
        apply_cpl_session_progression,
        cpl_active_from_session,
        load_saved_progression,
        start_new_progression,
    )

    if action == "edit_active":
        active = cpl_active_from_session(session)
    elif action == "new_song":
        active = start_new_progression()
    else:
        name = str(pending.get("name") or "").strip()
        if not name:
            return False
        saved = session.get(CPL_SAVED_KEY) or {}
        active = load_saved_progression(saved, name)

    apply_cpl_session_progression(session, active, reset_display_key=True)

    if action == "activate":
        song_name = str(pending.get("name") or active.get("name") or "").strip()
        commit_custom_active_song(st, active, invalidate_backing=invalidate_backing)
        if song_name:
            session["_cpl_activation_toast"] = song_name
        session["_custom_active_song_applied_this_run"] = True
    elif action in ("edit", "edit_active", "new_song"):
        try:
            from studio_nav_history import navigate_studio_page

            navigate_studio_page(session, "custom")
        except ImportError:
            session["studio_page"] = "custom"

    session["_custom_library_action_applied_this_run"] = True
    return True


def apply_pending_custom_active_song_activation_before_widgets(
    st: Any,
    *,
    invalidate_backing,
) -> bool:
    """Apply queued CPL activation before any widget-bound session keys are touched."""
    session = st.session_state
    pending = session.pop(PENDING_CUSTOM_ACTIVE_SONG_KEY, None)
    if not isinstance(pending, dict):
        return False
    cpl_active_key = str(pending.get("cpl_active_key") or "cpl_active_progression").strip()
    active = session.get(cpl_active_key)
    if not isinstance(active, dict):
        return False
    commit_custom_active_song(
        st,
        active,
        cpl_active_key=cpl_active_key,
        invalidate_backing=invalidate_backing,
    )
    toast_title = str(pending.get("toast_title") or "").strip()
    if toast_title:
        session["_cpl_activation_toast"] = toast_title
    session["_custom_active_song_applied_this_run"] = True
    return True


def commit_custom_active_song(
    st: Any,
    active: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
    invalidate_backing,
    reset_practice_to_original: bool = False,
) -> dict[str, Any]:
    """Promote CPL draft to the global active song (source, title, key, playback, cloud).

    Must run before sidebar/global widgets render. Use ``queue_custom_active_song_activation``
    from page callbacks, then ``apply_pending_custom_active_song_activation_before_widgets``
    at app startup.

    ``reset_practice_to_original``: True on explicit Catalog/Custom/Composition or
    song switch — clears saved Practice Key and uses the progression's original key.
    False for same-source refresh / hub disk sync (preserve current Practice Key).
    """
    from custom_progression_lab import (
        ensure_all_cpl_sections,
        ensure_original_structure,
        prepare_cpl_backing_handoff,
        cpl_draft_written_key,
        cpl_default_groove_for_active,
    )
    from songs.playback_defaults import (
        active_song_sync_id,
        canonical_active_song_bpm,
        get_song_default_meter,
        normalize_groove_label,
        playback_song_id,
    )
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    session = st.session_state
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active
    _push_recent_custom_name(session, str(active.get("name") or "My Progression"))
    snapshot_last_custom_state(session)

    home_key = cpl_draft_written_key(active)
    selected = custom_selected_song_record(active)
    pick_key = str(selected.get("pick_key") or "").strip()
    practice_key = home_key
    if reset_practice_to_original:
        try:
            from songs.practice_key_state import reset_practice_key_to_original_on_source_switch

            practice_key = reset_practice_key_to_original_on_source_switch(
                session,
                pick_key=pick_key,
                original_key=home_key,
            )
        except ImportError:
            practice_key = home_key
    else:
        try:
            from practice_key_mode import resolve_practice_concert_key_for_song

            practice_key = resolve_practice_concert_key_for_song(
                session,
                home_key,
                pick_key=pick_key,
                fallback=home_key,
            )
        except ImportError:
            try:
                from songs.key_state import canonical_display_key_for_pick

                saved = canonical_display_key_for_pick(session, pick_key)
                if saved:
                    practice_key = saved
            except ImportError:
                pass

    set_custom_source(session)
    sync_song_picker_source_widget(session, force=True)

    default_bpm = int(active.get("bpm") or canonical_active_song_bpm(active) or 100)
    default_groove = normalize_groove_label(cpl_default_groove_for_active(active), song_data=active)
    default_meter = str(active.get("time_signature") or get_song_default_meter(active) or "4/4")
    song_id = playback_song_id(
        is_custom=True,
        song_title=str(active.get("name", "") or ""),
        song_artist="",
        custom_name=str(active.get("name", "") or ""),
        custom_revision=str(active.get("id", "") or ""),
    )
    sync_id = active_song_sync_id(pick_key=pick_key, playback_song_id=song_id, is_custom=True)
    on_active_song_identity_changed(
        st,
        pick_key=pick_key,
        title=str(selected.get("title") or ""),
        artist=str(selected.get("artist") or ""),
        original_key=home_key,
        is_custom=True,
        sync_id=sync_id,
        default_bpm=default_bpm,
        default_groove=default_groove,
        default_meter=default_meter,
        display_key=practice_key,
        custom_revision=str(active.get("id") or ""),
        song_data=active,
        invalidate_backing=invalidate_backing,
        force_reset=True,
    )
    note_active_source_change(st, invalidate_backing=invalidate_backing)

    session[SELECTED_SONG_STATE_KEY] = selected
    if pick_key:
        session[ACTIVE_CATALOG_PICK_KEY] = pick_key

    prepare_cpl_backing_handoff(session, active)

    try:
        from active_song_state import write_canonical_active_song_state
        from global_active_song_state import sync_active_song_to_canonical

        ctx = {
            "pick_key": pick_key,
            "display_key": practice_key,
            "instrument": str(session.get("instrument") or "").strip(),
            "level": str(session.get("level") or "").strip(),
            "focus": str(session.get("focus") or "").strip(),
            "selected_song": selected,
            "music_source": SOURCE_CUSTOM,
            "custom_progression_name": selected.get("title", ""),
            "custom_home_key": home_key,
        }
        write_canonical_active_song_state(
            session,
            ctx,
            reason="custom_active_song",
            local_edit=True,
        )
        sync_active_song_to_canonical(session)
    except ImportError:
        pass

    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st, save_reason="music_source_switch")
    except TypeError:
        try:
            from songs.state import persist_music_local_state

            # Older persist_music_local_state(**extra) signature — stash reason
            # on session for flush paths that read it.
            st.session_state["_music_persist_save_reason"] = "music_source_switch"
            persist_music_local_state(st)
        except ImportError:
            pass
    except ImportError:
        pass

    try:
        from music_persistent_state import clear_music_ephemeral_default_song

        clear_music_ephemeral_default_song(session)
    except ImportError:
        pass

    return active


def _merge_chart_song_overlay(canonical: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    from songs.catalog_song_resolution import merge_chart_song_overlay

    return merge_chart_song_overlay(canonical, overlay)


def resolve_catalog_song_for_chart(
    session_state: dict[str, Any],
    catalog_song_data: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    song_library: dict[str, dict[str, dict]] | None = None,
) -> tuple[dict[str, Any], str]:
    from songs.catalog_song_resolution import resolve_catalog_song_for_chart as _resolve

    return _resolve(
        session_state,
        catalog_song_data,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )


def build_active_chart_bundle(
    session_state: dict[str, Any],
    *,
    catalog_genre: str,
    catalog_song: str,
    catalog_song_data: dict[str, Any],
    level: str,
    display_key: str,
    cpl_active_key: str,
    sections_for_level: Callable[[dict, str], dict],
    transpose_sections: Callable[[dict, str], dict],
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    song_library: dict[str, dict[str, dict]] | None = None,
) -> dict[str, Any]:
    """Resolve genre, song, song_data, and chord sections for the active source."""
    if composition_song_is_active(session_state):
        from composition_songs_bridge import (
            SOURCE_COMPOSITION as _SRC_COMP,
            composition_as_chart_active,
            composition_home_key,
            find_composition_document,
        )
        from custom_progression_lab import sections_to_chord_lists

        doc = None
        try:
            from composition_session_state import get_active_document as _get_active_doc

            doc = _get_active_doc(session_state)
        except ImportError:
            doc = None
        if not isinstance(doc, dict):
            from songs.state import ACTIVE_CATALOG_PICK_KEY

            doc = find_composition_document(
                session_state,
                str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or ""),
            )
        if not isinstance(doc, dict):
            raise ValueError("Composition song is active but no document is loaded.")

        projected = composition_as_chart_active(doc)
        home_key = composition_home_key(doc)
        if not str(home_key or "").strip():
            from music_theory import MissingOriginalSongKeyError

            raise MissingOriginalSongKeyError(
                "Cannot transpose composition sections because the original key is not set."
            )
        home_sections = projected.get("original_sections") or {}
        level_source_sections = sections_to_chord_lists(home_sections)
        title = str(projected.get("name") or "Composition")
        level_song_data = {
            "key": home_key,
            "sections": level_source_sections,
            "title": title,
        }
        from music_theory import validate_chart_song_for_transpose

        validate_chart_song_for_transpose(
            level_song_data,
            original_key=home_key,
            provenance="composition_chart_bundle",
        )
        sections = transpose_sections(level_song_data, display_key)
        return {
            "source": _SRC_COMP,
            "genre": "Composition",
            "song": title,
            "song_data": {
                "title": title,
                "artist": "Composition",
                "genre": "Composition",
                "key": home_key,
                "sections": level_source_sections,
                "chart_status": "composition",
                "trusted_core": False,
            },
            "original_key": home_key,
            "level_source_sections": level_source_sections,
            "sections": sections,
            "cpl_active": None,
            "composition_document": doc,
            "default_bpm": int(projected.get("bpm", 96) or 96),
            "default_loops": int(projected.get("loops", 2) or 2),
            "default_groove": str(projected.get("groove_style") or "Auto"),
            "time_signature": projected.get("time_signature", "4/4") or "4/4",
        }

    if custom_progression_is_active(session_state):
        from custom_progression_lab import (
            cpl_default_groove_for_active,
            default_active_progression,
            ensure_all_cpl_sections,
            ensure_original_structure,
            sections_to_chord_lists,
        )

        active = ensure_original_structure(
            session_state.get(cpl_active_key) or default_active_progression()
        )
        active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
        session_state[cpl_active_key] = active
        home_key = custom_original_key(active)
        if not str(home_key or "").strip():
            from music_theory import MissingOriginalSongKeyError

            raise MissingOriginalSongKeyError(
                "Cannot transpose custom progression sections because the original key is not set."
            )
        home_sections = active.get("original_sections") or {}
        level_source_sections = sections_to_chord_lists(home_sections)
        title = active.get("name", "Custom Progression")
        level_song_data = {
            "key": home_key,
            "sections": level_source_sections,
            "title": title,
        }
        from music_theory import validate_chart_song_for_transpose

        validate_chart_song_for_transpose(
            level_song_data,
            original_key=home_key,
            provenance="custom_chart_bundle",
        )
        sections = transpose_sections(level_song_data, display_key)
        return {
            "source": SOURCE_CUSTOM,
            "genre": "Custom",
            "song": title,
            "song_data": {
                "title": title,
                "artist": "Your progression",
                "genre": "Custom",
                "key": home_key,
                "sections": level_source_sections,
                "chart_status": "custom",
                "trusted_core": False,
            },
            "original_key": home_key,
            "level_source_sections": level_source_sections,
            "sections": sections,
            "cpl_active": active,
            "default_bpm": int(active.get("bpm", 100) or 100),
            "default_loops": int(active.get("loops", 2) or 2),
            "default_groove": cpl_default_groove_for_active(active),
            "time_signature": active.get("time_signature", "4/4") or "4/4",
        }

    from backing_audio import infer_groove_style
    from music_theory import validate_chart_song_for_transpose
    from .playback_defaults import default_bpm_for_song_data, default_groove_for_song

    if song_picker_catalog is None:
        song_picker_catalog = _catalog_picker_from_session(session_state)
    if song_library is None:
        song_library = _catalog_library_from_session(session_state)

    resolved_song_data, original_key = resolve_catalog_song_for_chart(
        session_state,
        catalog_song_data,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    level_source_sections = sections_for_level(resolved_song_data, level)
    level_song_data = {
        **resolved_song_data,
        "key": original_key,
        "sections": level_source_sections,
    }
    validate_chart_song_for_transpose(
        level_song_data,
        original_key=original_key,
        provenance="catalog_chart_bundle",
    )
    sections = transpose_sections(level_song_data, display_key)
    ext = resolved_song_data.get("extensions") or {}
    return {
        "source": SOURCE_CATALOG,
        "genre": catalog_genre,
        "song": catalog_song,
        "song_data": resolved_song_data,
        "original_key": original_key,
        "level_source_sections": level_source_sections,
        "sections": sections,
        "cpl_active": None,
        "default_bpm": default_bpm_for_song_data(resolved_song_data),
        "default_loops": int(ext.get("default_loops", 2) or 2),
        "default_groove": default_groove_for_song(
            resolved_song_data,
            infer_fn=infer_groove_style,
        ),
        "time_signature": ext.get("time_signature", "4/4") or "4/4",
    }


def _pick_key_is_catalog(pick_key: str) -> bool:
    pk = str(pick_key or "").strip()
    return bool(pk) and not pk.startswith("custom::") and not pk.startswith("composition::")


def _catalog_picker_from_session(session_state: dict[str, Any]) -> dict[str, dict[str, dict]] | None:
    for key in ("_reconcile_song_picker_catalog", "_catalog_backup_picker"):
        raw = session_state.get(key)
        if isinstance(raw, dict) and raw:
            return raw
    return None


def _catalog_library_from_session(session_state: dict[str, Any]) -> dict[str, dict[str, dict]] | None:
    for key in ("_reconcile_song_library", "_catalog_backup_library"):
        raw = session_state.get(key)
        if isinstance(raw, dict) and raw:
            return raw
    return None


def stamp_chart_bundle_catalog_context(
    session_state: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    song_library: dict[str, dict[str, dict]] | None = None,
) -> None:
    """Persist catalog handles on session so chart bundle build survives API/caller drift."""
    if isinstance(song_picker_catalog, dict) and song_picker_catalog:
        session_state["_reconcile_song_picker_catalog"] = song_picker_catalog
        session_state["_catalog_backup_picker"] = song_picker_catalog
    if isinstance(song_library, dict) and song_library:
        session_state["_reconcile_song_library"] = song_library
        session_state["_catalog_backup_library"] = song_library


def build_active_chart_bundle_for_app(
    session_state: dict[str, Any],
    *,
    catalog_genre: str,
    catalog_song: str,
    catalog_song_data: dict[str, Any],
    level: str,
    display_key: str,
    cpl_active_key: str,
    sections_for_level: Callable[[dict, str], dict],
    transpose_sections: Callable[[dict, str], dict],
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    song_library: dict[str, dict[str, dict]] | None = None,
) -> dict[str, Any]:
    """App entry point: stamp session catalog context, then build (stable for Streamlit factory)."""
    import inspect

    stamp_chart_bundle_catalog_context(
        session_state,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    picker = song_picker_catalog or _catalog_picker_from_session(session_state)
    library = song_library or _catalog_library_from_session(session_state)
    kwargs: dict[str, Any] = {
        "catalog_genre": catalog_genre,
        "catalog_song": catalog_song,
        "catalog_song_data": catalog_song_data,
        "level": level,
        "display_key": display_key,
        "cpl_active_key": cpl_active_key,
        "sections_for_level": sections_for_level,
        "transpose_sections": transpose_sections,
    }
    params = inspect.signature(build_active_chart_bundle).parameters
    if "song_picker_catalog" in params:
        kwargs["song_picker_catalog"] = picker
    if "song_library" in params:
        kwargs["song_library"] = library
    return build_active_chart_bundle(session_state, **kwargs)


def normalize_catalog_pick_key(
    pick_key: str,
    *,
    session_state: dict[str, Any] | None = None,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> str:
    """Resolve legacy/plain pick keys to canonical catalog pick_key when possible."""
    pk = str(pick_key or "").strip()
    if not pk:
        return ""
    try:
        from song_catalog.catalog import PICK_KEY_SEP, format_pick_key, resolve_pick_key
    except ImportError:
        return pk
    if "::" in pk and PICK_KEY_SEP not in pk:
        genre, _, label = pk.partition("::")
        if genre.strip() and label.strip():
            pk = format_pick_key(genre.strip(), label.strip())
    catalog = song_picker_catalog
    if catalog is None and session_state is not None:
        catalog = _catalog_picker_from_session(session_state)
    if isinstance(catalog, dict):
        resolved = resolve_pick_key(pk, song_picker_catalog=catalog)
        if resolved:
            return resolved
    return pk


def _pick_keys_match(left: str, right: str, *, session_state: dict[str, Any] | None = None) -> bool:
    a = normalize_catalog_pick_key(left, session_state=session_state)
    b = normalize_catalog_pick_key(right, session_state=session_state)
    return bool(a) and a == b


def _catalog_row_for_pick(
    pick_key: str,
    song_picker_catalog: dict[str, dict[str, dict]],
    *,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(song_picker_catalog, dict) or not song_picker_catalog:
        return None
    try:
        from song_catalog.catalog import (
            format_pick_key,
            parse_pick_key,
            resolve_pick_key,
            resolve_picker_catalog_selection,
        )
    except ImportError:
        return None
    resolved = resolve_pick_key(
        pick_key,
        song_picker_catalog=song_picker_catalog,
        records=records,
    )
    candidate = str(resolved or pick_key or "").strip()
    genre, label = parse_pick_key(candidate)
    if genre and label:
        labels = song_picker_catalog.get(genre)
        if isinstance(labels, dict) and label in labels:
            data = dict(labels[label])
            data.setdefault("genre", genre)
            data.setdefault("label", label)
            data["pick_key"] = format_pick_key(genre, label)
            return data
    _genre, _label, row = resolve_picker_catalog_selection(
        pick_key,
        song_picker_catalog,
        records=records,
    )
    if not row:
        return None
    data = dict(row)
    if _genre:
        data.setdefault("genre", _genre)
    if _label:
        data.setdefault("label", _label)
        data["pick_key"] = format_pick_key(_genre, _label) if _genre else pick_key
    return data


def catalog_transport_bpm_for_pick(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> int:
    """Authoritative catalog BPM from picker row extensions.default_bpm."""
    catalog = song_picker_catalog or _catalog_picker_from_session(session_state)
    if not isinstance(catalog, dict):
        return 0
    pick = normalize_catalog_pick_key(
        pick_key,
        session_state=session_state,
        song_picker_catalog=catalog,
    )
    row = _catalog_row_for_pick(pick, catalog)
    return _catalog_bpm_from_row(row) if row else 0


def _catalog_bpm_from_row(row: dict[str, Any]) -> int:
    ext = row.get("extensions") if isinstance(row.get("extensions"), dict) else {}
    try:
        bpm = int(row.get("bpm") or ext.get("default_bpm") or 0)
    except (TypeError, ValueError):
        return 0
    return bpm if bpm > 0 else 0


def _merge_catalog_transport_into_selected(
    selected: dict[str, Any],
    pick_key: str,
    catalog: dict[str, dict[str, dict]] | None,
    *,
    authoritative: bool = False,
) -> dict[str, Any]:
    """Fill BPM/groove/extensions from picker catalog row when session blob is thin or stale."""
    if not isinstance(catalog, dict):
        return selected
    row = _catalog_row_for_pick(pick_key, catalog)
    if not row:
        return selected
    out = dict(selected)
    ext = row.get("extensions") if isinstance(row.get("extensions"), dict) else {}
    row_bpm = _catalog_bpm_from_row(row)
    if row_bpm > 0 and (authoritative or not int(out.get("bpm") or 0)):
        out["bpm"] = row_bpm
    row_groove = str(ext.get("default_groove") or row.get("groove") or "").strip()
    if row_groove and (authoritative or not str(out.get("groove") or "").strip()):
        out["groove"] = row_groove
    if ext and (authoritative or not isinstance(out.get("extensions"), dict) or not out.get("extensions")):
        out["extensions"] = dict(ext)
    if authoritative or not str(out.get("genre") or "").strip():
        genre = str(row.get("genre") or out.get("genre") or "").strip()
        if genre:
            out["genre"] = genre
    for field in ("title", "artist", "key"):
        val = str(row.get(field) or "").strip()
        if val and (authoritative or not str(out.get(field) or "").strip()):
            out[field] = val
    return out


def resolve_catalog_song_for_pick(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    authoritative_transport: bool = False,
) -> tuple[dict[str, Any], str]:
    """Return (selected_song, original_key) for a catalog pick — never a mismatched stale blob."""
    from songs.state import SELECTED_SONG_STATE_KEY

    pick_key = normalize_catalog_pick_key(
        pick_key,
        session_state=session_state,
        song_picker_catalog=song_picker_catalog,
    )
    if not _pick_key_is_catalog(pick_key):
        return {}, "C"

    catalog = song_picker_catalog or _catalog_picker_from_session(session_state)

    def _finish(selected: dict[str, Any], original_key: str) -> tuple[dict[str, Any], str]:
        merged = _merge_catalog_transport_into_selected(
            selected,
            pick_key,
            catalog,
            authoritative=authoritative_transport,
        )
        return merged, original_key

    snap_keys = (
        (CATALOG_BEFORE_CREATIVE_KEY, CATALOG_BEFORE_CUSTOM_KEY)
        if authoritative_transport
        else (LAST_CATALOG_STATE_KEY, CATALOG_BEFORE_CUSTOM_KEY, CATALOG_BEFORE_CREATIVE_KEY)
    )
    for snap_key in snap_keys:
        raw = session_state.get(snap_key)
        if not isinstance(raw, dict):
            continue
        snap_pick = normalize_catalog_pick_key(
            str(raw.get("pick_key") or "").strip(),
            session_state=session_state,
            song_picker_catalog=catalog,
        )
        if snap_pick != pick_key:
            continue
        raw_sel = raw.get("selected_song")
        if isinstance(raw_sel, dict) and raw_sel:
            selected = dict(raw_sel)
            selected["pick_key"] = pick_key
            original = str(
                raw.get("original_key") or selected.get("key") or "C"
            ).strip() or "C"
            return _finish(selected, original)

    sel = session_state.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict) and _pick_keys_match(
        str(sel.get("pick_key") or "").strip(), pick_key, session_state=session_state
    ):
        selected = dict(sel)
        selected["pick_key"] = pick_key
        original = str(selected.get("key") or "C").strip() or "C"
        return _finish(selected, original)

    meta = session_state.get("active_song_state")
    if isinstance(meta, dict) and _pick_keys_match(
        str(meta.get("pick_key") or "").strip(), pick_key, session_state=session_state
    ):
        raw_sel = meta.get("selected_song")
        if isinstance(raw_sel, dict) and raw_sel:
            selected = dict(raw_sel)
            selected["pick_key"] = pick_key
            original = str(
                meta.get("original_key") or selected.get("key") or "C"
            ).strip() or "C"
            return _finish(selected, original)

    if isinstance(catalog, dict):
        row = _catalog_row_for_pick(pick_key, catalog)
        if row:
            try:
                from song_catalog.catalog import parse_pick_key
            except ImportError:
                parse_pick_key = lambda _k: ("", "")  # type: ignore[assignment,misc]
            genre, label = parse_pick_key(pick_key)
            ext = row.get("extensions") if isinstance(row.get("extensions"), dict) else {}
            selected = {
                "pick_key": pick_key,
                "title": str(row.get("title") or label or "").strip(),
                "artist": str(row.get("artist") or "").strip(),
                "genre": genre or str(row.get("genre") or "").strip(),
                "label": label or str(row.get("label") or "").strip(),
                "key": str(row.get("key") or "C").strip() or "C",
                "extensions": dict(ext),
            }
            row_bpm = _catalog_bpm_from_row(row)
            if row_bpm > 0:
                selected["bpm"] = row_bpm
            row_groove = str(ext.get("default_groove") or "").strip()
            if row_groove:
                selected["groove"] = row_groove
            return _finish(selected, selected["key"])

    try:
        from song_catalog.catalog import parse_pick_key
    except ImportError:
        parse_pick_key = lambda _k: ("", "")  # type: ignore[assignment,misc]
    genre, label = parse_pick_key(pick_key)
    title = str(label or pick_key).strip() or pick_key
    return {
        "pick_key": pick_key,
        "title": title,
        "artist": "",
        "genre": genre,
        "label": label or title,
        "key": "C",
    }, "C"


def _sync_catalog_session_surface_keys(
    session: dict[str, Any],
    *,
    pick_key: str,
    selected_song: dict[str, Any],
) -> None:
    """Mirror promoted catalog song into live session title keys."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    pick_key = str(pick_key or "").strip()
    selected = dict(selected_song)
    if pick_key:
        selected["pick_key"] = pick_key
    session[SELECTED_SONG_STATE_KEY] = selected
    if pick_key:
        session[ACTIVE_CATALOG_PICK_KEY] = pick_key
    title = str(selected.get("title") or "").strip()
    if title:
        session["song"] = title
        session["active_song_title"] = title
    genre = str(selected.get("genre") or "").strip()
    if genre:
        session["active_genre"] = genre


def resolve_catalog_pick_for_backing_restore(
    session_state: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    reason: str = "",
) -> str:
    """Catalog pick when leaving custom/creative backing."""
    pick, _source = resolve_catalog_pick_for_backing_restore_with_source(
        session_state,
        song_picker_catalog=song_picker_catalog,
        reason=reason,
    )
    return pick


def resolve_catalog_pick_for_backing_restore_with_source(
    session_state: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    reason: str = "",
) -> tuple[str, str]:
    """Catalog pick + source label for restore diagnostics."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    try:
        from backing_source_navigation import PRACTICE_SOURCE_PICK_KEY
    except ImportError:
        PRACTICE_SOURCE_PICK_KEY = "_practice_source_pick_key"  # type: ignore[misc,assignment]

    _creative_return_reasons = {
        "creative_to_catalog",
        "switch_to_catalog_backing",
        "catalog_source_switch",
    }

    def _normalize(pk: str) -> str:
        return normalize_catalog_pick_key(
            pk,
            session_state=session_state,
            song_picker_catalog=song_picker_catalog,
        )

    def _record(source: str, pk: str) -> tuple[str, str]:
        session_state["catalog_restore_pick_source"] = source
        return _normalize(pk), source

    if str(reason or "").strip() in _creative_return_reasons:
        # Pre-Creative catalog wins over stale catalog_before_custom / last_catalog (e.g. Say).
        snap_order = (
            ("catalog_before_creative", CATALOG_BEFORE_CREATIVE_KEY),
            ("catalog_before_custom", CATALOG_BEFORE_CUSTOM_KEY),
            ("last_catalog_state", LAST_CATALOG_STATE_KEY),
        )
        for source, snap_key in snap_order:
            raw = session_state.get(snap_key)
            if not isinstance(raw, dict):
                continue
            pk = str(raw.get("pick_key") or "").strip()
            if _pick_key_is_catalog(pk):
                return _record(source, pk)
        practice_pk = str(session_state.get(PRACTICE_SOURCE_PICK_KEY) or "").strip()
        if _pick_key_is_catalog(practice_pk):
            return _record("practice_source_pick", practice_pk)
        live = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
        if _pick_key_is_catalog(live):
            return _record("active_catalog_pick_key", live)
        meta = session_state.get("active_song_state")
        if isinstance(meta, dict):
            pk = str(meta.get("pick_key") or "").strip()
            if _pick_key_is_catalog(pk):
                return _record("active_song_state", pk)
        session_state["catalog_restore_pick_source"] = "none"
        return "", "none"

    for source, snap_key in (
        ("catalog_before_custom", CATALOG_BEFORE_CUSTOM_KEY),
        ("last_catalog_state", LAST_CATALOG_STATE_KEY),
    ):
        raw = session_state.get(snap_key)
        if not isinstance(raw, dict):
            continue
        pk = str(raw.get("pick_key") or "").strip()
        if _pick_key_is_catalog(pk):
            return _record(source, pk)
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict):
        pk = str(meta.get("pick_key") or "").strip()
        if _pick_key_is_catalog(pk):
            return _record("active_song_state", pk)
    live = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if _pick_key_is_catalog(live):
        return _record("active_catalog_pick_key", live)
    last = resolve_last_catalog_pick_key(session_state)
    if last:
        return _record("recent_catalog_fallback", last)
    session_state["catalog_restore_pick_source"] = "none"
    return "", "none"


def activate_catalog_song_for_backing(
    st: Any,
    pick_key: str = "",
    *,
    reason: str = "catalog_source_switch",
    invalidate_backing: Callable[[Any], None] | None = None,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> Any:
    """Atomically commit a catalog song and rebuild regular_song backing context."""
    from music_source_ownership import (
        rebuild_catalog_backing_from_canonical_pick,
        write_catalog_backing_restore_diag,
        write_catalog_restore_diag,
        write_key_transition_diag,
    )

    session = st.session_state
    pick_before = str(session.get("active_catalog_pick_key") or "").strip()
    pick_key = str(pick_key or "").strip()
    if not _pick_key_is_catalog(pick_key):
        pick_key, pick_source = resolve_catalog_pick_for_backing_restore_with_source(
            session,
            song_picker_catalog=song_picker_catalog,
            reason=reason,
        )
    else:
        pick_source = "explicit_argument"
    before_creative = session.get(CATALOG_BEFORE_CREATIVE_KEY) if isinstance(session.get(CATALOG_BEFORE_CREATIVE_KEY), dict) else {}
    creative_key_before = str(
        session.get("display_key") or session.get("concert_key") or session.get("improv_jam_key") or ""
    ).strip()
    write_catalog_restore_diag(
        session,
        catalog_before_creative_pick=str(before_creative.get("pick_key") or "").strip(),
        catalog_restore_pick_chosen=pick_key,
        catalog_restore_pick_source=pick_source,
        creative_key_before_restore=creative_key_before,
        catalog_restore_reason=reason,
    )
    write_catalog_backing_restore_diag(
        session,
        pick_before=pick_before,
        pick_chosen=pick_key,
        action=reason,
    )
    if not pick_key:
        write_catalog_backing_restore_diag(session, ok=False, error="no_catalog_pick")
        return None
    if invalidate_backing is None:
        invalidate_backing = lambda _st: None
    selected, original_key = resolve_catalog_song_for_pick(
        session,
        pick_key,
        song_picker_catalog=song_picker_catalog,
        authoritative_transport=True,
    )
    if not selected:
        write_catalog_backing_restore_diag(session, ok=False, error="catalog_row_missing")
        return None
    catalog_original = str(original_key or selected.get("key") or "C").strip() or "C"
    _reset_reasons = (
        "catalog_source_switch",
        "creative_to_catalog",
        "switch_to_catalog_backing",
        "last_catalog_restore",
        "previous_catalog_restore",
    )
    display_key = catalog_original
    try:
        from songs.practice_key_state import resolve_practice_concert_key_for_pick

        display_key = resolve_practice_concert_key_for_pick(
            session,
            pick_key,
            original_key=catalog_original,
        )
    except ImportError:
        if reason not in _reset_reasons:
            display_key = (
                str(session.get("display_key") or session.get("concert_key") or catalog_original).strip()
                or catalog_original
            )
    write_key_transition_diag(
        session,
        catalog_original_key=catalog_original,
        catalog_target_key=display_key,
        key_transition_intent=reason,
        active_transport_owner="catalog",
        last_key_writer="activate_catalog_song_for_backing",
    )
    commit_catalog_active_song(
        st,
        pick_key=pick_key,
        selected_song=selected,
        original_key=original_key,
        display_key=display_key,
        invalidate_backing=invalidate_backing,
        reason=reason,
    )
    ctx = rebuild_catalog_backing_from_canonical_pick(
        session,
        st_like=st,
        pick_key=pick_key,
        practice_concert_key=display_key,
        reset_to_original=reason in _reset_reasons,
        force_bpm_reset=True,
    )
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session) or ctx
    except ImportError:
        pass
    write_catalog_restore_diag(
        session,
        catalog_restore_original_key=catalog_original,
        catalog_restore_target_key=str(session.get("display_key") or session.get("concert_key") or "").strip(),
        catalog_restore_bpm=int(getattr(ctx, "bpm", 0) or session.get("backing_track_bpm") or 0) if ctx else 0,
        display_key_after_restore=str(session.get("display_key") or "").strip(),
        concert_key_after_restore=str(session.get("concert_key") or "").strip(),
        backing_context_title_after_restore=str(getattr(ctx, "song_title", "") or "") if ctx else "",
    )
    write_catalog_backing_restore_diag(
        session,
        ok=ctx is not None,
        pick_after=str(session.get("active_catalog_pick_key") or "").strip(),
        active_song_title=str(session.get("song") or session.get("active_song_title") or "").strip(),
        backing_source=str(getattr(ctx, "source", "") or "") if ctx else "",
        backing_title=str(getattr(ctx, "song_title", "") or "") if ctx else "",
        bound_pick=str(getattr(ctx, "bound_pick_key", "") or "") if ctx else "",
        catalog_restore_pin_pick=str(session.get(CATALOG_RESTORE_PIN_KEY) or pick_key).strip(),
    )
    return ctx


def resolve_last_catalog_pick_key(session_state: dict[str, Any]) -> str:
    """Last catalog song pick for Use Catalog Song Backing — never custom."""
    try:
        from backing_source_navigation import PRACTICE_SOURCE_PICK_KEY
    except ImportError:
        PRACTICE_SOURCE_PICK_KEY = "_practice_source_pick_key"
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    candidates: list[str] = []
    for raw in (
        session_state.get(PRACTICE_SOURCE_PICK_KEY),
        (session_state.get(LAST_CATALOG_STATE_KEY) or {}).get("pick_key")
        if isinstance(session_state.get(LAST_CATALOG_STATE_KEY), dict)
        else None,
        (session_state.get(CATALOG_BEFORE_CUSTOM_KEY) or {}).get("pick_key")
        if isinstance(session_state.get(CATALOG_BEFORE_CUSTOM_KEY), dict)
        else None,
    ):
        pk = str(raw or "").strip()
        if _pick_key_is_catalog(pk):
            candidates.append(pk)
    recent = session_state.get(CATALOG_RECENT_PICK_KEYS)
    if isinstance(recent, list):
        for pk in recent:
            text = str(pk or "").strip()
            if _pick_key_is_catalog(text):
                candidates.append(text)
    live = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if _pick_key_is_catalog(live):
        candidates.append(live)
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict):
        mp = str(meta.get("pick_key") or "").strip()
        if _pick_key_is_catalog(mp):
            candidates.append(mp)
    for pk in candidates:
        return pk
    return ""


def activate_catalog_pick_for_backing(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    st_like: Any | None = None,
    invalidate_backing=None,
) -> str:
    """Promote a catalog pick into session for catalog backing — returns original key."""
    pick_key = str(pick_key or "").strip()
    if not _pick_key_is_catalog(pick_key):
        pick_key = resolve_last_catalog_pick_key(session_state)
    selected, original_key = resolve_catalog_song_for_pick(session_state, pick_key)
    if not selected:
        selected = {"pick_key": pick_key, "key": original_key}
    if invalidate_backing is None:
        invalidate_backing = lambda _st: None
    if st_like is None:
        from types import SimpleNamespace

        st_like = SimpleNamespace(session_state=session_state)
    commit_catalog_active_song(
        st_like,
        pick_key=pick_key,
        selected_song=selected,
        original_key=original_key,
        display_key=original_key,
        invalidate_backing=invalidate_backing,
        reason="catalog_source_switch",
    )
    return original_key


def ensure_custom_progression_for_backing(session_state: dict[str, Any]) -> str:
    """Ensure CPL active progression exists for Use Custom Progression Backing. Returns original key."""
    # Refuse to clobber Composition ownership (Songs→Backing after Composition).
    if composition_song_is_active(session_state) or picker_composition_mode(session_state):
        try:
            from composition_session_state import get_active_document
            from composition_songs_bridge import composition_home_key, find_composition_document

            doc = get_active_document(session_state)
            if not isinstance(doc, dict):
                from songs.state import ACTIVE_CATALOG_PICK_KEY

                doc = find_composition_document(
                    session_state,
                    str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or ""),
                )
            if isinstance(doc, dict):
                return str(composition_home_key(doc) or "C").strip() or "C"
        except ImportError:
            pass
        return str(session_state.get("display_key") or "C").strip() or "C"
    try:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            default_active_progression,
            ensure_original_structure,
            written_home_key,
        )
    except ImportError:
        return "C"
    active = session_state.get(CPL_ACTIVE_KEY)
    if not isinstance(active, dict) or not active.get("original_sections"):
        active = default_active_progression()
    active = ensure_original_structure(active)
    session_state[CPL_ACTIVE_KEY] = active
    set_custom_source(session_state)
    name = str(active.get("name") or "My Progression").strip()
    session_state["song"] = name
    session_state["active_song_title"] = name
    pick = custom_pick_key_for(active)
    if pick:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        session_state[ACTIVE_CATALOG_PICK_KEY] = pick
        session_state[SELECTED_SONG_STATE_KEY] = {
            "pick_key": pick,
            "title": name,
            "artist": "Your progression",
            "key": str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C",
        }
    return str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C"
