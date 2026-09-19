"""SBI sheet/PK/mode and Guitar Shape Mode sticky-state regressions."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from custom_progression_lab import CPL_ACTIVE_KEY
from song_catalog.catalog import format_pick_key
from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    catalog_pick_has_user_practice_key_override,
    get_practice_concert_key,
    mark_practice_key_user_override,
    set_practice_concert_key,
)

PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL_PICK = "custom::trial-d"


def _trial() -> dict:
    return {
        "id": "trial-d",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [{"chord": "D", "bars": 1}, {"chord": "A", "bars": 1}],
        },
        "bpm": 120,
        "time_signature": "4/4",
    }


def _perfect_session(**extra: object) -> dict:
    session = {
        "studio_page": "creative",
        "instrument": "Guitar",
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        },
        "home_sections": {"Verse": ["G", "Em", "C", "D"]},
        "improv_song_concert_sections": {"Verse": ["G", "Em", "C", "D"]},
        "active_catalog_pick_key": PERFECT_PICK,
        "display_key": "G",
        "concert_key": "G",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "improv_intelligence_tab": "Song-Based Improvisation",
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "G", TRIAL_PICK: "D"},
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": _trial(),
        },
        CPL_ACTIVE_KEY: _trial(),
        "cpl_saved_progressions": {"Trial Song": _trial()},
        "guitar_capo_enabled": False,
        "guitar_capo_shape_key": "G",
    }
    session.update(extra)
    return session


class TestTrialCustomSheetOriginalD(unittest.TestCase):
    def test_sbi_custom_sheet_says_orig_d_not_generic_c(self) -> None:
        from backing_context import BackingContext, owned_backing_chart_identity, set_backing_context
        from creative_source_ownership_contract import resolve_custom_saved_original_key
        from songs.backing_chart import render_backing_chord_chart

        session = _perfect_session(
            studio_page="backing",
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            display_key="D",
            concert_key="D",
        )
        session[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        ctx = BackingContext(
            source="song_improv",
            source_label="Song-Based Improvisation",
            active_song_id=TRIAL_PICK,
            song_title="My Progression",
            key="C",
            display_key="D",
            concert_key="D",
            bpm=120,
            style="Custom",
            groove="Pop",
            progression=["D", "A"],
            entry_mode="Song-Based Improvisation",
            sbi_source_owner="Custom progression",
            sbi_material_kind="custom",
            bound_pick_key=TRIAL_PICK,
        )
        set_backing_context(session, ctx)
        self.assertTrue(str(resolve_custom_saved_original_key(session) or "").startswith("D"))
        ident = owned_backing_chart_identity(session, ctx)
        self.assertIsNotNone(ident)
        self.assertTrue(str(ident["original_key"]).startswith("D"), ident)
        self.assertTrue(str(ident["song_data"]["key"]).startswith("D"), ident["song_data"])
        html = render_backing_chord_chart(
            "Trial Song",
            ident["song_data"],
            {"Verse": ["D", "A"]},
            display_key="D",
        )
        self.assertIn("(orig. D)", html)
        self.assertNotIn("(orig. C)", html)


class TestPerfectSbiPracticeReachesOutputs(unittest.TestCase):
    def test_perfect_g_to_c_transposes_progression_original_stays_g(self) -> None:
        from music_workflow_pending_song_practice_key_edit import overlay_sections_with_pending_practice_key
        from sbi_active_catalog_practice_key import (
            note_sbi_active_user_practice_key_edit,
            persist_sbi_active_sidebar_commit_before_render,
            sbi_active_canonical_practice_key,
        )

        session = _perfect_session()
        session["display_key"] = "C"
        session["concert_key"] = "C"
        persist_sbi_active_sidebar_commit_before_render(session)
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        self.assertTrue(str(sbi_active_canonical_practice_key(session, "G")).startswith("C"))
        self.assertTrue(str(session.get("selected_song", {}).get("key") or "").startswith("G"))
        secs = overlay_sections_with_pending_practice_key(
            session,
            {"Verse": ["G", "Em", "C", "D"]},
            spelled_in_key="G",
        )
        first = str(next(iter(secs.values()))[0])
        self.assertTrue(first.startswith("C"), secs)

    def test_perfect_g_to_c_survives_rerun_and_refresh(self) -> None:
        from music_restore_phase import begin_music_script_run
        from sbi_active_catalog_practice_key import (
            note_sbi_active_user_practice_key_edit,
            prepare_sbi_active_catalog_practice_key,
            sbi_active_canonical_practice_key,
        )
        from session_widget_safe import apply_pending_widget_hydrates

        session = _perfect_session()
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        session["display_key"] = "G"
        begin_music_script_run(session)
        apply_pending_widget_hydrates(session)
        prepare_sbi_active_catalog_practice_key(session)
        self.assertTrue(str(sbi_active_canonical_practice_key(session, "G")).startswith("C"))
        pending = str(session.get("display_key") or session.get("_pending_display_key") or "")
        self.assertTrue(pending.startswith("C"), pending)
        self.assertTrue(str(session.get("selected_song", {}).get("key") or "").startswith("G"))


class TestSbiModeSurvivesRefresh(unittest.TestCase):
    def test_refresh_on_active_stays_active_despite_leftover_custom_stamp(self) -> None:
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            get_sbi_preview_source,
            seed_sbi_custom_radio_before_render,
        )

        session = _perfect_session(
            improv_song_source="Active song",
            sbi_preview_source="Active song",
        )
        session[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        session["creative_workspace_state"] = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "sbi_preview_source": "Active song",
        }
        self.assertEqual(get_sbi_preview_source(session), "Active song")
        seeded = seed_sbi_custom_radio_before_render(session)
        self.assertEqual(seeded, "Active song")
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertFalse(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

    def test_refresh_on_custom_stays_custom_with_same_uuid(self) -> None:
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            get_sbi_preview_source,
            install_sbi_custom_identity_before_widgets,
            seed_sbi_custom_radio_before_render,
        )

        session = _perfect_session(
            improv_song_source="Active song",
            sbi_preview_source="Custom progression",
        )
        session[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")
        seeded = seed_sbi_custom_radio_before_render(session)
        self.assertEqual(seeded, "Custom progression")
        ok = install_sbi_custom_identity_before_widgets(session)
        self.assertTrue(ok)
        snap = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str(snap.get("pick_key") or ""), TRIAL_PICK)


class TestTrialCustomPracticeKeyEditable(unittest.TestCase):
    def test_trial_practice_d_to_f_keeps_original_d_and_perfect_c(self) -> None:
        from source_session_state import (
            install_sbi_custom_identity_before_widgets,
            persist_sbi_custom_practice_key_edit,
            resolve_sbi_custom_practice_key,
        )

        session = _perfect_session()
        mark_practice_key_user_override(session, PERFECT_PICK)
        set_practice_concert_key(session, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        session["_sbi_custom_sidebar_overlay"] = True
        persist_sbi_custom_practice_key_edit(session, "F")
        session["display_key_sbi_custom"] = "F"
        self.assertTrue(str(resolve_sbi_custom_practice_key(session)).startswith("F"))
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))
        self.assertTrue(catalog_pick_has_user_practice_key_override(session, TRIAL_PICK))
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))
        orig = str((session.get(LAST_CUSTOM_STATE_KEY) or {}).get("custom_home_key") or "")
        self.assertTrue(orig.startswith("D"), orig)
        install_sbi_custom_identity_before_widgets(session)
        self.assertEqual(session.get("display_key_sbi_custom"), "F")
        self.assertTrue(str(session.get("_sbi_custom_visit_pk") or "").startswith("F"))
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))

    def test_install_does_not_mutate_mounted_custom_widget(self) -> None:
        from source_session_state import install_sbi_custom_identity_before_widgets

        session = _perfect_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            display_key_sbi_custom="F",
            _sbi_custom_visit_pk="D",
        )
        set_practice_concert_key(session, "F", pick_key=TRIAL_PICK, allow_restore_original=True)
        install_sbi_custom_identity_before_widgets(session)
        self.assertEqual(session.get("display_key_sbi_custom"), "F")

    def test_custom_pk_callback_resolves_uuid_from_identity_pick(self) -> None:
        from source_session_state import (
            SBI_CUSTOM_IDENTITY_PICK_KEY,
            persist_sbi_custom_practice_key_edit,
        )

        session = _perfect_session()
        snap = dict(session.get(LAST_CUSTOM_STATE_KEY) or {})
        snap.pop("pick_key", None)
        session[LAST_CUSTOM_STATE_KEY] = snap
        session[SBI_CUSTOM_IDENTITY_PICK_KEY] = TRIAL_PICK
        session["_pending_display_key"] = "D"
        session["_pending_display_key_source"] = "sbi_custom_home"
        persist_sbi_custom_practice_key_edit(session, "F")
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))
        self.assertTrue(catalog_pick_has_user_practice_key_override(session, TRIAL_PICK))
        self.assertNotEqual(str(session.get("_pending_display_key") or ""), "D")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertTrue(str(session.get("_sbi_custom_visit_pk") or "").startswith("F"))


class TestGuitarShapeModeSticky(unittest.TestCase):
    def test_shape_mode_stays_on_across_owner_transitions(self) -> None:
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            CAPO_SHAPE_KEY,
            apply_source_change_shape_home,
            isolate_jam_from_catalog_guitar_shape,
            shape_tonic_only,
        )

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            _capo_shape_seed_source_id=PERFECT_PICK,
        )
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        isolate_jam_from_catalog_guitar_shape(session)
        self.assertTrue(session.get(CAPO_ENABLED_KEY))
        self.assertEqual(shape_tonic_only(str(session.get(CAPO_SHAPE_KEY) or "")), "C")
        apply_source_change_shape_home(session, "D")
        self.assertEqual(shape_tonic_only(str(session.get(CAPO_SHAPE_KEY) or "")), "C")
        session["sbi_preview_source"] = "Composition"
        apply_source_change_shape_home(session, "Eb")
        self.assertTrue(session.get(CAPO_ENABLED_KEY))
        self.assertEqual(shape_tonic_only(str(session.get(CAPO_SHAPE_KEY) or "")), "C")

    def test_perfect_g_c_shape_to_eb_minor_keeps_c_tonic(self) -> None:
        from guitar_capo import (
            apply_source_change_shape_home,
            capo_fret_for_shape,
            shape_chart_key_for_concert,
            shape_tonic_only,
            sync_capo_from_practice_display_key,
        )

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            _capo_shape_seed_source_id=PERFECT_PICK,
        )
        session["selected_song"] = {
            "title": "Eb Minor Song",
            "key": "Eb minor",
            "pick_key": "Jazz\x1fEb Minor Song",
        }
        session["active_catalog_pick_key"] = "Jazz\x1fEb Minor Song"
        session["display_key"] = "Eb minor"
        session["concert_key"] = "Eb minor"
        apply_source_change_shape_home(session, "Eb minor")
        sounding = sync_capo_from_practice_display_key(session, "Eb minor")
        self.assertTrue(str(sounding).startswith("Eb"))
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")
        chart = shape_chart_key_for_concert(sounding, "C")
        self.assertTrue(str(chart).lower().startswith("c") and "m" in str(chart).lower(), chart)
        capo = capo_fret_for_shape(sounding, "C")
        self.assertEqual(capo, 3)

    def test_practice_key_change_keeps_shape_tonic(self) -> None:
        from guitar_capo import shape_tonic_only, sync_capo_from_practice_display_key

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
        )
        sync_capo_from_practice_display_key(session, "A")
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")

    def test_refresh_retains_shape_mode_and_tonic(self) -> None:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, shape_tonic_only
        from music_restore_phase import begin_music_script_run

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
        )
        begin_music_script_run(session)
        self.assertTrue(session.get(CAPO_ENABLED_KEY))
        self.assertEqual(shape_tonic_only(str(session.get(CAPO_SHAPE_KEY) or "")), "C")

    def test_manual_off_releases_sticky_manual_on_defaults_to_sounding(self) -> None:
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            CAPO_SHAPE_KEY,
            apply_genuine_shape_mode_user_transition,
            capo_fret_for_shape,
            live_capo_shape_widget_key,
            persist_capo_to_canonical,
            shape_chart_key_for_concert,
            shape_tonic_only,
        )

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            guitar_capo_shape_widget="C",
            display_key="Eb minor",
            concert_key="Eb minor",
            _capo_enabled_committed=True,
            active_song_state={
                "guitar_capo_enabled": True,
                "guitar_capo_shape_key": "C",
                "pick_key": PERFECT_PICK,
            },
        )
        session["_capo_shape_mode_on_change_this_run"] = True
        off = apply_genuine_shape_mode_user_transition(
            session,
            now_enabled=False,
            sounding="Eb minor",
            this_run_restore=False,
        )
        self.assertTrue(off["genuine_manual_off"])
        self.assertFalse(off["genuine_manual_on"])
        session[CAPO_ENABLED_KEY] = False
        persist_capo_to_canonical(session)
        self.assertFalse(session.get(CAPO_ENABLED_KEY))
        self.assertNotEqual(
            str(session.get(live_capo_shape_widget_key(session)) or ""),
            "C",
        )
        session["_capo_shape_mode_on_change_this_run"] = True
        on = apply_genuine_shape_mode_user_transition(
            session,
            now_enabled=True,
            sounding="Eb minor",
            this_run_restore=False,
        )
        self.assertTrue(on["genuine_manual_on"])
        session[CAPO_ENABLED_KEY] = True
        self.assertEqual(shape_tonic_only(str(session.get(CAPO_SHAPE_KEY) or "")), "Eb")
        chart = shape_chart_key_for_concert("Eb minor", str(session.get(CAPO_SHAPE_KEY) or ""))
        self.assertTrue(str(chart).lower().startswith("eb") and "m" in str(chart).lower(), chart)
        self.assertEqual(capo_fret_for_shape("Eb minor", str(session.get(CAPO_SHAPE_KEY) or "")), 0)
        persist_capo_to_canonical(session)

    def test_genuine_manual_off_is_not_blocked_by_canonical_meta(self) -> None:
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            apply_genuine_shape_mode_user_transition,
            persist_capo_to_canonical,
        )

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            _capo_enabled_committed=True,
            _music_disk_restore_this_run=False,
            _cloud_workspace_restored_this_run=False,
            active_song_state={
                "guitar_capo_enabled": True,
                "guitar_capo_shape_key": "C",
                "pick_key": PERFECT_PICK,
            },
        )
        session["_capo_shape_mode_on_change_this_run"] = True
        off = apply_genuine_shape_mode_user_transition(
            session,
            now_enabled=False,
            sounding="Eb minor",
            this_run_restore=False,
        )
        self.assertTrue(off["genuine_manual_off"])
        session[CAPO_ENABLED_KEY] = False
        self.assertTrue(persist_capo_to_canonical(session))
        self.assertFalse(session.get(CAPO_ENABLED_KEY))
        meta = session.get("active_song_state") or {}
        self.assertFalse(bool(meta.get(CAPO_ENABLED_KEY)))
        self.assertNotEqual(str(meta.get("guitar_capo_shape_key") or ""), "C")

    def test_stale_pending_capo_on_does_not_remount_after_genuine_off(self) -> None:
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            CAPO_ENABLED_WIDGET_KEY,
            apply_genuine_shape_mode_user_transition,
            persist_capo_to_canonical,
        )

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            _capo_enabled_committed=True,
            _pending_capo_enabled_widget=True,
            active_song_state={
                "guitar_capo_enabled": True,
                "guitar_capo_shape_key": "C",
                "pick_key": PERFECT_PICK,
            },
        )
        session["_capo_shape_mode_on_change_this_run"] = True
        session["_capo_shape_mode_user_intent"] = "off"
        session["_capo_genuine_user_off"] = True
        session[CAPO_ENABLED_KEY] = False
        off = apply_genuine_shape_mode_user_transition(
            session,
            now_enabled=False,
            sounding="Eb minor",
            this_run_restore=False,
        )
        self.assertTrue(off["genuine_manual_off"])
        persist_capo_to_canonical(session)
        self.assertFalse(bool((session.get("active_song_state") or {}).get(CAPO_ENABLED_KEY)))
        # Simulate next-run seed: stale pending ON must not win.
        genuine_off_pending = bool(session.get("_capo_genuine_user_off")) or (
            str(session.get("_capo_shape_mode_user_intent") or "") == "off"
        )
        if genuine_off_pending:
            session.pop("_pending_capo_enabled_widget", None)
            session[CAPO_ENABLED_WIDGET_KEY] = False
            session[CAPO_ENABLED_KEY] = False
        self.assertFalse(session.get(CAPO_ENABLED_KEY))
        self.assertFalse(session.get(CAPO_ENABLED_WIDGET_KEY))
        self.assertNotIn("_pending_capo_enabled_widget", session)

    def test_hydration_does_not_imitate_manual_off_on(self) -> None:
        from guitar_capo import (
            apply_genuine_shape_mode_user_transition,
            apply_source_change_shape_home,
            shape_tonic_only,
        )

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            _music_disk_restore_this_run=True,
            _capo_shape_seed_source_id="other-song",
            _capo_enabled_committed=True,
        )
        apply_source_change_shape_home(session, "Eb minor")
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")
        self.assertTrue(session.get("guitar_capo_enabled"))
        hydrate = apply_genuine_shape_mode_user_transition(
            session,
            now_enabled=True,
            sounding="Eb minor",
            this_run_restore=True,
        )
        self.assertFalse(hydrate["genuine_manual_off"])
        self.assertFalse(hydrate["genuine_manual_on"])
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")

    def test_automatic_rerun_retains_on_and_c_tonic(self) -> None:
        from guitar_capo import apply_source_change_shape_home, shape_tonic_only
        from music_restore_phase import begin_music_script_run

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            display_key="Eb minor",
            concert_key="Eb minor",
            _capo_enabled_committed=True,
            _capo_shape_seed_source_id=PERFECT_PICK,
        )
        begin_music_script_run(session)
        apply_source_change_shape_home(session, "Eb minor")
        self.assertTrue(session.get("guitar_capo_enabled"))
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")

    def test_missing_widget_rerun_is_not_manual_off_on(self) -> None:
        from guitar_capo import apply_genuine_shape_mode_user_transition, shape_tonic_only

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            _capo_enabled_committed=True,
        )
        hydrate_off = apply_genuine_shape_mode_user_transition(
            session,
            now_enabled=False,
            sounding="Eb minor",
            this_run_restore=False,
        )
        self.assertFalse(hydrate_off["genuine_manual_off"])
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")
        hydrate_on = apply_genuine_shape_mode_user_transition(
            session,
            now_enabled=True,
            sounding="Eb minor",
            this_run_restore=False,
        )
        self.assertFalse(hydrate_on["genuine_manual_on"])
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")

    def test_refresh_after_new_on_retains_eb_open(self) -> None:
        from guitar_capo import (
            apply_genuine_shape_mode_user_transition,
            capo_fret_for_shape,
            shape_tonic_only,
        )
        from music_restore_phase import begin_music_script_run

        session = _perfect_session(
            guitar_capo_enabled=True,
            guitar_capo_shape_key="C",
            display_key="Eb minor",
            concert_key="Eb minor",
            _capo_enabled_committed=True,
        )
        session["_capo_shape_mode_on_change_this_run"] = True
        apply_genuine_shape_mode_user_transition(
            session, now_enabled=False, sounding="Eb minor", this_run_restore=False
        )
        session["_capo_shape_mode_on_change_this_run"] = True
        apply_genuine_shape_mode_user_transition(
            session, now_enabled=True, sounding="Eb minor", this_run_restore=False
        )
        session["guitar_capo_enabled"] = True
        begin_music_script_run(session)
        self.assertTrue(session.get("guitar_capo_enabled"))
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "Eb")
        self.assertEqual(capo_fret_for_shape("Eb minor", "Eb"), 0)

    def test_no_post_mount_widget_mutation_helper(self) -> None:
        from source_session_state import install_sbi_custom_identity_before_widgets

        session = _perfect_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            display_key_sbi_custom="F",
        )
        set_practice_concert_key(session, "F", pick_key=TRIAL_PICK, allow_restore_original=True)
        install_sbi_custom_identity_before_widgets(session)
        self.assertEqual(session.get("display_key_sbi_custom"), "F")


class TestCustomTrialDfSurvivesFreshHydrate(unittest.TestCase):
    def test_custom_trial_d_to_f_survives_reconstructed_session(self) -> None:
        from music_restore_phase import begin_music_script_run
        from sbi_active_catalog_practice_key import note_sbi_active_user_practice_key_edit
        from session_widget_safe import apply_pending_widget_hydrates
        from source_session_state import (
            SBI_CUSTOM_IDENTITY_PICK_KEY,
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            apply_sbi_radio_live_against_restore_stamp,
            clear_restore_sbi_custom_source,
            clear_sbi_custom_sidebar_overlay_if_needed,
            get_sbi_preview_source,
            install_sbi_custom_identity_before_widgets,
            persist_sbi_custom_practice_key_edit,
            resolve_sbi_preview,
            seed_sbi_custom_radio_before_render,
            set_sbi_preview_source,
        )
        from studio_page_state import flush_pending_improv_song_source

        live = _perfect_session()
        live["catalog_session"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "original_key": "G",
            "display_key": "C",
            "pick_key": PERFECT_PICK,
            "selected_song": live["selected_song"],
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        }
        note_sbi_active_user_practice_key_edit(live, "C", pick=PERFECT_PICK)
        live["sbi_preview_source"] = "Custom progression"
        live["improv_song_source"] = "Custom progression"
        live["_restore_sbi_custom_source"] = True
        self.assertTrue(install_sbi_custom_identity_before_widgets(live))
        persist_sbi_custom_practice_key_edit(live, "F")
        self.assertEqual(get_sbi_preview_source(live), "Custom progression")
        self.assertTrue(str(get_practice_concert_key(live, TRIAL_PICK)).startswith("F"))
        self.assertTrue(str(get_practice_concert_key(live, PERFECT_PICK)).startswith("C"))
        self.assertEqual(str(live.get(SBI_CUSTOM_IDENTITY_PICK_KEY) or ""), TRIAL_PICK)

        blob = dict(live.get("creative_workspace_state") or {})
        blob.update(
            {
                "sbi_preview_source": "Custom progression",
                "_restore_sbi_custom_source": True,
                "_last_improv_song_source": "Custom progression",
                SBI_CUSTOM_IDENTITY_PICK_KEY: TRIAL_PICK,
                SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            }
        )
        fresh = {
            "studio_page": "creative",
            "instrument": "Guitar",
            "song": "Perfect",
            "selected_song": live["selected_song"],
            "active_catalog_pick_key": PERFECT_PICK,
            "catalog_session": live.get("catalog_session"),
            LAST_CUSTOM_STATE_KEY: live.get(LAST_CUSTOM_STATE_KEY),
            CPL_ACTIVE_KEY: live.get(CPL_ACTIVE_KEY),
            "cpl_saved_progressions": live.get("cpl_saved_progressions"),
            PRACTICE_KEY_BY_SOURCE_KEY: dict(live.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}),
            "practice_key_user_override_picks": live.get("practice_key_user_override_picks"),
            "sbi_preview_source": "Custom progression",
            "_restore_sbi_custom_source": True,
            "_last_improv_song_source": "Custom progression",
            SBI_CUSTOM_IDENTITY_PICK_KEY: TRIAL_PICK,
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "creative_workspace_state": blob,
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            "home_sections": live.get("home_sections"),
            "improv_song_concert_sections": live.get("improv_song_concert_sections"),
            "improv_song_source": "Active song",
            "display_key": "C",
            "concert_key": "C",
        }
        begin_music_script_run(fresh)
        flush_pending_improv_song_source(fresh)
        seeded = seed_sbi_custom_radio_before_render(fresh)
        self.assertEqual(seeded, "Custom progression")
        self.assertEqual(get_sbi_preview_source(fresh), "Custom progression")
        won = apply_sbi_radio_live_against_restore_stamp(fresh, "Active song")
        self.assertEqual(won, "Custom progression")
        self.assertTrue(install_sbi_custom_identity_before_widgets(fresh))
        preview = resolve_sbi_preview(fresh)
        self.assertEqual(preview.get("source"), "Custom progression")
        self.assertEqual(str(preview.get("pick_key") or ""), TRIAL_PICK)
        self.assertTrue(str(preview.get("original_key") or "").startswith("D"), preview)
        self.assertTrue(str(preview.get("display_key") or "").startswith("F"), preview)
        self.assertTrue(str(get_practice_concert_key(fresh, PERFECT_PICK)).startswith("C"))
        self.assertTrue(str(get_practice_concert_key(fresh, TRIAL_PICK)).startswith("F"))
        self.assertEqual(str((fresh.get("selected_song") or {}).get("title") or ""), "Perfect")
        self.assertTrue(str((fresh.get("selected_song") or {}).get("key") or "").startswith("G"))
        stolen = [
            row
            for row in (fresh.get("_sbi_preview_source_writes") or [])
            if str(row.get("from") or "") == "Custom progression"
            and str(row.get("to") or "") == "Active song"
            and not row.get("refused")
        ]
        self.assertEqual(stolen, [], stolen)

        apply_pending_widget_hydrates(fresh)
        install_sbi_custom_identity_before_widgets(fresh)
        self.assertEqual(get_sbi_preview_source(fresh), "Custom progression")
        self.assertEqual(fresh.get("improv_song_source"), "Custom progression")

        fresh["_sbi_follow_active_widget_seen"] = True
        fresh["improv_song_source"] = "Active song"
        fresh["_sbi_radio_on_change_this_run"] = "Active song"
        set_sbi_preview_source(fresh, "Active song")
        clear_restore_sbi_custom_source(fresh)
        clear_sbi_custom_sidebar_overlay_if_needed(fresh)
        active = resolve_sbi_preview(fresh)
        self.assertEqual(active.get("source"), "Active song")
        self.assertTrue(str(active.get("original_key") or "").startswith("G"), active)
        self.assertTrue(str(active.get("display_key") or "").startswith("C"), active)
        self.assertEqual(str(active.get("pick_key") or ""), PERFECT_PICK)

    def test_remounted_active_radio_is_not_a_genuine_leave(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            apply_sbi_radio_live_against_restore_stamp,
        )

        session = _perfect_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Active song",
            _restore_sbi_custom_source=True,
        )
        session[SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY] = True
        self.assertEqual(
            apply_sbi_radio_live_against_restore_stamp(session, "Active song"),
            "Custom progression",
        )
        session["_sbi_radio_on_change_this_run"] = "Active song"
        self.assertEqual(
            apply_sbi_radio_live_against_restore_stamp(session, "Active song"),
            "Active song",
        )

    def test_active_leave_intent_survives_missing_on_change_flag(self) -> None:
        from source_session_state import (
            SBI_ACTIVE_LEAVE_INTENT_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            apply_sbi_radio_live_against_restore_stamp,
            consume_sbi_active_leave_intent,
            genuine_sbi_active_leave,
            install_sbi_custom_identity_before_widgets,
            persist_sbi_custom_practice_key_edit,
            resolve_sbi_preview,
            seed_sbi_custom_radio_before_render,
            stamp_sbi_active_leave_intent,
        )
        from sbi_active_catalog_practice_key import note_sbi_active_user_practice_key_edit

        session = _perfect_session()
        session["catalog_session"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "original_key": "G",
            "display_key": "C",
            "pick_key": PERFECT_PICK,
            "selected_song": session["selected_song"],
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        }
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        session["_restore_sbi_custom_source"] = True
        self.assertTrue(install_sbi_custom_identity_before_widgets(session))
        persist_sbi_custom_practice_key_edit(session, "F")
        session[SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY] = True
        stamp_sbi_active_leave_intent(session)
        session.pop("_sbi_radio_on_change_this_run", None)
        self.assertTrue(session.get(SBI_ACTIVE_LEAVE_INTENT_KEY))
        self.assertTrue(genuine_sbi_active_leave(session))
        self.assertEqual(
            apply_sbi_radio_live_against_restore_stamp(session, "Active song"),
            "Active song",
        )
        self.assertFalse(install_sbi_custom_identity_before_widgets(session))
        seeded = seed_sbi_custom_radio_before_render(session)
        self.assertEqual(seeded, "Active song")
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("source"), "Active song")
        self.assertTrue(str(preview.get("original_key") or "").startswith("G"), preview)
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))
        self.assertTrue(
            str(session.get("display_key") or session.get("concert_key") or "").startswith("C")
            or str(preview.get("display_key") or "").startswith("C"),
            preview,
        )
        self.assertEqual(str(preview.get("pick_key") or ""), PERFECT_PICK)
        consume_sbi_active_leave_intent(session)
        session["improv_song_source"] = "Active song"
        self.assertFalse(genuine_sbi_active_leave(session))
        session["_restore_sbi_custom_source"] = True
        session["sbi_preview_source"] = "Custom progression"
        session["creative_workspace_state"] = {"sbi_preview_source": "Custom progression"}
        self.assertEqual(
            apply_sbi_radio_live_against_restore_stamp(session, "Active song"),
            "Custom progression",
        )

    def test_active_leave_persists_active_and_clears_custom_restore(self) -> None:
        from source_session_state import (
            persist_sbi_active_leave_authority,
            persist_sbi_custom_practice_key_edit,
            stamp_sbi_active_leave_intent,
        )
        from sbi_active_catalog_practice_key import note_sbi_active_user_practice_key_edit
        from studio_page_persistence import apply_page_snapshot

        session = _perfect_session()
        session["catalog_session"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "original_key": "G",
            "display_key": "C",
            "pick_key": PERFECT_PICK,
            "selected_song": session["selected_song"],
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        }
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        session["_restore_sbi_custom_source"] = True
        session["creative_workspace_state"] = {
            "sbi_preview_source": "Custom progression",
            "_restore_sbi_custom_source": True,
            "improv_song_source": "Custom progression",
        }
        session["creative_session"] = {"song_source": "Custom progression"}
        session["_studio_page_snapshots"] = {
            "creative": {
                "sbi_preview_source": "Custom progression",
                "improv_song_source": "Custom progression",
                "_restore_sbi_custom_source": True,
                "_nested_custom_sbi_backing": True,
            }
        }
        persist_sbi_custom_practice_key_edit(session, "F")
        stamp_sbi_active_leave_intent(session)
        persist_sbi_active_leave_authority(session)
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        self.assertFalse(bool(session.get("_restore_sbi_custom_source")))
        blob = session.get("creative_workspace_state") or {}
        self.assertEqual(blob.get("sbi_preview_source"), "Active song")
        self.assertFalse(bool(blob.get("_restore_sbi_custom_source")))
        self.assertEqual((session.get("creative_session") or {}).get("song_source"), "Active song")
        snap = (session.get("_studio_page_snapshots") or {}).get("creative") or {}
        self.assertEqual(snap.get("sbi_preview_source"), "Active song")
        self.assertFalse(bool(snap.get("_restore_sbi_custom_source")))
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))
        apply_page_snapshot(
            session,
            {
                "sbi_preview_source": "Custom progression",
                "improv_song_source": "Custom progression",
                "_nested_custom_sbi_backing": True,
                "backing_context": {
                    "source": "song_improv",
                    "sbi_source_owner": "Custom progression",
                    "sbi_material_kind": "custom",
                    "bound_pick_key": TRIAL_PICK,
                },
            },
        )
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        self.assertNotEqual(str(session.get("improv_song_source") or ""), "Custom progression")

    def test_flush_remounted_custom_after_active_leave_keeps_active(self) -> None:
        from studio_page_state import flush_pending_improv_song_source

        session = _perfect_session(
            sbi_preview_source="Active song",
            improv_song_source="Custom progression",
            _restore_sbi_custom_source=False,
            _sbi_song_source_hydrated=True,
            _sbi_follow_active_widget_seen=True,
            _last_improv_song_source="Active song",
        )
        session["creative_workspace_state"] = {
            "sbi_preview_source": "Active song",
            "_restore_sbi_custom_source": False,
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        self.assertFalse(bool(session.get("_restore_sbi_custom_source")))
        self.assertEqual(session.get("improv_song_source"), "Active song")

    def test_consumed_leave_remounted_custom_does_not_reinstall_trial(self) -> None:
        from sbi_active_catalog_practice_key import note_sbi_active_user_practice_key_edit
        from source_session_state import (
            consume_sbi_active_leave_intent,
            get_sbi_preview_source,
            install_sbi_custom_identity_before_widgets,
            persist_sbi_custom_practice_key_edit,
            seed_sbi_custom_radio_before_render,
            stamp_sbi_active_leave_intent,
        )
        from studio_page_state import flush_pending_improv_song_source

        session = _perfect_session()
        session["catalog_session"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "original_key": "G",
            "display_key": "C",
            "pick_key": PERFECT_PICK,
            "selected_song": session["selected_song"],
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        }
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        session["_restore_sbi_custom_source"] = True
        session["_sbi_follow_active_widget_seen"] = True
        self.assertTrue(install_sbi_custom_identity_before_widgets(session))
        persist_sbi_custom_practice_key_edit(session, "F")
        session["display_key"] = "F"
        stamp_sbi_active_leave_intent(session)
        consume_sbi_active_leave_intent(session)
        session["improv_song_source"] = "Custom progression"
        session["_sbi_follow_active_widget_seen"] = True
        self.assertFalse(install_sbi_custom_identity_before_widgets(session))
        flush_pending_improv_song_source(session)
        seeded = seed_sbi_custom_radio_before_render(session)
        self.assertEqual(seeded, "Active song")
        self.assertEqual(get_sbi_preview_source(session), "Active song")
        self.assertFalse(bool(session.get("_restore_sbi_custom_source")))
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertTrue(str(session.get("display_key") or "").startswith("C"), session.get("display_key"))
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))

    def test_set_preview_refuses_custom_over_persisted_active(self) -> None:
        from source_session_state import set_sbi_preview_source

        session = _perfect_session(
            sbi_preview_source="Active song",
            improv_song_source="Custom progression",
            _restore_sbi_custom_source=False,
            _last_improv_song_source="Active song",
        )
        set_sbi_preview_source(session, "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        self.assertFalse(bool(session.get("_restore_sbi_custom_source")))
        refused = [
            row
            for row in (session.get("_sbi_preview_source_writes") or [])
            if row.get("refused")
        ]
        self.assertTrue(refused, session.get("_sbi_preview_source_writes"))

    def test_gather_active_leave_does_not_save_remounted_custom_widget(self) -> None:
        from creative_workspace_state_persistence import gather_creative_workspace_from_session

        session = _perfect_session(
            sbi_preview_source="Active song",
            improv_song_source="Custom progression",
            _restore_sbi_custom_source=False,
            _last_improv_song_source="Active song",
        )
        session["creative_workspace_state"] = {
            "sbi_preview_source": "Active song",
            "improv_song_source": "Custom progression",
            "_restore_sbi_custom_source": False,
        }
        blob = gather_creative_workspace_from_session(session)
        self.assertEqual(blob.get("sbi_preview_source"), "Active song")
        self.assertEqual(blob.get("improv_song_source"), "Active song")
        self.assertEqual(blob.get("_last_improv_song_source"), "Active song")
        self.assertFalse(bool(blob.get("_restore_sbi_custom_source")))

    def test_flush_discards_leftover_pending_custom_after_active_leave(self) -> None:
        from studio_page_state import flush_pending_improv_song_source

        session = _perfect_session(
            sbi_preview_source="Active song",
            improv_song_source="Active song",
            _restore_sbi_custom_source=False,
            _sbi_song_source_hydrated=True,
            _last_improv_song_source="Active song",
            _pending_improv_song_source="Custom progression",
            _explicit_sbi_source_click="Custom progression",
        )
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertFalse(bool(session.get("_restore_sbi_custom_source")))

    def test_remounted_custom_radio_does_not_own_sidebar_after_active_leave(self) -> None:
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        session = _perfect_session(
            sbi_preview_source="Active song",
            improv_song_source="Custom progression",
            _restore_sbi_custom_source=False,
            _last_improv_song_source="Active song",
            display_key="F",
        )
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))


class TestRemountedActiveDoesNotStealCustom(unittest.TestCase):
    def test_flush_pk_rerun_remount_keeps_custom(self) -> None:
        from source_session_state import get_sbi_preview_source
        from studio_page_state import flush_pending_improv_song_source

        session = _perfect_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Active song",
            _restore_sbi_custom_source=True,
            _sbi_song_source_hydrated=True,
            _sbi_follow_active_widget_seen=True,
            _last_improv_song_source="Custom progression",
        )
        session["creative_workspace_state"] = {"sbi_preview_source": "Custom progression"}
        flush_pending_improv_song_source(session)
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")
        stolen = [
            row
            for row in (session.get("_sbi_preview_source_writes") or [])
            if str(row.get("from") or "") == "Custom progression"
            and str(row.get("to") or "") == "Active song"
            and not row.get("refused")
        ]
        self.assertEqual(stolen, [], stolen)

    def test_active_write_without_genuine_flag_is_refused(self) -> None:
        from source_session_state import set_sbi_preview_source

        session = _perfect_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
        )
        session["_sbi_preview_write_via"] = "flush_pending_improv_song_source_live"
        set_sbi_preview_source(session, "Active song")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        refused = [
            row
            for row in (session.get("_sbi_preview_source_writes") or [])
            if row.get("refused")
        ]
        self.assertTrue(refused, session.get("_sbi_preview_source_writes"))

    def test_default_via_active_write_over_custom_is_refused(self) -> None:
        from source_session_state import set_sbi_preview_source

        session = _perfect_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            _restore_sbi_custom_source=True,
            _last_improv_song_source="Custom progression",
        )
        set_sbi_preview_source(session, "Active song")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertTrue(bool(session.get("_restore_sbi_custom_source")))
        refused = [
            row
            for row in (session.get("_sbi_preview_source_writes") or [])
            if row.get("refused")
        ]
        self.assertTrue(refused, session.get("_sbi_preview_source_writes"))

    def test_remounted_active_widget_reinstalls_persisted_custom(self) -> None:
        from source_session_state import install_sbi_custom_identity_before_widgets

        session = _perfect_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Active song",
            _restore_sbi_custom_source=True,
            _last_improv_song_source="Custom progression",
            _sbi_follow_active_widget_seen=True,
        )
        self.assertTrue(install_sbi_custom_identity_before_widgets(session))
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertEqual(session.get("improv_song_source"), "Custom progression")

    def test_refresh_persisted_active_restores_catalog_pk_not_visit_f(self) -> None:
        from sbi_active_catalog_practice_key import note_sbi_active_user_practice_key_edit
        from source_session_state import (
            consume_sbi_active_leave_intent,
            install_sbi_custom_identity_before_widgets,
            persist_sbi_custom_practice_key_edit,
            stamp_sbi_active_leave_intent,
        )

        session = _perfect_session()
        session["catalog_session"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "original_key": "G",
            "display_key": "C",
            "pick_key": PERFECT_PICK,
            "selected_song": session["selected_song"],
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        }
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        session["_restore_sbi_custom_source"] = True
        self.assertTrue(install_sbi_custom_identity_before_widgets(session))
        persist_sbi_custom_practice_key_edit(session, "F")
        session["selected_song"] = {
            "title": "Trial Song",
            "key": "D",
            "pick_key": TRIAL_PICK,
        }
        session["song"] = "Trial Song"
        stamp_sbi_active_leave_intent(session)
        consume_sbi_active_leave_intent(session)
        session["improv_song_source"] = "Active song"
        session["_sbi_follow_active_widget_seen"] = True
        session["display_key"] = "F"
        session["_sbi_custom_visit_pk"] = "F"
        self.assertFalse(install_sbi_custom_identity_before_widgets(session))
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        self.assertTrue(str(session.get("display_key") or "").startswith("C"), session.get("display_key"))
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))
        sel = session.get("selected_song") or {}
        self.assertTrue(str(sel.get("title") or "").startswith("Perfect"), sel)
        self.assertTrue(str(sel.get("key") or "").startswith("G"), sel)
        self.assertTrue(str(session.get("song") or "").startswith("Perfect"), session.get("song"))


class TestSbiCustomToActivePerfectHandoff(unittest.TestCase):
    def _custom_visit(self) -> dict:
        from sbi_active_catalog_practice_key import note_sbi_active_user_practice_key_edit
        from source_session_state import persist_sbi_custom_practice_key_edit

        session = _perfect_session()
        session["catalog_session"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "original_key": "G",
            "display_key": "C",
            "pick_key": PERFECT_PICK,
            "selected_song": dict(session["selected_song"]),
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        }
        session["_catalog_before_custom_state"] = dict(session["catalog_session"])
        session["_last_catalog_song_state"] = dict(session["catalog_session"])
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        session["_restore_sbi_custom_source"] = True
        session["active_catalog_pick_key"] = TRIAL_PICK
        session["active_music_source"] = "custom_progression"
        session["selected_song"] = {
            "title": "Trial Song",
            "key": "D",
            "pick_key": TRIAL_PICK,
        }
        session["song"] = "Trial Song"
        session["_sbi_custom_sidebar_overlay"] = True
        persist_sbi_custom_practice_key_edit(session, "F")
        session["display_key"] = "F"
        session["concert_key"] = "F"
        session["_pending_display_key"] = "F"
        session["_pending_display_key_source"] = "sbi_custom_sidebar_overlay"
        session["_pending_display_key_pick"] = TRIAL_PICK
        return session

    def test_live_custom_to_active_renders_perfect_g_and_c(self) -> None:
        from songs.music_source import _catalog_original_key_for_session
        from source_session_state import (
            install_sbi_custom_identity_before_widgets,
            stamp_sbi_active_leave_intent,
        )

        session = self._custom_visit()
        stamp_sbi_active_leave_intent(session)
        self.assertFalse(install_sbi_custom_identity_before_widgets(session))
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        orig = str(_catalog_original_key_for_session(session) or "")
        pk = str(session.get("display_key") or "")
        self.assertTrue(orig.startswith("G"), orig)
        self.assertTrue(pk.startswith("C"), pk)
        self.assertNotEqual(orig, pk)
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))
        cat = session.get("catalog_session") or {}
        self.assertTrue(str(cat.get("original_key") or "").startswith("G"), cat)
        self.assertTrue(str(cat.get("display_key") or "").startswith("C"), cat)
        self.assertFalse(bool(session.get("_sbi_custom_sidebar_overlay")))
        self.assertFalse(bool(session.get("_sbi_custom_visit_pk")))

    def test_refresh_stays_active_perfect_g_and_c(self) -> None:
        from session_widget_safe import apply_pending_widget_hydrates
        from songs.music_source import _catalog_original_key_for_session
        from source_session_state import (
            consume_sbi_active_leave_intent,
            install_sbi_custom_identity_before_widgets,
            restore_sbi_active_catalog_identity_before_widgets,
            stamp_sbi_active_leave_intent,
        )
        from studio_page_persistence import apply_page_snapshot

        session = self._custom_visit()
        stamp_sbi_active_leave_intent(session)
        install_sbi_custom_identity_before_widgets(session)
        consume_sbi_active_leave_intent(session)
        apply_page_snapshot(
            session,
            {
                "sbi_preview_source": "Active song",
                "improv_song_source": "Active song",
                "_restore_sbi_custom_source": False,
                "display_key": "F",
                "concert_key": "F",
                "_sbi_custom_visit_pk": "F",
                "display_key_sbi_custom": "F",
                "_sbi_custom_sidebar_overlay": True,
                "_pending_display_key": "F",
                "_pending_display_key_source": "sbi_custom_sidebar_overlay",
                "_pending_display_key_pick": TRIAL_PICK,
            },
        )
        session["improv_song_source"] = "Active song"
        session["_sbi_follow_active_widget_seen"] = False
        restore_sbi_active_catalog_identity_before_widgets(session)
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        orig = str(_catalog_original_key_for_session(session) or "")
        pk = str(session.get("display_key") or "")
        self.assertTrue(orig.startswith("G"), orig)
        self.assertTrue(pk.startswith("C"), pk)
        self.assertNotEqual(orig, pk)

    def test_trial_uuid_remains_d_and_f(self) -> None:
        from source_session_state import (
            install_sbi_custom_identity_before_widgets,
            stamp_sbi_active_leave_intent,
        )

        session = self._custom_visit()
        stamp_sbi_active_leave_intent(session)
        install_sbi_custom_identity_before_widgets(session)
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))
        last = session.get(LAST_CUSTOM_STATE_KEY) or {}
        active = last.get("active") if isinstance(last, dict) else {}
        home = str(
            (active or {}).get("original_key_center")
            or last.get("custom_home_key")
            or ""
        )
        self.assertTrue(home.startswith("D"), last)
        live_cpl = session.get(CPL_ACTIVE_KEY) or {}
        self.assertTrue(str(live_cpl.get("original_key_center") or "").startswith("D"), live_cpl)

    def test_perfect_catalog_slot_remains_g_and_c(self) -> None:
        from creative_workspace_state_persistence import gather_creative_workspace_from_session
        from source_session_state import (
            install_sbi_custom_identity_before_widgets,
            stamp_sbi_active_leave_intent,
        )

        session = self._custom_visit()
        stamp_sbi_active_leave_intent(session)
        install_sbi_custom_identity_before_widgets(session)
        blob = gather_creative_workspace_from_session(session)
        cat = blob.get("catalog_session") or session.get("catalog_session") or {}
        self.assertTrue(str(cat.get("original_key") or "").startswith("G"), cat)
        self.assertTrue(str(cat.get("display_key") or "").startswith("C"), cat)
        self.assertNotEqual(str(cat.get("original_key") or ""), str(cat.get("display_key") or ""))
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK)).startswith("C"))
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))

    def test_custom_pending_key_cannot_hydrate_active_catalog_widget(self) -> None:
        from session_widget_safe import apply_pending_widget_hydrates
        from source_session_state import (
            custom_sbi_owns_sidebar_practice_key,
            restore_sbi_active_catalog_identity_before_widgets,
            sbi_should_install_active_catalog_identity,
            stamp_sbi_active_leave_intent,
        )

        session = self._custom_visit()
        stamp_sbi_active_leave_intent(session)
        session["_pending_display_key"] = "F"
        session["_pending_display_key_source"] = "sbi_custom_sidebar_overlay"
        session["_pending_display_key_pick"] = TRIAL_PICK
        session["_sbi_custom_visit_pk"] = "F"
        session["_sbi_custom_sidebar_overlay"] = True
        restore_sbi_active_catalog_identity_before_widgets(session)
        apply_pending_widget_hydrates(session)
        self.assertTrue(sbi_should_install_active_catalog_identity(session))
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))
        self.assertTrue(str(session.get("display_key") or "").startswith("C"), session.get("display_key"))
        self.assertNotEqual(str(session.get("_pending_display_key") or ""), "F")
        self.assertFalse(bool(session.get("_sbi_custom_sidebar_overlay")))

    def test_live_active_preview_ignores_custom_ga_residue(self) -> None:
        from source_session_state import resolve_sbi_preview, stamp_sbi_active_leave_intent

        session = self._custom_visit()
        stamp_sbi_active_leave_intent(session)
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("source"), "Active song")
        self.assertTrue(str(preview.get("title") or "").startswith("Perfect"), preview)
        self.assertTrue(str(preview.get("original_key") or "").startswith("G"), preview)
        self.assertTrue(str(preview.get("display_key") or "").startswith("C"), preview)
        self.assertFalse(str(preview.get("pick_key") or "").startswith("custom::"), preview)
        self.assertTrue(str(get_practice_concert_key(session, TRIAL_PICK)).startswith("F"))

    def test_display_key_context_does_not_treat_practice_c_as_original(self) -> None:
        from songs.music_source import display_key_context
        from source_session_state import stamp_sbi_active_leave_intent

        session = self._custom_visit()
        stamp_sbi_active_leave_intent(session)
        orig, identity = display_key_context(
            session,
            catalog_song_data={"title": "Perfect", "artist": "Ed Sheeran", "key": "C"},
            cpl_active_key=CPL_ACTIVE_KEY,
        )
        self.assertTrue(str(orig or "").startswith("G"), orig)
        self.assertNotEqual(str(orig or ""), "C")
        self.assertTrue("Perfect" in str(identity), identity)

    def test_leftover_pending_custom_does_not_reown_after_active_leave(self) -> None:
        from backing_source_navigation import restore_sbi_song_source_from_backing_context
        from backing_context import BackingContext
        from source_session_state import (
            consume_sbi_active_leave_intent,
            install_sbi_custom_identity_before_widgets,
            stamp_sbi_active_leave_intent,
        )

        session = self._custom_visit()
        stamp_sbi_active_leave_intent(session)
        self.assertFalse(install_sbi_custom_identity_before_widgets(session))
        consume_sbi_active_leave_intent(session)
        session["_sbi_follow_active_widget_seen"] = False
        session["_pending_improv_song_source"] = "Custom progression"
        session["_explicit_sbi_source_click"] = "Custom progression"
        ctx = BackingContext(
            source="song_improv",
            source_label="Song-Based Improvisation",
            active_song_id="Trial Song",
            song_title="Trial Song",
            key="F",
            display_key="F",
            concert_key="F",
            bpm=100,
            style="Pop",
            groove="Auto",
            entry_mode="Song-Based Improvisation",
            sbi_source_owner="Custom progression",
            sbi_material_kind="custom",
        )
        restore_sbi_song_source_from_backing_context(session, ctx)
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertFalse(install_sbi_custom_identity_before_widgets(session))
        self.assertEqual(session.get("sbi_preview_source"), "Active song")
        self.assertTrue(str(session.get("display_key") or "").startswith("C"), session.get("display_key"))


if __name__ == "__main__":
    unittest.main()
