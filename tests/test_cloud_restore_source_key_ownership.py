"""Restore/reconciliation ownership: a previous owner's value must never win.

Two concrete violations of that rule were found on ``4a63e32a``:

1. ``resolve_sbi_custom_practice_key`` CASE A returned the global
   ``display_key`` / ``concert_key``. Those globals hold whatever owner
   rendered last, so right after a Catalog -> Custom switch (or a cloud
   restore) a Catalog song's Practice Key outranked the active Custom song's
   own key. Key Cycling inherits the same resolver via
   ``current_backing_owner_practice_key``, so it would start from the foreign
   key too.
2. ``bind_backing_rendered_widgets_from_canonical`` kept a restored per-song
   BPM slider value over the canonical blob it was restored alongside. That is
   covered by ``test_bind_restores_canonical_on_cloud_restore_mismatch``; the
   non-restore direction is pinned here so the fix is not widened.

A pristine session cannot catch either one: the leaked values are empty, which
is why fresh-data runs passed while persisted Cloud state failed.
"""

from __future__ import annotations

from backing_track_state import (
    BACKING_RESTORED_KEY,
    BACKING_WIDGETS_SEEDED_KEY,
    bind_backing_rendered_widgets_from_canonical,
)
from source_session_state import (
    CUSTOM_SESSION_KEY,
    resolve_sbi_custom_practice_key,
)

FOREIGN_KEY = "F"  # the Catalog song (Girl from Ipanema) that rendered last
CUSTOM_KEY = "D"  # the Custom song that is now active
CUSTOM_PICK = "custom::trial-song-uuid"
CUSTOM_WIDGET = "display_key_custom_backing"
SBI_CUSTOM_WIDGET = "display_key_sbi_custom"


def _custom_is_global_active() -> dict:
    """Minimal CASE A session: a ``custom::`` pick owns Global Active.

    ``active_catalog_pick_key`` starting with ``custom::`` is what
    ``sbi_custom_identity_is_global_active`` keys off, so this reaches CASE A
    without asserting anything about unrelated session plumbing.
    """
    return {
        "active_catalog_pick_key": CUSTOM_PICK,
        # Leaked from whichever owner rendered last.
        "display_key": FOREIGN_KEY,
        "concert_key": FOREIGN_KEY,
        CUSTOM_SESSION_KEY: {
            "pick_key": CUSTOM_PICK,
            "title": "Trial Song",
            "original_key": CUSTOM_KEY,
            "display_key": CUSTOM_KEY,
            "sections": {"Verse": []},
        },
    }


def test_case_a_never_returns_the_foreign_global_display_key() -> None:
    session = _custom_is_global_active()

    assert resolve_sbi_custom_practice_key(session) != FOREIGN_KEY


def test_case_a_prefers_the_custom_owners_own_widget() -> None:
    """An uncommitted Practice Key edit lives in the Custom owner's widget."""
    session = _custom_is_global_active()
    session[SBI_CUSTOM_WIDGET] = CUSTOM_KEY

    assert resolve_sbi_custom_practice_key(session) == CUSTOM_KEY

    other = _custom_is_global_active()
    other[CUSTOM_WIDGET] = CUSTOM_KEY
    assert resolve_sbi_custom_practice_key(other) == CUSTOM_KEY


def test_case_a_foreign_global_loses_even_when_it_is_the_only_global() -> None:
    """Removing concert_key must not re-open the display_key path."""
    session = _custom_is_global_active()
    session.pop("concert_key", None)

    assert resolve_sbi_custom_practice_key(session) != FOREIGN_KEY


def _bind_session(slider_key: str, *, restored: bool) -> dict:
    session = {
        "backing_track_state": {
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
            "backing_track_bpm": 130,
            "backing_groove_style": "Ballad",
            "last_write_reason": "cloud_restore" if restored else "backing_edit",
        },
        "backing_track_bpm": 130,
        "backing_track_scope": "Full song",
        "backing_track_loops": 2,
        "backing_groove_style": "Ballad",
        slider_key: 100,
        BACKING_WIDGETS_SEEDED_KEY: True,
    }
    if restored:
        session[BACKING_RESTORED_KEY] = True
    return session


def test_cloud_restore_bind_pushes_canonical_into_the_restored_slider() -> None:
    sync_id = "pk::Pop::Song — Artist"
    slider_key = "backing_track_bpm::pk__Pop__Song_—_Artist"
    session = _bind_session(slider_key, restored=True)

    bind_backing_rendered_widgets_from_canonical(
        session, sync_id=sync_id, default_bpm=100
    )

    assert session[slider_key] == 130
    assert session["backing_track_bpm"] == 130
    assert session["_backing_render_bind_reason"] == "cloud_restore"


def test_non_restore_bind_still_keeps_a_live_rendered_slider() -> None:
    """The restore fix must not stomp a same-session slider the user moved."""
    sync_id = "pk::Pop::Song — Artist"
    slider_key = "backing_track_bpm::pk__Pop__Song_—_Artist"
    session = _bind_session(slider_key, restored=False)

    bind_backing_rendered_widgets_from_canonical(
        session, sync_id=sync_id, default_bpm=100
    )

    assert session["backing_track_bpm"] == 100


def test_key_cycle_ui_error_is_surfaced_in_developer_paths_only() -> None:
    """The caught Key Cycling render error must be visible to a developer.

    c6410064 replaced a visible caption with a session key that nothing read,
    so a Cloud "Key Cycling does nothing" report had no diagnostic at all. It
    now renders in the developer expander and goes to the server log — but the
    old user-facing copy must not come back onto the Backing page.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    ui = (root / "backing_context_ui.py").read_text(encoding="utf-8")

    # Server log carries the traceback.
    assert "[key_cycle_ui] render_backing_key_cycle_controls failed" in app
    # Developer diagnostics render the stored value.
    assert "_backing_key_cycle_ui_error" in ui
    assert "Key Cycling controls error" in ui
    # The user-facing fallback copy stays gone.
    assert "Key cycling unavailable:" not in app
