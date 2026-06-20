#!/usr/bin/env python3
"""Simulate CPL page order: Verse -> C -> 4 bars and print diagnostics snapshot."""

from __future__ import annotations

import json
import copy
from types import SimpleNamespace
from unittest.mock import patch

from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    build_cpl_developer_diagnostics,
    cpl_active_from_session,
    cpl_apply_chord_with_bars_to_session,
    cpl_draft_preview_key,
    cpl_get_pending_chord,
    cpl_save_draft,
    cpl_set_pending_chord,
    default_active_progression,
    ensure_all_cpl_sections,
    ensure_cpl_widget_keys_initialized,
    sync_cpl_draft_widgets_to_active,
)


def _pending_key(section: str) -> str:
    return f"cpl_pending_chord_{section}"


def _last_bars_key(section: str) -> str:
    return f"cpl_last_bars_{section}"


def _home_sections(session: dict) -> dict:
    active = cpl_active_from_session(session)
    return ensure_all_cpl_sections(active.get("original_sections"))


def _metadata_save(session: dict, *, persist: bool = False) -> None:
    """Mirror cpl_page_ui metadata block + _save(_home_sections())."""
    active = sync_cpl_draft_widgets_to_active(session, cpl_active_from_session(session))
    session[CPL_ACTIVE_KEY] = active
    home = _home_sections(session)
    cpl_save_draft(session, active, home, persist=persist, st=None)


def _apply_bars(session: dict, *, section: str, bars: int, persist: bool = False) -> bool:
    """Mirror cpl_page_ui._apply_bars pending path."""
    pending_key = _pending_key(section)
    last_bars = _last_bars_key(section)
    session[last_bars] = int(bars)
    pending = session.get(pending_key) or cpl_get_pending_chord(session, section)
    if not pending:
        return False
    active = cpl_apply_chord_with_bars_to_session(
        session,
        section_name=section,
        chord=str(pending),
        bars=int(bars),
        persist=persist,
    )
    session["_cpl_last_bar_apply"] = {
        "section": section,
        "chord": str(pending),
        "bars": int(bars),
        "pending_key": pending_key,
        "verse_entries": copy.deepcopy(_home_sections(session).get("Verse") or []),
        "chord_count": sum(
            len(_home_sections(session).get(name) or [])
            for name in ("Intro", "Verse", "Pre-Chorus", "Chorus", "Bridge", "Solo", "Outro")
        ),
    }
    return True


def _diag(session: dict, *, edit_section: str = "Verse") -> dict:
    return build_cpl_developer_diagnostics(
        session,
        cpl_active_from_session(session),
        edit_section=edit_section,
    )


def main() -> None:
    session = {
        CPL_ACTIVE_KEY: default_active_progression(),
        "cpl_edit_section": "Verse",
        "cpl_title_input": "Trial Song",
        "cpl_bpm_builder": 100,
        "cpl_time_signature": "4/4",
        "cpl_original_key": "C",
        "cpl_style_early": "Pop",
        "cpl_artist_input": "Daniel",
    }
    ensure_cpl_widget_keys_initialized(session, session[CPL_ACTIVE_KEY])

    print("=== RUN 0: initial page load (metadata save only) ===")
    _metadata_save(session, persist=False)
    d0 = _diag(session)
    print(json.dumps({
        "chord_count": d0["draft"]["chord_count"],
        "last_bar_apply": d0["chord_pipeline"]["last_bar_apply"],
        "pending_by_section": d0["pending"]["pending_by_section"],
    }, indent=2))

    print("\n=== RUN 1: user clicked chord C (rerun) ===")
    _metadata_save(session, persist=False)
    session[_pending_key("Verse")] = "C"
    cpl_set_pending_chord(session, section="Verse", chord="C")
    d1 = _diag(session)
    print(json.dumps({
        "chord_count": d1["draft"]["chord_count"],
        "pending_by_section": d1["pending"]["pending_by_section"],
        "native_rows": d1["display_path"]["section_view"]["native_rows"],
        "show_panel": d1["display_path"]["section_view"]["show_panel"],
    }, indent=2))

    print("\n=== RUN 2: user clicked 4 bars ===")
    _metadata_save(session, persist=False)
    committed = _apply_bars(session, section="Verse", bars=4, persist=False)
    d2 = _diag(session)
    print(f"apply_bars committed: {committed}")
    print(json.dumps({
        "chord_pipeline.last_bar_apply": d2["chord_pipeline"]["last_bar_apply"],
        "pending_by_section": d2["pending"]["pending_by_section"],
        "session_verse_entries": d2["chord_pipeline"]["session_verse_entries"],
        "draft.chord_count": d2["draft"]["chord_count"],
        "draft.original_sections.Verse": d2["draft"]["original_sections"].get("Verse"),
        "display_path.section_view.native_rows": d2["display_path"]["section_view"]["native_rows"],
        "display_path.whole_song_view.has_any": d2["display_path"]["whole_song_view"]["has_any"],
    }, indent=2, default=str))

    print("\n=== RUN 3: next rerun after bars (metadata save first, like live page) ===")
    _metadata_save(session, persist=False)
    d3 = _diag(session)
    print(json.dumps({
        "chord_pipeline.last_bar_apply": d3["chord_pipeline"]["last_bar_apply"],
        "pending_by_section": d3["pending"]["pending_by_section"],
        "session_verse_entries": d3["chord_pipeline"]["session_verse_entries"],
        "draft.chord_count": d3["draft"]["chord_count"],
        "draft.original_sections.Verse": d3["draft"]["original_sections"].get("Verse"),
        "display_path.section_view.native_rows": d3["display_path"]["section_view"]["native_rows"],
        "display_path.whole_song_view.has_any": d3["display_path"]["whole_song_view"]["has_any"],
    }, indent=2, default=str))

    print("\n=== CASE classification (RUN 3 = what user sees after flow) ===")
    cc = d3["draft"]["chord_count"]
    nr = d3["display_path"]["section_view"]["native_rows"]
    if cc == 0:
        print("CASE A: chord not committed (draft.chord_count = 0)")
    elif cc > 0 and not nr:
        print("CASE B: committed but display path empty")
    elif nr:
        print("CASE C would NOT apply — native_rows populated; if UI empty, render skipped/hidden")
    else:
        print("Unknown")


if __name__ == "__main__":
    main()
