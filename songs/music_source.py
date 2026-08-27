"""Active music source: catalog song vs custom progression (shared session contract)."""

from __future__ import annotations

import copy
from typing import Any, Callable

ACTIVE_MUSIC_SOURCE_KEY = "active_music_source"
SOURCE_CATALOG = "catalog_song"
SOURCE_CUSTOM = "custom_progression"
_LAST_SOURCE_KEY = "_last_active_music_source"
_LAST_ACTIVE_PICK_KEY = "_last_active_pick_key_for_reset"
PENDING_CUSTOM_ACTIVE_SONG_KEY = "_pending_custom_active_song_activation"
PENDING_CUSTOM_LIBRARY_ACTION_KEY = "_pending_custom_library_action"
SONG_PICKER_SOURCE_CATALOG = "Song Selection (catalog song)"
SONG_PICKER_SOURCE_CUSTOM = "Use Custom Progression / Create Your Own Song"
SONG_PICKER_ACTIVE_SOURCE_KEY = "song_picker_active_source"
PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY = "_pending_song_picker_active_source"
LAST_CATALOG_STATE_KEY = "_last_catalog_song_state"
LAST_CUSTOM_STATE_KEY = "_last_custom_song_state"
CATALOG_BEFORE_CUSTOM_KEY = "_catalog_before_custom_state"
# Locked Catalog return pick stamped on Catalog→Custom. Survives reload and blocks
# same-run Say restamps into _catalog_before_custom_state.
CATALOG_BEFORE_CUSTOM_LOCK_KEY = "_catalog_before_custom_lock_pick"
PENDING_CATALOG_FROM_PICKER_KEY = "_pending_catalog_from_picker_switch"
CATALOG_BEFORE_CREATIVE_KEY = "_catalog_before_creative_state"
CATALOG_RESTORE_PIN_KEY = "_catalog_restore_pin_pick"
PENDING_PREVIOUS_CATALOG_RESTORE_KEY = "_pending_previous_catalog_restore"
USER_CATALOG_SOURCE_CHOICE_KEY = "_user_chose_catalog_music_source"
CATALOG_RECENT_PICK_KEYS = "catalog_recent_pick_keys"
CUSTOM_RECENT_ACTIVE_NAMES_KEY = "custom_recent_active_names"
LAST_RECONCILED_SONG_PICKER_SOURCE_KEY = "_last_reconciled_song_picker_source"
EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY = "_explicit_custom_activation_epoch"
EXPLICIT_CATALOG_SELECTION_EPOCH_KEY = "_explicit_catalog_selection_epoch"
# Last Music-source radio value we successfully presented (or queued) to the widget.
# Used to distinguish genuine Catalog clicks from stale Catalog widget callbacks after
# Custom Set-as-Active (E5) — not a wall-clock grace window.
SONG_PICKER_PRESENTED_SOURCE_KEY = "_song_picker_presented_source"


def explicit_custom_activation_is_authoritative(session_state: dict[str, Any]) -> bool:
    """True when a newer explicit Custom Set-as-Active outranks stale catalog recovery.

    Explicit Catalog selection stamps ``EXPLICIT_CATALOG_SELECTION_EPOCH_KEY`` and then
    legitimately outranks Custom. A bare ``USER_CATALOG`` flag without that epoch is
    treated as stale and must not reclaim Country Roads after Trial Set-as-Active.
    """
    custom_epoch = session_state.get(EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY)
    if custom_epoch is None:
        return False
    catalog_epoch = session_state.get(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY)
    if catalog_epoch is None:
        return True
    try:
        return float(custom_epoch) > float(catalog_epoch)
    except Exception:
        return True


def explicit_catalog_selection_is_authoritative(session_state: dict[str, Any]) -> bool:
    """True when a newer explicit Catalog choice outranks a prior Custom Set-as-Active.

    Used so a queued Custom pending cannot re-apply Trial Song after the user
    clicked ``Use catalog song instead`` / Catalog radio (E5 reverse).
    """
    catalog_epoch = session_state.get(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY)
    if catalog_epoch is None:
        return False
    custom_epoch = session_state.get(EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY)
    if custom_epoch is None:
        return True
    try:
        return float(catalog_epoch) >= float(custom_epoch)
    except Exception:
        return True


def begin_explicit_catalog_selection(session_state: dict[str, Any]) -> None:
    """Stamp an explicit Catalog choice so Custom ownership cannot lock the switch.

    Product order: EXPLICIT USER SONG PICK > CURRENT GLOBAL ACTIVE OWNER >
    LAST_CUSTOM / preview / sticky. Call this before ``set_catalog_source`` /
    ``apply_pick_key`` on Songs dropdown, Catalog radio, or Use-catalog-instead.
    """
    try:
        import time as _time

        session_state[EXPLICIT_CATALOG_SELECTION_EPOCH_KEY] = float(_time.time())
    except Exception:
        session_state[EXPLICIT_CATALOG_SELECTION_EPOCH_KEY] = 1.0
    session_state.pop(EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY, None)
    session_state[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    session_state.pop(PENDING_CUSTOM_ACTIVE_SONG_KEY, None)
    session_state.pop(PENDING_CUSTOM_LIBRARY_ACTION_KEY, None)


def forget_catalog_visit_practice_key(session_state: dict[str, Any]) -> None:
    """Prior Catalog Practice Key does not survive Custom becoming Global Active.

    Shape Bm→Dm then Trial Set-as-Active must not keep Shape sticky Dm for a later
    explicit Shape reactivation (fresh activation = Original B minor).
    """
    picks: list[str] = []
    live = str(session_state.get("active_catalog_pick_key") or "").strip()
    if live and not live.startswith("custom::") and not live.startswith("custom\x1f"):
        picks.append(live)
    for snap_key in (CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY, "catalog_session"):
        raw = session_state.get(snap_key)
        if not isinstance(raw, dict):
            continue
        pk = str(raw.get("pick_key") or "").strip()
        if pk and not pk.startswith("custom::") and not pk.startswith("custom\x1f"):
            picks.append(pk)
    if not picks:
        return
    try:
        from songs.practice_key_state import clear_practice_concert_key

        seen: set[str] = set()
        for pk in picks:
            if pk in seen:
                continue
            seen.add(pk)
            clear_practice_concert_key(session_state, pk)
    except ImportError:
        pass


def ensure_active_music_source(session_state: dict[str, Any]) -> None:
    session_state.setdefault(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)
    # Explicit Catalog must not leave ACTIVE_MUSIC_SOURCE stuck on custom after a
    # lagging Custom radio / CPL residue (sidebar ACTIVE SONG identity).
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY) or explicit_catalog_selection_is_authoritative(
        session_state
    ):
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CUSTOM:
            session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
            pick = str(session_state.get("active_catalog_pick_key") or "").strip()
            if pick.startswith("custom::"):
                for snap_key in (LAST_CATALOG_STATE_KEY, CATALOG_BEFORE_CUSTOM_KEY):
                    raw = session_state.get(snap_key)
                    if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip():
                        pk = str(raw.get("pick_key") or "").strip()
                        if pk and not pk.startswith("custom::"):
                            session_state["active_catalog_pick_key"] = pk
                            sel = raw.get("selected_song")
                            if isinstance(sel, dict) and sel:
                                session_state["selected_song"] = dict(sel)
                                session_state["song"] = str(sel.get("title") or "")
                            break



def is_custom_progression(session_state: dict[str, Any]) -> bool:
    # Explicit Catalog choice outranks a lagging ACTIVE_MUSIC_SOURCE / radio.
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if explicit_catalog_selection_is_authoritative(session_state):
        return False
    return session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CUSTOM


def custom_progression_is_active(session_state: dict[str, Any]) -> bool:
    """True when Custom Progression is the active song (session or canonical blob)."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CATALOG:
        return False
    if is_custom_progression(session_state):
        return True
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick_key.startswith("custom::"):
        return True
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict):
        if str(meta.get("music_source") or "") == SOURCE_CUSTOM:
            return True
        if str(meta.get("pick_key") or "").strip().startswith("custom::"):
            return True
    return False


def picker_custom_progression_mode(session_state: dict[str, Any]) -> bool:
    """True when the Songs page radio is on Custom Progression."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    return choice == SONG_PICKER_SOURCE_CUSTOM or choice.startswith("Use Custom")


