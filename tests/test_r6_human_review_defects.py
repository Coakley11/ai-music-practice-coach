"""R6 — human-review stabilization defects (Custom / Mission / Composition authority).

Pure session-state-dict tests calling real production functions, matching the
R1-R5 convention. Each class pins the first incorrect transition found by live
AppTest tracing on origin/dev.

Trial Song throughout: Custom song, Original D major, Verse D · A · Bm · G,
style Bossa.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from backing_context import BackingContext, get_backing_context, set_backing_context
from custom_progression_lab import CPL_ACTIVE_KEY, default_active_progression

ROOT = Path(__file__).resolve().parents[1]


def _trial_song_session() -> dict:
    from songs.music_source import commit_custom_active_song

    session: dict = {}
    active = default_active_progression()
    active["id"] = "trial-1"
    active["name"] = "Trial Song"
    active["original_key_center"] = "D"
    active["user_locked_home_key"] = True
    active["progression_style"] = "Bossa"
    active["groove_style"] = "Auto"
    active["original_sections"]["Verse"] = [
        {"chord": c, "bars": 1} for c in ("D", "A", "Bm", "G")
    ]
    session[CPL_ACTIVE_KEY] = active
    commit_custom_active_song(
        SimpleNamespace(session_state=session), active, invalidate_backing=lambda *a, **k: None
    )
    return session


def _custom_backing_ctx(pick: str, key: str = "D") -> BackingContext:
    return BackingContext(
        source="custom_progression",
        source_label="Custom progression",
        active_song_id=pick,
        song_title="Trial Song",
        key="D",
        display_key=key,
        concert_key=key,
        bpm=100,
        style="Bossa",
        groove="Auto",
        progression=["D", "A", "Bm", "G"],
        bound_pick_key=pick,
    )


class TestOrdinaryCustomBackingIsNotSbiCustom(unittest.TestCase):
    """#2/#3: ordinary Custom → Backing shares the sbi_custom musical owner but
    must keep the Custom-page return family. Previously every stamp used
    return_destination=sbi_custom, so nav actions emitted ``return_creative``
    (label "Return to Custom Page", destination Creative/SBI Custom)."""

    def _stamp_on_backing_page(self, session: dict, ctx: BackingContext) -> None:
        from backing_owner_envelope import (
            OWNER_SBI_CUSTOM,
            RETURN_CUSTOM_PAGE,
            stamp_envelope_from_backing_context,
        )

        session["studio_page"] = "backing"
        set_backing_context(session, ctx, trace_caller="test")
        stamp_envelope_from_backing_context(
            session, ctx, source_override=OWNER_SBI_CUSTOM, return_destination=RETURN_CUSTOM_PAGE
        )

    def test_restamp_off_custom_page_keeps_custom_return_family(self) -> None:
        from backing_owner_envelope import envelope_return_destination, live_backing_owner

        session = _trial_song_session()
        pick = str(session.get("active_catalog_pick_key") or "custom::trial-1")
        self._stamp_on_backing_page(session, _custom_backing_ctx(pick, key="E"))
        self.assertEqual(live_backing_owner(session), "sbi_custom")
        self.assertEqual(envelope_return_destination(session), "custom")
        self.assertEqual(session.get("_backing_explicit_handoff_source"), "custom_progression")

    def test_default_return_for_custom_progression_ctx_is_custom_page(self) -> None:
        from backing_owner_envelope import (
            OWNER_SBI_CUSTOM,
            ensure_envelope_matches_backing_context,
            envelope_return_destination,
        )

        session = _trial_song_session()
        session["studio_page"] = "backing"
        pick = str(session.get("active_catalog_pick_key") or "custom::trial-1")
        ctx = _custom_backing_ctx(pick)
        set_backing_context(session, ctx, trace_caller="test")
        ensure_envelope_matches_backing_context(session, ctx, source_override=OWNER_SBI_CUSTOM)
        self.assertEqual(envelope_return_destination(session), "custom")

    def test_nav_actions_return_to_custom_page_not_creative(self) -> None:
        from backing_nav_actions import build_backing_nav_actions

        session = _trial_song_session()
        pick = str(session.get("active_catalog_pick_key") or "custom::trial-1")
        self._stamp_on_backing_page(session, _custom_backing_ctx(pick))
        actions, _removed = build_backing_nav_actions(session)
        ids = [a.action_id for a in actions]
        self.assertIn("return_custom_songs", ids)
        self.assertNotIn("return_creative", ids)
        self.assertNotIn("return_catalog_backing", ids)
        custom = [a for a in actions if a.action_id == "return_custom_songs"][0]
        self.assertEqual(custom.destination, "custom")

    def test_restore_does_not_rebuild_ordinary_custom_as_sbi(self) -> None:
        from backing_context import _persisted_backing_is_custom_sbi

        session = _trial_song_session()
        pick = str(session.get("active_catalog_pick_key") or "custom::trial-1")
        set_backing_context(session, _custom_backing_ctx(pick, key="E"), trace_caller="test")
        session["_backing_explicit_handoff_source"] = "custom_progression"
        # Leftover SBI preview from an earlier Creative visit.
        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        session["studio_page"] = "backing"
        self.assertFalse(_persisted_backing_is_custom_sbi(session))

    def test_genuine_sbi_custom_still_restores_as_sbi(self) -> None:
        from backing_context import _persisted_backing_is_custom_sbi

        session: dict = {"studio_page": "backing"}
        session["backing_context"] = {
            "source": "song_improv",
            "sbi_material_kind": "custom",
            "bound_pick_key": "custom::trial-1",
        }
        self.assertTrue(_persisted_backing_is_custom_sbi(session))


class TestMissionBackingPracticeKeyRetargetsChord(unittest.TestCase):
    """#4: Mission Backing E → F# must move C#m → D#m everywhere the card and
    later rebuilds read it: BackingContext (previously double-transposed to Fm),
    the sealed Mission chord snapshot, and the Mission section map (previously
    stale, so the card projected index 2 back to C#m)."""

    def _session(self) -> dict:
        from creative_chord_selection_authority import MISSION_CHORD_SNAPSHOT_KEY
        from creative_mission_config_persistence import IMPROV_MISSION_SECTION_MAP_SESSION_KEY

        session = _trial_song_session()
        session["studio_page"] = "backing"
        session["selected_song"] = {"title": "Trial Song", "key": "D"}
        session["display_key"] = "E"
        session["concert_key"] = "E"
        session["improv_mission_concert_key"] = "E"
        session["ii_selected_chord"] = "C#m"
        session["ii_selected_section"] = "Verse"
        session["ii_selected_chord_index"] = 2
        session[IMPROV_MISSION_SECTION_MAP_SESSION_KEY] = [("Verse", ["E", "B", "C#m", "A"])]
        session["improv_mission_chord_options"] = ["E", "B", "C#m", "A"]
        session[MISSION_CHORD_SNAPSHOT_KEY] = {
            "mission_id": "",
            "session_id": "",
            "source_identity": "",
            "section": "Verse",
            "chord_index": 2,
            "concert_chord": "C#m",
            "concert_practice_key": "E",
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id="custom::trial-1",
                song_title="Trial Song",
                key="E",
                display_key="E",
                concert_key="E",
                bpm=100,
                style="Bossa",
                groove="Auto",
                section="Verse",
                progression=["C#m"],
                mission_id="Improvise using only chord tones",
            ),
            trace_caller="test",
        )
        session["_mission_pk_transpose_from"] = "E"
        return session

    def test_all_mission_chord_authorities_follow_f_sharp(self) -> None:
        from creative_chord_selection_authority import MISSION_CHORD_SNAPSHOT_KEY
        from creative_key_sync import apply_specialized_mission_practice_key
        from creative_mission_config_persistence import IMPROV_MISSION_SECTION_MAP_SESSION_KEY

        session = self._session()
        apply_specialized_mission_practice_key(session, "F#")

        ctx = get_backing_context(session)
        self.assertEqual(ctx.concert_key, "F#")
        self.assertEqual(list(ctx.progression), ["D#m"])
        self.assertEqual(session["ii_selected_chord"], "D#m")
        snap = session[MISSION_CHORD_SNAPSHOT_KEY]
        self.assertEqual(snap["concert_chord"], "D#m")
        self.assertEqual(snap["concert_practice_key"], "F#")
        sm = session[IMPROV_MISSION_SECTION_MAP_SESSION_KEY]
        self.assertEqual([list(chs) for _sec, chs in sm], [["F#", "C#", "D#m", "B"]])
        self.assertEqual(session["improv_mission_chord_options"], ["F#", "C#", "D#m", "B"])

    def test_second_same_key_callback_does_not_transpose_again(self) -> None:
        from creative_key_sync import apply_specialized_mission_practice_key

        session = self._session()
        apply_specialized_mission_practice_key(session, "F#")
        apply_specialized_mission_practice_key(session, "F#")
        self.assertEqual(list(get_backing_context(session).progression), ["D#m"])
        self.assertEqual(session["ii_selected_chord"], "D#m")

    def test_card_projection_reads_d_sharp_minor(self) -> None:
        from creative_key_sync import apply_specialized_mission_practice_key
        from creative_mission_config_persistence import IMPROV_MISSION_SECTION_MAP_SESSION_KEY
        from mission_projection_state import resolve_mission_projection_state

        session = self._session()
        apply_specialized_mission_practice_key(session, "F#")
        proj = resolve_mission_projection_state(
            session,
            section_map=session[IMPROV_MISSION_SECTION_MAP_SESSION_KEY],
            fallback_key="F#",
        )
        self.assertEqual(proj.concert_chord, "D#m")
        self.assertEqual(session["ii_selected_chord"], "D#m")


