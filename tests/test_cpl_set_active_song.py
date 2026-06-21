"""Custom Progression — set active song, draft key isolation, cloud restore."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from active_song_state import (
    ACTIVE_SONG_STATE_KEY,
    apply_cloud_active_song_state_if_allowed,
    gather_active_song_context,
)
from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    commit_home_sections,
    cpl_apply_pending_chord_to_section,
    cpl_section_progression_view,
    default_active_progression,
    display_entries_for_section,
    entries_chord_tiles_html,
    ensure_all_cpl_sections,
    ensure_original_structure,
    set_original_key_center,
    written_home_key,
)
from songs.key_state import (
    IDENTITY_KEY,
    PENDING_DISPLAY_KEY,
    apply_display_key_for_active_song,
    song_display_identity,
)
from songs.music_source import (
    LAST_CATALOG_STATE_KEY,
    PENDING_CUSTOM_ACTIVE_SONG_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    active_song_key_pair,
    apply_pending_custom_active_song_activation_before_widgets,
    commit_custom_active_song,
    custom_selected_song_record,
    is_custom_progression,
    queue_custom_active_song_activation,
    restore_last_catalog_active_song,
    save_last_catalog_snapshot,
    sync_song_picker_source_widget,
    SONG_PICKER_SOURCE_CATALOG,
    SONG_PICKER_SOURCE_CUSTOM,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


class TestCplSetActiveSong(unittest.TestCase):
    def _draft_with_chords(self) -> dict:
        active = default_active_progression()
        active["name"] = "My Progression"
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        home = ensure_all_cpl_sections(active["original_sections"])
        home["Verse"] = [
            {"chord": "C", "bars": 1},
            {"chord": "Am", "bars": 1},
            {"chord": "F", "bars": 1},
            {"chord": "G", "bars": 1},
        ]
        return commit_home_sections(active, home)

    def test_chord_tiles_render_from_draft_home_key(self) -> None:
        active = self._draft_with_chords()
        preview = written_home_key(active)
        display = display_entries_for_section(active, preview, "Verse")
        html = entries_chord_tiles_html(display, time_signature="4/4")
        self.assertEqual(len(display), 4)
        self.assertIn(">C<", html)
        self.assertIn(">Am<", html)

    def test_builder_view_after_chord_and_bars_matches_page_path(self) -> None:
        active = default_active_progression()
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        active = cpl_apply_pending_chord_to_section(
            active,
            section_name="Verse",
            pending_chord="C",
            bars=2,
        )
        active = cpl_apply_pending_chord_to_section(
            active,
            section_name="Verse",
            pending_chord="G",
            bars=2,
        )
        preview = written_home_key(active)
        view = cpl_section_progression_view(
            active,
            section_name="Verse",
            preview_key=preview,
        )
        self.assertTrue(view["show_panel"])
        self.assertTrue(view["has_chords"])
        self.assertEqual(len(view["native_rows"]), 2)
        self.assertEqual(view["native_rows"][0], ("C", 2))
        self.assertEqual(view["native_rows"][1], ("G", 2))
        self.assertIn("C — 2 bars", view["native_lines"])

    def test_builder_view_shows_pending_chord_before_bars(self) -> None:
        active = default_active_progression()
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        view = cpl_section_progression_view(
            active,
            section_name="Verse",
            preview_key="C",
            pending_chord="Am",
        )
        self.assertTrue(view["show_panel"])
        self.assertIn("cpl-pending-hint", view["panel_html"])
        self.assertEqual(view["native_rows"], [])

    def test_native_fallback_would_render_rows(self) -> None:
        active = self._draft_with_chords()
        view = cpl_section_progression_view(
            active,
            section_name="Verse",
            preview_key=written_home_key(active),
        )
        self.assertGreater(len(view["native_rows"]), 0)
        self.assertTrue(all(ch and bars >= 1 for ch, bars in view["native_rows"]))

    def test_draft_key_change_does_not_require_global_display_key(self) -> None:
        active = self._draft_with_chords()
        session = {"display_key": "G", CPL_ACTIVE_KEY: active}
        active = set_original_key_center(active, "D")
        session[CPL_ACTIVE_KEY] = active
        self.assertEqual(session["display_key"], "G")
        self.assertEqual(written_home_key(active), "D")

    def test_queue_activation_does_not_mutate_widget_keys(self) -> None:
        active = self._draft_with_chords()
        st = SimpleNamespace(session_state={
            "display_key": "G",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "General",
            CPL_ACTIVE_KEY: active,
        })
        queue_custom_active_song_activation(st, active, toast_title="My Progression")
        ss = st.session_state
        self.assertIn(PENDING_CUSTOM_ACTIVE_SONG_KEY, ss)
        self.assertEqual(ss["display_key"], "G")
        self.assertEqual(ss["instrument"], "Piano")
        self.assertEqual(ss["level"], "Intermediate")
        self.assertEqual(ss["focus"], "General")
        self.assertNotIn(PENDING_DISPLAY_KEY, ss)

    def test_apply_pending_activation_before_widgets(self) -> None:
        active = self._draft_with_chords()
        st = SimpleNamespace(session_state={
            "display_key": "G",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "General",
            CPL_ACTIVE_KEY: active,
            PENDING_CUSTOM_ACTIVE_SONG_KEY: {
                "cpl_active_key": CPL_ACTIVE_KEY,
                "toast_title": "My Progression",
            },
        })
        with patch("songs.state.persist_music_local_state"):
            applied = apply_pending_custom_active_song_activation_before_widgets(
                st,
                invalidate_backing=lambda _st: None,
            )
        self.assertTrue(applied)
        ss = st.session_state
        self.assertTrue(is_custom_progression(ss))
        self.assertEqual(ss["display_key"], "C")
        self.assertEqual(ss["_cpl_activation_toast"], "My Progression")
        self.assertNotIn(PENDING_CUSTOM_ACTIVE_SONG_KEY, ss)
        self.assertEqual(
            ss[IDENTITY_KEY],
            song_display_identity("My Progression", "Your progression", "C"),
        )

    def test_pending_display_key_applied_before_widget_on_next_run(self) -> None:
        identity = song_display_identity("My Progression", "Your progression", "C")
        st = SimpleNamespace(
            session_state={
                "display_key": "G",
                PENDING_DISPLAY_KEY: "C",
                IDENTITY_KEY: identity,
            }
        )
        apply_display_key_for_active_song(st, "C", identity)
        self.assertEqual(st.session_state["display_key"], "C")
        self.assertNotIn(PENDING_DISPLAY_KEY, st.session_state)

    def test_commit_custom_active_song_updates_global_state(self) -> None:
        active = self._draft_with_chords()
        st = SimpleNamespace(session_state={
            "display_key": "G",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "General",
            CPL_ACTIVE_KEY: active,
        })

        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                st,
                active,
                invalidate_backing=lambda _st: None,
            )

        ss = st.session_state
        self.assertTrue(is_custom_progression(ss))
        self.assertEqual(ss["display_key"], "C")
        selected = ss[SELECTED_SONG_STATE_KEY]
        self.assertEqual(selected["title"], "My Progression")
        self.assertEqual(selected["key"], "C")
        self.assertTrue(str(ss[ACTIVE_CATALOG_PICK_KEY]).startswith("custom::"))
        meta = ss[ACTIVE_SONG_STATE_KEY]
        self.assertEqual(meta["music_source"], SOURCE_CUSTOM)
        self.assertEqual(meta["custom_progression_name"], "My Progression")
        self.assertEqual(meta["custom_home_key"], "C")

    def test_gather_context_reports_custom_source(self) -> None:
        active = self._draft_with_chords()
        session = {
            "active_music_source": SOURCE_CUSTOM,
            CPL_ACTIVE_KEY: active,
            "display_key": "C",
        }
        ctx = gather_active_song_context(session)
        self.assertEqual(ctx["music_source"], SOURCE_CUSTOM)
        self.assertEqual(ctx["selected_song"]["title"], "My Progression")
        self.assertEqual(ctx["display_key"], "C")

    def test_cloud_restore_custom_progression_source(self) -> None:
        active = self._draft_with_chords()
        cloud = {
            "session": {
                "active_music_source": SOURCE_CUSTOM,
                "cpl_active_progression": active,
            },
            "active_song_state": {
                "music_source": SOURCE_CUSTOM,
                "display_key": "C",
                "custom_progression_name": "My Progression",
                "custom_home_key": "C",
            },
        }
        session: dict = {"display_key": "G"}
        self.assertTrue(apply_cloud_active_song_state_if_allowed(session, cloud))
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertEqual(session["display_key"], "C")
        self.assertEqual(session[SELECTED_SONG_STATE_KEY]["title"], "My Progression")
        self.assertEqual(session[ACTIVE_SONG_STATE_KEY]["music_source"], SOURCE_CUSTOM)

    def test_cloud_restore_custom_display_key_from_workspace(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        cloud = {
            "session": {
                "active_music_source": SOURCE_CUSTOM,
                "cpl_active_progression": active,
            },
            "active_song_state": {
                "music_source": SOURCE_CUSTOM,
                "display_key": "",
                "custom_home_key": "D",
            },
            "music_workspace_state": {
                "active_song": {
                    "display_key": "Eb",
                    "music_source": SOURCE_CUSTOM,
                }
            },
        }
        session: dict = {"display_key": "D"}
        self.assertTrue(apply_cloud_active_song_state_if_allowed(session, cloud))
        self.assertEqual(session["display_key"], "Eb")
        self.assertEqual(session[ACTIVE_SONG_STATE_KEY]["display_key"], "Eb")

    def test_commit_preserves_display_key_on_same_custom_reactivation(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        st = SimpleNamespace(session_state={
            "display_key": "G",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "General",
            CPL_ACTIVE_KEY: active,
        })
        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(st, active, invalidate_backing=lambda _st: None)
            st.session_state["display_key"] = "Eb"
            commit_custom_active_song(st, active, invalidate_backing=lambda _st: None)
        self.assertEqual(st.session_state["display_key"], "Eb")
        self.assertEqual(st.session_state[ACTIVE_SONG_STATE_KEY]["display_key"], "Eb")

    def test_cpl_default_groove_maps_bossa_style(self) -> None:
        from custom_progression_lab import cpl_default_groove_for_active

        active = self._draft_with_chords()
        active["progression_style"] = "Bossa"
        active["groove_style"] = "Auto"
        self.assertEqual(cpl_default_groove_for_active(active), "Bossa nova")

    def test_custom_selected_song_record_shape(self) -> None:
        active = self._draft_with_chords()
        record = custom_selected_song_record(active)
        self.assertEqual(record["title"], "My Progression")
        self.assertEqual(record["key"], "C")
        self.assertTrue(record["is_custom"])

    def test_active_song_key_pair_uses_cpl_original_not_stale_rec_key(self) -> None:
        active = self._draft_with_chords()
        session = {
            "active_music_source": SOURCE_CUSTOM,
            CPL_ACTIVE_KEY: active,
            "display_key": "C",
            "instrument": "Piano",
        }
        original, practice = active_song_key_pair(session, {"key": "G"})
        self.assertEqual(original, "C")
        self.assertEqual(practice, "C")

    def test_active_song_key_pair_keeps_display_not_written_key(self) -> None:
        from songs.music_source import active_song_written_chart_key

        active = self._draft_with_chords()
        session = {
            "active_music_source": SOURCE_CUSTOM,
            CPL_ACTIVE_KEY: active,
            "display_key": "C",
            "instrument": "Saxophone",
            "selected_transposing_instrument": "Alto saxophone (Eb)",
            "show_chart_in_instrument_key": True,
        }
        original, practice = active_song_key_pair(session, {"key": "G"})
        self.assertEqual(original, "C")
        self.assertEqual(practice, "C")
        written = active_song_written_chart_key(session)
        self.assertEqual(written, "A")

    def test_commit_custom_active_song_syncs_picker_source_widget(self) -> None:
        active = self._draft_with_chords()
        st = SimpleNamespace(session_state={
            "display_key": "G",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "General",
            CPL_ACTIVE_KEY: active,
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
        })

        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                st,
                active,
                invalidate_backing=lambda _st: None,
            )

        self.assertEqual(
            st.session_state["song_picker_active_source"],
            SONG_PICKER_SOURCE_CUSTOM,
        )

    def test_save_and_restore_last_catalog_snapshot(self) -> None:
        session = {
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: "pop::Shallow — Lady Gaga",
            SELECTED_SONG_STATE_KEY: {
                "pick_key": "pop::Shallow — Lady Gaga",
                "title": "Shallow",
                "artist": "Lady Gaga",
                "key": "G",
            },
            "display_key": "F",
        }
        save_last_catalog_snapshot(session)
        snap = session.get(LAST_CATALOG_STATE_KEY) or {}
        self.assertEqual(snap.get("pick_key"), "pop::Shallow — Lady Gaga")
        self.assertEqual(snap.get("original_key"), "G")
        self.assertEqual(snap.get("display_key"), "F")

    def test_sync_picker_widget_does_not_clobber_user_choice(self) -> None:
        session = {
            "active_music_source": SOURCE_CUSTOM,
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
        }
        sync_song_picker_source_widget(session)
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CATALOG)
        sync_song_picker_source_widget(session, force=True)
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CUSTOM)


if __name__ == "__main__":
    unittest.main()
