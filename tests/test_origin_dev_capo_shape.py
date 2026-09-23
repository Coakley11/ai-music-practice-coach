"""Phase C Capo/Shape contract: sounding from owner Practice Key; Shape never competes."""

from __future__ import annotations

import unittest

from custom_progression_lab import CPL_ACTIVE_KEY
from song_catalog.catalog import format_pick_key
from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, set_practice_concert_key

PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL_PICK = "custom::trial-d"
BEAT_IT_PICK = format_pick_key("Pop", "Beat It — Michael Jackson")


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


def _base(**extra: object) -> dict:
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
        "active_catalog_pick_key": PERFECT_PICK,
        "display_key": "C",
        "concert_key": "C",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "improv_intelligence_tab": "Song-Based Improvisation",
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "C", TRIAL_PICK: "F"},
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": _trial(),
        },
        CPL_ACTIVE_KEY: _trial(),
        "cpl_saved_progressions": {"Trial Song": _trial()},
        "guitar_capo_enabled": True,
        "guitar_capo_shape_key": "C",
        "_capo_shape_seed_source_id": PERFECT_PICK,
    }
    session.update(extra)
    return session


class TestPhaseCCapoShapeContract(unittest.TestCase):
    def test_capo_fret_math_open_trial_f_and_ebm(self) -> None:
        from guitar_capo import capo_fret_for_shape

        self.assertEqual(capo_fret_for_shape("C", "C"), 0)
        self.assertEqual(capo_fret_for_shape("F", "C"), 5)
        self.assertEqual(capo_fret_for_shape("Eb minor", "C"), 3)
        self.assertEqual(capo_fret_for_shape("Ebm", "C"), 3)
        self.assertEqual(capo_fret_for_shape("F minor", "C"), 5)

    def test_custom_source_id_wins_before_jam_fallthrough(self) -> None:
        from guitar_capo import live_capo_shape_source_id

        # SBI Custom on Song-Based Improvisation must resolve Custom UUID before
        # any Jam fallthrough (Custom block is ordered above Jam in source_id).
        session = _base(
            improv_entry_mode="Song-Based Improvisation",
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Entry & Jam",
        )
        live = live_capo_shape_source_id(session)
        self.assertTrue(str(live).startswith("custom::"), live)
        self.assertFalse(str(live).startswith("generated::jam"), live)

    def test_sbi_custom_owns_sounding_even_on_phrase_motif_tab(self) -> None:
        """Browser C3: Trial card shows F but Capo Sounding leaked Perfect C.

        Custom owns sidebar PK on Phrase & Motif; Capo source id must follow.
        """
        from guitar_capo import live_capo_shape_source_id, owner_guitar_concert_key

        session = _base(
            improv_entry_mode="Song-Based Improvisation",
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Phrase & Motif",
            display_key="F",
            concert_key="F",
        )
        live = live_capo_shape_source_id(session)
        self.assertEqual(live, TRIAL_PICK)
        self.assertEqual(owner_guitar_concert_key(session, fallback="C"), "F")

    def test_capo_seal_keeps_custom_preview_before_save(self) -> None:
        from guitar_capo import _seal_temporary_sbi_custom_before_capo_save
        from source_session_state import RESTORE_SBI_CUSTOM_SOURCE_KEY

        session = _base(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Song-Based Improvisation",
            creative_workspace_state={
                "sbi_preview_source": "Active song",
                RESTORE_SBI_CUSTOM_SOURCE_KEY: False,
                "improv_song_source": "Active song",
            },
        )
        _seal_temporary_sbi_custom_before_capo_save(session)
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertTrue(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        blob = session.get("creative_workspace_state") or {}
        self.assertEqual(blob.get("sbi_preview_source"), "Custom progression")
        self.assertTrue(blob.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

    def test_capo_save_seals_temporary_custom_preview(self) -> None:
        from guitar_capo import _seal_temporary_sbi_custom_before_capo_save
        from source_session_state import RESTORE_SBI_CUSTOM_SOURCE_KEY

        session = _base(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Song-Based Improvisation",
            display_key="F",
            concert_key="F",
            # Remount residue that Capo used to persist over Trial.
            _last_improv_song_source="Active song",
        )
        session["creative_workspace_state"] = {
            "sbi_preview_source": "Active song",
            RESTORE_SBI_CUSTOM_SOURCE_KEY: False,
        }
        _seal_temporary_sbi_custom_before_capo_save(session)
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertTrue(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        self.assertEqual(
            session["creative_workspace_state"].get("sbi_preview_source"),
            "Custom progression",
        )

    def test_owner_sounding_from_pick_scoped_practice_key(self) -> None:
        from guitar_capo import owner_guitar_concert_key, sync_capo_from_practice_display_key

        session = _base(display_key="G", concert_key="G")
        sounding = owner_guitar_concert_key(session, fallback="G")
        self.assertEqual(sounding, "C")
        synced = sync_capo_from_practice_display_key(session, sounding)
        self.assertEqual(synced, "C")
        self.assertEqual(session.get("guitar_capo_sounding_key"), "C")
        self.assertEqual(session.get("guitar_capo_shape_key"), "C")

    def test_temporary_custom_f_keeps_shape_c_capo_5(self) -> None:
        from guitar_capo import (
            apply_source_change_shape_home,
            capo_fret_for_shape,
            live_capo_shape_source_id,
            owner_guitar_concert_key,
            shape_tonic_only,
            sync_capo_from_practice_display_key,
        )

        session = _base(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            display_key="F",
            concert_key="F",
            guitar_capo_shape_key="C",
            _capo_shape_seed_source_id=PERFECT_PICK,
        )
        live = live_capo_shape_source_id(session)
        self.assertEqual(live, TRIAL_PICK)
        sounding = owner_guitar_concert_key(session, fallback="C")
        self.assertEqual(sounding, "F")
        apply_source_change_shape_home(session, sounding)
        synced = sync_capo_from_practice_display_key(session, sounding)
        self.assertEqual(synced, "F")
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")
        self.assertEqual(capo_fret_for_shape(synced, "C"), 5)
        self.assertTrue(session.get("guitar_capo_enabled"))

    def test_return_active_perfect_restores_sounding_c_open_capo(self) -> None:
        from guitar_capo import (
            apply_source_change_shape_home,
            capo_fret_for_shape,
            owner_guitar_concert_key,
            shape_tonic_only,
            sync_capo_from_practice_display_key,
        )

        session = _base(
            sbi_preview_source="Active song",
            display_key="C",
            concert_key="C",
            guitar_capo_shape_key="C",
            _capo_shape_seed_source_id=TRIAL_PICK,
        )
        sounding = owner_guitar_concert_key(session, fallback="C")
        apply_source_change_shape_home(session, sounding)
        synced = sync_capo_from_practice_display_key(session, sounding)
        self.assertEqual(synced, "C")
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")
        self.assertEqual(capo_fret_for_shape(synced, "C"), 0)

    def test_beat_it_ebm_retains_shape_c_capo_3_then_pk_recalc(self) -> None:
        from guitar_capo import (
            apply_source_change_shape_home,
            capo_fret_for_shape,
            owner_guitar_concert_key,
            shape_tonic_only,
            sync_capo_from_practice_display_key,
        )

        session = _base(
            song="Beat It",
            active_catalog_pick_key=BEAT_IT_PICK,
            selected_song={
                "title": "Beat It",
                "artist": "Michael Jackson",
                "genre": "Pop",
                "key": "Ebm",
                "pick_key": BEAT_IT_PICK,
            },
            display_key="Eb minor",
            concert_key="Eb minor",
            guitar_capo_shape_key="C",
            _capo_shape_seed_source_id=PERFECT_PICK,
        )
        set_practice_concert_key(
            session, "Eb minor", pick_key=BEAT_IT_PICK, commit_catalog_practice_key=True
        )
        sounding = owner_guitar_concert_key(session, fallback="C")
        apply_source_change_shape_home(session, sounding)
        synced = sync_capo_from_practice_display_key(session, sounding)
        self.assertTrue(str(synced).lower().startswith("eb"), synced)
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")
        self.assertEqual(capo_fret_for_shape(synced, "C"), 3)

        # Practice Key change: sounding follows new owner PK; Shape tonic stays C; capo recalcs.
        session["display_key"] = "F minor"
        session["concert_key"] = "F minor"
        session[PRACTICE_KEY_BY_SOURCE_KEY][BEAT_IT_PICK] = "F minor"
        sounding2 = owner_guitar_concert_key(session, fallback="C")
        synced2 = sync_capo_from_practice_display_key(session, sounding2)
        self.assertTrue(str(synced2).lower().startswith("f"), synced2)
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")
        self.assertEqual(capo_fret_for_shape(synced2, "C"), 5)

    def test_manual_off_on_initializes_from_sounding_not_old_c(self) -> None:
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            CAPO_SHAPE_KEY,
            apply_genuine_shape_mode_user_transition,
            capo_fret_for_shape,
            shape_tonic_only,
        )

        session = _base(
            guitar_capo_shape_key="C",
            display_key="Eb minor",
            concert_key="Eb minor",
            _capo_enabled_committed=True,
            active_song_state={
                "guitar_capo_enabled": True,
                "guitar_capo_shape_key": "C",
                "pick_key": BEAT_IT_PICK,
            },
        )
        session["_capo_shape_mode_on_change_this_run"] = True
        off = apply_genuine_shape_mode_user_transition(
            session, now_enabled=False, sounding="Eb minor", this_run_restore=False
        )
        self.assertTrue(off["genuine_manual_off"])
        session[CAPO_ENABLED_KEY] = False

        session["_capo_shape_mode_on_change_this_run"] = True
        on = apply_genuine_shape_mode_user_transition(
            session, now_enabled=True, sounding="Eb minor", this_run_restore=False
        )
        self.assertTrue(on["genuine_manual_on"])
        home = shape_tonic_only(str(session.get(CAPO_SHAPE_KEY) or ""))
        self.assertEqual(home, "Eb")
        self.assertEqual(capo_fret_for_shape("Eb minor", home), 0)

    def test_practice_key_never_overwrites_shape_while_on(self) -> None:
        from guitar_capo import shape_tonic_only, sync_capo_from_practice_display_key

        session = _base(guitar_capo_enabled=True, guitar_capo_shape_key="C")
        sync_capo_from_practice_display_key(session, "A")
        self.assertEqual(session.get("guitar_capo_sounding_key"), "A")
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "C")


class TestC4SbiCustomRefreshHydration(unittest.TestCase):
    """C4: refresh while SBI Custom Trial owns must keep F / Shape C / capo 5."""

    def test_capo_seal_reason_bypasses_restore_cooldown(self) -> None:
        from music_startup_save_suppression import (
            STARTUP_FINGERPRINT_MATCHES_KEY,
            STARTUP_SUPPRESSION_ARMED_KEY,
            should_suppress_music_workspace_save,
        )
        from music_workspace_cloud_save import _USER_FORCE_REASONS

        self.assertIn("capo_seal_temporary_custom", _USER_FORCE_REASONS)
        self.assertIn("capo_widget", _USER_FORCE_REASONS)
        armed = {
            STARTUP_SUPPRESSION_ARMED_KEY: True,
            STARTUP_FINGERPRINT_MATCHES_KEY: True,
        }
        blocked, why = should_suppress_music_workspace_save(dict(armed), "capo_widget")
        self.assertTrue(blocked, why)
        seal_blocked, why2 = should_suppress_music_workspace_save(
            dict(armed), "capo_seal_temporary_custom"
        )
        self.assertFalse(seal_blocked, why2)

    def test_capo_seal_clears_follow_active_and_survives_gather(self) -> None:
        from creative_workspace_state_persistence import gather_creative_workspace_from_session
        from guitar_capo import _seal_temporary_sbi_custom_before_capo_save
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
        )

        session = _base(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Entry & Jam",
            display_key="F",
            concert_key="F",
            guitar_capo_sounding_key="F",
            _capo_shape_seed_source_id=TRIAL_PICK,
        )
        session[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        _seal_temporary_sbi_custom_before_capo_save(session)
        self.assertFalse(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertTrue(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        # Remounted Active radio during Capo save must not wipe sealed Custom.
        session["improv_song_source"] = "Active song"
        session["sbi_preview_source"] = "Active song"
        session["_capo_custom_owner_sealed_id"] = TRIAL_PICK
        gathered = gather_creative_workspace_from_session(session)
        self.assertEqual(gathered.get("sbi_preview_source"), "Custom progression")
        self.assertEqual(gathered.get("improv_song_source"), "Custom progression")
        self.assertTrue(gathered.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        self.assertNotIn(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY, gathered)

    def test_refresh_rehydrates_trial_f_capo_5_not_perfect_c(self) -> None:
        from creative_workspace_state_persistence import (
            CREATIVE_WORKSPACE_RESTORED_KEY,
            project_creative_workspace_to_session,
        )
        from creative_tab_tool_persistence import project_creative_selectors_from_canonical
        from guitar_capo import (
            _seal_temporary_sbi_custom_before_capo_save,
            capo_fret_for_shape,
            live_capo_shape_source_id,
            owner_guitar_concert_key,
            sync_capo_from_practice_display_key,
        )
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            install_sbi_custom_identity_before_widgets,
            seed_sbi_custom_radio_before_render,
        )

        live = _base(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Entry & Jam",
            display_key="F",
            concert_key="F",
            guitar_capo_sounding_key="F",
            _capo_shape_seed_source_id=TRIAL_PICK,
        )
        live[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        _seal_temporary_sbi_custom_before_capo_save(live)
        cws = dict(live.get("creative_workspace_state") or {})

        # Refresh remount: Streamlit defaults Song Source to Active; Catalog GA still Perfect.
        fresh = _base(
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            display_key="C",
            concert_key="C",
            improv_song_source="Active song",
            sbi_preview_source="Active song",
            guitar_capo_sounding_key="C",
            _capo_shape_seed_source_id=PERFECT_PICK,
            creative_workspace_state=cws,
        )
        fresh[CREATIVE_WORKSPACE_RESTORED_KEY] = True
        fresh["_creative_selector_hydration_complete"] = True
        project_creative_workspace_to_session(fresh, overwrite=True)
        project_creative_selectors_from_canonical(fresh, overwrite=True)
        seeded = seed_sbi_custom_radio_before_render(fresh)
        self.assertEqual(seeded, "Custom progression")
        install_sbi_custom_identity_before_widgets(fresh)
        live_id = live_capo_shape_source_id(fresh)
        self.assertTrue(str(live_id).startswith("custom::"), live_id)
        sounding = owner_guitar_concert_key(fresh, fallback="C")
        self.assertEqual(sounding, "F")
        synced = sync_capo_from_practice_display_key(fresh, sounding)
        self.assertEqual(synced, "F")
        self.assertEqual(capo_fret_for_shape(synced, "C"), 5)
        self.assertTrue(fresh.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

    def test_catalog_refresh_still_restores_perfect_when_active_owns(self) -> None:
        from guitar_capo import (
            capo_fret_for_shape,
            live_capo_shape_source_id,
            owner_guitar_concert_key,
            sync_capo_from_practice_display_key,
        )
        from source_session_state import RESTORE_SBI_CUSTOM_SOURCE_KEY, seed_sbi_custom_radio_before_render

        session = _base(
            sbi_preview_source="Active song",
            improv_song_source="Active song",
            improv_intelligence_tab="Entry & Jam",
            display_key="C",
            concert_key="C",
            guitar_capo_sounding_key="C",
            creative_workspace_state={
                "sbi_preview_source": "Active song",
                "improv_song_source": "Active song",
                RESTORE_SBI_CUSTOM_SOURCE_KEY: False,
            },
        )
        seeded = seed_sbi_custom_radio_before_render(session)
        self.assertEqual(seeded, "Active song")
        live_id = live_capo_shape_source_id(session)
        self.assertEqual(live_id, PERFECT_PICK)
        sounding = owner_guitar_concert_key(session, fallback="G")
        self.assertEqual(sounding, "C")
        synced = sync_capo_from_practice_display_key(session, sounding)
        self.assertEqual(capo_fret_for_shape(synced, "C"), 0)

    def test_return_active_then_custom_restores_f_capo_5_again(self) -> None:
        from guitar_capo import (
            capo_fret_for_shape,
            live_capo_shape_source_id,
            owner_guitar_concert_key,
            sync_capo_from_practice_display_key,
        )
        from source_session_state import (
            EXPLICIT_SBI_SOURCE_CLICK_KEY,
            SBI_ACTIVE_LEAVE_INTENT_KEY,
            install_sbi_custom_identity_before_widgets,
            set_sbi_preview_source,
        )

        session = _base(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Entry & Jam",
            display_key="F",
            concert_key="F",
            guitar_capo_sounding_key="F",
            _capo_shape_seed_source_id=TRIAL_PICK,
        )
        # Leave to Catalog Active Perfect → C / open (genuine Active click).
        session.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
        session[SBI_ACTIVE_LEAVE_INTENT_KEY] = True
        session["_sbi_preview_write_via"] = "after_sbi_source_radio_active"
        set_sbi_preview_source(session, "Active song")
        session["improv_song_source"] = "Active song"
        install_sbi_custom_identity_before_widgets(session)
        sounding = owner_guitar_concert_key(session, fallback="G")
        synced = sync_capo_from_practice_display_key(session, sounding)
        self.assertEqual(synced, "C")
        self.assertEqual(capo_fret_for_shape(synced, "C"), 0)
        self.assertEqual(live_capo_shape_source_id(session), PERFECT_PICK)

        # Return to Trial Custom → F / capo 5 (genuine Custom click).
        session[EXPLICIT_SBI_SOURCE_CLICK_KEY] = "Custom progression"
        session["_sbi_preview_write_via"] = "after_sbi_source_radio_custom"
        set_sbi_preview_source(session, "Custom progression")
        self.assertTrue(install_sbi_custom_identity_before_widgets(session))
        sounding = owner_guitar_concert_key(session, fallback="C")
        synced = sync_capo_from_practice_display_key(session, sounding)
        self.assertEqual(synced, "F")
        self.assertEqual(capo_fret_for_shape(synced, "C"), 5)
        self.assertTrue(str(live_capo_shape_source_id(session)).startswith("custom::"))


if __name__ == "__main__":
    unittest.main()