def cpl_session_is_active(session_state: dict[str, Any]) -> bool:
    """True when the loaded song is a Custom Progression (for key display/sync)."""
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return False
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    # Live Catalog pick outranks lagging Custom radio / CPL residue so Shape of You
    # never shows Original Key C after Use Catalog (H9 / Catalog↔Custom toggle).
    if _pick_key_is_catalog(pick_key):
        return False
    live_title = str(
        session_state.get("song") or session_state.get("active_song_title") or ""
    ).strip()
    if (
        live_title
        and not live_title.lower().startswith("my progression")
        and session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CATALOG
    ):
        return False
    if is_custom_progression(session_state):
        return True
    if picker_custom_progression_mode(session_state):
        return True
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

    Custom ownership is authoritative on ordinary hydrate/rerun. A catalog radio
    value only queues a catalog reclaim when the user just flipped Custom → Catalog
    (previous reconciled radio was Custom). Stale catalog radio + live Custom must
    heal the widget — not silently restore the previous catalog song.
    """
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    try:
        from music_restore_phase import music_restore_phase_complete

        phase_done = music_restore_phase_complete(session_state)
    except ImportError:
        phase_done = False

    if phase_done and session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        # Stale USER_CATALOG without a newer explicit Catalog epoch must not reclaim
        # after Trial Set-as-Active (E5 delayed Country Roads flake).
        if explicit_custom_activation_is_authoritative(session_state):
            session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
            session_state.pop(PENDING_CATALOG_FROM_PICKER_KEY, None)
        else:
            pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
            # USER_CATALOG can be set while identity is still custom:: (partial switch).
            # Queue a real catalog restore instead of only flipping the source flag.
            if pick_key.startswith("custom::") or (
                isinstance(session_state.get("active_song_state"), dict)
                and str((session_state.get("active_song_state") or {}).get("music_source") or "")
                == SOURCE_CUSTOM
            ):
                session_state[PENDING_CATALOG_FROM_PICKER_KEY] = True
                if str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip() != SONG_PICKER_SOURCE_CATALOG:
                    _assign_song_picker_source_widget(session_state, SONG_PICKER_SOURCE_CATALOG)
                session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
                return True
            expected = SONG_PICKER_SOURCE_CATALOG
            current = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
            changed = False
            if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
                set_catalog_source(session_state)
                changed = True
            # Only force the Songs radio back to Catalog while the post-"Use catalog"
            # stale-Custom block is live AND we are still on Backing. On Songs, an
            # explicit Custom radio must stick immediately (H1/H8 after H9).
            page_now = str(
                session_state.get("studio_page") or session_state.get("page") or ""
            ).strip()
            block_n = int(session_state.get("_block_stale_custom_radio_reclaim") or 0)
            force_n = int(session_state.get("_force_catalog_backing_after_use_catalog") or 0)
            if page_now == "backing" and (block_n > 0 or force_n > 0) and current != expected:
                _assign_song_picker_source_widget(session_state, expected)
                changed = True
                session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = expected
                return changed
            if current.startswith("Use Custom") or current == SONG_PICKER_SOURCE_CUSTOM:
                # Deliberate Custom after Catalog ownership — fall through.
                if page_now == "picker":
                    session_state.pop("_block_stale_custom_radio_reclaim", None)
                pass
            else:
                session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = expected
                return changed

    pick_key = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    custom_active = custom_progression_is_active(session_state)
    expected = SONG_PICKER_SOURCE_CUSTOM if custom_active else SONG_PICKER_SOURCE_CATALOG
    current = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    changed = False

    # Pending catalog switch already queued (prepare reconcile → apply_pending).
    # A second reconcile in the same run (Songs radio render) must NOT heal the
    # widget back to Custom before apply_pending / on_change can run.
    if session_state.get(PENDING_CATALOG_FROM_PICKER_KEY):
        if current != SONG_PICKER_SOURCE_CATALOG:
            _assign_song_picker_source_widget(session_state, SONG_PICKER_SOURCE_CATALOG)
            changed = True
        session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        return changed

    # Do NOT infer Custom→Catalog from (prev=Custom, radio=Catalog): after
    # Set-as-Active, Streamlit often lags the radio on Catalog while Custom
    # owns practice — that used to reclaim Country Roads and wipe Trial (E5).
    # Deliberate flips go through on_change / hub button (USER_CATALOG + switch)
    # or PENDING already queued above.

    # Stale catalog radio while Custom owns the source (refresh / pre-widget hydrate).
    # Force widget_safe=False so a locked radio key cannot keep Catalog and later
    # trigger an accidental Country Roads reclaim on the Songs page (E5).
    if custom_active and current == SONG_PICKER_SOURCE_CATALOG:
        _assign_song_picker_source_widget(
            session_state, SONG_PICKER_SOURCE_CUSTOM, widget_safe=False
        )
        current = SONG_PICKER_SOURCE_CUSTOM
        changed = True

    if custom_active:
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CUSTOM:
            session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
            changed = True
    elif pick_key and not pick_key.startswith("custom::"):
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
            set_catalog_source(session_state)
            changed = True

    if current != expected:
        _assign_song_picker_source_widget(session_state, expected, widget_safe=False)
        changed = True
    session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = str(
        session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or expected
    )
    return changed


def ensure_active_music_source_from_canonical(session_state: dict[str, Any]) -> None:
    """Align session source flag with canonical custom songs after restore/hydrate."""
    if is_custom_progression(session_state):
        return
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY
    except ImportError:
        return
    meta = session_state.get(ACTIVE_SONG_STATE_KEY)
    if not isinstance(meta, dict) or str(meta.get("music_source") or "") != SOURCE_CUSTOM:
        return
    try:
        from music_restore_phase import authoritative_restore_in_progress

        restore_applying = authoritative_restore_in_progress(session_state)
    except ImportError:
        restore_applying = bool(
            session_state.get("_cloud_workspace_restored_this_run")
            or session_state.get("_suite_persist_restore_applied")
        )
    pick = str(session_state.get("active_catalog_pick_key") or meta.get("pick_key") or "").strip()
    if restore_applying or pick.startswith("custom::") or custom_progression_is_active(session_state):
        session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
        session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)


def set_catalog_source(session_state: dict[str, Any]) -> None:
    try:
        from e5_reclaim_trace import note_e5_reclaim_writer

        note_e5_reclaim_writer(session_state, writer="set_catalog_source")
    except ImportError:
        pass
    # Newer explicit Custom Set-as-Active outranks stale catalog restore.
    # Intentional Catalog selection stamps EXPLICIT_CATALOG_SELECTION_EPOCH_KEY
    # first so this check returns False and the switch proceeds.
    if explicit_custom_activation_is_authoritative(session_state):
        try:
            from e5_reclaim_trace import note_e5_reclaim_writer

            note_e5_reclaim_writer(
                session_state,
                writer="set_catalog_source_blocked",
                reason="explicit_custom_epoch",
            )
        except ImportError:
            pass
        return
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
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY)
        or (sel.get("pick_key") if isinstance(sel, dict) else "")
        or ""
    ).strip()
    if not _pick_key_is_catalog(pick_key):
        # Canonical active-song blob may still hold Catalog while pick is already
        # custom:: (SBI preview) — prefer that Catalog pick when present.
        meta = session_state.get("active_song_state")
        if isinstance(meta, dict) and str(meta.get("music_source") or "") == SOURCE_CATALOG:
            meta_pk = str(meta.get("pick_key") or "").strip()
            if _pick_key_is_catalog(meta_pk):
                pick_key = meta_pk
    if not _pick_key_is_catalog(pick_key):
        return None
    # Catalog library Original Key — never trust selected_song.key when it was
    # polluted by Custom C (Shape of You must snapshot as Bm, not C).
    original_key = _catalog_original_key_for_session(session_state, sel if isinstance(sel, dict) else None)
    title = ""
    artist = ""
    if isinstance(sel, dict) and str(sel.get("pick_key") or "").strip() == pick_key:
        title = str(sel.get("title") or "").strip()
        artist = str(sel.get("artist") or "").strip()
    if not title:
        title = str(
            session_state.get("active_song_title") or session_state.get("song") or ""
        ).strip()
    if not title:
        # Derive from pick label (genre\x1ftitle — artist).
        label = pick_key.split("\x1f", 1)[-1] if "\x1f" in pick_key else pick_key
        title = label.split(" — ", 1)[0].strip() or label
        if " — " in label:
            artist = label.split(" — ", 1)[-1].strip()
    selected = {
        "pick_key": pick_key,
        "title": title,
        "artist": artist,
        "key": original_key,
    }
    if isinstance(sel, dict) and str(sel.get("pick_key") or "").strip() == pick_key:
        selected = {**dict(sel), **selected}
    display_key = str(session_state.get("display_key") or original_key).strip() or original_key
    try:
        from songs.practice_key_state import get_practice_concert_key

        sticky = str(get_practice_concert_key(session_state, pick_key) or "").strip()
        if sticky:
            display_key = sticky
    except ImportError:
        pass
    return {
        "pick_key": pick_key,
        "selected_song": selected,
        "original_key": original_key,
        "display_key": display_key,
    }


def _catalog_title_matches_live(snap_or_pick_title: str, live_title: str) -> bool:
    a = str(snap_or_pick_title or "").strip().lower()
    b = str(live_title or "").strip().lower()
    if not a or not b:
        return False
    if b.startswith("my progression"):
        return False
    return a in b or b in a


def _resolve_catalog_pick_for_live_title(
    session_state: dict[str, Any],
    live_title: str,
) -> str:
    """Find a catalog pick whose label matches Global Active title (Shape, not Say)."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    if not live_title or live_title.lower().startswith("my progression"):
        return ""
    candidates: list[str] = []
    live_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if _pick_key_is_catalog(live_pick):
        candidates.append(live_pick)
    for pk in session_state.get(CATALOG_RECENT_PICK_KEYS) or []:
        cand = str(pk or "").strip()
        if _pick_key_is_catalog(cand) and cand not in candidates:
            candidates.append(cand)
    for snap_key in (
        "catalog_session",
        CATALOG_BEFORE_CUSTOM_KEY,
        LAST_CATALOG_STATE_KEY,
        CATALOG_BEFORE_CREATIVE_KEY,
    ):
        raw = session_state.get(snap_key)
        if isinstance(raw, dict):
            cand = str(raw.get("pick_key") or "").strip()
            if _pick_key_is_catalog(cand) and cand not in candidates:
                candidates.append(cand)
    # Full picker catalog — Shape may be live while recent/LAST still hold Say.
    catalog = session_state.get("_reconcile_song_picker_catalog")
    if isinstance(catalog, dict):
        try:
            from song_catalog import format_pick_key
        except ImportError:
            format_pick_key = None  # type: ignore[assignment]
        for genre, songs in catalog.items():
            if not isinstance(songs, dict):
                continue
            for song_name, row in songs.items():
                label = str(song_name)
                row_title = ""
                if isinstance(row, dict):
                    row_title = str(row.get("title") or "").strip()
                title_part = label.split(" — ", 1)[0].strip()
                if not (
                    _catalog_title_matches_live(title_part, live_title)
                    or _catalog_title_matches_live(label, live_title)
                    or (row_title and _catalog_title_matches_live(row_title, live_title))
                ):
                    continue
                if format_pick_key is not None:
                    cand = format_pick_key(str(genre), song_name)
                else:
                    cand = f"{genre}\x1f{song_name}"
                if _pick_key_is_catalog(cand) and cand not in candidates:
                    candidates.append(cand)
    for cand in candidates:
        label = cand.split("\x1f", 1)[-1] if "\x1f" in cand else cand
        title_part = label.split(" — ", 1)[0].strip()
        if _catalog_title_matches_live(title_part, live_title) or _catalog_title_matches_live(
            label, live_title
        ):
            return cand
    return ""


