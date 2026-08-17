"""Same-rerun Practice Key owner simulation (callback write → pre-widget hydrate).

Proves Bm→Dm survives the exact first-divergence path that broke 7fee436.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

OUT = Path(__file__).resolve().parent


def main() -> None:
    from music_workflow_song_practice import (
        ensure_missions_parent_practice_key_hydrated,
        ensure_song_practice_blob_for_active_song,
        resolve_song_practice_key_token,
    )
    from songs.key_state import mark_display_key_changed
    from songs.practice_key_state import get_practice_concert_key
    from source_session_state import resolve_sbi_preview
    from workflow_key_identity import resolve_practice_key_identity_for_ui

    pick = "Pop::Shape of You — Ed Sheeran"
    session: dict = {
        "active_catalog_pick_key": pick,
        "display_key": "Bm",
        "concert_key": "Bm",
        "improv_intelligence_tab": "Song-Based Improvisation",
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": pick,
        },
        "catalog_session": {
            "pick_key": pick,
            "display_key": "Bm",
            "original_key": "Bm",
            "selected_song": {"title": "Shape of You", "key": "Bm"},
            "sections": {"Verse": ["Bm", "Em", "G", "A"]},
        },
        "home_sections": {"Verse": ["Bm", "Em", "G", "A"]},
        "improv_song_concert_sections": {"Verse": ["Bm", "Em", "G", "A"]},
    }
    ensure_song_practice_blob_for_active_song(session, practice_key="Bm", original_key="Bm")

    before = {
        "display_key": session["display_key"],
        "blob": resolve_song_practice_key_token(session),
        "store": get_practice_concert_key(session, pick),
        "sbi": resolve_sbi_preview(session).get("display_key"),
    }

    # USER SELECTS Dm (sidebar widget callback)
    session["display_key"] = "Dm"
    st = SimpleNamespace(session_state=session)
    mark_display_key_changed(st)

    after_callback = {
        "display_key": session.get("display_key"),
        "blob": resolve_song_practice_key_token(session),
        "store": get_practice_concert_key(session, pick),
    }

    # NEXT RERUN pre-widget hydrate (the 7fee436 divergence point)
    session.pop("_missions_parent_key_hydrate_guard", None)
    ensure_missions_parent_practice_key_hydrated(session)
    ident = resolve_practice_key_identity_for_ui(session)
    after_hydrate = {
        "display_key": session.get("display_key"),
        "blob": resolve_song_practice_key_token(session),
        "store": get_practice_concert_key(session, pick),
        "ui_identity": getattr(ident, "practice_key_token", None) if ident else None,
        "sbi": resolve_sbi_preview(session).get("display_key"),
        "sbi_first": (list((resolve_sbi_preview(session).get("sections") or {}).values()) or [[]])[0][:3],
    }

    ok = (
        after_callback["display_key"] == "Dm"
        and after_hydrate["display_key"] == "Dm"
        and after_hydrate["blob"] == "Dm"
        and after_hydrate["store"] == "Dm"
        and after_hydrate["sbi"] == "Dm"
    )
    payload = {
        "ok": ok,
        "before": before,
        "after_callback": after_callback,
        "after_hydrate": after_hydrate,
        "first_divergence_was": "ensure_missions_parent_practice_key_hydrated → sync_session_practice_key_from_song_blob (fixed by reconcile_catalog_practice_key_owner)",
    }
    (OUT / "pk-owner-sim.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT / "pk-owner-sim.txt").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
