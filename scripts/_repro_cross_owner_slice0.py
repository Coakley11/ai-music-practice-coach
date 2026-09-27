"""Reproduce mixed-owner authority collisions at e5444de (no product patches).

Uses the same install hooks the Creative/SBI path uses before widgets.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from custom_progression_lab import CPL_ACTIVE_KEY
from song_catalog.catalog import format_pick_key
from songs.music_source import LAST_CUSTOM_STATE_KEY, resolve_active_song_keys
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)
from source_session_state import (
    SBI_PREVIEW_SOURCE_KEY,
    get_sbi_preview_source,
    install_sbi_custom_identity_before_widgets,
    note_explicit_sbi_source_selection,
    prepare_sbi_custom_sidebar_display_key,
    resolve_sidebar_original_key_for_caption,
    restore_sbi_active_catalog_identity_before_widgets,
    set_sbi_preview_source,
)

OUT = Path("scripts/evidence-cross-owner-slice0")
OUT.mkdir(parents=True, exist_ok=True)

PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
COLLISIONS: list[dict] = []


def _st(ss: dict) -> MagicMock:
    st = MagicMock()
    st.session_state = ss
    return st


def snap(ss: dict, label: str) -> dict:
    try:
        from practice_focus_creative import format_creative_practice_focus_caption

        focus = format_creative_practice_focus_caption(ss)
    except Exception as exc:
        focus = f"<focus err {exc}>"
    try:
        orig_cap = resolve_sidebar_original_key_for_caption(
            ss,
            current_original=str(ss.get("original_key") or ""),
        )
    except Exception as exc:
        orig_cap = f"<orig err {exc}>"
    try:
        keys = resolve_active_song_keys(ss)
    except Exception as exc:
        keys = {"error": str(exc)}
    try:
        pk = get_practice_concert_key(ss)
    except Exception as exc:
        pk = f"<pk err {exc}>"
    sel = ss.get("selected_song") if isinstance(ss.get("selected_song"), dict) else {}
    cpl = ss.get(CPL_ACTIVE_KEY) if isinstance(ss.get(CPL_ACTIVE_KEY), dict) else {}
    last = ss.get(LAST_CUSTOM_STATE_KEY) if isinstance(ss.get(LAST_CUSTOM_STATE_KEY), dict) else {}
    last_active = last.get("active") if isinstance(last.get("active"), dict) else {}
    return {
        "label": label,
        "studio_page": ss.get("studio_page"),
        "active_music_source": ss.get("active_music_source"),
        "explicit_music_source_choice": ss.get("explicit_music_source_choice"),
        "active_catalog_pick_key": ss.get("active_catalog_pick_key"),
        "improv_song_source": ss.get("improv_song_source"),
        "sbi_preview": get_sbi_preview_source(ss) or ss.get(SBI_PREVIEW_SOURCE_KEY),
        "workflow_owner": ss.get("_active_workflow_owner")
        or ss.get("temporary_workflow_owner")
        or ss.get("_temporary_workflow_owner"),
        "song": ss.get("song"),
        "selected_title": sel.get("title"),
        "cpl_name": cpl.get("name"),
        "cpl_orig": cpl.get("original_key_center"),
        "last_custom_name": last_active.get("name"),
        "sidebar_original_caption": orig_cap,
        "practice_key": pk,
        "display_key": ss.get("display_key"),
        "display_key_sbi_custom": ss.get("display_key_sbi_custom"),
        "concert_key": ss.get("concert_key"),
        "improv_jam_style": ss.get("improv_jam_style"),
        "practice_focus": focus,
        "resolve_active_song_keys": keys,
        "practice_key_by_source": dict(ss.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}),
        "sbi_custom_visit_pk": ss.get("_sbi_custom_visit_pk"),
        "creative_backing_song_source": ss.get("creative_backing_song_source"),
    }


def note_collision(kind: str, detail: str, before: dict, after: dict) -> None:
    COLLISIONS.append({"kind": kind, "detail": detail, "before": before, "after": after})
    safe = str(detail).encode("ascii", "replace").decode("ascii")
    print(f"COLLISION [{kind}] {safe}")


def _trial() -> dict:
    return {
        "id": "trial-d",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
        "bpm": 100,
        "time_signature": "4/4",
        "progression_style": "Pop",
    }


def perfect_plus_stale_trial(**extra) -> dict:
    trial = _trial()
    ss = {
        "studio_page": "creative",
        "instrument": "Guitar",
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
        },
        "active_music_source": "catalog",
        "explicit_music_source_choice": "catalog",
        "active_catalog_pick_key": PERFECT_PICK,
        "original_key": "G",
        "display_key": "C",
        "concert_key": "C",
        "catalog_session": {
            "pick_key": PERFECT_PICK,
            "original_key": "G",
            "selected_song": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
        },
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "C", "custom::trial-d": "F"},
        CPL_ACTIVE_KEY: trial,
        LAST_CUSTOM_STATE_KEY: {
            "pick_key": "custom::trial-d",
            "custom_home_key": "D",
            "active": trial,
        },
        "improv_jam_style": "Jewish ballad",
        "improv_song_source": "Active song",
        SBI_PREVIEW_SOURCE_KEY: "Active song",
        **extra,
    }
    set_practice_concert_key(ss, "C")
    return ss


def trial_active_saved_f(**extra) -> dict:
    trial = _trial()
    ss = {
        "studio_page": "creative",
        "instrument": "Clarinet (Bb)",
        "song": "Trial Song",
        "selected_song": {"title": "Trial Song", "key": "D", "pick_key": "custom::trial-d"},
        "active_music_source": "custom_progression",
        "explicit_music_source_choice": "custom_progression",
        "active_catalog_pick_key": "custom::trial-d",
        "original_key": "D",
        "display_key": "F",
        "concert_key": "F",
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "C", "custom::trial-d": "F"},
        "_catalog_before_custom_state": {
            "pick_key": PERFECT_PICK,
            "original_key": "G",
            "selected_song": {"title": "Perfect", "key": "G", "pick_key": PERFECT_PICK},
        },
        "_last_catalog_song_state": {
            "pick_key": PERFECT_PICK,
            "original_key": "G",
            "selected_song": {"title": "Perfect", "key": "G", "pick_key": PERFECT_PICK},
        },
        "catalog_session": {
            "pick_key": PERFECT_PICK,
            "original_key": "G",
            "selected_song": {"title": "Perfect", "key": "G", "pick_key": PERFECT_PICK},
        },
        CPL_ACTIVE_KEY: trial,
        LAST_CUSTOM_STATE_KEY: {
            "pick_key": "custom::trial-d",
            "custom_home_key": "D",
            "active": trial,
        },
        "improv_jam_style": "Jewish ballad",
        "improv_song_source": "Custom progression",
        SBI_PREVIEW_SOURCE_KEY: "Custom progression",
        **extra,
    }
    set_practice_concert_key(ss, "F")
    return ss


def open_sbi_custom(ss: dict) -> None:
    ss["studio_page"] = "creative"
    note_explicit_sbi_source_selection(ss, "Custom progression")
    set_sbi_preview_source(ss, "Custom progression")
    ss["improv_song_source"] = "Custom progression"
    install_sbi_custom_identity_before_widgets(ss)
    try:
        prepare_sbi_custom_sidebar_display_key(_st(ss), ss)
    except Exception as exc:
        print("prepare_sbi_custom_sidebar_display_key:", exc)


def open_sbi_active(ss: dict) -> None:
    ss["studio_page"] = "creative"
    note_explicit_sbi_source_selection(ss, "Active song")
    set_sbi_preview_source(ss, "Active song")
    ss["improv_song_source"] = "Active song"
    restore_sbi_active_catalog_identity_before_widgets(ss)
    # Custom install path also handles genuine Active leave
    install_sbi_custom_identity_before_widgets(ss)


def main() -> int:
    rows: list[dict] = []

    # --- Probe 1: Perfect GA + LAST_CUSTOM Trial ---
    ss = perfect_plus_stale_trial()
    b = snap(ss, "Perfect_GA_with_LAST_CUSTOM_Trial")
    rows.append(b)
    if b["selected_title"] == "Perfect" and b["last_custom_name"] == "Trial Song":
        note_collision(
            "dual_identity_memory",
            "Global Active Perfect coexists with LAST_CUSTOM Trial — any surface may bind either",
            b,
            b,
        )

    open_sbi_custom(ss)
    a = snap(ss, "after_SBI_Custom_from_Perfect_GA")
    rows.append(a)
    # Daniel: Trial owns progression but Perfect still shown / PK becomes G
    if a["selected_title"] == "Perfect" and a["cpl_name"] == "Trial Song":
        note_collision(
            "sbi_custom_mixed_header",
            (
                f"selected={a['selected_title']} cpl={a['cpl_name']} "
                f"focus={a['practice_focus']!r} pk={a['practice_key']!r} "
                f"orig={a['sidebar_original_caption']!r} visit_pk={a['sbi_custom_visit_pk']!r}"
            ),
            b,
            a,
        )
    pk = str(a["practice_key"] or "").upper()
    visit = str(a.get("sbi_custom_visit_pk") or a.get("display_key_sbi_custom") or "").upper()
    if a["cpl_name"] == "Trial Song" and pk not in {"F", "F MAJOR"} and visit not in {"F", "F MAJOR"}:
        note_collision(
            "sbi_custom_wrong_pk",
            f"Trial CPL but practice={a['practice_key']!r} visit={a['sbi_custom_visit_pk']!r} expected F",
            b,
            a,
        )
    if "Jewish" in str(a["practice_focus"]) and "Jam" not in str(a["improv_song_source"]):
        note_collision(
            "jewish_ballad_residue",
            f"Non-Jam SBI focus still Jewish: {a['practice_focus']!r}",
            b,
            a,
        )

    # --- Probe 2: Perfect Practice C → SBI Active (Eb pollution) ---
    ss2 = perfect_plus_stale_trial()
    set_practice_concert_key(ss2, "C")
    ss2["mission_practice_key"] = "Eb"
    ss2["written_key"] = "Eb"
    b2 = snap(ss2, "Perfect_before_SBI_Active")
    rows.append(b2)
    open_sbi_active(ss2)
    a2 = snap(ss2, "after_SBI_Active_Perfect")
    rows.append(a2)
    pk2 = str(a2["practice_key"] or "").upper()
    if pk2 not in {"C", "C MAJOR"}:
        note_collision(
            "perfect_sbi_pk_reclaim",
            f"Perfect SBI Active PK={a2['practice_key']!r} expected C; orig={a2['sidebar_original_caption']!r}",
            b2,
            a2,
        )
    if str(a2["sidebar_original_caption"]).upper().startswith("D"):
        note_collision(
            "perfect_original_d_leak",
            f"Perfect SBI Original caption={a2['sidebar_original_caption']!r}",
            b2,
            a2,
        )

    # --- Probe 3: Trial active F + stale Perfect blobs → SBI Custom ---
    ss3 = trial_active_saved_f()
    b3 = snap(ss3, "Trial_active_F")
    rows.append(b3)
    open_sbi_custom(ss3)
    a3 = snap(ss3, "Trial_after_SBI_Custom")
    rows.append(a3)
    if a3["selected_title"] == "Perfect" or (
        "Perfect" in str(a3["practice_focus"]) and "Trial" not in str(a3["practice_focus"])
    ):
        note_collision(
            "trial_sbi_shows_perfect",
            f"selected={a3['selected_title']} focus={a3['practice_focus']!r}",
            b3,
            a3,
        )
    pk3 = str(a3["practice_key"] or "").upper()
    visit3 = str(a3.get("sbi_custom_visit_pk") or a3.get("display_key_sbi_custom") or "").upper()
    if pk3.startswith("G") or visit3.startswith("G"):
        note_collision(
            "trial_sbi_pk_to_g",
            f"Trial SBI Practice/visit became G: pk={a3['practice_key']!r} visit={a3['sbi_custom_visit_pk']!r}",
            b3,
            a3,
        )
    if str(a3["sidebar_original_caption"]).upper().startswith("G"):
        note_collision(
            "trial_original_g_leak",
            f"Trial Original caption G: {a3['sidebar_original_caption']!r}",
            b3,
            a3,
        )
    if pk3 not in {"F", "F MAJOR"} and visit3 not in {"F", "F MAJOR"}:
        note_collision(
            "trial_sbi_lost_saved_f",
            f"Trial saved F lost: pk={a3['practice_key']!r} visit={a3['sbi_custom_visit_pk']!r} orig={a3['sidebar_original_caption']!r}",
            b3,
            a3,
        )

    # --- Probe 4: Perfect GA + Jam style Jewish; focus/identity ---
    ss4 = perfect_plus_stale_trial()
    b4 = snap(ss4, "Perfect_before_jam")
    rows.append(b4)
    ss4["improv_song_source"] = "Jam generator"
    set_sbi_preview_source(ss4, "Jam generator")
    ss4["improv_jam_style"] = "Jewish ballad"
    try:
        from active_song_transition import mark_temporary_workflow_owner

        mark_temporary_workflow_owner(ss4, "jam_generator")
    except Exception as exc:
        print("mark_temporary_workflow_owner:", exc)
    a4 = snap(ss4, "Perfect_after_jam_owner")
    rows.append(a4)
    if "Trial" in str(a4["practice_focus"]) and a4["selected_title"] == "Perfect":
        note_collision(
            "jam_steals_trial_identity",
            f"Jam under Perfect surfaces Trial in focus={a4['practice_focus']!r}",
            b4,
            a4,
        )
    if "Jewish ballad" in str(a4["practice_focus"]) and "Perfect" not in str(a4["practice_focus"]):
        note_collision(
            "jam_focus_jewish_without_perfect",
            f"Jam focus Jewish without Perfect: {a4['practice_focus']!r}",
            b4,
            a4,
        )

    # --- Probe 5: Live Coach / Original while Perfect GA + Trial LAST_CUSTOM ---
    ss5 = perfect_plus_stale_trial()
    ss5["creative_lab_tab"] = "Live Coach"
    orig = resolve_sidebar_original_key_for_caption(ss5, current_original="G")
    b5 = snap(ss5, "LiveCoach_Perfect_orig")
    b5["resolved_orig"] = orig
    rows.append(b5)
    # Also force Custom overlay flags that Daniel's polluted path may leave
    ss5b = perfect_plus_stale_trial(_sbi_custom_sidebar_overlay=True, improv_song_source="Active song")
    orig_b = resolve_sidebar_original_key_for_caption(ss5b, current_original="G")
    b5b = snap(ss5b, "LiveCoach_Perfect_with_custom_overlay_flag")
    b5b["resolved_orig"] = orig_b
    rows.append(b5b)
    if str(orig).upper().startswith("D") or str(orig_b).upper().startswith("D"):
        note_collision(
            "live_coach_original_d",
            f"Perfect GA Original resolved orig={orig!r} overlay_orig={orig_b!r}",
            b5,
            b5b,
        )

    # --- Probe 6: Songs hub vs sidebar dual owner (picker page + Custom banner keys) ---
    ss6 = perfect_plus_stale_trial(studio_page="picker")
    # Sidebar path often reads CPL / LAST_CUSTOM when custom flags linger
    ss6["_sbi_custom_sidebar_overlay"] = True
    ss6["improv_song_source"] = "Custom progression"
    set_sbi_preview_source(ss6, "Custom progression")
    b6 = snap(ss6, "Songs_hub_Perfect_GA_custom_overlay")
    rows.append(b6)
    if b6["selected_title"] == "Perfect" and (
        b6["cpl_name"] == "Trial Song"
        or str(b6["sidebar_original_caption"]).upper().startswith("D")
        or "Trial" in str(b6["practice_focus"])
    ):
        note_collision(
            "songs_sidebar_owner_split",
            (
                f"hub selected={b6['selected_title']} but sidebar/custom path "
                f"cpl={b6['cpl_name']} orig={b6['sidebar_original_caption']!r} "
                f"pk={b6['practice_key']!r} focus={b6['practice_focus']!r}"
            ),
            b6,
            b6,
        )

    report = {"sha": "e5444de", "branch": "hotfix/cross-owner-authority-stabilize", "collisions": COLLISIONS, "snaps": rows}
    (OUT / "slice0_collisions.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nTOTAL_COLLISIONS={len(COLLISIONS)}")
    for c in COLLISIONS:
        print(f" - {c['kind']}")
    print(f"wrote {OUT / 'slice0_collisions.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
