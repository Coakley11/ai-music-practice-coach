"""Custom Progression — set active song, draft key isolation, cloud restore."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from active_song_state import (
    ACTIVE_SONG_STATE_KEY,
    apply_cloud_active_song_state_if_allowed,
    gather_active_song_context,
    prepare_active_song_context,
    _resolve_custom_display_key_for_session,
    _resolve_display_key_from_music_blob,
)
from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    CPL_SAVED_KEY,
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
    CATALOG_BEFORE_CUSTOM_KEY,
    PENDING_CUSTOM_ACTIVE_SONG_KEY,
    PENDING_CUSTOM_LIBRARY_ACTION_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    active_song_key_pair,
    apply_pending_custom_active_song_activation_before_widgets,
    apply_pending_custom_library_action_before_widgets,
    build_active_chart_bundle,
    commit_custom_active_song,
    cpl_session_is_active,
    custom_progression_is_active,
    custom_selected_song_record,
    is_custom_progression,
    on_song_picker_source_change,
    previous_catalog_snapshot,
    queue_custom_active_song_activation,
    queue_custom_library_action,
    restore_last_catalog_active_song,
    restore_previous_catalog_song,
    resolve_active_song_keys,
    save_last_catalog_snapshot,
    set_custom_source,
    reconcile_picker_music_source,
    snapshot_current_catalog_state,
    display_key_context,
    switch_to_catalog_from_custom,
    sync_song_picker_source_widget,
    SONG_PICKER_SOURCE_CATALOG,
    SONG_PICKER_SOURCE_CUSTOM,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
from song_catalog.catalog import format_pick_key

PK_A = format_pick_key("Pop", "Song A — Artist A")
PK_SAY = format_pick_key("Pop", "Say — John Mayer")
_CATALOG_FIXTURE = {
    "Pop": {
        "Song A — Artist A": {"title": "Song A", "artist": "Artist A", "key": "G"},
    }
}


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

    def test_get_song_context_skips_catalog_when_custom_active(self) -> None:
        from songs.state import get_song_context, SELECTED_SONG_STATE_KEY

        active = self._draft_with_chords()
        active["name"] = "New Song"
        active["original_key_center"] = "D"
        st = SimpleNamespace(session_state={
            "active_music_source": SOURCE_CUSTOM,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            CPL_ACTIVE_KEY: active,
            SELECTED_SONG_STATE_KEY: {
                "pick_key": "custom::draft-1",
                "title": "New Song",
                "artist": "Your progression",
                "key": "D",
            },
        })
        with patch("songs.state.apply_pick_key") as mock_apply:
            genre, title, song_data = get_song_context(
                st,
                song_library={},
                song_picker_catalog={"Pop": {}},
            )
        mock_apply.assert_not_called()
        self.assertEqual(genre, "Custom")
        self.assertEqual(title, "New Song")
        self.assertEqual(song_data.get("key"), "D")

    def test_set_custom_source_clears_catalog_source_choice_flag(self) -> None:
        session = {USER_CATALOG_SOURCE_CHOICE_KEY: True, "active_music_source": SOURCE_CATALOG}
        set_custom_source(session)
        self.assertNotIn(USER_CATALOG_SOURCE_CHOICE_KEY, session)
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertTrue(custom_progression_is_active(session))

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

    def test_set_active_custom_resets_display_to_original_key(self) -> None:
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
            self.assertEqual(st.session_state["display_key"], "D")
            st.session_state["display_key"] = "Eb"
            commit_custom_active_song(st, active, invalidate_backing=lambda _st: None)
        self.assertEqual(st.session_state["display_key"], "D")
        self.assertEqual(st.session_state[ACTIVE_SONG_STATE_KEY]["display_key"], "D")

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

    def test_set_custom_source_preserves_previous_catalog_snapshot(self) -> None:
        session = {
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            LAST_CATALOG_STATE_KEY: {
                "pick_key": PK_A,
                "selected_song": {"title": "Song A", "artist": "Artist A", "key": "G"},
                "original_key": "G",
                "display_key": "G",
            },
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SAY,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
        }
        set_custom_source(session)
        self.assertEqual(session[LAST_CATALOG_STATE_KEY]["pick_key"], PK_A)
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        before_custom = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before_custom.get("pick_key"), PK_SAY)

    def test_reconcile_picker_music_source_activates_custom_on_picker_page(self) -> None:
        session = {
            "studio_page": "picker",
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            "active_music_source": SOURCE_CATALOG,
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SAY,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
        }
        self.assertTrue(reconcile_picker_music_source(session))
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)

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
        snapshot_current_catalog_state(session)
        snap = session.get(LAST_CATALOG_STATE_KEY) or {}
        self.assertEqual(snap.get("pick_key"), "pop::Shallow — Lady Gaga")
        self.assertEqual(snap.get("original_key"), "G")
        self.assertEqual(snap.get("display_key"), "F")

    def test_previous_catalog_snapshot_hidden_when_same_pick(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: "pop::Shallow — Lady Gaga",
            LAST_CATALOG_STATE_KEY: {
                "pick_key": "pop::Shallow — Lady Gaga",
                "selected_song": {"title": "Shallow"},
            },
        }
        self.assertIsNone(previous_catalog_snapshot(session))

    def test_save_progression_assigns_id_without_activation(self) -> None:
        from custom_progression_lab import save_progression

        store: dict = {}
        active = self._draft_with_chords()
        active["name"] = "Bossa Practice"
        save_progression(store, "Bossa Practice", active)
        saved = store["Bossa Practice"]
        self.assertTrue(str(saved.get("id") or "").strip())
        self.assertIn("updated_at", saved)
        self.assertIn("created_at", saved)

    def test_apply_cpl_session_progression_can_reset_display_key(self) -> None:
        from custom_progression_lab import apply_cpl_session_progression, load_saved_progression, save_progression

        store: dict = {}
        active = self._draft_with_chords()
        active["name"] = "Trial Song"
        active["original_key_center"] = "D"
        active["artist"] = "Daniel"
        active["bpm"] = 115
        save_progression(store, "Trial Song", active)
        session = {"display_key": "Eb", CPL_ACTIVE_KEY: default_active_progression()}
        loaded = load_saved_progression(store, "Trial Song")
        apply_cpl_session_progression(session, loaded, reset_display_key=True)
        self.assertEqual(session[CPL_ACTIVE_KEY]["name"], "Trial Song")
        self.assertEqual(int(session[CPL_ACTIVE_KEY]["bpm"]), 115)
        self.assertEqual(session["display_key"], "D")
        self.assertEqual(session["cpl_bpm_builder"], 115)
        self.assertEqual(session["cpl_title_input"], "Trial Song")

    def test_deferred_custom_library_activate_resets_display_key(self) -> None:
        from custom_progression_lab import CPL_SAVED_KEY, save_progression

        store: dict = {}
        active = self._draft_with_chords()
        active["name"] = "Trial Song"
        active["original_key_center"] = "D"
        save_progression(store, "Trial Song", active)
        st = SimpleNamespace(
            session_state={
                "display_key": "F#",
                CPL_SAVED_KEY: store,
                "active_music_source": SOURCE_CUSTOM,
            }
        )
        queue_custom_library_action(st, name="Trial Song", action="activate")
        with patch("songs.state.persist_music_local_state"):
            applied = apply_pending_custom_library_action_before_widgets(
                st,
                invalidate_backing=lambda _st: None,
            )
        self.assertTrue(applied)
        self.assertNotIn(PENDING_CUSTOM_LIBRARY_ACTION_KEY, st.session_state)
        self.assertEqual(st.session_state["display_key"], "D")
        self.assertEqual(st.session_state[CPL_ACTIVE_KEY]["name"], "Trial Song")

    def test_deferred_custom_library_edit_active_reseeds_without_crash(self) -> None:
        active = self._draft_with_chords()
        active["name"] = "Trial Song"
        active["original_key_center"] = "D"
        active["bpm"] = 115
        st = SimpleNamespace(
            session_state={
                "display_key": "F#",
                CPL_ACTIVE_KEY: active,
                "active_music_source": SOURCE_CUSTOM,
            }
        )
        queue_custom_library_action(st, action="edit_active")
        applied = apply_pending_custom_library_action_before_widgets(
            st,
            invalidate_backing=lambda _st: None,
        )
        self.assertTrue(applied)
        self.assertEqual(st.session_state["display_key"], "D")
        self.assertEqual(st.session_state.get("studio_page"), "custom")
        self.assertEqual(st.session_state["cpl_bpm_builder"], 115)

    def test_commit_custom_pushes_recent_name(self) -> None:
        from songs.music_source import CUSTOM_RECENT_ACTIVE_NAMES_KEY, commit_custom_active_song

        st = SimpleNamespace(session_state={})
        active = self._draft_with_chords()
        active["name"] = "Minor Blues Idea"
        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(st, active, invalidate_backing=lambda _st: None)
        recent = st.session_state.get(CUSTOM_RECENT_ACTIVE_NAMES_KEY) or []
        self.assertEqual(recent[0], "Minor Blues Idea")

    def test_merge_live_global_controls_keeps_canonical_custom_display_key(self) -> None:
        from active_song_state import _merge_live_global_controls

        session = {
            "active_music_source": SOURCE_CUSTOM,
            ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
            CPL_ACTIVE_KEY: self._draft_with_chords(),
            "display_key": "D",
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "display_key": "Eb",
                "custom_home_key": "D",
            },
        }
        ctx = {
            "music_source": SOURCE_CUSTOM,
            "display_key": "Eb",
            "custom_home_key": "D",
            "pick_key": "custom::my-progression",
        }
        merged = _merge_live_global_controls(session, ctx)
        self.assertEqual(merged["display_key"], "Eb")

    def test_prepare_pushes_canonical_display_key_to_session(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        session = {
            "active_music_source": SOURCE_CUSTOM,
            CPL_ACTIVE_KEY: active,
            "display_key": "D",
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "display_key": "Eb",
                "custom_home_key": "D",
                "pick_key": "custom::my-progression",
            },
        }
        prepare_active_song_context(session)
        self.assertEqual(session.get("display_key"), "Eb")

    def test_sync_picker_widget_does_not_clobber_user_choice(self) -> None:
        session = {
            "active_music_source": SOURCE_CUSTOM,
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
        }
        sync_song_picker_source_widget(session)
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CATALOG)
        sync_song_picker_source_widget(session, force=True)
        self.assertEqual(session["song_picker_active_source"], SONG_PICKER_SOURCE_CUSTOM)

    def test_gather_custom_display_key_from_canonical_when_session_empty(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        session = {
            "active_music_source": SOURCE_CUSTOM,
            CPL_ACTIVE_KEY: active,
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "display_key": "Eb",
                "custom_home_key": "D",
            },
        }
        ctx = gather_active_song_context(session)
        self.assertEqual(ctx["display_key"], "Eb")

    def test_resolve_display_key_from_workspace_envelope_top_level(self) -> None:
        self.assertEqual(
            _resolve_display_key_from_music_blob(
                {
                    "music_workspace_state": {"display_key": "Eb"},
                    "active_song_state": {"display_key": ""},
                },
                home_key="D",
            ),
            "Eb",
        )

    def test_custom_progression_is_active_from_canonical_pick_key(self) -> None:
        session = {
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "pick_key": "custom::my-progression",
            },
        }
        self.assertFalse(custom_progression_is_active(session))

    def test_custom_progression_is_active_when_session_custom(self) -> None:
        session = {
            "active_music_source": SOURCE_CUSTOM,
            ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
        }
        self.assertTrue(custom_progression_is_active(session))

    def test_custom_progression_not_active_when_catalog_source_and_catalog_pick(self) -> None:
        session = {
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: "pop::Shallow — Lady Gaga",
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "pick_key": "custom::my-progression",
            },
        }
        self.assertFalse(custom_progression_is_active(session))

    def test_resolve_custom_display_key_prefers_canonical_over_session_home(self) -> None:
        session = {
            "display_key": "D",
            ACTIVE_SONG_STATE_KEY: {"display_key": "Eb"},
        }
        self.assertEqual(
            _resolve_custom_display_key_for_session(session, home_key="D"),
            "Eb",
        )

    def test_prepare_active_song_context_does_not_force_custom_when_catalog_pick(self) -> None:
        session = {
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: "pop::Shallow — Lady Gaga",
            SELECTED_SONG_STATE_KEY: {
                "pick_key": "pop::Shallow — Lady Gaga",
                "title": "Shallow",
                "artist": "Lady Gaga",
                "key": "G",
            },
            "display_key": "G",
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "pick_key": "custom::my-progression",
                "display_key": "Eb",
            },
        }
        ctx = prepare_active_song_context(session)
        self.assertEqual(ctx.get("music_source"), SOURCE_CATALOG)
        self.assertEqual(str(ctx.get("pick_key") or ""), "pop::Shallow — Lady Gaga")

    def test_switch_to_catalog_from_custom_commits_catalog_canonical(self) -> None:
        active = self._draft_with_chords()
        st = SimpleNamespace(session_state={
            "active_music_source": SOURCE_CUSTOM,
            CPL_ACTIVE_KEY: active,
            LAST_CATALOG_STATE_KEY: {
                "pick_key": "pop::Shallow — Lady Gaga",
                "original_key": "G",
                "display_key": "F",
                "selected_song": {
                    "pick_key": "pop::Shallow — Lady Gaga",
                    "title": "Shallow",
                    "artist": "Lady Gaga",
                    "key": "G",
                },
            },
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
        })
        catalog = {
            "pop": {
                "Shallow — Lady Gaga": {"title": "Shallow", "artist": "Lady Gaga", "key": "G"},
            }
        }

        def _apply_pick_key(_st, pick_key, song_picker_catalog, **kwargs):
            genre, title = pick_key.split("::", 1)
            data = song_picker_catalog[genre][title]
            _st.session_state[SELECTED_SONG_STATE_KEY] = {
                "pick_key": pick_key,
                **data,
            }
            return dict(data)

        with patch("songs.state.apply_pick_key", side_effect=_apply_pick_key):
            with patch("songs.state.persist_music_local_state"):
                ok = switch_to_catalog_from_custom(
                    st,
                    song_picker_catalog=catalog,
                    invalidate_backing=lambda _st: None,
                )
        self.assertTrue(ok)
        ss = st.session_state
        self.assertFalse(is_custom_progression(ss))
        self.assertEqual(ss[ACTIVE_SONG_STATE_KEY]["music_source"], SOURCE_CATALOG)
        self.assertEqual(ss[ACTIVE_SONG_STATE_KEY]["pick_key"], "pop::Shallow — Lady Gaga")

    def test_switch_to_catalog_fallback_uses_active_catalog_pick_key(self) -> None:
        active = self._draft_with_chords()
        st = SimpleNamespace(session_state={
            "active_music_source": SOURCE_CUSTOM,
            CPL_ACTIVE_KEY: active,
            ACTIVE_CATALOG_PICK_KEY: "pop::Shallow — Lady Gaga",
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
        })
        catalog = {
            "pop": {
                "Shallow — Lady Gaga": {"title": "Shallow", "artist": "Lady Gaga", "key": "G"},
            }
        }

        def _apply_pick_key(_st, pick_key, song_picker_catalog, **kwargs):
            genre, title = pick_key.split("::", 1)
            data = song_picker_catalog[genre][title]
            _st.session_state[SELECTED_SONG_STATE_KEY] = {
                "pick_key": pick_key,
                **data,
            }
            return dict(data)

        with patch("songs.state.apply_pick_key", side_effect=_apply_pick_key):
            with patch("songs.state.persist_music_local_state"):
                ok = switch_to_catalog_from_custom(
                    st,
                    song_picker_catalog=catalog,
                    invalidate_backing=lambda _st: None,
                )
        self.assertTrue(ok)
        ss = st.session_state
        self.assertFalse(is_custom_progression(ss))
        self.assertEqual(ss[ACTIVE_SONG_STATE_KEY]["music_source"], SOURCE_CATALOG)

    def test_build_active_chart_bundle_uses_custom_keys_when_stale_catalog_flag(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        active["progression_style"] = "Bossa"
        session = {
            "active_music_source": SOURCE_CUSTOM,
            ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
            CPL_ACTIVE_KEY: active,
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "pick_key": "custom::my-progression",
            },
            "display_key": "Eb",
        }
        bundle = build_active_chart_bundle(
            session,
            catalog_genre="pop",
            catalog_song="Shallow — Lady Gaga",
            catalog_song_data={"title": "Shallow", "artist": "Lady Gaga", "key": "G"},
            level="Intermediate",
            display_key="Eb",
            cpl_active_key=CPL_ACTIVE_KEY,
            sections_for_level=lambda data, lvl: data.get("sections") or {},
            transpose_sections=lambda data, key: data.get("sections") or {},
        )
        self.assertEqual(bundle.get("original_key"), "D")
        self.assertEqual(bundle.get("default_groove"), "Bossa nova")

    def test_active_song_key_pair_ignores_stale_catalog_rec_when_pick_custom(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        session = {
            "active_music_source": SOURCE_CUSTOM,
            ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
            ACTIVE_SONG_STATE_KEY: {"music_source": SOURCE_CUSTOM, "pick_key": "custom::my-progression"},
            CPL_ACTIVE_KEY: active,
            "display_key": "Eb",
        }
        original, practice = active_song_key_pair(session, {"key": "G"})
        self.assertEqual(original, "D")
        self.assertEqual(practice, "Eb")

    def test_resolve_active_song_keys_prefers_live_session_over_stale_canonical(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_A,
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_A,
                "title": "Song A",
                "artist": "Artist A",
                "key": "G",
            },
            "display_key": "G",
            ACTIVE_SONG_STATE_KEY: {
                "pick_key": PK_A,
                "display_key": "C",
                "music_source": SOURCE_CATALOG,
            },
        }
        original, display, _written = resolve_active_song_keys(session, {"key": "G"})
        self.assertEqual(original, "G")
        self.assertEqual(display, "G")

    def test_switch_to_catalog_from_custom_resets_display_to_song_key(self) -> None:
        from songs.key_state import IDENTITY_KEY

        session = {
            "active_music_source": SOURCE_CUSTOM,
            ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
            "display_key": "Eb",
            CPL_ACTIVE_KEY: self._draft_with_chords(),
            LAST_CATALOG_STATE_KEY: {
                "pick_key": PK_A,
                "selected_song": {
                    "pick_key": PK_A,
                    "title": "Song A",
                    "artist": "Artist A",
                    "key": "G",
                },
                "original_key": "G",
                "display_key": "G",
            },
        }
        st = SimpleNamespace(session_state=session)

        def _apply_pick_key(_st, pick_key, song_picker_catalog, **kwargs):
            _st.session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key
            _st.session_state[SELECTED_SONG_STATE_KEY] = {
                "pick_key": pick_key,
                "title": "Song A",
                "artist": "Artist A",
                "key": "G",
            }
            return _st.session_state[SELECTED_SONG_STATE_KEY]

        with patch("songs.state.persist_music_local_state"):
            with patch("songs.state.apply_pick_key", side_effect=_apply_pick_key):
                ok = switch_to_catalog_from_custom(
                    st,
                    song_picker_catalog=_CATALOG_FIXTURE,
                    invalidate_backing=lambda _st: None,
                )
        self.assertTrue(ok)
        self.assertEqual(st.session_state["display_key"], "G")
        self.assertEqual(
            st.session_state.get(IDENTITY_KEY),
            song_display_identity("Song A", "Artist A", "G"),
        )

    def test_resolve_active_song_keys_prefers_canonical_over_stale_session(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        session = {
            ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
            CPL_ACTIVE_KEY: active,
            "display_key": "D",
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "pick_key": "custom::my-progression",
                "display_key": "Eb",
                "custom_home_key": "D",
            },
        }
        self.assertTrue(cpl_session_is_active(session))
        original, display, _written = resolve_active_song_keys(session, {"key": "G"})
        self.assertEqual(original, "D")
        self.assertEqual(display, "Eb")

    def test_display_key_context_uses_cpl_when_pick_custom_not_catalog_home(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        session = {
            ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
            CPL_ACTIVE_KEY: active,
        }
        home, identity = display_key_context(
            session,
            catalog_song_data={"title": "Shallow", "artist": "Lady Gaga", "key": "G"},
            cpl_active_key=CPL_ACTIVE_KEY,
        )
        self.assertEqual(home, "D")
        self.assertEqual(identity[2], "D")

    def test_identity_change_applies_explicit_pending_key(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        st = SimpleNamespace(
            session_state={
                CPL_ACTIVE_KEY: active,
                ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
                PENDING_DISPLAY_KEY: "Eb",
                IDENTITY_KEY: ("Shallow", "Lady Gaga", "G"),
                "display_key": "D",
            }
        )
        identity = song_display_identity("My Progression", "Custom progression", "D")
        apply_display_key_for_active_song(st, "D", identity, pending_key="Eb")
        self.assertEqual(st.session_state["display_key"], "Eb")

    def test_identity_change_ignores_stale_pending_without_explicit_key(self) -> None:
        active = self._draft_with_chords()
        active["original_key_center"] = "D"
        st = SimpleNamespace(
            session_state={
                CPL_ACTIVE_KEY: active,
                ACTIVE_CATALOG_PICK_KEY: "custom::my-progression",
                PENDING_DISPLAY_KEY: "Eb",
                IDENTITY_KEY: ("Shallow", "Lady Gaga", "G"),
                "display_key": "D",
            }
        )
        identity = song_display_identity("My Progression", "Custom progression", "D")
        apply_display_key_for_active_song(st, "D", identity)
        self.assertEqual(st.session_state["display_key"], "D")
        self.assertNotIn(PENDING_DISPLAY_KEY, st.session_state)

    def test_merge_display_key_after_cpl_to_catalog_transition(self) -> None:
        from active_song_state import _merge_display_key_for_active_song
        from songs.music_source import PREVIOUS_ACTIVE_SONG_IDENTITY_KEY, SOURCE_CATALOG

        session = {
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: PK_A,
            "display_key": "Eb",
            PREVIOUS_ACTIVE_SONG_IDENTITY_KEY: "cpl::draft-1",
        }
        ctx = {
            "music_source": SOURCE_CATALOG,
            "pick_key": PK_A,
            "display_key": "G",
            "selected_song": {"key": "G"},
        }
        merged = _merge_display_key_for_active_song(session, ctx)
        self.assertEqual(merged, "G")


if __name__ == "__main__":
    unittest.main()