def capture_catalog_before_custom(session_state: dict[str, Any]) -> bool:
    """Stamp ``_catalog_before_custom_state`` from the live Catalog Global Active.

    Call this **before** Catalog ownership is replaced by Custom on every activation
    path. Live Catalog id/title/Original Key win; never stamp Say / pick_options[0]
    / stale LAST when the live owner is Shape of You (or any other catalog song).

    Returns True when a catalog BEFORE snap was written.
    """
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    live_title = str(
        session_state.get("song") or session_state.get("active_song_title") or ""
    ).strip()
    live_pick_now = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    live_is_custom_title = bool(
        live_title.lower().startswith("my progression")
        or live_pick_now.startswith("custom::")
    )
    custom_owns_global = bool(
        live_is_custom_title
        or str(session_state.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip() == SOURCE_CUSTOM
    )

    def _restore_before_from_lock(lock_pk: str) -> bool:
        """Keep/heal BEFORE to the locked Catalog pick; never leave Say under Shape lock."""
        existing = session_state.get(CATALOG_BEFORE_CUSTOM_KEY)
        if (
            isinstance(existing, dict)
            and str(existing.get("pick_key") or "").strip() == lock_pk
        ):
            return True
        for snap_key in (
            "catalog_session",
            LAST_CATALOG_STATE_KEY,
            CATALOG_BEFORE_CUSTOM_KEY,
            CATALOG_BEFORE_CREATIVE_KEY,
        ):
            raw = session_state.get(snap_key)
            if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip() == lock_pk:
                session_state[CATALOG_BEFORE_CUSTOM_KEY] = dict(raw)
                return True
        # Last resort: rebuild a minimal snap from the locked pick label.
        label = lock_pk.split("\x1f", 1)[-1] if "\x1f" in lock_pk else lock_pk
        title = label.split(" — ", 1)[0].strip() or label
        artist = label.split(" — ", 1)[-1].strip() if " — " in label else ""
        probe = dict(session_state)
        probe[ACTIVE_CATALOG_PICK_KEY] = lock_pk
        orig = ""
        try:
            orig = str(_catalog_original_key_for_session(probe) or "").strip()
        except Exception:
            orig = ""
        session_state[CATALOG_BEFORE_CUSTOM_KEY] = {
            "pick_key": lock_pk,
            "original_key": orig or "C",
            "display_key": orig or "C",
            "selected_song": {
                "pick_key": lock_pk,
                "title": title,
                "artist": artist,
                "key": orig or "C",
            },
        }
        return True

    # Sticky lock wins before any live/fallback stamp. Reload hydrate often has
    # empty titles + stale Say catalog_session; never let that restamp BEFORE.
    existing_lock = str(session_state.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY) or "").strip()
    if _pick_key_is_catalog(existing_lock):
        if custom_owns_global or not live_title:
            _restore_before_from_lock(existing_lock)
            return False
        # Catalog still owns Global: only allow restamp when live pick matches lock
        # (or title resolves to the same pick). Different live Catalog song clears
        # the lock in apply_pick_key before calling capture.

    # Prefer title-matched catalog pick when Global Active is still a catalog song
    # but ACTIVE_CATALOG_PICK_KEY / LAST still point at a prior song (Say).
    if live_title and not live_is_custom_title:
        matched = _resolve_catalog_pick_for_live_title(session_state, live_title)
        if matched:
            live_pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
            if live_pick != matched:
                session_state[ACTIVE_CATALOG_PICK_KEY] = matched
    live = _catalog_snapshot_from_session(session_state)
    if not live and live_title and not live_is_custom_title:
        matched = _resolve_catalog_pick_for_live_title(session_state, live_title)
        if matched:
            probe = dict(session_state)
            probe[ACTIVE_CATALOG_PICK_KEY] = matched
            live = _catalog_snapshot_from_session(probe)
    if live and _pick_key_is_catalog(str(live.get("pick_key") or "")):
        # Reject ambiguous snaps whose title conflicts with live Global Active title.
        snap_title = str((live.get("selected_song") or {}).get("title") or "").strip()
        if (
            live_title
            and snap_title
            and not live_is_custom_title
            and not _catalog_title_matches_live(snap_title, live_title)
        ):
            live = None
    if live and _pick_key_is_catalog(str(live.get("pick_key") or "")):
        # Prefer catalog_session Original Key when live snap fell back to "C"
        # (missing picker catalog) but the Catalog bucket already has Bm.
        live_orig = str(live.get("original_key") or "").strip()
        if not live_orig or live_orig == "C":
            cat = session_state.get("catalog_session")
            if (
                isinstance(cat, dict)
                and str(cat.get("pick_key") or "").strip() == str(live.get("pick_key") or "").strip()
            ):
                cat_orig = str(cat.get("original_key") or "").strip()
                if cat_orig and cat_orig != "C":
                    live = dict(live)
                    live["original_key"] = cat_orig
                    sel = dict(live.get("selected_song") or {})
                    sel["key"] = cat_orig
                    live["selected_song"] = sel
        # Seal sticky Practice Key onto this catalog pick for Use Catalog restore.
        # Never write Original Key into the sticky store — that overwrites C#m with Bm
        # and breaks H2 leave→return (sticky must stay the user's Practice Key).
        try:
            from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key

            seal_pick = str(live.get("pick_key") or "").strip()
            seal_dk = str(live.get("display_key") or "").strip()
            seal_orig = str(live.get("original_key") or "").strip()
            if seal_pick:
                existing_pk = str(get_practice_concert_key(session_state, seal_pick) or "").strip()
                if existing_pk and seal_orig and existing_pk != seal_orig:
                    live = dict(live)
                    live["display_key"] = existing_pk
                elif seal_dk and seal_orig and seal_dk != seal_orig:
                    set_practice_concert_key(session_state, seal_dk, pick_key=seal_pick)
                elif existing_pk:
                    live = dict(live)
                    live["display_key"] = existing_pk
        except ImportError:
            pass
        lock_pk = str(live.get("pick_key") or "").strip()
        existing_lock = str(session_state.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY) or "").strip()
        if existing_lock and lock_pk and existing_lock != lock_pk:
            # Lock is sticky until Use Catalog clears it. A same-run Say restamp
            # (title still Shape, pick lagging on Say) must not replace Shape.
            _restore_before_from_lock(existing_lock)
            return False
        session_state[CATALOG_BEFORE_CUSTOM_KEY] = live
        # Keep LAST aligned with the live Catalog owner so restore paths that
        # prefer LAST do not resurrect Say after Shape was the Global Active.
        session_state[LAST_CATALOG_STATE_KEY] = dict(live)
        if lock_pk:
            session_state[CATALOG_BEFORE_CUSTOM_LOCK_KEY] = lock_pk
        return True

    # Honor lock when Custom owns Global (or titles not yet restored on reload).
    lock_pk = str(session_state.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY) or "").strip()
    if _pick_key_is_catalog(lock_pk) and (custom_owns_global or not live_title):
        _restore_before_from_lock(lock_pk)
        return False

    # Once Custom owns Global titles/picks, never replace a valid Catalog BEFORE.
    # Reload was stamping stale Say from catalog_session/recent[0] over Shape.
    # First-activation stamping must happen while the title is still Catalog.
    existing = session_state.get(CATALOG_BEFORE_CUSTOM_KEY)
    if (
        custom_owns_global
        and isinstance(existing, dict)
        and _pick_key_is_catalog(str(existing.get("pick_key") or ""))
    ):
        return False

    def _stamp_from_bucket(raw: Any) -> bool:
        if not isinstance(raw, dict):
            return False
        pk = str(raw.get("pick_key") or "").strip()
        if not _pick_key_is_catalog(pk):
            return False
        bucket_title = str((raw.get("selected_song") or {}).get("title") or "").strip()
        if not bucket_title:
            label = pk.split("\x1f", 1)[-1] if "\x1f" in pk else pk
            bucket_title = label.split(" — ", 1)[0].strip()
        if live_title and not live_is_custom_title:
            if bucket_title and not _catalog_title_matches_live(bucket_title, live_title):
                return False
        existing_lock = str(session_state.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY) or "").strip()
        if existing_lock and existing_lock != pk:
            return False
        existing_before = session_state.get(CATALOG_BEFORE_CUSTOM_KEY)
        if (
            isinstance(existing_before, dict)
            and _pick_key_is_catalog(str(existing_before.get("pick_key") or ""))
            and str(existing_before.get("pick_key") or "").strip() != pk
        ):
            # Never replace Shape BEFORE with Say via stale catalog_session/LAST
            # during Custom hydrate (empty title / mid-restore).
            return False
        # Re-resolve Original Key from catalog row for this pick (never keep Say G
        # / Custom C pollution on a Shape snap).
        healed = dict(raw)
        try:
            probe = dict(session_state)
            probe["active_catalog_pick_key"] = pk
            orig = _catalog_original_key_for_session(probe)
            bucket_orig = str(raw.get("original_key") or "").strip()
            if orig and orig != "C":
                healed["original_key"] = orig
            elif bucket_orig and bucket_orig != "C":
                healed["original_key"] = bucket_orig
                orig = bucket_orig
            if orig and orig != "C":
                sel = dict(healed.get("selected_song") or {})
                sel["key"] = orig
                sel["pick_key"] = pk
                healed["selected_song"] = sel
        except Exception:
            pass
        session_state[CATALOG_BEFORE_CUSTOM_KEY] = healed
        session_state[LAST_CATALOG_STATE_KEY] = dict(healed)
        if pk and not (existing_lock and existing_lock != pk):
            session_state[CATALOG_BEFORE_CUSTOM_LOCK_KEY] = pk
        return True

    # catalog_session is the live Catalog owner bucket — prefer it over stale
    # BEFORE/LAST (Say) once Custom has already flipped titles/picks.
    if _stamp_from_bucket(session_state.get("catalog_session")):
        return True
    # Keep an existing BEFORE only when it still matches the live Catalog title.
    existing = session_state.get(CATALOG_BEFORE_CUSTOM_KEY)
    if isinstance(existing, dict) and _pick_key_is_catalog(str(existing.get("pick_key") or "")):
        ex_title = str((existing.get("selected_song") or {}).get("title") or "").strip()
        if live_title and ex_title and _catalog_title_matches_live(ex_title, live_title):
            return False
        elif live_title and not live_is_custom_title:
            # Stale BEFORE (Say) while live Catalog title is Shape — drop it.
            session_state.pop(CATALOG_BEFORE_CUSTOM_KEY, None)
    if _stamp_from_bucket(session_state.get(LAST_CATALOG_STATE_KEY)):
        return True
    return False


def snapshot_catalog_before_custom(session_state: dict[str, Any]) -> None:
    """Remember the active catalog song before entering Custom Progression."""
    capture_catalog_before_custom(session_state)


def ensure_catalog_memory_before_leaving_for_custom(session_state: dict[str, Any]) -> None:
    """Alias for ``capture_catalog_before_custom`` (legacy call sites)."""
    capture_catalog_before_custom(session_state)


def _custom_snapshot_from_session(session_state: dict[str, Any]) -> dict[str, Any] | None:
    """Snapshot the live Custom draft for LAST_CUSTOM memory.

    Prefer a raw deepcopy of the CPL blob so incomplete drafts still snapshot;
    do not depend on Global Active being Custom.
    """
    import copy

    try:
        from custom_progression_lab import CPL_ACTIVE_KEY
    except ImportError:
        CPL_ACTIVE_KEY = "cpl_active_progression"
    raw = session_state.get(CPL_ACTIVE_KEY)
    if not isinstance(raw, dict):
        return None
    active = copy.deepcopy(raw)
    name = str(active.get("name") or "").strip()
    if not name:
        return None
    return {"name": name, "active": active}


def cpl_active_is_substantive(active: object) -> bool:
    """True when live CPL is a real Custom song, not the empty My Progression shell.

    ``original_sections`` alone is not enough — the default shell always has a
    truthy empty-sections dict, which previously blocked LAST_CUSTOM install.
    """
    if not isinstance(active, dict):
        return False
    title = str(active.get("name") or "").strip()
    if title and title not in {"My Progression", "My progression"}:
        return True
    for key in ("original_sections", "sections"):
        secs = active.get(key)
        if isinstance(secs, dict):
            for chs in secs.values():
                if isinstance(chs, list) and any(str(c).strip() for c in chs):
                    return True
    return False


def _cpl_chord_count(active: object) -> int:
    if not isinstance(active, dict):
        return 0
    n = 0
    for key in ("original_sections", "sections"):
        secs = active.get(key)
        if not isinstance(secs, dict):
            continue
        for chs in secs.values():
            if isinstance(chs, list):
                n += sum(1 for c in chs if str(c).strip())
    return n


# After explicit New song, do not reinstall LAST_CUSTOM over the blank draft.
CPL_SKIP_LAST_CUSTOM_RESTORE_KEY = "_cpl_skip_last_custom_restore"


def mark_cpl_intentional_new_song(session_state: dict[str, Any]) -> None:
    """User clicked New song — keep the blank draft until they load/activate another."""
    session_state[CPL_SKIP_LAST_CUSTOM_RESTORE_KEY] = True


def clear_cpl_intentional_new_song(session_state: dict[str, Any]) -> None:
    session_state.pop(CPL_SKIP_LAST_CUSTOM_RESTORE_KEY, None)


def install_last_custom_into_live_cpl(
    session_state: dict[str, Any],
    *,
    reset_practice_key_to_original: bool = False,
) -> bool:
    """If live CPL is non-substantive, install LAST_CUSTOM into CPL.

    Also upgrades a chordless draft whose **title matches** LAST_CUSTOM when that
    snapshot has chords (SBI Custom previously showed ``Trial Song · 0 chords``
    while the library had Em Em D D).

    Does **not** clobber an intentional New song blank (``My Progression`` / 0 chords).

    Returns True when LAST_CUSTOM was installed (or live CPL was already substantive).
    Does not promote Global Active.
    """
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY, apply_cpl_session_progression
    except ImportError:
        return False
    live = session_state.get(CPL_ACTIVE_KEY)
    snap = session_state.get(LAST_CUSTOM_STATE_KEY)
    if not isinstance(snap, dict):
        return bool(cpl_active_is_substantive(live))
    active = snap.get("active")
    if not isinstance(active, dict) or not cpl_active_is_substantive(active):
        return bool(cpl_active_is_substantive(live))
    live_chords = _cpl_chord_count(live)
    snap_chords = _cpl_chord_count(active)
    if cpl_active_is_substantive(live) and live_chords > 0:
        clear_cpl_intentional_new_song(session_state)
        return True
    live_name = str((live or {}).get("name") or "").strip() if isinstance(live, dict) else ""
    snap_name = str(active.get("name") or "").strip()
    # Heal titled chordless draft that still bears LAST_CUSTOM's name only.
    if live_chords == 0 and snap_chords > 0 and live_name and live_name == snap_name:
        clear_cpl_intentional_new_song(session_state)
        apply_cpl_session_progression(
            session_state,
            dict(active),
            reset_display_key=bool(reset_practice_key_to_original),
        )
        return True
    if session_state.get(CPL_SKIP_LAST_CUSTOM_RESTORE_KEY):
        return False
    if cpl_active_is_substantive(live):
        return True
    apply_cpl_session_progression(
        session_state,
        dict(active),
        reset_display_key=bool(reset_practice_key_to_original),
    )
    return True


def snapshot_last_custom_state(session_state: dict[str, Any]) -> None:
    """Remember the Custom draft last worked on (Custom page / SBI Custom).

    LAST_CUSTOM is identity memory for the Custom workspace — not Global Active.
    Snapshot whenever the live CPL draft is substantive, even if Catalog still owns
    Global Active (user edited Custom then left via Songs without Set-as-Active).
    """
    snap = _custom_snapshot_from_session(session_state)
    if not isinstance(snap, dict) or not isinstance(snap.get("active"), dict):
        return
    if cpl_active_is_substantive(snap["active"]):
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


def retire_catalog_transition_intents(session_state: dict[str, Any]) -> None:
    """Clear Use-catalog / Catalog-radio transition latches so a later Use Custom wins.

    USER_CATALOG / force-catalog / block-custom are *transition* intents (H9), not
    permanent locks. Explicit Songs Custom must retire them immediately (H1/H8).
    """
    session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
    session_state.pop(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY, None)
    session_state.pop(PENDING_CATALOG_FROM_PICKER_KEY, None)
    session_state.pop("_block_stale_custom_radio_reclaim", None)
    session_state.pop("_force_catalog_backing_after_use_catalog", None)


CATALOG_SWITCH_APPLIED_THIS_RUN_KEY = "_catalog_switch_applied_this_run"


