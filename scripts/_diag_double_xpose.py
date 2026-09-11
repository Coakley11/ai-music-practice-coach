"""Reproduce Bm→Dm same-rerun double transposition (Dm→Fm)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from music_workflow_song_practice import (
    ensure_missions_parent_practice_key_hydrated,
    ensure_song_practice_blob_for_active_song,
    reconcile_catalog_practice_key_owner,
    rehydrate_full_song_concert_sections,
    resolve_song_practice_key_token,
    song_practice_blob,
)
from music_workflow_pending_song_practice_key_edit import (
    infer_catalog_sections_spelled_in_key,
    overlay_destination_practice_key,
    overlay_sections_with_pending_practice_key,
)
from songs.key_state import mark_display_key_changed
from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
from source_session_state import resolve_sbi_preview
from workflow_musical_authority import sync_song_improv_sections_to_practice_key
from creative_key_sync import creative_progression_display
from music_workflow_state_store import save_workflow_blob

OUT = Path("scripts/evidence-creative-backing")
SHAPE_SECTIONS = {
    "Intro": ["Bm", "Em", "G", "A"],
    "Verse": ["Bm", "Em", "G", "A", "Bm", "Em", "G", "A"],
}
PICK = "Pop::Shape of You — Ed Sheeran"


def _first(sections, n=6):
    vals = list((sections or {}).values())
    if not vals:
        return []
    return list(vals[0])[:n]


def _base_session():
    song = {
        "title": "Shape of You",
        "artist": "Ed Sheeran",
        "key": "Bm",
        "pick_key": PICK,
        "sections": copy.deepcopy(SHAPE_SECTIONS),
        "bpm": 96,
    }
    session = {
        "active_catalog_pick_key": PICK,
        "display_key": "Bm",
        "concert_key": "Bm",
        "improv_intelligence_tab": "Song-Based Improvisation",
        "creative_improv_intelligence_tab": "Song-Based Improvisation",
        "selected_song": song,
        "song": "Shape of You",
        "home_sections": copy.deepcopy(SHAPE_SECTIONS),
        "improv_song_concert_sections": copy.deepcopy(SHAPE_SECTIONS),
        "instrument": "Guitar",
        "guitar_capo_enabled": True,
        "guitar_capo_shape_key": "E",
        "catalog_session": {
            "pick_key": PICK,
            "display_key": "Bm",
            "original_key": "Bm",
            "selected_song": song,
            "sections": copy.deepcopy(SHAPE_SECTIONS),
        },
    }
    ensure_song_practice_blob_for_active_song(session, practice_key="Bm", original_key="Bm")
    blob = song_practice_blob(session)
    assert blob is not None
    blob.section_map = copy.deepcopy(SHAPE_SECTIONS)
    save_workflow_blob(session, blob, source="diag")
    return session


def main() -> None:
    session = _base_session()
    out: dict = {"steps": []}

    with patch(
        "songs.music_source.catalog_chart_sections_for_pick",
        return_value=copy.deepcopy(SHAPE_SECTIONS),
    ):
        before = resolve_sbi_preview(session)
        out["before"] = {"key": before["display_key"], "first": _first(before["sections"])}

        # USER selects Dm via sidebar callback (includes 9ebf7d0 blob heal)
        session["display_key"] = "Dm"
        mark_display_key_changed(SimpleNamespace(session_state=session))
        out["after_callback"] = {
            "display_key": session.get("display_key"),
            "blob": resolve_song_practice_key_token(session),
            "store": get_practice_concert_key(session, PICK),
            "blob_section_first": _first(song_practice_blob(session).section_map),
            "improv_first": _first(session.get("improv_song_concert_sections")),
        }

        # Same-rerun / next-rerun hydrate (SBI fallthrough)
        session.pop("_missions_parent_key_hydrate_guard", None)
        rehydrate_full_song_concert_sections(session, source="diag")
        out["steps"].append(
            {
                "name": "rehydrate_alone",
                "improv_first": _first(session.get("improv_song_concert_sections")),
            }
        )

        token = reconcile_catalog_practice_key_owner(session, source="diag")
        out["steps"].append(
            {
                "name": "reconcile",
                "token": token,
                "improv_first": _first(session.get("improv_song_concert_sections")),
            }
        )

        ensure_missions_parent_practice_key_hydrated(session)
        synced = sync_song_improv_sections_to_practice_key(session)
        spelled = resolve_song_practice_key_token(session)
        inferred = infer_catalog_sections_spelled_in_key(session, synced, fallback=spelled)
        dest = overlay_destination_practice_key(session)
        overlaid = overlay_sections_with_pending_practice_key(
            session, synced, spelled_in_key=spelled
        )
        # Critical wrong-spelled path
        wrong = overlay_sections_with_pending_practice_key(
            session, synced, spelled_in_key="Bm"
        )

        prev = resolve_sbi_preview(session)
        disp = creative_progression_display(
            session, prev["sections"], concert_key=prev["display_key"]
        )
        out["after_hydrate"] = {
            "display_key": session.get("display_key"),
            "blob": spelled,
            "synced_first": _first(synced),
            "inferred": inferred,
            "dest": dest,
            "overlaid_first": _first(overlaid),
            "wrong_spelled_Bm_first": _first(wrong),
            "sbi_key": prev["display_key"],
            "sbi_first": _first(prev["sections"]),
            "progression_display": disp,
        }

        # Double-apply: sync then overlay when pending still active with blob already Dm
        session_b = _base_session()
        session_b["display_key"] = "Dm"
        session_b["concert_key"] = "Dm"
        set_practice_concert_key(session_b, "Dm", pick_key=PICK)
        ensure_song_practice_blob_for_active_song(
            session_b, practice_key="Dm", original_key="Bm"
        )
        # Leave section_map at Bm (heal keys only) — then sync once into improv
        synced_b = sync_song_improv_sections_to_practice_key(session_b)
        # Force improv cache to Dm, then call sync AGAIN (idempotence check)
        session_b["improv_song_concert_sections"] = copy.deepcopy(synced_b)
        blob_b = song_practice_blob(session_b)
        blob_b.section_map = copy.deepcopy(synced_b)  # already Dm in blob
        save_workflow_blob(session_b, blob_b, source="diag")
        synced_b2 = sync_song_improv_sections_to_practice_key(session_b)
        overlaid_b = overlay_sections_with_pending_practice_key(
            session_b, synced_b2, spelled_in_key=resolve_song_practice_key_token(session_b)
        )
        # Also: what if catalog_session.sections still Bm and resolve uses that path?
        session_b["catalog_session"]["sections"] = copy.deepcopy(SHAPE_SECTIONS)
        prev_b = resolve_sbi_preview(session_b)
        out["idempotence"] = {
            "after_first_sync": _first(synced_b),
            "after_second_sync": _first(synced_b2),
            "after_overlay": _first(overlaid_b),
            "sbi_first": _first(prev_b["sections"]),
            "sbi_key": prev_b["display_key"],
        }

        # Path: cached Dm sections + overlay with inferred Bm (the smoking gun)
        dm_secs = synced_b
        inferred_dm = infer_catalog_sections_spelled_in_key(
            session_b, dm_secs, fallback="Bm"
        )
        out["infer_on_dm_with_bm_fallback"] = {
            "inferred": inferred_dm,
            "overlay_from_bm_fallback": _first(
                overlay_sections_with_pending_practice_key(
                    session_b, dm_secs, spelled_in_key="Bm"
                )
            ),
        }

        # Pollute home_sections with already-practice pitch; clear selected.sections
        session_c = _base_session()
        session_c["display_key"] = "Dm"
        session_c["concert_key"] = "Dm"
        set_practice_concert_key(session_c, "Dm", pick_key=PICK)
        ensure_song_practice_blob_for_active_song(
            session_c, practice_key="Dm", original_key="Bm"
        )
        first_sync = sync_song_improv_sections_to_practice_key(session_c)
        session_c["home_sections"] = copy.deepcopy(first_sync)
        session_c["selected_song"] = {
            **dict(session_c["selected_song"]),
            "sections": copy.deepcopy(first_sync),  # practice pitch in selected!
            "key": "Bm",
        }
        second = sync_song_improv_sections_to_practice_key(session_c)
        prev_c = resolve_sbi_preview(session_c)
        out["polluted_selected_sections"] = {
            "first": _first(first_sync),
            "second": _first(second),
            "sbi": _first(prev_c["sections"]),
        }

        # song_improv retranspose path (backing)
        from types import SimpleNamespace as SN
        from backing_context import sections_dict_from_backing_context

        session_d = _base_session()
        session_d["display_key"] = "Dm"
        session_d["concert_key"] = "Dm"
        set_practice_concert_key(session_d, "Dm", pick_key=PICK)
        ensure_song_practice_blob_for_active_song(
            session_d, practice_key="Dm", original_key="Bm"
        )
        sync_song_improv_sections_to_practice_key(session_d)
        ctx = SN(
            source="song_improv",
            concert_key="Dm",
            display_key="Dm",
            key="Bm",  # original catalog key on sealed ctx
            song_title="Shape of You",
            progression_label="Shape of You",
            progression=[],
            section="",
            sections=[],
            entry_mode="",
        )
        secs_out = sections_dict_from_backing_context(session_d, ctx)
        out["song_improv_retranspose"] = {
            "first": _first(secs_out),
            "note": "ctx.key=Bm + sync already Dm should become Fm if bug",
        }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diag-double-xpose.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))

    for label in ("polluted_selected_sections", "song_improv_retranspose"):
        block = out.get(label) or {}
        cand = block.get("second") or block.get("sbi") or block.get("first")
        if cand and str(cand[0]).startswith("F"):
            print(f"REPRODUCED via {label}: {cand}")
            raise SystemExit(2)
    print("Primary hydrate OK; see polluted/retranspose fields for Fm")


if __name__ == "__main__":
    main()