class TestMissionBackingInheritsCustomStyle(unittest.TestCase):
    """#5: the Catalog-shaped Custom row never exported the Custom style, so the
    Mission style resolver fell back to the groove token ("Auto")."""

    def test_custom_song_row_exports_chosen_style(self) -> None:
        from songs.music_source import custom_song_data_from_active

        session = _trial_song_session()
        row = custom_song_data_from_active(session[CPL_ACTIVE_KEY])
        self.assertEqual(row["extensions"].get("default_style"), "Bossa")

    def test_custom_row_without_style_does_not_invent_one(self) -> None:
        from songs.music_source import custom_song_data_from_active

        active = default_active_progression()
        active["progression_style"] = ""
        row = custom_song_data_from_active(active)
        self.assertNotIn("default_style", row["extensions"])

    def test_mission_jam_style_resolves_to_custom_bossa(self) -> None:
        from mission_song_backing_style import resolve_mission_jam_backing_style

        session = _trial_song_session()
        session["improv_style"] = "Rock"
        session["improv_groove"] = "Rock groove"
        res = resolve_mission_jam_backing_style(session)
        self.assertEqual(res.style, "Bossa")
        self.assertNotIn("rock", res.style.lower())


class TestHarmonyMapPracticeKeySurvivesPersist(unittest.TestCase):
    """#7: the persist hook replays the SBI Custom PK mirror onto the Custom
    UUID. A Custom-workspace / Harmony Map edit (F#) left that mirror at D, so
    the next save wrote D back over F#."""

    def _session(self) -> tuple[dict, str]:
        from source_session_state import SBI_CUSTOM_IDENTITY_PICK_KEY
        from songs.practice_key_state import mark_practice_key_user_override, set_practice_concert_key

        session = _trial_song_session()
        pick = "custom::trial-1"
        session[SBI_CUSTOM_IDENTITY_PICK_KEY] = pick
        session["_sbi_custom_visit_pk"] = "D"
        session["display_key_sbi_custom"] = "D"
        set_practice_concert_key(session, "F#", pick_key=pick, allow_restore_original=True)
        mark_practice_key_user_override(session, pick)
        return session, pick

    def test_mirror_follows_custom_sticky_and_replay_keeps_f_sharp(self) -> None:
        from source_session_state import (
            persist_sbi_custom_practice_key_edit,
            sync_sbi_custom_mirror_to_custom_sticky,
        )
        from songs.practice_key_state import get_practice_concert_key

        session, pick = self._session()
        sync_sbi_custom_mirror_to_custom_sticky(session, pick, "F#")
        self.assertEqual(session["_sbi_custom_visit_pk"], "F#")
        self.assertEqual(session["display_key_sbi_custom"], "F#")
        # What sync_creative_workspace_before_persist replays on save:
        persist_sbi_custom_practice_key_edit(session, session["display_key_sbi_custom"])
        self.assertEqual(get_practice_concert_key(session, pick), "F#")

    def test_mirror_for_a_different_custom_song_is_untouched(self) -> None:
        from source_session_state import sync_sbi_custom_mirror_to_custom_sticky

        session, _pick = self._session()
        sync_sbi_custom_mirror_to_custom_sticky(session, "custom::other-song", "A")
        self.assertEqual(session["_sbi_custom_visit_pk"], "D")
        self.assertEqual(session["display_key_sbi_custom"], "D")

    def test_canonical_original_is_not_mutated(self) -> None:
        from source_session_state import sync_sbi_custom_mirror_to_custom_sticky

        session, pick = self._session()
        sync_sbi_custom_mirror_to_custom_sticky(session, pick, "F#")
        active = session[CPL_ACTIVE_KEY]
        self.assertEqual(active["original_key_center"], "D")
        self.assertEqual(
            [e["chord"] for e in active["original_sections"]["Verse"]], ["D", "A", "Bm", "G"]
        )


