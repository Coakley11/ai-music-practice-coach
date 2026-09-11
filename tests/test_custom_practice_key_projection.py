"""Custom page Original Key ↔ Practice Key projection contract."""

from __future__ import annotations

import unittest

from custom_progression_lab import (
    apply_cpl_session_progression,
    build_style_preset_entries,
    cpl_apply_pending_chord_to_section,
    cpl_draft_written_key,
    cpl_workspace_practice_key,
    display_sections_for_key,
    practice_entries_to_original_key,
    simple_chords_for_key,
    start_new_progression,
    sync_custom_workspace_practice_key,
    sync_cpl_draft_widgets_to_active,
)
from songs.music_source import custom_pick_key_for
from songs.practice_key_state import get_practice_concert_key


def _chord_symbols(entries: list[dict]) -> list[str]:
    return [str(e.get("chord") or "").strip() for e in entries]


class TestCustomPracticeKeyProjection(unittest.TestCase):
    def test_new_song_resets_practice_key_to_original(self) -> None:
        session = {
            "display_key": "E",
            "concert_key": "E",
            "practice_key_by_source": {"custom::old": "E"},
        }
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        active = session["cpl_active_progression"]
        self.assertEqual(cpl_draft_written_key(active), "C")
        self.assertEqual(session.get("display_key"), "C")
        self.assertEqual(cpl_workspace_practice_key(session, active), "C")

    def test_choosing_original_key_sets_practice_key(self) -> None:
        session: dict = {}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        session["cpl_original_key"] = "D"
        active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
        session["cpl_active_progression"] = active
        self.assertEqual(cpl_draft_written_key(active), "D")
        self.assertEqual(session.get("display_key"), "D")
        pick = custom_pick_key_for(active)
        self.assertEqual(get_practice_concert_key(session, pick), "D")

    def test_builder_and_presets_follow_practice_key(self) -> None:
        self.assertEqual(simple_chords_for_key("D")[:4], ["D", "Em", "F#m", "G"])
        self.assertEqual(simple_chords_for_key("E")[:4], ["E", "F#m", "G#m", "A"])
        d_preset = _chord_symbols(build_style_preset_entries("Pop", "I–V–vi–IV", "D"))
        e_preset = _chord_symbols(build_style_preset_entries("Pop", "I–V–vi–IV", "E"))
        eb_preset = _chord_symbols(build_style_preset_entries("Pop", "I–V–vi–IV", "Eb"))
        self.assertEqual(d_preset, ["D", "A", "Bm", "G"])
        self.assertEqual(e_preset, ["E", "B", "C#m", "A"])
        self.assertEqual(eb_preset, ["Eb", "Bb", "Cm", "Ab"])

    def test_sidebar_practice_key_projects_without_rewriting_original(self) -> None:
        session: dict = {}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        session["cpl_original_key"] = "D"
        active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
        # Store I–V–vi–IV in Original D via Practice=D entries.
        practice_entries = build_style_preset_entries("Pop", "I–V–vi–IV", "D")
        active["original_sections"]["Verse"] = practice_entries_to_original_key(
            practice_entries, "D", "D"
        )
        session["cpl_active_progression"] = active

        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        projected = display_sections_for_key(active, "E")["Verse"]
        self.assertEqual(_chord_symbols(projected), ["E", "B", "C#m", "A"])
        self.assertEqual(cpl_draft_written_key(active), "D")
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
        )

        sync_custom_workspace_practice_key(session, practice_key="Eb", active=active)
        projected_eb = display_sections_for_key(active, "Eb")["Verse"]
        self.assertEqual(_chord_symbols(projected_eb), ["Eb", "Bb", "Cm", "Ab"])

        sync_custom_workspace_practice_key(session, practice_key="D", active=active)
        projected_d = display_sections_for_key(active, "D")["Verse"]
        self.assertEqual(_chord_symbols(projected_d), ["D", "A", "Bm", "G"])

    def test_append_practice_chord_stores_original(self) -> None:
        active = start_new_progression()
        active["original_key_center"] = "D"
        active["user_locked_home_key"] = True
        active = cpl_apply_pending_chord_to_section(
            active,
            section_name="Verse",
            pending_chord="E",
            bars=1,
            practice_key="E",
        )
        self.assertEqual(active["original_sections"]["Verse"][0]["chord"], "D")
        projected = display_sections_for_key(active, "E")["Verse"]
        self.assertEqual(projected[0]["chord"], "E")

    def test_custom_sidebar_prep_uses_original_key_family(self) -> None:
        from types import SimpleNamespace

        from custom_progression_lab import prepare_custom_workspace_sidebar_display_key

        session = {
            "display_key": "Bm",
            "concert_key": "Bm",
            "practice_key_by_source": {"Pop::Shape of You — Ed Sheeran": "Bm"},
            "_pending_display_key": "D",
        }
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        session["cpl_original_key"] = "D"
        active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
        session["cpl_active_progression"] = active
        session["_pending_display_key"] = "D"
        st = SimpleNamespace(session_state=session)
        opts = prepare_custom_workspace_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "D")
        self.assertIn("D", opts)
        self.assertNotEqual(session.get("display_key"), "Bm")

    def test_sidebar_prep_snaps_pk_when_original_widget_ahead(self) -> None:
        from types import SimpleNamespace

        from custom_progression_lab import prepare_custom_workspace_sidebar_display_key

        session: dict = {"display_key": "C", "concert_key": "C"}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        # Widget already advanced to D; canonical blob still C until CPL sync later.
        session["cpl_original_key"] = "D"
        st = SimpleNamespace(session_state=session)
        prepare_custom_workspace_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "D")

    def test_sidebar_prep_prefers_live_practice_key_over_sticky(self) -> None:
        from types import SimpleNamespace

        from custom_progression_lab import (
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            prepare_custom_workspace_sidebar_display_key,
        )
        from songs.music_source import custom_pick_key_for
        from songs.practice_key_state import set_practice_concert_key

        session: dict = {}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        session["cpl_original_key"] = "D"
        active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
        session["cpl_active_progression"] = active
        set_practice_concert_key(session, "D", pick_key=custom_pick_key_for(active))
        session[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET] = "E"
        session["display_key"] = "D"
        session["concert_key"] = "D"
        session["_custom_pk_widget_owner_pick"] = custom_pick_key_for(active)
        st = SimpleNamespace(session_state=session)
        prepare_custom_workspace_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "E")
        self.assertEqual(session.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET), "E")

    def test_sidebar_prep_live_pk_wins_over_pending_home(self) -> None:
        """Stale PENDING home-key hydrate must not wipe an explicit Practice Key."""
        from types import SimpleNamespace

        from custom_progression_lab import (
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            prepare_custom_workspace_sidebar_display_key,
        )
        from songs.music_source import custom_pick_key_for
        from songs.practice_key_state import set_practice_concert_key

        session: dict = {}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        session["cpl_original_key"] = "D"
        active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
        session["cpl_active_progression"] = active
        set_practice_concert_key(session, "D", pick_key=custom_pick_key_for(active))
        session[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET] = "E"
        session["display_key"] = "E"
        session["concert_key"] = "E"
        session["_pending_display_key"] = "D"
        session["_custom_pk_widget_owner_pick"] = custom_pick_key_for(active)
        st = SimpleNamespace(session_state=session)
        prepare_custom_workspace_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "E")
        self.assertEqual(session.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET), "E")

    def test_sidebar_prep_ignores_major_label_mismatch(self) -> None:
        """'D major' widget label vs stored 'D' must not look like Original Key changed."""
        from types import SimpleNamespace

        from custom_progression_lab import (
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            prepare_custom_workspace_sidebar_display_key,
        )
        from songs.music_source import custom_pick_key_for
        from songs.practice_key_state import set_practice_concert_key

        session: dict = {}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        session["cpl_original_key"] = "D"
        active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
        session["cpl_active_progression"] = active
        set_practice_concert_key(session, "D", pick_key=custom_pick_key_for(active))
        session[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET] = "E"
        session["display_key"] = "E"
        session["concert_key"] = "E"
        session["cpl_original_key"] = "D major"
        session["_custom_pk_widget_owner_pick"] = custom_pick_key_for(active)
        st = SimpleNamespace(session_state=session)
        prepare_custom_workspace_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "E")
        self.assertEqual(session.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET), "E")

    def test_sync_custom_sets_dedicated_widget_key(self) -> None:
        from custom_progression_lab import (
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            sync_custom_workspace_practice_key,
        )

        session: dict = {}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        active = session["cpl_active_progression"]
        sync_custom_workspace_practice_key(
            session, practice_key="E", active=active, source="test"
        )
        self.assertEqual(session.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET), "E")
        self.assertEqual(session.get("display_key"), "E")

    def test_sync_custom_defers_widget_when_locked(self) -> None:
        from custom_progression_lab import (
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            PENDING_CUSTOM_WORKSPACE_PRACTICE_KEY,
            sync_custom_workspace_practice_key,
        )

        session: dict = {
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET: "D",
            "display_key": "D",
            "concert_key": "D",
            "_streamlit_widgets_locked_this_run": True,
        }
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        active = session["cpl_active_progression"]
        # Simulate post-sidebar Original Key / New song path.
        session["_streamlit_widgets_locked_this_run"] = True
        session[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET] = "D"
        sync_custom_workspace_practice_key(
            session, practice_key="C", active=active, source="cpl_original_key_choice"
        )
        self.assertEqual(session.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET), "D")
        self.assertEqual(session.get(PENDING_CUSTOM_WORKSPACE_PRACTICE_KEY), "C")
        self.assertEqual(
            get_practice_concert_key(session, custom_pick_key_for(active)), "C"
        )

    def test_sync_custom_skips_pending_when_widget_already_matches(self) -> None:
        from custom_progression_lab import (
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            PENDING_CUSTOM_WORKSPACE_PRACTICE_KEY,
            sync_custom_workspace_practice_key,
        )

        session: dict = {
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET: "D",
            "display_key": "D",
            "_streamlit_widgets_locked_this_run": True,
            PENDING_CUSTOM_WORKSPACE_PRACTICE_KEY: "stale",
        }
        active = start_new_progression()
        active["original_key_center"] = "D"
        active["user_locked_home_key"] = True
        session["cpl_active_progression"] = active
        sync_custom_workspace_practice_key(
            session, practice_key="D", active=active, source="cpl_original_key_choice"
        )
        self.assertIsNone(session.get(PENDING_CUSTOM_WORKSPACE_PRACTICE_KEY))
        self.assertEqual(session.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET), "D")
    def test_opening_different_custom_song_resets_to_its_original(self) -> None:
        session = {"display_key": "E", "concert_key": "E"}
        song_d = start_new_progression()
        song_d["name"] = "Trial Song"
        song_d["id"] = "trial-d"
        song_d["original_key_center"] = "D"
        song_d["user_locked_home_key"] = True
        apply_cpl_session_progression(session, song_d, reset_display_key=True)
        self.assertEqual(session.get("display_key"), "D")

        song_c = start_new_progression()
        song_c["name"] = "Trial Song 2"
        song_c["id"] = "trial-c"
        song_c["original_key_center"] = "C"
        song_c["user_locked_home_key"] = True
        apply_cpl_session_progression(session, song_c, reset_display_key=True)
        self.assertEqual(session.get("display_key"), "C")
        self.assertEqual(cpl_draft_written_key(session["cpl_active_progression"]), "C")

    def test_sbi_visit_c_does_not_seed_custom_workspace_as_c_minor(self) -> None:
        from types import SimpleNamespace

        from custom_progression_lab import (
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            prepare_custom_workspace_sidebar_display_key,
        )

        session: dict = {
            "studio_page": "custom",
            "display_key": "C",
            "concert_key": "C",
            "active_music_source": "catalog",
            "active_catalog_pick_key": "Pop::Shape of You — Ed Sheeran",
            "practice_key_by_source": {"Pop::Shape of You — Ed Sheeran": "Bm"},
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET: "C",
            "_sbi_custom_last_visit_pk": "C",
        }
        song = start_new_progression()
        song["name"] = "Trial Song"
        song["original_key_center"] = "D"
        song["user_locked_home_key"] = True
        apply_cpl_session_progression(session, song, reset_display_key=False)
        st = SimpleNamespace(session_state=session)
        prepare_custom_workspace_sidebar_display_key(st, session)
        pk = str(session.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET) or session.get("display_key") or "")
        self.assertTrue(pk.startswith("D"), pk)
        self.assertNotIn("m", pk.lower().replace("major", ""))

    def _d_major_custom_session(self, *, presets_key: str = "C") -> dict:
        from custom_progression_lab import CPL_PRESETS_KEY_WIDGET

        session: dict = {}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        session["cpl_original_key"] = "D"
        session["cpl_title_input"] = "Preset Trial"
        active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
        session["cpl_active_progression"] = active
        sync_custom_workspace_practice_key(session, practice_key="D", active=active)
        session[CPL_PRESETS_KEY_WIDGET] = presets_key
        session["cpl_edit_section"] = "Verse"
        return session

    def test_preset_append_uses_presets_key_not_song_practice_key(self) -> None:
        from custom_progression_lab import cpl_append_style_preset_to_section

        session = self._d_major_custom_session(presets_key="C")
        cpl_append_style_preset_to_section(
            session, style="Pop", preset_id="I–V–vi–IV"
        )
        active = session["cpl_active_progression"]
        displayed = _chord_symbols(display_sections_for_key(active, "D")["Verse"])
        self.assertEqual(displayed, ["C", "G", "Am", "F"])
        self.assertEqual(cpl_workspace_practice_key(session, active), "D")
        self.assertEqual(cpl_draft_written_key(active), "D")

    def test_preset_append_e_major_while_song_stays_d(self) -> None:
        from custom_progression_lab import cpl_append_style_preset_to_section

        session = self._d_major_custom_session(presets_key="E")
        cpl_append_style_preset_to_section(
            session, style="Pop", preset_id="I–V–vi–IV"
        )
        active = session["cpl_active_progression"]
        displayed = _chord_symbols(display_sections_for_key(active, "D")["Verse"])
        self.assertEqual(displayed, ["E", "B", "C#m", "A"])
        self.assertEqual(cpl_workspace_practice_key(session, active), "D")

    def test_preset_append_f_family_while_song_stays_d(self) -> None:
        from custom_progression_lab import cpl_append_style_preset_to_section

        session = self._d_major_custom_session(presets_key="F")
        cpl_append_style_preset_to_section(
            session, style="Pop", preset_id="I–V–vi–IV"
        )
        active = session["cpl_active_progression"]
        displayed = _chord_symbols(display_sections_for_key(active, "D")["Verse"])
        self.assertEqual(displayed, ["F", "C", "Dm", "Bb"])
        self.assertEqual(cpl_workspace_practice_key(session, active), "D")

    def test_existing_chords_then_preset_then_manual(self) -> None:
        from custom_progression_lab import (
            cpl_append_style_preset_to_section,
            cpl_apply_chord_with_bars_to_session,
        )

        session = self._d_major_custom_session(presets_key="C")
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="Em", bars=1
        )
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="A", bars=1
        )
        cpl_append_style_preset_to_section(
            session, style="Pop", preset_id="I–V–vi–IV"
        )
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="Dm", bars=1
        )
        active = session["cpl_active_progression"]
        displayed = _chord_symbols(display_sections_for_key(active, "D")["Verse"])
        self.assertEqual(displayed, ["Em", "A", "C", "G", "Am", "F", "Dm"])
        self.assertEqual(cpl_workspace_practice_key(session, active), "D")

    def test_clear_section_only_current_then_preset_and_manual(self) -> None:
        from custom_progression_lab import (
            cpl_append_style_preset_to_section,
            cpl_apply_chord_with_bars_to_session,
            cpl_clear_current_section,
        )

        session = self._d_major_custom_session(presets_key="C")
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="D", bars=1
        )
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="A", bars=1
        )
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="Bm", bars=1
        )
        session["cpl_edit_section"] = "Chorus"
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Chorus", chord="D", bars=1
        )
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Chorus", chord="G", bars=1
        )
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Chorus", chord="A", bars=1
        )
        session["cpl_edit_section"] = "Verse"
        cpl_clear_current_section(session)
        active = session["cpl_active_progression"]
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Verse"]),
            [],
        )
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Chorus"]),
            ["D", "G", "A"],
        )
        cpl_append_style_preset_to_section(
            session, style="Pop", preset_id="I–V–vi–IV"
        )
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="Dm", bars=1
        )
        active = session["cpl_active_progression"]
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Verse"]),
            ["C", "G", "Am", "F", "Dm"],
        )
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Chorus"]),
            ["D", "G", "A"],
        )

    def test_preset_append_to_chorus_not_verse(self) -> None:
        from custom_progression_lab import (
            cpl_append_style_preset_to_section,
            cpl_apply_chord_with_bars_to_session,
            cpl_clear_current_section,
        )

        session = self._d_major_custom_session(presets_key="C")
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="Em", bars=1
        )
        session["cpl_edit_section"] = "Chorus"
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Chorus", chord="D", bars=1
        )
        session["cpl_edit_section"] = "Verse"
        cpl_clear_current_section(session)
        session["cpl_edit_section"] = "Chorus"
        cpl_append_style_preset_to_section(
            session, style="Pop", preset_id="I–V–vi–IV"
        )
        active = session["cpl_active_progression"]
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Verse"]),
            [],
        )
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Chorus"]),
            ["D", "C", "G", "Am", "F"],
        )

    def test_clear_does_not_restore_last_custom_chords(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            cpl_apply_chord_with_bars_to_session,
            cpl_clear_current_section,
        )
        from songs.music_source import LAST_CUSTOM_STATE_KEY, install_last_custom_into_live_cpl

        session = self._d_major_custom_session(presets_key="C")
        cpl_apply_chord_with_bars_to_session(
            session, section_name="Verse", chord="D", bars=1
        )
        from songs.music_source import snapshot_last_custom_state

        snapshot_last_custom_state(session)
        self.assertTrue(
            _chord_symbols(
                display_sections_for_key(session[CPL_ACTIVE_KEY], "D")["Verse"]
            )
        )
        cpl_clear_current_section(session)
        install_last_custom_into_live_cpl(session)
        active = session[CPL_ACTIVE_KEY]
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Verse"]),
            [],
        )
        last = (session.get(LAST_CUSTOM_STATE_KEY) or {}).get("active") or {}
        self.assertEqual(
            _chord_symbols(display_sections_for_key(last, "D")["Verse"]),
            [],
        )

    def test_minor_presets_key_on_minor_custom_song(self) -> None:
        from custom_progression_lab import (
            CPL_PRESETS_KEY_WIDGET,
            cpl_append_style_preset_to_section,
        )

        session: dict = {}
        apply_cpl_session_progression(
            session, start_new_progression(), reset_display_key=True
        )
        session["cpl_original_key"] = "Dm"
        active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
        session["cpl_active_progression"] = active
        sync_custom_workspace_practice_key(session, practice_key="Dm", active=active)
        session[CPL_PRESETS_KEY_WIDGET] = "Am"
        session["cpl_edit_section"] = "Verse"
        cpl_append_style_preset_to_section(
            session, style="Pop", preset_id="I–V–vi–IV"
        )
        displayed = _chord_symbols(
            display_sections_for_key(session["cpl_active_progression"], "Dm")["Verse"]
        )
        expected = _chord_symbols(build_style_preset_entries("Pop", "I–V–vi–IV", "Am"))
        self.assertEqual(displayed, expected)
        self.assertEqual(displayed, ["A", "E", "F#m", "D"])
        self.assertEqual(
            cpl_workspace_practice_key(session, session["cpl_active_progression"]),
            "Dm",
        )

    def test_custom_active_owns_songs_practice_key_widget(self) -> None:
        from custom_progression_lab import custom_active_owns_sidebar_practice_key
        from songs.music_source import SOURCE_CUSTOM

        custom = "custom::trial-1"
        session = {
            "studio_page": "picker",
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": custom,
        }
        self.assertTrue(custom_active_owns_sidebar_practice_key(session))
        session["studio_page"] = "creative"
        session["active_music_source"] = "catalog_song"
        session["active_catalog_pick_key"] = "Pop\x1fShape of You — Ed Sheeran"
        self.assertFalse(custom_active_owns_sidebar_practice_key(session))


if __name__ == "__main__":
    unittest.main()