def mark_catalog_switch_applied_this_run(session_state: dict[str, Any]) -> None:
    """Stamp so a lagging Custom radio cannot reclaim Custom in the same run (H9/H7)."""
    run_seq = int(session_state.get("_script_run_seq") or 0)
    session_state[CATALOG_SWITCH_APPLIED_THIS_RUN_KEY] = run_seq
    _assign_song_picker_source_widget(
        session_state, SONG_PICKER_SOURCE_CATALOG, widget_safe=False
    )
    # Always queue for next-run apply before reconcile (widget may be locked this run).
    session_state[PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
    session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
    session_state[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
    # Multi-run guard: Songs reconcile must not re-queue Custom while this is set.
    session_state["_catalog_owns_until_custom_click"] = True


def _ignore_stale_custom_radio_after_catalog_switch(session_state: dict[str, Any]) -> bool:
    """True when a Custom radio event is lag right after Use Catalog (H7).

    Streamlit often fires the old Custom radio on_change on the post-switch rerun,
    which used to pop ``_catalog_owns_until_custom_click`` and reclaim My Progression.
    Genuine Songs Use Custom after a couple of runs (H1/H8/H10) must still win.
    """
    page = str(session_state.get("studio_page") or session_state.get("page") or "").strip()
    block_n = int(session_state.get("_block_stale_custom_radio_reclaim") or 0)
    force_n = int(session_state.get("_force_catalog_backing_after_use_catalog") or 0)
    # Backing-only counters suppress Custom widget lag after Use catalog song backing.
    if page == "backing" and (block_n > 0 or force_n > 0):
        return True
    stamped = session_state.get(CATALOG_SWITCH_APPLIED_THIS_RUN_KEY)
    if stamped is None:
        return False
    try:
        run_seq = int(session_state.get("_script_run_seq") or 0)
        # Absorb widget lag on the switch run and the immediate following run only.
        return run_seq <= int(stamped) + 1
    except Exception:
        return bool(session_state.get("_catalog_owns_until_custom_click"))


def set_custom_source(session_state: dict[str, Any]) -> None:
    # Heal Catalog pick from Global Active title *before* sync — otherwise a stale
    # Say pick makes sync_catalog_session wipe a good Shape catalog_session, and
    # capture then stamps Say into _catalog_before_custom_state (H1/H9).
    leaving_catalog = str(session_state.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip() != SOURCE_CUSTOM
    try:
        from e5_reclaim_trace import note_e5_reclaim_writer

        # Always record Custom promotion after Catalog (H7 reclaim hunt).
        note_e5_reclaim_writer(
            session_state,
            writer="set_custom_source",
            reason=(
                "after_catalog"
                if (
                    session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY)
                    or session_state.get(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY)
                    or str(session_state.get(ACTIVE_MUSIC_SOURCE_KEY) or "") == SOURCE_CATALOG
                )
                else ""
            ),
        )
    except ImportError:
        pass
    live_title = str(
        session_state.get("song") or session_state.get("active_song_title") or ""
    ).strip()
    if live_title and not live_title.lower().startswith("my progression"):
        matched = _resolve_catalog_pick_for_live_title(session_state, live_title)
        if matched:
            from songs.state import ACTIVE_CATALOG_PICK_KEY

            session_state[ACTIVE_CATALOG_PICK_KEY] = matched
    capture_catalog_before_custom(session_state)
    # Hard guarantee: never leave Say in BEFORE when Global Active title is Shape
    # (hydration can leave pick/LAST on Say while the UI already shows Shape Bm).
    live_title = str(
        session_state.get("song") or session_state.get("active_song_title") or ""
    ).strip()
    before = session_state.get(CATALOG_BEFORE_CUSTOM_KEY)
    before_pick = (
        str((before or {}).get("pick_key") or "")
        if isinstance(before, dict)
        else ""
    )
    if (
        live_title
        and not live_title.lower().startswith("my progression")
        and before_pick
        and not _catalog_title_matches_live(
            str(((before or {}).get("selected_song") or {}).get("title") or before_pick),
            live_title,
        )
    ):
        cat = session_state.get("catalog_session")
        if isinstance(cat, dict) and _pick_key_is_catalog(str(cat.get("pick_key") or "")):
            cat_title = str((cat.get("selected_song") or {}).get("title") or "").strip()
            if cat_title and _catalog_title_matches_live(cat_title, live_title):
                session_state[CATALOG_BEFORE_CUSTOM_KEY] = dict(cat)
            else:
                matched = _resolve_catalog_pick_for_live_title(session_state, live_title)
                if matched:
                    from songs.state import ACTIVE_CATALOG_PICK_KEY

                    session_state[ACTIVE_CATALOG_PICK_KEY] = matched
                    capture_catalog_before_custom(session_state)
        else:
            matched = _resolve_catalog_pick_for_live_title(session_state, live_title)
            if matched:
                from songs.state import ACTIVE_CATALOG_PICK_KEY

                session_state[ACTIVE_CATALOG_PICK_KEY] = matched
                capture_catalog_before_custom(session_state)
    retire_catalog_transition_intents(session_state)
    try:
        import time as _time

        session_state[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = float(_time.time())
    except Exception:
        session_state[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = 1.0
    session_state.pop(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY, None)
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
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
    try:
        from workflow_musical_authority import refresh_custom_improv_concert_sections

        refresh_custom_improv_concert_sections(session_state)
    except ImportError:
        pass
    if leaving_catalog:
        # After catalog_session sync — otherwise it restamps the leftover Shape Dm.
        forget_catalog_visit_practice_key(session_state)


def promote_last_custom_for_picker_entry(session_state: dict[str, Any]) -> bool:
    """Custom→Songs nav: hydrate LAST_CUSTOM identity + Custom picker without radio click."""
    try:
        from songs.music_source import (
            SONG_PICKER_SOURCE_CUSTOM,
            _queue_last_custom_restore_from_session,
            install_last_custom_into_live_cpl,
            set_custom_source,
        )
        from songs.state import ACTIVE_CATALOG_PICK_KEY
    except ImportError:
        return False
    installed = install_last_custom_into_live_cpl(
        session_state, reset_practice_key_to_original=False
    )
    if not installed:
        snap = session_state.get(LAST_CUSTOM_STATE_KEY)
        active = (snap or {}).get("active") if isinstance(snap, dict) else None
        if not isinstance(active, dict):
            return False
    session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
    session_state.pop("_catalog_owns_until_custom_click", None)
    set_custom_source(session_state)
    _assign_song_picker_source_widget(
        session_state, SONG_PICKER_SOURCE_CUSTOM, widget_safe=False
    )
    session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
    _queue_last_custom_restore_from_session(session_state)
    pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if not pick.startswith("custom::"):
        try:
            from custom_progression_lab import cpl_active_from_session
            from songs.music_source import custom_pick_key_for, ensure_custom_active_song_identity

            ensure_custom_active_song_identity(session_state)
            active = cpl_active_from_session(session_state)
            pick = str(custom_pick_key_for(active) or "").strip()
            if pick.startswith("custom::"):
                session_state[ACTIVE_CATALOG_PICK_KEY] = pick
        except ImportError:
            pass
    try:
        from workflow_musical_authority import refresh_custom_improv_concert_sections

        refresh_custom_improv_concert_sections(session_state)
    except ImportError:
        pass
    return True


def music_picker_shows_custom_hub(session_state: dict[str, Any]) -> bool:
    """True when the Song Selection UI should show the custom library, not catalog."""
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if choice == SONG_PICKER_SOURCE_CATALOG:
        return False
    if choice.startswith("Use Custom"):
        return True
    return custom_progression_is_active(session_state)


def _expected_song_picker_source(session_state: dict[str, Any]) -> str:
    return (
        SONG_PICKER_SOURCE_CUSTOM
        if custom_progression_is_active(session_state) or is_custom_progression(session_state)
        else SONG_PICKER_SOURCE_CATALOG
    )


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
        session_state[SONG_PICKER_PRESENTED_SOURCE_KEY] = value
    except ImportError:
        try:
            session_state[SONG_PICKER_ACTIVE_SOURCE_KEY] = value
            session_state[SONG_PICKER_PRESENTED_SOURCE_KEY] = value
        except Exception:
            session_state[PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY] = value
    except Exception:
        # Streamlit locks the radio key after instantiate — queue for next run
        # (E5: Custom Set-as-Active must not crash the script mid-persist).
        session_state[PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY] = value


def apply_pending_song_picker_source_widget(session_state: dict[str, Any]) -> None:
    """Apply deferred Songs radio heal before the radio widget is created."""
    pending = session_state.pop(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, None)
    if pending is None:
        return
    try:
        session_state[SONG_PICKER_ACTIVE_SOURCE_KEY] = str(pending)
        session_state[SONG_PICKER_PRESENTED_SOURCE_KEY] = str(pending)
    except Exception:
        session_state[PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY] = pending


def note_song_picker_source_presented(session_state: dict[str, Any], value: str | None = None) -> None:
    """Record the Music-source radio value shown after the widget renders."""
    choice = str(value or session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if choice:
        session_state[SONG_PICKER_PRESENTED_SOURCE_KEY] = choice


def sync_song_picker_source_widget(
    session_state: dict[str, Any],
    *,
    force: bool = False,
    widget_safe: bool = True,
) -> None:
    """Align Song Selection source radio with active_music_source (init or forced promotion only)."""
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
    try:
        from e5_reclaim_trace import note_e5_reclaim_writer

        note_e5_reclaim_writer(
            session,
            writer="commit_catalog_active_song",
            reason=str(reason or ""),
            new_pick=str(pick_key or ""),
        )
    except ImportError:
        pass
    # Do not let restore/recovery catalog commits overwrite a newer Custom Set-as-Active.
    if explicit_custom_activation_is_authoritative(session):
        try:
            from e5_reclaim_trace import note_e5_reclaim_writer

            note_e5_reclaim_writer(
                session,
                writer="commit_catalog_active_song_blocked",
                reason=str(reason or "explicit_custom_epoch"),
                new_pick=str(pick_key or ""),
            )
        except ImportError:
            pass
        return
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
    )
    if reason in _reset_reasons:
        sticky = ""
        try:
            from songs.practice_key_state import get_practice_concert_key

            sticky = str(get_practice_concert_key(session, pick_key) or "").strip()
        except ImportError:
            sticky = ""
        if sticky:
            # Same-pick sticky Practice Key outranks Original (H2/H9).
            display_key = sticky
        elif reason in {"last_catalog_restore", "previous_catalog_restore", "switch_to_catalog_backing"}:
            # Keep caller/snap display_key. Do not inherit live Custom Practice Key
            # (Trial Eb must not become Catalog Shallow's Practice Key).
            display_key = str(display_key or original_key).strip() or original_key
        else:
            try:
                from practice_key_mode import resolve_practice_concert_key_for_song

                display_key = resolve_practice_concert_key_for_song(
                    session,
                    original_key,
                    pick_key=pick_key,
                    fallback=original_key,
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
    # True catalog *song* switches may force Original Key. Same-pick restores
    # ("Use catalog song backing", leave Custom/Creative) must keep sticky PK —
    # force_reset still runs identity apply, but reconcile skips Original when
    # display_key is an explicit sticky (≠ Original).
    _force_identity_reset = reason in {
        "catalog_source_switch",
        "last_catalog_restore",
        "previous_catalog_restore",
    }
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
        force_reset=_force_identity_reset,
    )
    # Force the Songs radio key immediately — widget_safe deferral leaves Custom
    # selected and the custom hub re-asserts Trial Song on the next paint.
    sync_song_picker_source_widget(session, force=True, widget_safe=False)
    session.pop(PENDING_CUSTOM_ACTIVE_SONG_KEY, None)
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

        persist_music_local_state(st, _persist_reason=reason)
    except ImportError:
        pass
    push_catalog_recent_pick_key(session, pick_key)
    pin_catalog_restore_identity(
        session,
        pick_key,
        selected_song,
        writer=reason,
    )
    # Keep LAST_CATALOG aligned with Global Catalog so Custom → Catalog restores
    # the song that was actually active (Shape), not a stale Say snap on disk.
    if _pick_key_is_catalog(pick_key):
        session[LAST_CATALOG_STATE_KEY] = {
            "pick_key": pick_key,
            "selected_song": dict(selected_song),
            "original_key": original_key,
            "display_key": display_key,
        }


def switch_to_catalog_from_custom(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
    force: bool = False,
) -> bool:
    """Leave Custom Progression for the last catalog song (or current catalog pick).

    When ``force`` is True (explicit \"Use catalog song backing\"), always restore
    the remembered Global Catalog source even if Custom flags were already cleared.
    """
    from songs.state import ACTIVE_CATALOG_PICK_KEY, apply_pick_key, first_valid_pick_key

    session = st.session_state
    pick_now = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    # Capture Custom identity BEFORE stamping the catalog epoch — otherwise
    # is_custom_progression() yields False and soft switch early-returns.
    identity_still_custom = bool(
        pick_now.startswith("custom::")
        or pick_now.startswith("custom\x1f")
        or str(session.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip() == SOURCE_CUSTOM
        or (
            isinstance(session.get("active_song_state"), dict)
            and str((session.get("active_song_state") or {}).get("music_source") or "") == SOURCE_CUSTOM
        )
        or (
            not session.get(USER_CATALOG_SOURCE_CHOICE_KEY)
            and (is_custom_progression(session) or custom_progression_is_active(session))
        )
    )
    # Stamp explicit catalog epoch BEFORE set_catalog_source so Custom epoch yields.
    begin_explicit_catalog_selection(session)
    # Drop queued Custom activation so the next prepare cannot re-apply Trial (E5 reverse).
    session.pop(PENDING_CUSTOM_ACTIVE_SONG_KEY, None)
    session.pop(PENDING_CUSTOM_LIBRARY_ACTION_KEY, None)
    try:
        from e5_reclaim_trace import note_e5_reclaim_writer

        note_e5_reclaim_writer(session, writer="switch_to_catalog_from_custom")
    except ImportError:
        pass
    if (
        not force
        and not identity_still_custom
        and str(session.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip() != SOURCE_CUSTOM
    ):
        return False
    snapshot_last_custom_state(session)
    session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    session.pop(CATALOG_SWITCH_APPLIED_THIS_RUN_KEY, None)
    mark_catalog_switch_applied_this_run(session)
    # Keep lock until restore succeeds so apply_pick_key can treat lock==pick as
    # an explicit Catalog switch (and BEFORE Say cannot outrank Shape lock).
    lock_pick = str(session.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY) or "").strip()

    # prepare_canonical pops reconcile catalog; Backing click must still resolve Shape.
    song_picker_catalog = ensure_song_picker_catalog(session, song_picker_catalog)
    song_library = ensure_song_library(session, song_library)

    def _trace(msg: str) -> None:
        try:
            from pathlib import Path

            p = Path("scripts/evidence-creative-backing/e5-switch-trace.txt")
            prev = p.read_text(encoding="utf-8") if p.exists() else ""
            p.write_text(prev + msg + "\n", encoding="utf-8")
        except Exception:
            pass

    _trace(
        f"enter pick={pick_now!r} genres={list((song_picker_catalog or {}).keys())[:6]!r} "
        f"has_last={isinstance(session.get(LAST_CATALOG_STATE_KEY), dict)} "
        f"has_before={isinstance(session.get(CATALOG_BEFORE_CUSTOM_KEY), dict)} "
        f"lock={lock_pick!r}"
    )

    def _snap_for_lock(pk: str) -> dict[str, Any] | None:
        if not _pick_key_is_catalog(pk):
            return None
        for snap_key in (
            CATALOG_BEFORE_CUSTOM_KEY,
            LAST_CATALOG_STATE_KEY,
            "catalog_session",
        ):
            raw = session.get(snap_key)
            if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip() == pk:
                return dict(raw)
        label = pk.split("\x1f", 1)[-1] if "\x1f" in pk else pk
        title = label.split(" — ", 1)[0].strip() or label
        artist = label.split(" — ", 1)[-1].strip() if " — " in label else ""
        return {
            "pick_key": pk,
            "selected_song": {
                "pick_key": pk,
                "title": title,
                "artist": artist,
            },
        }

    def _data_matches_pick(data: dict[str, Any], pick_key: str) -> bool:
        """Reject apply_pick blocked-returns of Custom / wrong SELECTED."""
        title = str(data.get("title") or "").strip()
        if not title:
            return False
        if title.lower().startswith("my progression"):
            return False
        label = pick_key.split("\x1f", 1)[-1] if "\x1f" in pick_key else pick_key
        expected = label.split(" — ", 1)[0].strip()
        if expected and not _catalog_title_matches_live(title, expected):
            return False
        return True

    def _try_restore_from_snap(snap: dict[str, Any]) -> bool:
        pick_key = str(snap.get("pick_key") or "").strip()
        if not _pick_key_is_catalog(pick_key):
            return False
        selected = dict(snap.get("selected_song") or {})
        data = apply_pick_key(
            st,
            pick_key,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
        )
        if not data or not _data_matches_pick(data, pick_key):
            return False
        # Catalog row key is authoritative Original Key — never trust a hardcoded
        # snap fallback of "C" (that polluted Shape of You → Original Key C).
        catalog_key = str(data.get("key") or "").strip()
        snap_orig = str(snap.get("original_key") or selected.get("key") or "").strip()
        original_key = catalog_key or snap_orig or "C"
        if original_key == "C" and catalog_key and catalog_key != "C":
            original_key = catalog_key
        # Prefer non-C snap/catalog when row key is missing but snap has Bm.
        if (not catalog_key or catalog_key == "C") and snap_orig and snap_orig != "C":
            original_key = snap_orig
        selected.setdefault("title", str(data.get("title") or ""))
        selected.setdefault("artist", str(data.get("artist") or ""))
        selected["key"] = original_key
        selected["pick_key"] = pick_key
        # Fresh Catalog activation after Custom Global Active uses Original Key.
        # Same-pick return while Catalog never lost GA keeps visit sticky.
        display_key = original_key
        if not identity_still_custom:
            try:
                from songs.practice_key_state import get_practice_concert_key

                sticky = str(get_practice_concert_key(session, pick_key) or "").strip()
                if sticky:
                    display_key = sticky
                else:
                    snap_dk = str(snap.get("display_key") or "").strip()
                    # Ignore snap display when it is only the bogus hardcoded "C" default
                    # and the catalog original is something else.
                    if snap_dk and not (snap_dk == "C" and original_key != "C" and not sticky):
                        display_key = snap_dk
            except ImportError:
                snap_dk = str(snap.get("display_key") or original_key).strip() or original_key
                display_key = snap_dk
        else:
            try:
                from songs.practice_key_state import clear_practice_concert_key

                clear_practice_concert_key(session, pick_key)
            except ImportError:
                pass
        commit_catalog_active_song(
            st,
            pick_key=pick_key,
            selected_song=selected,
            original_key=original_key,
            display_key=display_key,
            invalidate_backing=invalidate_backing,
            reason="last_catalog_restore",
        )
        # Restore succeeded — clear sticky Catalog→Custom lock.
        session.pop(CATALOG_BEFORE_CUSTOM_LOCK_KEY, None)
        _trace(
            f"after_commit pick={session.get(ACTIVE_CATALOG_PICK_KEY)!r} "
            f"source={session.get(ACTIVE_MUSIC_SOURCE_KEY)!r} "
            f"song={session.get('song')!r} orig={original_key!r} dk={display_key!r}"
        )
        return True

    # Lock pick wins over a polluted BEFORE (Say) when live Catalog was Shape.
    if _pick_key_is_catalog(lock_pick):
        lock_snap = _snap_for_lock(lock_pick)
        if lock_snap and _try_restore_from_snap(lock_snap):
            _trace(f"restored_from lock pick={lock_pick!r}")
            return True

    for snap_key in (CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY):
        snap = session.get(snap_key)
        if isinstance(snap, dict) and _try_restore_from_snap(snap):
            _trace(f"restored_from {snap_key} pick={snap.get('pick_key')!r}")
            return True

    # Prefer the live catalog pick when leaving Custom if snaps were polluted
    # (e.g. LAST_CATALOG still Say while the user had Shape active).
    pick_key = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if _pick_key_is_catalog(pick_key):
        if _try_restore_from_snap({"pick_key": pick_key, "selected_song": {}}):
            _trace(f"restored_from live_pick={pick_key!r}")
            return True

    for pick_key in session.get(CATALOG_RECENT_PICK_KEYS) or []:
        pk = str(pick_key or "").strip()
        if not _pick_key_is_catalog(pk):
            continue
        # Do not pass original_key/display_key "C" — catalog row supplies them.
        if _try_restore_from_snap({"pick_key": pk, "selected_song": {}}):
            _trace(f"restored_from recent pick={pk!r}")
            return True

    pick_key = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if _pick_key_is_catalog(pick_key):
        data = apply_pick_key(
            st,
            pick_key,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
        )
        if data and _data_matches_pick(data, pick_key):
            original_key = str(data.get("key") or "C").strip() or "C"
            display_key = original_key
            if not identity_still_custom:
                try:
                    from songs.practice_key_state import get_practice_concert_key

                    sticky = str(get_practice_concert_key(session, pick_key) or "").strip()
                    if sticky:
                        display_key = sticky
                except ImportError:
                    pass
            else:
                try:
                    from songs.practice_key_state import clear_practice_concert_key

                    clear_practice_concert_key(session, pick_key)
                except ImportError:
                    pass
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
                reason="last_catalog_restore",
            )
            session.pop(CATALOG_BEFORE_CUSTOM_LOCK_KEY, None)
            return True

    # Prefer lock/BEFORE target over first_valid (Say) when catalog was empty then loaded.
    preferred = lock_pick
    if not _pick_key_is_catalog(preferred):
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY)
        if isinstance(before, dict):
            preferred = str(before.get("pick_key") or "").strip()
    if _pick_key_is_catalog(preferred):
        # Second chance after disk load above — catalog may have been empty on entry.
        song_picker_catalog = ensure_song_picker_catalog(session, song_picker_catalog)
        song_library = ensure_song_library(session, song_library)
        if _try_restore_from_snap(_snap_for_lock(preferred) or {"pick_key": preferred}):
            _trace(f"restored_from preferred_retry pick={preferred!r}")
            return True

    fallback = first_valid_pick_key(song_picker_catalog)
    # Never let first_valid (often Say) beat a remembered Shape lock/BEFORE.
    if fallback and (
        not _pick_key_is_catalog(preferred) or fallback == preferred
    ):
        if _try_restore_from_snap({"pick_key": fallback, "selected_song": {}}):
            return True

    # Last resort: still leave custom:: identity so Songs/Backing cannot stay stuck.
    if fallback and (
        not _pick_key_is_catalog(preferred) or fallback == preferred
    ):
        data = apply_pick_key(
            st,
            fallback,
            song_picker_catalog,
            song_library=song_library,
            skip_activity_log=True,
        )
        if data and _data_matches_pick(data, fallback):
            original_key = str(data.get("key") or "C").strip() or "C"
            commit_catalog_active_song(
                st,
                pick_key=fallback,
                selected_song={
                    "pick_key": fallback,
                    "title": str(data.get("title") or ""),
                    "artist": str(data.get("artist") or ""),
                    "key": original_key,
                },
                original_key=original_key,
                display_key=original_key,
                invalidate_backing=invalidate_backing,
                reason="catalog_source_switch_fallback",
            )
            session.pop(CATALOG_BEFORE_CUSTOM_LOCK_KEY, None)
            _trace(f"restored_from fallback_commit pick={fallback!r}")
            return True

    # Do NOT set catalog_song with song=None when we still have a remembered pick —
    # that leaves the UI showing Custom / blank identity (H7). Keep Custom flags
    # cleared only after a real restore; retry preferred once more is already done.
    if _pick_key_is_catalog(preferred):
        _trace(f"restore_failed_keep_attempting preferred={preferred!r}")
        # Force-apply via commit using snap selected_song when picker rows missing.
        snap = _snap_for_lock(preferred) or {}
        sel = dict(snap.get("selected_song") or {})
        if sel.get("title"):
            orig = str(snap.get("original_key") or sel.get("key") or "C").strip() or "C"
            commit_catalog_active_song(
                st,
                pick_key=preferred,
                selected_song=sel,
                original_key=orig,
                display_key=str(snap.get("display_key") or orig).strip() or orig,
                invalidate_backing=invalidate_backing,
                reason="last_catalog_restore",
            )
            session.pop(CATALOG_BEFORE_CUSTOM_LOCK_KEY, None)
            if str(session.get("song") or "").strip():
                _trace(f"restored_from snap_direct pick={preferred!r}")
                return True

    _trace("fallback_set_catalog_source_only")
    set_catalog_source(session)
    sync_song_picker_source_widget(session, force=True)
    note_active_source_change(st, invalidate_backing=invalidate_backing)
    return True


def restore_last_custom_active_song(
    st: Any,
    *,
    invalidate_backing,
) -> bool:
    """Restore the last custom progression when returning from catalog."""
    session = st.session_state
    # Explicit Catalog ownership (Use catalog / Catalog radio) must not be
    # overwritten by LAST_CUSTOM memory (H9).
    if session.get(USER_CATALOG_SOURCE_CHOICE_KEY) or explicit_catalog_selection_is_authoritative(session):
        return False
    snap = session.get(LAST_CUSTOM_STATE_KEY)
    if isinstance(snap, dict) and isinstance(snap.get("active"), dict):
        commit_custom_active_song(
            st,
            dict(snap["active"]),
            invalidate_backing=invalidate_backing,
        )
        return True
    try:
        from custom_progression_lab import cpl_active_from_session

        active = cpl_active_from_session(session)
        if str(active.get("name") or "").strip():
            commit_custom_active_song(st, active, invalidate_backing=invalidate_backing)
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
    # Stale PENDING after Set-as-Active must not reclaim Country Roads while Custom
    # owns practice and the user has not stamped an explicit Catalog epoch (E5).
    if explicit_custom_activation_is_authoritative(st.session_state):
        return False
    if custom_progression_is_active(st.session_state) and not st.session_state.get(
        USER_CATALOG_SOURCE_CHOICE_KEY
    ):
        return False
    return switch_to_catalog_from_custom(
        st,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
        invalidate_backing=invalidate_backing,
    )


def on_song_picker_source_change(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]] | None = None,
    invalidate_backing,
) -> None:
    """Radio callback: switch catalog ↔ custom without post-render rerun loops."""
    choice = str(st.session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    if choice.startswith("Use Custom") or choice == SONG_PICKER_SOURCE_CUSTOM:
        # After "Use catalog song backing/instead", suppress stale Custom radio
        # restores from Streamlit widget lag (H7/H9). Genuine Songs Custom a few
        # seconds later still wins (H1/H8) once the Catalog epoch ages out.
        if _ignore_stale_custom_radio_after_catalog_switch(st.session_state):
            _block_n = int(st.session_state.get("_block_stale_custom_radio_reclaim") or 0)
            if _block_n > 0:
                st.session_state["_block_stale_custom_radio_reclaim"] = _block_n - 1
                if st.session_state["_block_stale_custom_radio_reclaim"] <= 0:
                    st.session_state.pop("_block_stale_custom_radio_reclaim", None)
            try:
                from e5_reclaim_trace import note_e5_reclaim_writer

                note_e5_reclaim_writer(
                    st.session_state,
                    writer="on_song_picker_source_change_ignored",
                    reason="stale_custom_radio_after_use_catalog",
                )
            except ImportError:
                pass
            _assign_song_picker_source_widget(
                st.session_state, SONG_PICKER_SOURCE_CATALOG, widget_safe=False
            )
            st.session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
            return
        # Songs (or other): retire Catalog transition intents; explicit Custom wins.
        session_state = st.session_state
        session_state.pop("_catalog_owns_until_custom_click", None)
        retire_catalog_transition_intents(session_state)
        set_custom_source(session_state)
        if not restore_last_custom_active_song(st, invalidate_backing=invalidate_backing):
            try:
                from custom_progression_lab import cpl_active_from_session

                queue_custom_active_song_activation(st, cpl_active_from_session(st.session_state))
            except Exception:
                pass
        else:
            note_active_source_change(st, invalidate_backing=invalidate_backing)
        st.session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        st.rerun()
        return
    # Stale Catalog radio callbacks after Custom Set-as-Active must not reclaim
    # Country Roads (E5). Distinguish:
    # - Spurious: Custom owns AND the radio never left Catalog (presented still Catalog)
    #   → heal, ignore.
    # - Genuine: Custom owns AND radio was showing Custom (or last reconciled Custom),
    #   user selected Catalog → switch immediately. Explicit user choice always wins.
    if explicit_custom_activation_is_authoritative(st.session_state):
        presented = str(st.session_state.get(SONG_PICKER_PRESENTED_SOURCE_KEY) or "").strip()
        presented_custom = presented.startswith("Use Custom") or presented == SONG_PICKER_SOURCE_CUSTOM
        last_rec = str(st.session_state.get(LAST_RECONCILED_SONG_PICKER_SOURCE_KEY) or "").strip()
        last_was_custom = last_rec.startswith("Use Custom") or last_rec == SONG_PICKER_SOURCE_CUSTOM
        pick_now = str(st.session_state.get("active_catalog_pick_key") or "").strip()
        identity_still_custom = (
            pick_now.startswith("custom::")
            or is_custom_progression(st.session_state)
            or custom_progression_is_active(st.session_state)
        )
        # If Custom still owns Global Active, a Catalog radio click is genuine only
        # when the Songs radio actually presented Custom (user flipped Catalog), not
        # when Set-as-Active left a lagging Catalog widget (E5). Hub "Use catalog"
        # buttons call switch_to_catalog_from_custom directly (H7/H9).
        genuine_catalog_from_custom = presented_custom or last_was_custom
        if not genuine_catalog_from_custom:
            try:
                from e5_reclaim_trace import note_e5_reclaim_writer

                note_e5_reclaim_writer(
                    st.session_state,
                    writer="on_song_picker_source_change_ignored",
                    reason="stale_catalog_widget_not_presented_custom",
                )
            except ImportError:
                pass
            st.session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
            _assign_song_picker_source_widget(
                st.session_state, SONG_PICKER_SOURCE_CUSTOM, widget_safe=False
            )
            st.session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
            return
    st.session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
    pick_now = str(st.session_state.get("active_catalog_pick_key") or "").strip()
    leaving_custom = (
        is_custom_progression(st.session_state)
        or custom_progression_is_active(st.session_state)
        or pick_now.startswith("custom::")
    )
    begin_explicit_catalog_selection(st.session_state)
    st.session_state[SONG_PICKER_PRESENTED_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
    mark_catalog_switch_applied_this_run(st.session_state)
    if leaving_custom:
        switch_to_catalog_from_custom(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
            invalidate_backing=invalidate_backing,
        )
    st.rerun()
    return


def _queue_last_custom_restore_from_session(session_state: dict[str, Any]) -> bool:
    """Queue LAST_CUSTOM / CPL active for before-widget commit (Songs Use Custom)."""
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    # Source flag alone is not enough — after H9, set_custom_source may flip the
    # flag while Global identity is still Shape. Only skip when Custom already owns.
    if pick.startswith("custom::") and is_custom_progression(session_state):
        return False
    active = None
    snap = session_state.get(LAST_CUSTOM_STATE_KEY)
    if isinstance(snap, dict) and isinstance(snap.get("active"), dict):
        active = dict(snap["active"])
    if active is None:
        try:
            from custom_progression_lab import cpl_active_from_session

            candidate = cpl_active_from_session(session_state)
            if str(candidate.get("name") or "").strip():
                active = candidate
        except Exception:
            active = None
    if not isinstance(active, dict):
        return False
    try:
        import time as _time

        session_state[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = float(_time.time())
    except Exception:
        session_state[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = 1.0
    session_state.pop(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY, None)
    session_state["cpl_active_progression"] = active
    session_state[PENDING_CUSTOM_ACTIVE_SONG_KEY] = {
        "cpl_active_key": "cpl_active_progression",
    }
    return True


def reconcile_picker_music_source(session_state: dict[str, Any]) -> bool:
    """Align active source with Songs page picker widget before widgets render."""
    page = str(
        session_state.get("studio_page") or session_state.get("page") or ""
    ).strip()
    choice = str(session_state.get(SONG_PICKER_ACTIVE_SOURCE_KEY) or "").strip()
    choice_custom = choice.startswith("Use Custom") or choice == SONG_PICKER_SOURCE_CUSTOM
    # After Use catalog, heal lagging Custom radio ONLY on Backing (widget lag).
    # On Songs, the same latch must never defeat an explicit Use Custom (H1/H8).
    if (
        page == "backing"
        and int(session_state.get("_block_stale_custom_radio_reclaim") or 0) > 0
        and choice_custom
    ):
        _assign_song_picker_source_widget(
            session_state, SONG_PICKER_SOURCE_CATALOG, widget_safe=False
        )
        session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        session_state[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
            set_catalog_source(session_state)
        return True
    if page != "picker":
        return reconcile_music_picker_source_widget(session_state)
    if choice_custom:
        stamped = session_state.get(CATALOG_SWITCH_APPLIED_THIS_RUN_KEY)
        run_seq = int(session_state.get("_script_run_seq") or 0)
        catalog_guard = bool(session_state.get("_catalog_owns_until_custom_click"))
        if (
            (stamped is not None and int(stamped) == run_seq)
            or catalog_guard
            or _ignore_stale_custom_radio_after_catalog_switch(session_state)
        ):
            # Catalog switch still owns — heal lagging Custom radio; do not reclaim.
            # Cleared only by explicit Songs Custom on_change / set_custom (H1/H8).
            _assign_song_picker_source_widget(
                session_state, SONG_PICKER_SOURCE_CATALOG, widget_safe=False
            )
            session_state[PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
            session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
            session_state.pop(PENDING_CUSTOM_ACTIVE_SONG_KEY, None)
            if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) != SOURCE_CATALOG:
                set_catalog_source(session_state)
            return True
        # Explicit Songs Custom (H1/H8): retire Catalog transition intents and promote.
        session_state.pop("_catalog_owns_until_custom_click", None)
        retire_catalog_transition_intents(session_state)
        changed = False
        if not is_custom_progression(session_state):
            set_custom_source(session_state)
            changed = True
        else:
            retire_catalog_transition_intents(session_state)
        _assign_song_picker_source_widget(
            session_state, SONG_PICKER_SOURCE_CUSTOM, widget_safe=False
        )
        session_state[LAST_RECONCILED_SONG_PICKER_SOURCE_KEY] = SONG_PICKER_SOURCE_CUSTOM
        if _queue_last_custom_restore_from_session(session_state):
            changed = True
        return changed or True
    # Catalog radio showing. Keep ``_catalog_owns_until_custom_click`` until an
    # explicit Custom click — clearing it here let lagging Custom reclaim after
    # Use Catalog restored Shape (H7).
    if session_state.get(USER_CATALOG_SOURCE_CHOICE_KEY):
        return reconcile_music_picker_source_widget(session_state)
    return reconcile_music_picker_source_widget(session_state)


def custom_original_key(active: dict[str, Any]) -> str:
    """User-chosen CPL original key (never inferred from chord analysis)."""
    from custom_progression_lab import cpl_draft_written_key, ensure_original_structure

    return cpl_draft_written_key(ensure_original_structure(active))


def _catalog_original_key_for_session(
    session_state: dict[str, Any],
    rec: dict[str, Any] | None = None,
) -> str:
    """Original/home key from catalog library — never a Custom-polluted selected.key.

    Shape of You must stay Bm even when selected_song.key was overwritten with C
    from a Custom progression snapshot (H9).
    """
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    selected = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY)
        or selected.get("pick_key")
        or ""
    ).strip()
    record = rec if isinstance(rec, dict) else {}
    # Prefer live catalog row over selected_song.key / passed rec (which can carry
    # Custom C pollution onto Shape of You).
    try:
        catalog = session_state.get("_reconcile_song_picker_catalog")
        row = _catalog_row_for_pick(pick_key, catalog) if pick_key and isinstance(catalog, dict) else None
        if isinstance(row, dict) and row.get("key"):
            return str(row.get("key") or "C").strip() or "C"
    except Exception:
        pass
    try:
        selected_resolved, original = resolve_catalog_song_for_pick(session_state, pick_key)
        if original:
            # Heal polluted selected_song.key so sidebar stays on catalog Original.
            if isinstance(selected_resolved, dict) and pick_key:
                live_sel = dict(selected) if isinstance(selected, dict) else {}
                if str(live_sel.get("pick_key") or "").strip() == pick_key:
                    if str(live_sel.get("key") or "").strip() != str(original).strip():
                        live_sel["key"] = str(original).strip()
                        session_state[SELECTED_SONG_STATE_KEY] = live_sel
            return str(original).strip() or "C"
    except Exception:
        pass
    if record.get("key") and pick_key and not str(pick_key).startswith("custom"):
        # Only trust passed rec after catalog row lookup failed.
        return str(record.get("key") or "C").strip() or "C"
    if pick_key and str(selected.get("pick_key") or "").strip() == pick_key and selected.get("key"):
        return str(selected.get("key") or "C").strip() or "C"
    # Do not fall through to an unrelated selected_song.key (Say G / Custom C)
    # when the live pick is a different catalog song (Shape → Bm).
    return "C"


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
            from backing_source_navigation import invalidate_backing_restore_for_active_source_change

            prev_id = f"pk::{previous_pick}" if previous_pick else ""
            new_id = f"pk::{current_pick}" if current_pick else ""
            if current_source == SOURCE_CUSTOM:
                new_id = compute_active_song_identity(is_custom=True, pick_key=current_pick)
            invalidate_backing_restore_for_active_source_change(
                session_state,
                previous_identity=str(prev_id or ""),
                new_identity=str(new_id or ""),
                reason="note_active_source_change",
            )
        except ImportError:
            pass
        if pick_changed and current_source == SOURCE_CATALOG:
            try:
                snapshot_catalog_before_creative(session_state, refresh_if_pick_changed=True)
            except Exception:
                pass
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
        # Explicit Mission/SBI/Jam Backing visit: sticky Custom restore / force_reset
        # must not wipe the live Practice Key or reclaim specialized ownership.
        handoff = str(session.get("_backing_explicit_handoff_source") or "").strip()
        if handoff in {"mission", "song_improv", "entry_jam"} and not session.get(
            "_backing_released_specialized_context"
        ):
            session[ACTIVE_SONG_IDENTITY_KEY] = new_identity
            try:
                from mission_pk_reclaim_trace import note_mission_pk_reclaim

                note_mission_pk_reclaim(
                    session,
                    writer="on_active_song_identity_changed:skipped_specialized",
                    extra={
                        "force_reset": bool(force_reset),
                        "prev_identity": str(prev_identity or ""),
                        "new_identity": new_identity,
                        "handoff": handoff,
                    },
                )
            except ImportError:
                pass
            return False
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
        try:
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

            if is_fixed_practice_key_mode(session):
                target_display = resolve_practice_concert_key_for_song(
                    session,
                    original_key,
                    pick_key=pick_key,
                    fallback=target_display,
                )
            elif display_key is None:
                target_display = resolve_practice_concert_key_for_song(
                    session,
                    original_key,
                    pick_key=pick_key,
                    fallback=target_display,
                )
        except ImportError:
            pass
        if not is_custom and pick_key:
            try:
                from music_workflow_song_practice import reconcile_practice_key_after_active_source_change

                prev_pick = ""
                prev_id = str(prev_identity or "").strip()
                if prev_id.startswith("pk::"):
                    prev_pick = prev_id[4:]
                # When the caller already resolved sticky Practice Key into
                # display_key, do not force Original via source-change reconcile.
                explicit_sticky = (
                    display_key is not None
                    and str(display_key).strip()
                    and str(display_key).strip() != str(original_key or "").strip()
                )
                healed = reconcile_practice_key_after_active_source_change(
                    session,
                    pick_key=str(pick_key).strip(),
                    original_key=str(original_key or "").strip(),
                    previous_pick_key=prev_pick,
                    source="on_active_song_identity_changed",
                    force_source_change=bool(force_reset) and not explicit_sticky,
                )
                if healed and not explicit_sticky:
                    target_display = healed
            except ImportError:
                pass
        if pick_key:
            session["active_catalog_pick_key"] = str(pick_key).strip()
        try:
            from session_widget_safe import reconcile_practice_key_fields

            reconcile_practice_key_fields(session, authoritative=target_display)
        except ImportError:
            session["concert_key"] = target_display
            session["_pending_display_key"] = target_display
        try:
            from music_workflow_song_practice import ensure_song_practice_blob_for_active_song

            ensure_song_practice_blob_for_active_song(
                session,
                practice_key=target_display,
                original_key=original_key,
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
            from backing_source_navigation import invalidate_backing_restore_for_active_source_change

            invalidate_backing_restore_for_active_source_change(
                session,
                previous_identity=str(prev_identity or ""),
                new_identity=str(new_identity or ""),
                reason="on_active_song_identity_changed",
            )
        except ImportError:
            pass
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
            from songs.state import ACTIVE_CATALOG_PICK_KEY

            if pick_key and not is_custom:
                session[ACTIVE_CATALOG_PICK_KEY] = str(pick_key).strip()
            if title:
                session["song"] = str(title)
            try:
                from songs.state import SELECTED_SONG_STATE_KEY as _SEL_KEY
            except ImportError:
                _SEL_KEY = "selected_song"
            sel = _selected_song_for_identity(
                session.get(_SEL_KEY),
                pick_key=pick_key,
                title=title,
                artist=artist,
                original_key=original_key,
                song_data=song_data,
            )
            if sel:
                session[_SEL_KEY] = sel
        except ImportError:
            if pick_key and not is_custom:
                session["active_catalog_pick_key"] = str(pick_key).strip()
            if title:
                session["song"] = str(title)
            sel = _selected_song_for_identity(
                session.get("selected_song"),
                pick_key=pick_key,
                title=title,
                artist=artist,
                original_key=original_key,
                song_data=song_data,
            )
            if sel:
                session["selected_song"] = sel
        for stale_key in (
            "improv_song_concert_sections",
            "home_sections",
            "_music_song_creative_focus",
            "improv_mission_example",
            "_missions_tab_generate_context",
            "_mission_example_output_fp",
            "_mission_example_material_fp",
            "harmony_map_section_selections",
            "_creative_session_hydrated_creative",
        ):
            session.pop(stale_key, None)
        try:
            from workflow_musical_authority import sync_song_improv_sections_to_practice_key

            sync_song_improv_sections_to_practice_key(session)
        except ImportError:
            pass
        try:
            from backing_context import reset_backing_on_active_song_change

            # Explicit specialized Backing handoff outranks Custom/Catalog identity
            # force_reset (workspace sticky restore must not reclaim Mission PK visit).
            handoff = str(session.get("_backing_explicit_handoff_source") or "").strip()
            skip_reset = handoff in {"mission", "song_improv", "entry_jam"} and not session.get(
                "_backing_released_specialized_context"
            )
            if not skip_reset:
                reset_backing_on_active_song_change(
                    session,
                    new_pick_key=pick_key,
                    practice_concert_key=target_display,
                )
        except ImportError:
            pass
        try:
            from workflow_musical_authority import sync_song_improv_sections_to_practice_key

            sync_song_improv_sections_to_practice_key(session)
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
    """Return ``(source_kind, source_detail)`` for the sidebar active-source banner."""
    if is_custom_progression(session_state):
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

    pick_key = str(
        session_state.get(ACTIVE_CATALOG_PICK_KEY)
        or (session_state.get(SELECTED_SONG_STATE_KEY) or {}).get("pick_key")
        or ""
    ).strip()
    # Catalog Global Active must use catalog Original Key even if CPL widgets lag.
    if _pick_key_is_catalog(pick_key) or (
        session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CATALOG
        and not str(session_state.get("song") or "").lower().startswith("my progression")
        and not custom_progression_is_active(session_state)
    ):
        original = _catalog_original_key_for_session(session_state, catalog_song_data)
        if not original or original == "C":
            original = str(catalog_song_data.get("key") or original or "C").strip() or "C"
        from songs.key_state import song_display_identity

        return original, song_display_identity(
            str(catalog_song_data.get("title") or session_state.get("song") or ""),
            str(catalog_song_data.get("artist") or ""),
            str(original),
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
    # Capture BEFORE Catalog identity is replaced on the next-run commit.
    capture_catalog_before_custom(session)
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active
    # Stale Custom→Catalog pending must not beat Set-as-Active (E5): catalog
    # apply+persist would leave Trial in session while disk stays Country Roads.
    session.pop(PENDING_CATALOG_FROM_PICKER_KEY, None)
    session.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
    # Stamp Custom epoch on queue (not only on commit). Otherwise a prior Catalog
    # pick (e.g. Country Roads before Trial) makes
    # ``explicit_catalog_selection_is_authoritative`` discard this pending on the
    # next run and Set-as-Active never lands (E5 after E1–E4 residue).
    try:
        import time as _time

        session[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = float(_time.time())
    except Exception:
        session[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = 1.0
    session.pop(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY, None)
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
    if explicit_catalog_selection_is_authoritative(session):
        # Do not let a stale Custom library activate reclaim Trial after Catalog switch.
        pending_peek = session.get(PENDING_CUSTOM_LIBRARY_ACTION_KEY)
        if isinstance(pending_peek, dict) and str(pending_peek.get("action") or "") == "activate":
            session.pop(PENDING_CUSTOM_LIBRARY_ACTION_KEY, None)
            return False
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
        mark_cpl_intentional_new_song(session)
        active = start_new_progression()
    else:
        name = str(pending.get("name") or "").strip()
        if not name:
            return False
        saved = session.get(CPL_SAVED_KEY) or {}
        active = load_saved_progression(saved, name)
        clear_cpl_intentional_new_song(session)

    apply_cpl_session_progression(session, active, reset_display_key=True)

    if action == "activate":
        clear_cpl_intentional_new_song(session)
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
    if explicit_catalog_selection_is_authoritative(session):
        session.pop(PENDING_CUSTOM_ACTIVE_SONG_KEY, None)
        return False
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
) -> dict[str, Any]:
    """Promote CPL draft to the global active song (source, title, key, playback, cloud).

    Must run before sidebar/global widgets render. Use ``queue_custom_active_song_activation``
    from page callbacks, then ``apply_pending_custom_active_song_activation_before_widgets``
    at app startup.
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
    # Capture Catalog identity before pick_key becomes custom:: (H1/H9 toggle).
    capture_catalog_before_custom(session)
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active
    # Explicit Set-as-Active / Use Custom outranks post-Use-Catalog guard.
    session.pop("_catalog_owns_until_custom_click", None)
    retire_catalog_transition_intents(session)
    # Explicit Custom activation epoch — outranks stale catalog restore/recovery.
    try:
        import time as _time

        session[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = float(_time.time())
    except Exception:
        session[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = 1.0
    # Until the Songs radio successfully presents Custom, Catalog on_change is stale.
    session.pop(SONG_PICKER_PRESENTED_SOURCE_KEY, None)
    try:
        from e5_reclaim_trace import enable_e5_reclaim_sampling

        enable_e5_reclaim_sampling(session)
    except ImportError:
        pass
    _push_recent_custom_name(session, str(active.get("name") or "My Progression"))
    snapshot_last_custom_state(session)

    home_key = cpl_draft_written_key(active)
    selected = custom_selected_song_record(active)
    pick_key = str(selected.get("pick_key") or "").strip()
    leaving_catalog = str(session.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip() != SOURCE_CUSTOM
    practice_key = home_key
    if leaving_catalog:
        # New Custom activation from Catalog is fresh at Original Key.
        # Leftover Perfect G / Shape Dm must not become Trial Practice Key.
        try:
            from practice_key_mode import apply_fixed_mode_target, is_fixed_practice_key_mode

            if is_fixed_practice_key_mode(session):
                practice_key = apply_fixed_mode_target(session, home_key, home_key)
        except ImportError:
            pass
        session["display_key"] = practice_key
        session["concert_key"] = practice_key
        try:
            from custom_progression_lab import (
                CPL_LAST_DISPLAY_KEY,
                CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            )

            session[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET] = practice_key
            session[CPL_LAST_DISPLAY_KEY] = practice_key
            session["_cpl_force_pk_to_home"] = practice_key
        except ImportError:
            pass
        try:
            from songs.practice_key_state import set_practice_concert_key

            if pick_key.startswith("custom::"):
                # Catalog's last sidebar commit (Perfect G) must not block Original D.
                session.pop("_pk_user_commit_token", None)
                session.pop("_pk_user_commit_at", None)
                set_practice_concert_key(
                    session,
                    practice_key,
                    pick_key=pick_key,
                    allow_restore_original=True,
                )
        except ImportError:
            pass
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

    try:
        from workflow_musical_authority import refresh_custom_improv_concert_sections

        refresh_custom_improv_concert_sections(session)
    except ImportError:
        pass

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

        persist_music_local_state(st, _persist_reason="custom_active_song")
        # Drop any deferred page_change save that could stamp the prior catalog
        # song over Trial after Set-as-Active (E5 refresh flake).
        session.pop("_suite_deferred_page_change_save", None)
    except ImportError:
        pass

    try:
        from music_persistent_state import clear_music_ephemeral_default_song

        clear_music_ephemeral_default_song(session)
    except ImportError:
        pass

    if leaving_catalog:
        session["display_key"] = practice_key
        session["concert_key"] = practice_key
        try:
            from songs.practice_key_state import set_practice_concert_key

            if pick_key.startswith("custom::"):
                set_practice_concert_key(
                    session,
                    practice_key,
                    pick_key=pick_key,
                    allow_restore_original=True,
                )
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
    if not pk:
        return False
    # Reject both canonical custom:: and legacy custom\x1f separator forms.
    # LAST_CATALOG was once polluted with custom\x1fMy Progression and treated
    # as a catalog snap (Use catalog → Say / Custom reclaim).
    if pk.startswith("custom::") or pk.startswith("custom\x1f"):
        return False
    return True


def _catalog_picker_from_session(session_state: dict[str, Any]) -> dict[str, dict[str, dict]] | None:
    for key in ("_reconcile_song_picker_catalog", "_catalog_backup_picker", "song_picker_catalog"):
        raw = session_state.get(key)
        if isinstance(raw, dict) and raw:
            return raw
    return None


def _catalog_library_from_session(session_state: dict[str, Any]) -> dict[str, dict[str, dict]] | None:
    for key in ("_reconcile_song_library", "_catalog_backup_library", "song_library"):
        raw = session_state.get(key)
        if isinstance(raw, dict) and raw:
            return raw
    return None


def ensure_song_picker_catalog(
    session_state: dict[str, Any],
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> dict[str, dict[str, dict]]:
    """Resolve a non-empty picker catalog for Use Catalog / ownership switches.

    ``prepare_canonical`` pops ``_reconcile_song_picker_catalog`` after each run.
    Backing ``Use catalog song backing`` must still restore Shape of You even when
    that transient key is missing — fall back to backup handles, then disk load.
    """
    if isinstance(song_picker_catalog, dict) and song_picker_catalog:
        stamp_chart_bundle_catalog_context(
            session_state, song_picker_catalog=song_picker_catalog
        )
        return song_picker_catalog
    cached = _catalog_picker_from_session(session_state)
    if isinstance(cached, dict) and cached:
        return cached
    try:
        from song_catalog.catalog import load_song_catalog

        _library, picker, _genres, _records = load_song_catalog()
        if isinstance(picker, dict) and picker:
            stamp_chart_bundle_catalog_context(
                session_state,
                song_picker_catalog=picker,
                song_library=_library if isinstance(_library, dict) else None,
            )
            return picker
    except Exception:
        pass
    return {}


def ensure_song_library(
    session_state: dict[str, Any],
    song_library: dict[str, dict[str, dict]] | None = None,
) -> dict[str, dict[str, dict]] | None:
    if isinstance(song_library, dict) and song_library:
        return song_library
    cached = _catalog_library_from_session(session_state)
    if isinstance(cached, dict) and cached:
        return cached
    try:
        from song_catalog.catalog import load_song_catalog

        library, picker, _genres, _records = load_song_catalog()
        if isinstance(picker, dict) and picker:
            stamp_chart_bundle_catalog_context(
                session_state,
                song_picker_catalog=picker,
                song_library=library if isinstance(library, dict) else None,
            )
        return library if isinstance(library, dict) else None
    except Exception:
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
        # Never rewrite custom:: / creative:: identities into Genre\x1fLabel form.
        if not pk.startswith("custom::") and not pk.startswith("creative::"):
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


def _section_map_from_record(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, chords in raw.items():
        if not isinstance(chords, list):
            continue
        clean = [str(c).strip() for c in chords if str(c).strip()]
        if clean:
            out[str(name)] = clean
    return out


def _selected_song_for_identity(
    existing: Any,
    *,
    pick_key: str,
    title: str,
    artist: str,
    original_key: str,
    song_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Replace prior-song identity AND chart sections with the newly selected catalog row."""
    sel = dict(song_data) if isinstance(song_data, dict) and song_data else {}
    prior = dict(existing) if isinstance(existing, dict) else {}
    if not sel:
        sel = dict(prior)
        sel.pop("sections", None)
    elif str(prior.get("pick_key") or "").strip() != str(pick_key or "").strip():
        if not _section_map_from_record(sel.get("sections")):
            sel.pop("sections", None)
    if pick_key:
        sel["pick_key"] = str(pick_key).strip()
    if title:
        sel["title"] = str(title)
    if artist:
        sel["artist"] = str(artist)
    if original_key:
        sel["key"] = str(original_key)
    sections = _section_map_from_record(sel.get("sections"))
    if sections:
        sel["sections"] = copy.deepcopy(sections)
    elif "sections" in sel:
        sel.pop("sections", None)
    return sel


def catalog_chart_sections_for_pick(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    selected: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Catalog original-key sections for a pick — selected row, home, library, or picker."""
    sections = _section_map_from_record((selected or {}).get("sections"))
    if sections:
        return sections
    home = _section_map_from_record(session_state.get("home_sections"))
    if home:
        return home
    for catalog in (
        _catalog_library_from_session(session_state),
        _catalog_picker_from_session(session_state),
    ):
        if not isinstance(catalog, dict) or not catalog:
            continue
        row = _catalog_row_for_pick(pick_key, catalog)
        sections = _section_map_from_record((row or {}).get("sections"))
        if sections:
            return sections
    return {}


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
    row_sections = _section_map_from_record(row.get("sections"))
    if row_sections and (authoritative or not _section_map_from_record(out.get("sections"))):
        out["sections"] = copy.deepcopy(row_sections)
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

    def _catalog_row_original() -> str:
        row = _catalog_row_for_pick(pick_key, catalog) if isinstance(catalog, dict) else None
        if not row:
            return ""
        return str(row.get("key") or "").strip()

    def _finish(selected: dict[str, Any], original_key: str) -> tuple[dict[str, Any], str]:
        # Catalog library key is the only authoritative Original Key. Snapshots /
        # selected blobs may carry a polluted "C" from legacy restore fallbacks.
        row_key = _catalog_row_original()
        if row_key:
            original_key = row_key
            selected = dict(selected)
            selected["key"] = row_key
        merged = _merge_catalog_transport_into_selected(
            selected,
            pick_key,
            catalog,
            authoritative=authoritative_transport,
        )
        if row_key:
            merged["key"] = row_key
        if not _section_map_from_record(merged.get("sections")):
            extra = catalog_chart_sections_for_pick(session_state, pick_key, selected=merged)
            if extra:
                merged["sections"] = copy.deepcopy(extra)
        return merged, (row_key or original_key)

    snap_keys = (
        (CATALOG_BEFORE_CREATIVE_KEY, CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY)
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
            row_sections = _section_map_from_record(row.get("sections"))
            if row_sections:
                selected["sections"] = copy.deepcopy(row_sections)
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
        live = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
        practice_pk = str(session_state.get(PRACTICE_SOURCE_PICK_KEY) or "").strip()
        auth_pick = ""
        try:
            from backing_source_navigation import _authoritative_catalog_pick_for_nav

            auth_pick = _authoritative_catalog_pick_for_nav(session_state)
        except ImportError:
            auth_pick = ""
        # Source-change initialize (E4/E5): live committed pick wins over
        # catalog_before_creative (Love Story snapshot after Mission on same song).
        if str(reason) == "switch_to_catalog_backing":
            for source, pk in (
                ("authoritative_nav_pick", auth_pick),
                ("active_catalog_pick_key", live),
                ("practice_source_pick", practice_pk),
            ):
                if _pick_key_is_catalog(pk):
                    return _record(source, pk)
        # Capo is player context: after refresh, a stale catalog_before_creative
        # (Country Roads) must not displace the live Love Story identity when Capo
        # Shape Mode is on. Prefer live / active_song_state first.
        capo_on = False
        try:
            from guitar_capo import CAPO_ENABLED_KEY

            capo_on = bool(session_state.get(CAPO_ENABLED_KEY))
            if not capo_on:
                meta_capo = session_state.get("active_song_state")
                if isinstance(meta_capo, dict):
                    capo_on = bool(meta_capo.get(CAPO_ENABLED_KEY))
        except ImportError:
            capo_on = False
        if capo_on:
            meta = session_state.get("active_song_state")
            meta_pick = (
                str(meta.get("pick_key") or "").strip() if isinstance(meta, dict) else ""
            )
            for source, pk in (
                ("active_catalog_pick_key", live),
                ("practice_source_pick", practice_pk),
                ("active_song_state", meta_pick),
                ("authoritative_nav_pick", auth_pick),
            ):
                if _pick_key_is_catalog(pk):
                    return _record(f"capo_live:{source}", pk)
        # Pre-Creative snapshot wins when Jam/Creative overwrote the live pick.
        # Live catalog pick wins over stale last_catalog (e.g. leftover Say).
        snap_order = (
            ("catalog_before_creative", CATALOG_BEFORE_CREATIVE_KEY),
            ("catalog_before_custom", CATALOG_BEFORE_CUSTOM_KEY),
        )
        for source, snap_key in snap_order:
            raw = session_state.get(snap_key)
            if not isinstance(raw, dict):
                continue
            pk = str(raw.get("pick_key") or "").strip()
            if _pick_key_is_catalog(pk):
                return _record(source, pk)
        if _pick_key_is_catalog(live):
            return _record("active_catalog_pick_key", live)
        if _pick_key_is_catalog(practice_pk):
            return _record("practice_source_pick", practice_pk)
        meta = session_state.get("active_song_state")
        if isinstance(meta, dict):
            pk = str(meta.get("pick_key") or "").strip()
            if _pick_key_is_catalog(pk):
                return _record("active_song_state", pk)
        raw_last = session_state.get(LAST_CATALOG_STATE_KEY)
        if isinstance(raw_last, dict):
            pk = str(raw_last.get("pick_key") or "").strip()
            if _pick_key_is_catalog(pk):
                return _record("last_catalog_state", pk)
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
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_concert_key_for_pick

        display_key = resolve_practice_concert_key_for_pick(
            session,
            pick_key,
            original_key=catalog_original,
        )
        sticky_pk = str(get_practice_concert_key(session, pick_key) or "").strip()
    except ImportError:
        sticky_pk = ""
        if reason not in _reset_reasons:
            display_key = (
                str(session.get("display_key") or session.get("concert_key") or catalog_original).strip()
                or catalog_original
            )
    # Same-pick catalog restore: if sticky store missed (legacy :: vs \x1f, or
    # sidebar on_change lag), reuse the pre-custom / last-catalog snapshot PK.
    if not sticky_pk and reason in {
        "creative_to_catalog",
        "switch_to_catalog_backing",
        "last_catalog_restore",
        "previous_catalog_restore",
    }:
        for snap_key in (CATALOG_BEFORE_CUSTOM_KEY, CATALOG_BEFORE_CREATIVE_KEY, LAST_CATALOG_STATE_KEY):
            raw = session.get(snap_key)
            if not isinstance(raw, dict):
                continue
            snap_pick = str(raw.get("pick_key") or "").strip()
            snap_dk = str(raw.get("display_key") or "").strip()
            if not snap_dk or not snap_pick:
                continue
            if not _pick_keys_match(snap_pick, pick_key, session_state=session):
                continue
            sticky_pk = snap_dk
            display_key = snap_dk
            try:
                from songs.practice_key_state import set_practice_concert_key

                set_practice_concert_key(session, snap_dk, pick_key=pick_key)
            except ImportError:
                pass
            break
    # Sticky Practice Key for this pick must survive ordinary Backing restore /
    # Use-catalog-song-backing same-pick returns. Only true catalog song changes
    # force Original Key.
    if reason == "catalog_source_switch":
        reset_to_original = True
    elif reason in {
        "creative_to_catalog",
        "switch_to_catalog_backing",
        "last_catalog_restore",
        "previous_catalog_restore",
    }:
        reset_to_original = not bool(sticky_pk)
        if sticky_pk:
            display_key = sticky_pk
    else:
        reset_to_original = False
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
        reset_to_original=reset_to_original,
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


def ensure_custom_progression_for_backing(
    session_state: dict[str, Any],
    *,
    promote_to_global_active: bool = True,
) -> str:
    """Ensure CPL active progression exists for Custom Backing.

    When ``promote_to_global_active`` is False (SBI → Custom preview/handoff), only
    ensure CPL blob / LAST_CUSTOM material is present — do not steal Global Active.
    """
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
    # Default My Progression shell has truthy empty original_sections — must use
    # substantive check or LAST_CUSTOM (Trial Song) never installs for SBI Custom.
    if not cpl_active_is_substantive(active):
        if session_state.get(CPL_SKIP_LAST_CUSTOM_RESTORE_KEY):
            # Intentional New song blank — do not reinstall LAST_CUSTOM for Backing.
            pass
        else:
            snap = session_state.get(LAST_CUSTOM_STATE_KEY)
            if isinstance(snap, dict) and isinstance(snap.get("active"), dict) and cpl_active_is_substantive(
                snap["active"]
            ):
                active = dict(snap["active"])
            elif not isinstance(active, dict):
                active = default_active_progression()
            # else keep non-substantive live shell only when LAST_CUSTOM is absent
    if not isinstance(active, dict):
        active = default_active_progression()
    active = ensure_original_structure(active)
    session_state[CPL_ACTIVE_KEY] = active
    home = str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C"
    if not promote_to_global_active:
        # Keep Global Catalog identity snapshotted so Songs cannot fall through to
        # an unrelated catalog default (Say) after SBI Custom preview (H5).
        try:
            from source_session_state import sync_catalog_session

            sync_catalog_session(session_state)
        except ImportError:
            pass
        try:
            snapshot_catalog_before_custom(session_state)
        except Exception:
            pass
        return home
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
            "key": home,
        }
    return home
