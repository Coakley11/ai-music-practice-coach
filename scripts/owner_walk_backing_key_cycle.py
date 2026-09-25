"""Owner-checked Key Cycle simulation for all nine Backing owners (no Practice Key mutation)."""

from __future__ import annotations

from backing_key_cycle import (
    CYCLE_OWNERS,
    OWNER_CATALOG,
    OWNER_COMPOSITION,
    OWNER_CUSTOM,
    OWNER_JAM_GENERATOR,
    OWNER_MISSION,
    OWNER_SBI_ACTIVE,
    OWNER_SBI_COMPOSITION,
    OWNER_SBI_CUSTOM,
    OWNER_STYLE_JAM,
    note_backing_pass_finished,
    resolve_cycle_owner,
    start_key_cycle,
    stop_key_cycle,
    temporary_playback_key,
)

OWNER_SEEDS: dict[str, dict] = {
    OWNER_CATALOG: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "regular_song",
        "active_catalog_pick_key": "Pop|Shape of You",
        "display_key": "Bm",
        "concert_key": "Bm",
        "practice_key_by_source": {"Pop|Shape of You": "Bm"},
    },
    OWNER_CUSTOM: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "custom_progression",
        "display_key": "G",
        "concert_key": "G",
    },
    OWNER_COMPOSITION: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "composition_song",
        "display_key": "D",
        "concert_key": "D",
    },
    OWNER_SBI_ACTIVE: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "song_improv",
        "sbi_preview_source": "Active song",
        "display_key": "Bm",
        "concert_key": "Bm",
        "practice_key_by_source": {"Pop|Shape of You": "Bm"},
        "active_catalog_pick_key": "Pop|Shape of You",
    },
    OWNER_SBI_CUSTOM: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "song_improv",
        "sbi_preview_source": "Custom progression",
        "display_key": "A",
        "concert_key": "A",
    },
    OWNER_SBI_COMPOSITION: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "song_improv",
        "sbi_preview_source": "Composition",
        "display_key": "E",
        "concert_key": "E",
    },
    OWNER_STYLE_JAM: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "entry_jam",
        "improv_entry_mode": "Style Jam Mode",
        "improv_style_key": "F",
        "display_key": "F",
        "concert_key": "F",
    },
    OWNER_JAM_GENERATOR: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "entry_jam",
        "improv_entry_mode": "Jam Session Generator",
        "improv_jam_key": "C",
        "display_key": "C",
        "concert_key": "C",
    },
    OWNER_MISSION: {
        "studio_page": "backing",
        "_backing_explicit_handoff_source": "mission",
        "display_key": "Em",
        "concert_key": "Em",
        "improv_active_mission": "chord_tones",
    },
}


def walk_owner(owner: str) -> dict:
    session = dict(OWNER_SEEDS[owner])
    session["backing_key_cycle_step"] = "semitone"
    session["backing_key_cycle_direction"] = "up"
    resolved = resolve_cycle_owner(session)
    start_key = str(session.get("display_key") or "C")
    pk_before = dict(session.get("practice_key_by_source") or {})
    style_before = session.get("improv_style_key")
    jam_before = session.get("improv_jam_key")
    display_before = session.get("display_key")
    concert_before = session.get("concert_key")
    start_key_cycle(session, start_key=start_key)
    t0 = temporary_playback_key(session)
    note_backing_pass_finished(session, pass_signature=f"{owner}-1")
    t1 = temporary_playback_key(session)
    stop_key_cycle(session)
    t_stop = temporary_playback_key(session)
    pk_after = dict(session.get("practice_key_by_source") or {})
    # Saved Practice Key surfaces must not change (map may grow empty→empty).
    saved_ok = (
        all(pk_after.get(k) == v for k, v in pk_before.items())
        and session.get("improv_style_key") == style_before
        and session.get("improv_jam_key") == jam_before
        and session.get("display_key") == display_before
        and session.get("concert_key") == concert_before
    )
    return {
        "owner": owner,
        "resolved": resolved,
        "match": resolved == owner,
        "start": t0,
        "after_pass": t1,
        "after_stop_temp": t_stop or "(off→saved)",
        "pk_unchanged": saved_ok,
        "style_unchanged": session.get("improv_style_key") == style_before,
        "jam_unchanged": session.get("improv_jam_key") == jam_before,
        "advanced": bool(t0 and t1 and t0 != t1),
    }


def main() -> None:
    print("owner\tresolved\tmatch\tstart\tafter_pass\tadvanced\tpk_ok")
    ok = True
    for owner in CYCLE_OWNERS:
        row = walk_owner(owner)
        print(
            f"{row['owner']}\t{row['resolved']}\t{row['match']}\t{row['start']}\t"
            f"{row['after_pass']}\t{row['advanced']}\t{row['pk_unchanged']}"
        )
        if not (row["match"] and row["advanced"] and row["pk_unchanged"]):
            ok = False
    # Cross-leak: catalog cycle must not appear as custom practice
    catalog = dict(OWNER_SEEDS[OWNER_CATALOG])
    catalog["backing_key_cycle_step"] = "semitone"
    catalog["backing_key_cycle_direction"] = "up"
    start_key_cycle(catalog, start_key="Bm")
    note_backing_pass_finished(catalog, pass_signature="leak1")
    custom = dict(OWNER_SEEDS[OWNER_CUSTOM])
    custom["_backing_key_cycle_sessions"] = catalog.get("_backing_key_cycle_sessions")
    custom["backing_key_cycle_step"] = "semitone"
    custom["backing_key_cycle_direction"] = "up"
    assert resolve_cycle_owner(custom) == OWNER_CUSTOM
    start_key_cycle(custom, start_key="G")
    assert temporary_playback_key(custom) == "G"
    print("cross_leak_custom_vs_catalog\tPASS")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