class TestCompositionActivationKeepsOwnPracticeKey(unittest.TestCase):
    """#8: SBI "Active song" preview made the pre-widget restorer re-install the
    last Catalog pick while a Composition was Global Active, rewriting
    active_catalog_pick_key and seeding that song's Practice Key (C# → G/C)."""

    def test_no_catalog_install_while_composition_is_global_active(self) -> None:
        from source_session_state import sbi_should_install_active_catalog_identity

        session = {
            "active_music_source": "composition_song",
            "active_catalog_pick_key": "composition::doc-1",
            "sbi_preview_source": "Active song",
            "improv_song_source": "Active song",
        }
        self.assertFalse(sbi_should_install_active_catalog_identity(session))

    def test_no_catalog_install_while_custom_is_global_active(self) -> None:
        from source_session_state import sbi_should_install_active_catalog_identity

        session = _trial_song_session()
        session["sbi_preview_source"] = "Active song"
        session["improv_song_source"] = "Active song"
        self.assertFalse(sbi_should_install_active_catalog_identity(session))

    def test_catalog_global_active_still_installs(self) -> None:
        from source_session_state import sbi_should_install_active_catalog_identity

        session = {
            "active_music_source": "catalog_song",
            "active_catalog_pick_key": "Pop\x1fSay — John Mayer",
            "sbi_preview_source": "Active song",
            "improv_song_source": "Active song",
        }
        self.assertTrue(sbi_should_install_active_catalog_identity(session))


class TestUserFacingCopyAndControls(unittest.TestCase):
    """#9/#10/#11: presentation only."""

    def test_mission_diagnostic_copy_removed(self) -> None:
        text = (ROOT / "improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("Mission context is still syncing", text)
        self.assertNotIn("stale jam data removed", text)

    def test_backing_source_buttons_use_headphones_and_brand_colors(self) -> None:
        ui = (ROOT / "backing_context_ui.py").read_text(encoding="utf-8")
        for key in ("backing_context_reset_btn", "backing_context_reset_custom_btn"):
            block = ui.split(f'key="{key}"', 1)[1][:120]
            self.assertIn('icon=":material/headphones:"', block)
        css = (ROOT / "app_ui.py").read_text(encoding="utf-8")
        self.assertIn(".st-key-backing_context_reset_btn button", css)
        self.assertIn(".st-key-backing_context_reset_custom_btn button", css)
        catalog_rule = css.split(".st-key-backing_context_reset_btn button *", 1)[1][:80]
        custom_rule = css.split(".st-key-backing_context_reset_custom_btn button *", 1)[1][:80]
        self.assertIn("#6d28d9", catalog_rule)
        self.assertIn("#047857", custom_rule)


class TestStyleJamKeyIsNotPromotedIntoCustomSticky(unittest.TestCase):
    """Residual A: on the Creative Entry & Jam tab the Style Jam owns the
    left-panel key and seeds its key (C) into display_key. The display-key
    change hook then wrote that C into Trial Song's Custom sticky, and Backing
    and reboot consumed it."""

    def _session(self) -> dict:
        from custom_progression_lab import CPL_LAST_DISPLAY_KEY

        session = _trial_song_session()
        session[CPL_LAST_DISPLAY_KEY] = "D"
        return session

    def test_jam_owned_display_key_change_leaves_custom_sticky(self) -> None:
        from unittest import mock

        from custom_progression_lab import on_global_display_key_change
        from songs.practice_key_state import get_practice_concert_key

        session = self._session()
        pick = str(session.get("active_catalog_pick_key"))
        with mock.patch("creative_key_sync.jam_owns_left_panel_key", return_value=True):
            on_global_display_key_change(session, "C")
        self.assertEqual(get_practice_concert_key(session, pick), "D")

    def test_custom_owned_display_key_change_still_updates_sticky(self) -> None:
        from unittest import mock

        from custom_progression_lab import on_global_display_key_change
        from songs.practice_key_state import get_practice_concert_key

        session = self._session()
        pick = str(session.get("active_catalog_pick_key"))
        session["display_key_change_source"] = "sidebar_on_change"
        with mock.patch("creative_key_sync.jam_owns_left_panel_key", return_value=False):
            on_global_display_key_change(session, "E")
        self.assertEqual(get_practice_concert_key(session, pick), "E")


class TestCustomWidgetExportUsesCanonicalDraft(unittest.TestCase):
    """Residual B: with the Custom page unmounted, the widget snapshot fell back
    to the stale legacy alias (Pop) and restore replayed it over Bossa."""

    def test_unmounted_style_and_bpm_export_from_canonical_draft(self) -> None:
        from custom_progression_lab import export_cpl_widget_state

        session = _trial_song_session()
        session[CPL_ACTIVE_KEY]["bpm"] = 132
        session["cpl_progression_style"] = "Pop"
        session["cpl_bpm"] = 100
        session.pop("cpl_style_early", None)
        session.pop("cpl_bpm_builder", None)
        out = export_cpl_widget_state(session)
        self.assertEqual(out.get("cpl_style_early"), "Bossa")
        self.assertEqual(out.get("cpl_bpm_builder"), 132)

    def test_mounted_widget_value_still_wins(self) -> None:
        from custom_progression_lab import export_cpl_widget_state

        session = _trial_song_session()
        session["cpl_style_early"] = "Jazz"
        self.assertEqual(export_cpl_widget_state(session).get("cpl_style_early"), "Jazz")


class TestInactiveCompositionEditKeepsCustomPracticeKey(unittest.TestCase):
    """Residual C: on the Composer page the sidebar primer force-wrote the
    edited (inactive) Composition's key into the global Practice Key, which
    the display-key hook then wrote into Trial Song's sticky."""

    def _composition_ident(self):
        from sidebar_key_identity import SidebarKeyIdentity

        return SidebarKeyIdentity(
            owner="composition_song",
            concert_tonic="C#",
            concert_mode="major",
            practice_tonic="C#",
            practice_mode="major",
            written_tonic="",
            written_mode="",
            selector_token="C#",
            label="C# major",
        )

    def test_inactive_composition_does_not_prime_global_key(self) -> None:
        from unittest import mock

        from sidebar_key_identity import prime_sidebar_practice_key_from_identity

        session = _trial_song_session()
        session["studio_page"] = "composer"
        session["display_key"] = "D"
        session["concert_key"] = "D"
        with mock.patch(
            "sidebar_key_identity.resolve_sidebar_key_identity", return_value=self._composition_ident()
        ):
            prime_sidebar_practice_key_from_identity(session)
        self.assertEqual(session["display_key"], "D")
        self.assertEqual(session["concert_key"], "D")
        self.assertNotEqual(session.get("_pending_display_key"), "C#")

    def test_active_composition_still_primes_its_key(self) -> None:
        from unittest import mock

        from sidebar_key_identity import prime_sidebar_practice_key_from_identity

        session = {
            "studio_page": "practice",
            "active_music_source": "composition_song",
            "active_catalog_pick_key": "composition::doc-1",
            "display_key": "C",
            "concert_key": "C",
        }
        with mock.patch(
            "sidebar_key_identity.resolve_sidebar_key_identity", return_value=self._composition_ident()
        ):
            prime_sidebar_practice_key_from_identity(session)
        self.assertEqual(session["concert_key"], "C#")


class TestCompositionActivationAfterRebootIsNotReclaimed(unittest.TestCase):
    """Pre-existing on origin/dev, exposed once residual C stopped polluting
    Trial Song: after a reboot the startup restore re-applied the disk custom::
    pick and the hydrated source on every run, reclaiming a genuine
    Composition activation."""

    def test_saved_custom_pick_does_not_reclaim_explicit_composition(self) -> None:
        from songs.music_source import SOURCE_COMPOSITION, commit_explicit_music_source_choice
        from songs.state import apply_saved_custom_pick_key_context

        session = _trial_song_session()
        trial_pick = str(session["active_catalog_pick_key"])
        session["active_catalog_pick_key"] = "composition::doc-1"
        commit_explicit_music_source_choice(session, SOURCE_COMPOSITION)
        applied = apply_saved_custom_pick_key_context(
            SimpleNamespace(session_state=session),
            trial_pick,
            {},
            song_picker_catalog={},
        )
        self.assertFalse(applied)
        self.assertEqual(session["active_catalog_pick_key"], "composition::doc-1")

    def test_hydrated_source_does_not_overwrite_post_restore_composition(self) -> None:
        from music_startup_canonical_align import align_authoritative_canonical_from_hydrated

        session = {
            "active_catalog_pick_key": "composition::doc-1",
            "active_music_source": "composition_song",
            "active_song_state": {"pick_key": "composition::doc-1", "music_source": "composition_song"},
        }
        payload = {
            "core": {"pick_key": "custom::trial-1"},
            "active_song_state": {"pick_key": "custom::trial-1", "music_source": "custom_progression"},
            "music_workspace_state": {"active_song": {"music_source": "custom_progression"}},
        }
        align_authoritative_canonical_from_hydrated(session, payload)
        self.assertEqual(session["active_music_source"], "composition_song")
        self.assertEqual(session["active_song_state"]["music_source"], "composition_song")

    def test_hydrated_source_still_aligns_same_song(self) -> None:
        from music_startup_canonical_align import align_authoritative_canonical_from_hydrated

        session = {
            "active_catalog_pick_key": "custom::trial-1",
            "active_music_source": "catalog_song",
            "active_song_state": {"pick_key": "custom::trial-1", "music_source": "catalog_song"},
        }
        payload = {
            "active_song_state": {"pick_key": "custom::trial-1", "music_source": "custom_progression"},
            "music_workspace_state": {"active_song": {"music_source": "custom_progression"}},
        }
        align_authoritative_canonical_from_hydrated(session, payload)
        self.assertEqual(session["active_music_source"], "custom_progression")


if __name__ == "__main__":
    unittest.main()
