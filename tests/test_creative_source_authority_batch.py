"""Shape-seeded regressions: SBI/Jam ownership, Send to Practice, Focus, icons."""

from __future__ import annotations

import inspect
import unittest

from music_feature_icons import FEATURE_ICONS, semantic_field_icon
from song_catalog.catalog import format_pick_key

SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")


def _shape_catalog_session(**extra: object) -> dict:
    session = {
        "studio_page": "backing",
        "instrument": "Piano",
        "focus": "Harmony",
        "song": "Shape of You",
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "Bm",
            "pick_key": SHAPE_PICK,
        },
        "active_catalog_pick_key": SHAPE_PICK,
        "display_key": "Bm",
        "concert_key": "Bm",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "guitar_capo_enabled": True,
        "guitar_capo_shape_key": "C",
        "_capo_shape_seed_source_id": SHAPE_PICK,
    }
    session.update(extra)
    return session


class TestSbiHasNoSendToPractice(unittest.TestCase):
    def test_sbi_entry_row_never_passes_practice_callback(self) -> None:
        from improvisation_intelligence_ui import _tab_entry_modes

        src = inspect.getsource(_tab_entry_modes)
        self.assertIn("workflow=\"sbi\"", src.replace("'", '"'))
        self.assertIn("on_open_practice=None", src)
        self.assertIn("SBI Active / Custom / Composition", src)


class TestSbiCustomCatalogIsolation(unittest.TestCase):
    def test_shape_seeded_custom_chart_identity_has_no_shape(self) -> None:
        from backing_context import build_song_improv_context, owned_backing_chart_identity
        from songs.backing_chart import render_backing_chord_chart

        session = _shape_catalog_session(
            improv_song_source="Custom progression",
            sbi_preview_source="Custom progression",
            cpl_active_progression={
                "name": "Trial Song",
                "id": "trial-leak-1",
                "original_key_center": "E",
                "bpm": 120,
                "progression_style": "Blues",
                "groove_style": "Blues",
                "time_signature": "4/4",
                "original_sections": {
                    "A": [
                        {"chord": "Em/D", "bars": 2},
                        {"chord": "D", "bars": 2},
                    ],
                },
            },
        )
        ctx = build_song_improv_context(session)
        ident = owned_backing_chart_identity(session, ctx)
        self.assertIsNotNone(ident)
        html_out = render_backing_chord_chart(
            ident["song_name"],
            ident["song_data"],
            {"A": ["Em/D", "Em/D", "D", "D"]},
            display_key=ident["original_key"],
            bpm=int(ident["bpm"]),
            groove_style="Blues",
        )
        blob = " ".join(
            [
                ident["song_name"],
                str(ident["song_data"]),
                ident["coaching"],
                html_out,
            ]
        )
        self.assertEqual(ident["song_name"], "Trial Song")
        self.assertNotIn("Shape of You", blob)
        self.assertNotIn("Ed Sheeran", blob)
        self.assertNotIn("Shape of You — Backing chart", html_out)
        self.assertIn("Trial Song", html_out)
        self.assertNotEqual(str(ident["song_data"].get("key") or ""), "Bm")

    def test_composition_sbi_chart_identity_has_no_catalog(self) -> None:
        from backing_context import build_song_improv_context, owned_backing_chart_identity

        session = _shape_catalog_session(
            improv_song_source="Composition",
            sbi_preview_source="Composition",
            composition_active_title="My Composition",
        )
        ctx = build_song_improv_context(session)
        ident = owned_backing_chart_identity(session, ctx)
        self.assertIsNotNone(ident)
        blob = ident["song_name"] + str(ident["song_data"]) + ident["coaching"]
        self.assertNotIn("Shape of You", blob)
        self.assertNotIn("Ed Sheeran", blob)
        self.assertNotIn("Bm", str(ident["song_data"].get("key") or ""))


class TestJamOwnsKeys(unittest.TestCase):
    def test_c_major_jam_ignores_shape_capo_and_title(self) -> None:
        from backing_context import BackingContext, owned_backing_chart_identity, set_backing_context
        from backing_musical_state import resolve_current_backing_musical_state
        from backing_practice_key_control import commit_backing_practice_key

        session = _shape_catalog_session(
            improv_entry_mode="Jam Session Generator",
            improv_jam_key="C",
            display_key="C",
            concert_key="C",
            studio_page="backing",
            instrument="Guitar",
        )
        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry Style Jam",
            active_song_id="generated::Jam Session Generator::cmaj",
            song_title="Jam Session Generator",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=110,
            style="Jazz Swing",
            groove="Jazz Swing",
            meter="4/4",
            progression=["C", "Am", "F", "G"],
            entry_mode="Jam Session Generator",
            mode_label="Jam Session",
        )
        set_backing_context(session, ctx)
        ident = owned_backing_chart_identity(session, ctx)
        self.assertEqual(ident["song_name"], "Jam Session Generator")
        self.assertNotIn("Shape of You", ident["song_name"])
        self.assertNotIn("Shape of You", ident["coaching"])
        state = resolve_current_backing_musical_state(session, rec=None, applied_bpm=110)
        self.assertTrue(str(state.practice_concert_key).startswith("C"))
        self.assertTrue(state.guitar_shape_on)
        self.assertTrue(str(state.chart_display_key or "").startswith("C"))
        applied = commit_backing_practice_key(session, "D")
        self.assertTrue(str(applied or session.get("improv_jam_key") or "").startswith("D"))
        self.assertEqual(session.get("improv_jam_key"), "D")
        self.assertNotEqual(str(session.get("song") or ""), "D")


class TestPracticeFocusSurfaces(unittest.TestCase):
    def test_catalog_preview_does_not_keep_trial_song(self) -> None:
        from practice_focus_creative import format_creative_practice_focus_caption

        session = _shape_catalog_session(
            studio_page="creative",
            improv_song_source="Active song",
            sbi_preview_source="Active song",
            cpl_active_progression={"name": "Trial Song", "original_key_center": "E"},
        )
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Shape of You", caption)
        self.assertNotIn("Trial Song", caption)
        self.assertNotIn("SBI Custom", caption)

    def test_focus_changes_coaching_not_identity(self) -> None:
        from practice_focus_creative import (
            format_focus_surface_guidance,
            resolve_creative_practice_focus,
        )
        from practice_setup_globals import set_active_focus, set_active_instrument

        session = _shape_catalog_session(
            studio_page="creative",
            instrument="Piano",
        )
        set_active_instrument(session, "Piano")
        frozen_kind = None
        frozen_id = None
        copies = {}
        for focus in ("Harmony", "Rhythm", "Dynamics", "Improvisation", "Voicings"):
            set_active_focus(session, focus)
            ctx = resolve_creative_practice_focus(session)
            if frozen_kind is None:
                frozen_kind = ctx["kind"]
                frozen_id = ctx["identity"]
            self.assertEqual(ctx["kind"], frozen_kind)
            self.assertEqual(ctx["identity"], frozen_id)
            copies[focus] = {
                "live": format_focus_surface_guidance(session, "live_coach"),
                "missions": format_focus_surface_guidance(session, "missions"),
                "harmony": format_focus_surface_guidance(session, "harmony"),
                "motif": format_focus_surface_guidance(session, "motif"),
                "backing": format_focus_surface_guidance(session, "backing"),
            }
        self.assertNotEqual(copies["Harmony"]["live"], copies["Rhythm"]["live"])
        self.assertNotEqual(copies["Harmony"]["missions"], copies["Dynamics"]["missions"])
        self.assertNotEqual(copies["Improvisation"]["motif"], copies["Voicings"]["motif"])
        self.assertNotEqual(copies["Harmony"]["backing"], copies["Rhythm"]["backing"])


class TestCanonicalIcons(unittest.TestCase):
    def test_return_catalog_uses_songs_icon(self) -> None:
        from backing_context import build_regular_song_context
        from backing_source_navigation import return_to_source_button_label

        catalog = build_regular_song_context(
            {"song": "Day Tripper", "display_key": "G", "concert_key": "G"}
        )
        label = return_to_source_button_label(catalog)
        self.assertTrue(label.startswith(FEATURE_ICONS["songs"]))
        self.assertNotIn("🎵", label)

        from backing_context import set_backing_context
        from backing_nav_actions import build_backing_nav_actions
        from music_feature_icons import page_feature_label

        session: dict = {"studio_page": "backing"}
        set_backing_context(session, catalog)
        actions, _removed = build_backing_nav_actions(session)
        return_labels = [a.label for a in actions if "Return to Song Catalog" in a.label]
        self.assertTrue(return_labels, [a.label for a in actions])
        expected = page_feature_label("picker", "Return to Song Catalog")
        self.assertEqual(return_labels[0], expected)
        self.assertTrue(return_labels[0].startswith(FEATURE_ICONS["songs"]))
        self.assertNotIn("🎵", return_labels[0])
        self.assertNotIn(semantic_field_icon("source"), return_labels[0])

    def test_return_catalog_backing_uses_backing_icon(self) -> None:
        from backing_source_navigation import return_to_catalog_song_backing_label

        label = return_to_catalog_song_backing_label(custom=False)
        self.assertTrue(label.startswith(FEATURE_ICONS["backing"]))
        self.assertIn("Return to Regular Catalog Song Backing", label)
        self.assertNotIn("🎵", label)
        self.assertNotEqual(label[0], FEATURE_ICONS["songs"])

    def test_level_and_shape_key_registry(self) -> None:
        self.assertEqual(FEATURE_ICONS["level"], "📈")
        self.assertEqual(semantic_field_icon("level"), "📈")
        self.assertEqual(semantic_field_icon("shape_key"), "🎸")
        self.assertEqual(semantic_field_icon("written_key"), "🎷")
        self.assertNotEqual(semantic_field_icon("shape_key"), semantic_field_icon("written_key"))

    def test_source_field_icon_is_not_catalog_logo(self) -> None:
        from app_ui import studio_song_meta_badges_html

        source_icon = semantic_field_icon("source")
        self.assertEqual(source_icon, semantic_field_icon("source_other"))
        self.assertNotEqual(source_icon, FEATURE_ICONS["songs"])
        catalog_html = studio_song_meta_badges_html(
            original_key="G",
            display_key="C",
            source="Catalog Song",
        )
        self.assertIn(source_icon, catalog_html)
        self.assertIn("Catalog Song", catalog_html)
        self.assertNotIn(FEATURE_ICONS["songs"], catalog_html)
        self.assertIn('data-source-field="source"', catalog_html)
        self.assertIn(f'data-source-icon="{source_icon}"', catalog_html)
        self.assertEqual(source_icon, "📀")
        custom_html = studio_song_meta_badges_html(source="Custom progression")
        comp_html = studio_song_meta_badges_html(source="Composition")
        self.assertIn(source_icon, custom_html)
        self.assertIn(source_icon, comp_html)
        self.assertNotIn(FEATURE_ICONS["songs"], custom_html)
        self.assertNotIn(FEATURE_ICONS["custom"], custom_html)
        self.assertNotIn(FEATURE_ICONS["composition"], comp_html)


PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")


def _perfect_sbi_session(**extra: object) -> dict:
    session = _shape_catalog_session(
        studio_page="creative",
        song="Perfect",
        selected_song={
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
        },
        active_catalog_pick_key=PERFECT_PICK,
        display_key="D",
        concert_key="D",
        improv_jam_key="C",
        improv_style_key="C",
        _creative_visit_practice_key="C",
        _creative_visit_source="sbi_active",
        improv_entry_mode="Song-Based Improvisation",
        sbi_preview_source="Active song",
        improv_song_source="Active song",
        improv_intelligence_tab="Entry & Jam",
    )
    session.update(extra)
    return session


def _lock_widgets(session: dict) -> None:
    from music_restore_phase import STREAMLIT_WIDGETS_LOCKED_KEY, complete_music_restore_phase

    complete_music_restore_phase(session)
    session[STREAMLIT_WIDGETS_LOCKED_KEY] = True
    session["_streamlit_widgets_locked_this_run"] = True


class TestPerfectSbiActiveOneKey(unittest.TestCase):
    def test_leftover_c_and_d_cannot_replace_perfect_original_g(self) -> None:
        from improvisation_intelligence_ui import (
            _authoritative_practice_chart_key,
            _reclaim_sbi_active_catalog_keys,
            _sbi_active_canonical_practice_key,
        )
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            display_key="D",
            concert_key="D",
            improv_jam_key="C",
            improv_style_key="C",
            _creative_visit_practice_key="C",
            _creative_visit_source="sbi_active",
            improv_entry_mode="Song-Based Improvisation",
            sbi_preview_source="Active song",
            improv_song_source="Active song",
            improv_intelligence_tab="Entry & Jam",
        )
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {
            SHAPE_PICK: "D",
            PERFECT_PICK: "D",
            "custom::trial-song": "C",
        }
        token = _sbi_active_canonical_practice_key(session, "C")
        self.assertTrue(str(token).startswith("G"), token)
        chart = _authoritative_practice_chart_key(session, "C")
        self.assertTrue(str(chart).startswith("G"), chart)
        _reclaim_sbi_active_catalog_keys(session, token)
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))
        self.assertTrue(str(session.get("concert_key") or "").startswith("G"))
        self.assertNotEqual(str(session.get("display_key") or ""), "D")
        self.assertNotEqual(str(session.get("_creative_visit_practice_key") or ""), "C")

    def test_pending_restore_consumed_before_widget(self) -> None:
        from music_restore_phase import STREAMLIT_WIDGETS_LOCKED_KEY
        from sbi_active_catalog_practice_key import (
            PENDING_DISPLAY_KEY_PICK,
            PENDING_DISPLAY_KEY_SOURCE,
            SBI_ACTIVE_PK_RESTORE_SOURCE,
            reclaim_sbi_active_catalog_keys,
            sbi_active_canonical_practice_key,
        )
        from session_widget_safe import PENDING_DISPLAY_KEY, apply_pending_widget_hydrates
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        session = _perfect_sbi_session()
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {
            SHAPE_PICK: "D",
            PERFECT_PICK: "D",
            "custom::trial-song": "C",
        }
        _lock_widgets(session)
        token = sbi_active_canonical_practice_key(session, "C")
        reclaim_sbi_active_catalog_keys(session, token)
        self.assertTrue(str(session.get(PENDING_DISPLAY_KEY) or "").startswith("G"))
        self.assertEqual(session.get(PENDING_DISPLAY_KEY_PICK), PERFECT_PICK)
        self.assertEqual(session.get(PENDING_DISPLAY_KEY_SOURCE), SBI_ACTIVE_PK_RESTORE_SOURCE)
        self.assertEqual(session.get("display_key"), "D")

        session.pop("_streamlit_widgets_locked_this_run", None)
        session.pop(STREAMLIT_WIDGETS_LOCKED_KEY, None)
        apply_pending_widget_hydrates(session)
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))
        # Keep Catalog SBI pending until a locked widget pass confirms G.
        self.assertTrue(str(session.get(PENDING_DISPLAY_KEY) or "").startswith("G"))
        _lock_widgets(session)
        apply_pending_widget_hydrates(session)
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))
        self.assertNotIn(PENDING_DISPLAY_KEY, session)

    def test_no_write_to_display_key_after_widget_mount(self) -> None:
        from sbi_active_catalog_practice_key import reclaim_sbi_active_catalog_keys, sbi_active_canonical_practice_key
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        session = _perfect_sbi_session()
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {SHAPE_PICK: "D"}
        _lock_widgets(session)
        reclaim_sbi_active_catalog_keys(session, sbi_active_canonical_practice_key(session, "C"))
        self.assertEqual(session.get("display_key"), "D")
        self.assertTrue(str(session.get("concert_key") or "").startswith("G"))

    def test_no_infinite_rerun(self) -> None:
        from sbi_active_catalog_practice_key import (
            maybe_rerun_sbi_active_catalog_key_restore,
            reclaim_sbi_active_catalog_keys,
            sbi_active_canonical_practice_key,
        )
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        class _St:
            def __init__(self) -> None:
                self.rerun_count = 0

            def rerun(self) -> None:
                self.rerun_count += 1

        session = _perfect_sbi_session()
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {SHAPE_PICK: "D"}
        _lock_widgets(session)
        reclaim_sbi_active_catalog_keys(session, sbi_active_canonical_practice_key(session, "C"))
        st = _St()
        self.assertTrue(maybe_rerun_sbi_active_catalog_key_restore(st, session))
        self.assertEqual(st.rerun_count, 1)
        session["_sbi_active_pk_restore_needs_rerun"] = True
        self.assertFalse(maybe_rerun_sbi_active_catalog_key_restore(st, session))
        self.assertEqual(st.rerun_count, 1)

    def test_user_key_edit_outranks_automatic_restore(self) -> None:
        import time

        from sbi_active_catalog_practice_key import (
            note_sbi_active_user_practice_key_edit,
            reclaim_sbi_active_catalog_keys,
            sbi_active_canonical_practice_key,
        )
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, set_practice_concert_key

        session = _perfect_sbi_session(display_key="C", concert_key="C")
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {SHAPE_PICK: "D", "custom::trial-song": "C"}
        set_practice_concert_key(session, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        session["_pk_user_commit_at"] = time.time() - 60.0
        token = sbi_active_canonical_practice_key(session, "G")
        self.assertTrue(str(token).startswith("C"), token)
        _lock_widgets(session)
        reclaim_sbi_active_catalog_keys(session, "G")
        self.assertEqual(session.get("display_key"), "C")
        self.assertFalse(str(session.get("_pending_display_key") or "").startswith("G"))

    def test_user_c_survives_refresh_after_leftover_g_init(self) -> None:
        """Full G init → user C → refresh C → user G → refresh G."""
        from music_restore_phase import STREAMLIT_WIDGETS_LOCKED_KEY, begin_music_script_run
        from improvisation_intelligence_ui import _authoritative_practice_chart_key
        from sbi_active_catalog_practice_key import (
            PENDING_DISPLAY_KEY_PICK,
            PENDING_DISPLAY_KEY_SOURCE,
            SBI_ACTIVE_PK_RESTORE_SOURCE,
            maybe_rerun_sbi_active_catalog_key_restore,
            note_sbi_active_user_practice_key_edit,
            prepare_sbi_active_catalog_practice_key,
            reclaim_sbi_active_catalog_keys,
            sbi_active_canonical_practice_key,
        )
        from session_widget_safe import PENDING_DISPLAY_KEY, apply_pending_widget_hydrates
        from songs.practice_key_state import (
            PRACTICE_KEY_BY_SOURCE_KEY,
            catalog_pick_has_user_practice_key_override,
            get_practice_concert_key,
        )

        session = _perfect_sbi_session()
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {
            SHAPE_PICK: "D",
            PERFECT_PICK: "D",
            "custom::trial-song": "C",
        }

        class _St:
            def __init__(self) -> None:
                self.rerun_count = 0

            def rerun(self) -> None:
                self.rerun_count += 1

        st = _St()
        _lock_widgets(session)
        token = sbi_active_canonical_practice_key(session, "C")
        self.assertTrue(str(token).startswith("G"), token)
        reclaim_sbi_active_catalog_keys(session, token)
        self.assertEqual(session.get("display_key"), "D")
        self.assertTrue(str(session.get(PENDING_DISPLAY_KEY) or "").startswith("G"))
        self.assertTrue(maybe_rerun_sbi_active_catalog_key_restore(st, session))
        self.assertEqual(st.rerun_count, 1)

        begin_music_script_run(session)
        apply_pending_widget_hydrates(session)
        prepare_sbi_active_catalog_practice_key(session)
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))
        self.assertTrue(str(session.get("selected_song", {}).get("key") or "").startswith("G"))
        self.assertTrue(str(_authoritative_practice_chart_key(session, "C")).startswith("G"))
        self.assertTrue(str(session.get(PENDING_DISPLAY_KEY) or "").startswith("G"))
        _lock_widgets(session)
        apply_pending_widget_hydrates(session)
        self.assertNotIn(PENDING_DISPLAY_KEY, session)

        session["display_key"] = "C"
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        self.assertTrue(catalog_pick_has_user_practice_key_override(session, PERFECT_PICK))
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK) or "").startswith("C"))
        self.assertFalse(str(session.get(PENDING_DISPLAY_KEY) or "").startswith("G"))
        self.assertNotEqual(session.get(PENDING_DISPLAY_KEY_SOURCE), SBI_ACTIVE_PK_RESTORE_SOURCE)
        session["_pk_user_commit_at"] = 0.0
        session[PENDING_DISPLAY_KEY] = "G"
        session[PENDING_DISPLAY_KEY_PICK] = PERFECT_PICK
        session[PENDING_DISPLAY_KEY_SOURCE] = SBI_ACTIVE_PK_RESTORE_SOURCE
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        self.assertFalse(str(session.get(PENDING_DISPLAY_KEY) or "").startswith("G"))

        _lock_widgets(session)
        reclaim_sbi_active_catalog_keys(session, "G")
        self.assertEqual(session.get("display_key"), "C")
        self.assertFalse(str(session.get(PENDING_DISPLAY_KEY) or "").startswith("G"))

        begin_music_script_run(session)
        apply_pending_widget_hydrates(session)
        prepare_sbi_active_catalog_practice_key(session)
        self.assertTrue(str(session.get("display_key") or "").startswith("C"))
        self.assertTrue(str(session.get("concert_key") or "").startswith("C"))
        self.assertTrue(str(session.get("_creative_visit_practice_key") or "").startswith("C"))
        self.assertTrue(str(sbi_active_canonical_practice_key(session, "G")).startswith("C"))
        self.assertTrue(str(_authoritative_practice_chart_key(session, "G")).startswith("C"))
        self.assertTrue(str(session.get("selected_song", {}).get("key") or "").startswith("G"))
        session["_sbi_active_pk_restore_needs_rerun"] = True
        self.assertFalse(maybe_rerun_sbi_active_catalog_key_restore(st, session))
        self.assertEqual(st.rerun_count, 1)

        session["display_key"] = "G"
        note_sbi_active_user_practice_key_edit(session, "G", pick=PERFECT_PICK)
        session["_pk_user_commit_at"] = 0.0
        begin_music_script_run(session)
        apply_pending_widget_hydrates(session)
        prepare_sbi_active_catalog_practice_key(session)
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))
        self.assertTrue(str(session.get("concert_key") or "").startswith("G"))
        self.assertTrue(str(sbi_active_canonical_practice_key(session, "C")).startswith("G"))
        self.assertTrue(str(_authoritative_practice_chart_key(session, "C")).startswith("G"))
        self.assertEqual(st.rerun_count, 1)

    def test_widget_g_to_c_renders_card_and_caption_from_pick_scoped_c(self) -> None:
        """Callback + locked rerun must paint SBI Key / Practice concert key as C."""
        from unittest.mock import MagicMock

        from app_ui import render_creative_song_context_card
        from creative_key_sync import (
            creative_progression_display,
            sync_sidebar_creative_concert_key,
        )
        from improvisation_intelligence_ui import (
            _authoritative_practice_chart_key,
            _reclaim_sbi_active_catalog_keys,
            _sbi_active_canonical_practice_key,
        )
        from music_restore_phase import begin_music_script_run
        from sbi_active_catalog_practice_key import (
            persist_sbi_active_sidebar_commit_before_render,
            prepare_sbi_active_catalog_practice_key,
            sbi_active_catalog_owns_practice_key,
        )
        from session_widget_safe import PENDING_DISPLAY_KEY, apply_pending_widget_hydrates
        from song_practice_key_sidebar_change import capture_sidebar_song_practice_key_edit_intent
        from songs.key_state import mark_display_key_changed
        from songs.practice_key_state import (
            PRACTICE_KEY_BY_SOURCE_KEY,
            catalog_pick_has_user_practice_key_override,
            get_practice_concert_key,
        )
        from studio_page_state import resolve_improv_song_preview

        session = _perfect_sbi_session(
            display_key="G",
            concert_key="G",
            _creative_visit_practice_key="G",
            _creative_visit_source="sbi_active",
        )
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {
            SHAPE_PICK: "D",
            PERFECT_PICK: "G",
            "custom::trial-song": "C",
        }
        session["catalog_session"] = {
            "pick_key": PERFECT_PICK,
            "original_key": "G",
            "display_key": "G",
            "selected_song": session["selected_song"],
            "sections": {"Verse": ["G", "D/F#", "Em7", "D", "Cadd9"]},
        }
        session["improv_song_concert_sections"] = {"Verse": ["G", "D/F#", "Em7", "D", "Cadd9"]}
        session["backing_context"] = {
            "source": "entry_jam",
            "entry_mode": "Jam Session Generator",
            "concert_key": "C",
            "key": "C",
        }
        session["_generated_jam_key_owner_active"] = True
        self.assertTrue(sbi_active_catalog_owns_practice_key(session))

        class _St:
            def __init__(self) -> None:
                self.session_state = session

        session["display_key"] = "C"
        mark_display_key_changed(_St())
        capture_sidebar_song_practice_key_edit_intent(session)
        sync_sidebar_creative_concert_key(session)

        orig = str(session.get("selected_song", {}).get("key") or "")
        self.assertTrue(orig.startswith("G"), orig)
        self.assertTrue(catalog_pick_has_user_practice_key_override(session, PERFECT_PICK))
        saved = str(get_practice_concert_key(session, PERFECT_PICK) or "")
        self.assertTrue(saved.startswith("C"), saved)

        session["_pending_display_key"] = "G"
        session["_pending_display_key_pick"] = PERFECT_PICK
        session["_pending_display_key_source"] = "sbi_active_catalog"
        _lock_widgets(session)
        apply_pending_widget_hydrates(session)
        persist_sbi_active_sidebar_commit_before_render(session)
        self.assertNotEqual(str(session.get(PENDING_DISPLAY_KEY) or ""), "G")
        saved = str(get_practice_concert_key(session, PERFECT_PICK) or "")
        preview = resolve_improv_song_preview(session)
        fallback = str(preview.get("display_key") or "G")
        canonical = _sbi_active_canonical_practice_key(session, fallback)
        _reclaim_sbi_active_catalog_keys(session, canonical)
        chart = _authoritative_practice_chart_key(session, fallback)
        display = creative_progression_display(
            session,
            dict(preview.get("sections") or session.get("improv_song_concert_sections") or {}),
            concert_key=chart,
        )
        authority = {
            "display_key": session.get("display_key"),
            "pick_scoped": saved,
            "visit": session.get("_creative_visit_practice_key"),
            "sbi_preview_key": preview.get("display_key"),
            "canonical": canonical,
            "card_key": chart,
            "practice_concert_key": display["concert_key"],
            "pending": session.get("_pending_display_key"),
            "original": orig,
        }
        self.assertTrue(str(authority["display_key"] or "").startswith("C"), authority)
        self.assertTrue(str(authority["pick_scoped"] or "").startswith("C"), authority)
        self.assertTrue(str(authority["visit"] or "").startswith("C"), authority)
        self.assertTrue(str(authority["canonical"] or "").startswith("C"), authority)
        self.assertTrue(str(authority["card_key"] or "").startswith("C"), authority)
        self.assertTrue(str(authority["practice_concert_key"] or "").startswith("C"), authority)
        self.assertTrue(str(authority["original"] or "").startswith("G"), authority)
        self.assertFalse(str(authority["pending"] or "").startswith("G"), authority)

        card_st = MagicMock()
        render_creative_song_context_card(
            card_st,
            title="Perfect",
            artist="Ed Sheeran",
            display_key=chart,
            chord_count=5,
            source_label="Active song · Song Selection",
        )
        card_html = str(card_st.markdown.call_args[0][0])
        self.assertIn("Key C", card_html)
        self.assertNotIn("Key G", card_html)

        begin_music_script_run(session)
        apply_pending_widget_hydrates(session)
        prepare_sbi_active_catalog_practice_key(session)
        _lock_widgets(session)
        preview = resolve_improv_song_preview(session)
        fallback = str(preview.get("display_key") or "G")
        chart = _authoritative_practice_chart_key(session, fallback)
        display = creative_progression_display(
            session,
            dict(preview.get("sections") or {}),
            concert_key=chart,
        )
        self.assertTrue(str(session.get("display_key") or "").startswith("C"))
        self.assertTrue(str(chart).startswith("C"), chart)
        self.assertTrue(str(display["concert_key"]).startswith("C"), display)
        self.assertTrue(str(session.get("selected_song", {}).get("key") or "").startswith("G"))

        session["display_key"] = "G"
        mark_display_key_changed(_St())
        begin_music_script_run(session)
        apply_pending_widget_hydrates(session)
        prepare_sbi_active_catalog_practice_key(session)
        chart = _authoritative_practice_chart_key(session, "C")
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))
        self.assertTrue(str(chart).startswith("G"), chart)
        self.assertTrue(str(session.get("selected_song", {}).get("key") or "").startswith("G"))

    def test_each_catalog_pick_keeps_its_own_saved_key(self) -> None:
        from sbi_active_catalog_practice_key import sbi_active_canonical_practice_key
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, set_practice_concert_key

        session = _perfect_sbi_session()
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {SHAPE_PICK: "D"}
        self.assertTrue(str(sbi_active_canonical_practice_key(session, "C")).startswith("G"))
        set_practice_concert_key(session, "A", pick_key=PERFECT_PICK, allow_restore_original=True)
        self.assertTrue(str(sbi_active_canonical_practice_key(session, "G")).startswith("A"))
        session["active_catalog_pick_key"] = SHAPE_PICK
        session["selected_song"] = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "Bm",
            "pick_key": SHAPE_PICK,
        }
        self.assertEqual(str(session[PRACTICE_KEY_BY_SOURCE_KEY].get(SHAPE_PICK)), "D")
        self.assertEqual(str(session[PRACTICE_KEY_BY_SOURCE_KEY].get(PERFECT_PICK)), "A")

    def test_custom_jam_mission_ownership_untouched(self) -> None:
        from sbi_active_catalog_practice_key import (
            PENDING_DISPLAY_KEY_PICK,
            PENDING_DISPLAY_KEY_SOURCE,
            SBI_ACTIVE_PK_RESTORE_SOURCE,
            pending_sbi_active_restore_belongs_to_session,
            sbi_active_catalog_owns_practice_key,
        )
        from session_widget_safe import PENDING_DISPLAY_KEY, apply_pending_widget_hydrates
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        custom = _perfect_sbi_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            display_key="E",
            concert_key="E",
        )
        custom[LAST_CUSTOM_STATE_KEY] = {"name": "Trial Song", "pick_key": "custom::trial-song"}
        custom[PENDING_DISPLAY_KEY] = "G"
        custom[PENDING_DISPLAY_KEY_PICK] = PERFECT_PICK
        custom[PENDING_DISPLAY_KEY_SOURCE] = SBI_ACTIVE_PK_RESTORE_SOURCE
        self.assertFalse(sbi_active_catalog_owns_practice_key(custom))
        self.assertFalse(pending_sbi_active_restore_belongs_to_session(custom))
        apply_pending_widget_hydrates(custom)
        self.assertEqual(custom.get("display_key"), "E")
        self.assertNotIn(PENDING_DISPLAY_KEY, custom)

        jam = _perfect_sbi_session(
            improv_entry_mode="Jam Session Generator",
            improv_jam_key="C",
            display_key="C",
            concert_key="C",
        )
        jam[PENDING_DISPLAY_KEY] = "G"
        jam[PENDING_DISPLAY_KEY_PICK] = PERFECT_PICK
        jam[PENDING_DISPLAY_KEY_SOURCE] = SBI_ACTIVE_PK_RESTORE_SOURCE
        self.assertFalse(sbi_active_catalog_owns_practice_key(jam))
        apply_pending_widget_hydrates(jam)
        self.assertTrue(str(jam.get("display_key") or "").startswith("C"))


class TestJamDoesNotInheritCatalogShape(unittest.TestCase):
    def test_c_major_jam_disables_inherited_shape_d(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from backing_musical_state import resolve_current_backing_musical_state
        from guitar_capo import isolate_jam_from_catalog_guitar_shape, shape_tonic_only

        session = _shape_catalog_session(
            improv_entry_mode="Jam Session Generator",
            improv_jam_key="C",
            display_key="D",
            concert_key="D",
            studio_page="backing",
            instrument="Guitar",
            guitar_capo_enabled=True,
            guitar_capo_shape_key="D",
        )
        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry Style Jam",
            active_song_id="generated::Jam Session Generator::cmaj",
            song_title="Jam Session Generator",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=110,
            style="Jazz Swing",
            groove="Jazz Swing",
            meter="4/4",
            progression=["C", "Am", "F", "G"],
            entry_mode="Jam Session Generator",
            mode_label="Jam Session",
        )
        set_backing_context(session, ctx)
        isolate_jam_from_catalog_guitar_shape(session)
        self.assertTrue(bool(session.get("guitar_capo_enabled")))
        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "D")
        state = resolve_current_backing_musical_state(session, rec=None, applied_bpm=110)
        self.assertTrue(str(state.practice_concert_key).startswith("C"))
        self.assertTrue(state.guitar_shape_on)


class TestMotifFocusDropsLeftoverJam(unittest.TestCase):
    def test_shape_phrase_motif_does_not_caption_jam_generator(self) -> None:
        from practice_focus_creative import format_creative_practice_focus_caption

        session = _shape_catalog_session(
            studio_page="creative",
            improv_entry_mode="Jam Session Generator",
            improv_jam_style="Pop groove",
            improv_jam_key="C",
            improv_intelligence_tab="Phrase / Motif",
            sbi_preview_source="Active song",
            improv_song_source="Active song",
            focus="Strumming",
        )
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Shape of You", caption)
        self.assertNotIn("Jam Generator", caption)
        self.assertNotIn("Pop groove", caption)

    def test_perfect_phrase_motif_does_not_caption_jam_generator(self) -> None:
        from practice_focus_creative import format_creative_practice_focus_caption

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            improv_entry_mode="Jam Session Generator",
            improv_jam_style="Ballad",
            improv_intelligence_tab="Phrase / Motif",
            _improv_intelligence_tab_for_render="Phrase / Motif",
            sbi_preview_source="Active song",
            improv_song_source="Active song",
            focus="Strumming",
        )
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertNotIn("Jam Generator", caption)
        self.assertNotIn("Ballad", caption)

    def test_perfect_motif_view_drops_jam_even_if_entry_lags(self) -> None:
        from music_workflow_mutation import ACTIVE_CREATIVE_VIEW_KEY
        from practice_focus_creative import format_creative_practice_focus_caption

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            improv_entry_mode="Jam Session Generator",
            improv_jam_style="Ballad",
            sbi_preview_source="Active song",
            improv_song_source="Active song",
            focus="Strumming",
            _creative_visit_source="catalog",
        )
        session[ACTIVE_CREATIVE_VIEW_KEY] = "Motifs"
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertNotIn("Jam Generator", caption)
        self.assertNotIn("Ballad", caption)


class TestCustomBackingUsesSavedTitle(unittest.TestCase):
    def test_trial_song_not_my_progression(self) -> None:
        from backing_context import build_song_improv_context, owned_backing_chart_identity
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        trial = {
            "id": "trial-title-1",
            "name": "Trial Song",
            "original_key_center": "E",
            "bpm": 120,
            "progression_style": "Blues",
            "original_sections": {
                "A": [{"chord": "Em/D", "bars": 2}, {"chord": "D", "bars": 2}],
            },
        }
        session = _shape_catalog_session(
            improv_song_source="Custom progression",
            sbi_preview_source="Custom progression",
            cpl_active_progression={
                "name": "My Progression",
                "id": "shell",
                "original_key_center": "C",
                "original_sections": {},
            },
        )
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-title-1",
            "custom_home_key": "E",
            "active": trial,
        }
        ctx = build_song_improv_context(session)
        ident = owned_backing_chart_identity(session, ctx)
        self.assertIsNotNone(ident)
        self.assertEqual(ident["song_name"], "Trial Song")
        self.assertNotIn("My Progression", ident["song_name"])
        self.assertNotIn("Shape of You", ident["song_name"])
        self.assertEqual(str(ident["original_key"] or ident["song_data"]["key"]), "E")
        self.assertNotEqual(str(ident["song_data"]["key"]), "C")
        self.assertNotEqual(str(ident["song_data"]["key"]), "Bm")


class TestTrialSongOriginalKeyNotCatalogC(unittest.TestCase):
    def test_regular_custom_backing_original_is_saved_d(self) -> None:
        from backing_context import (
            BackingContext,
            owned_backing_chart_identity,
            set_backing_context,
        )
        from creative_source_ownership_contract import resolve_custom_saved_original_key
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        trial = {
            "id": "trial-orig-d",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
        }
        session = _shape_catalog_session(
            studio_page="backing",
            display_key="D",
            concert_key="D",
            cpl_active_progression=dict(trial),
        )
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-orig-d",
            "custom_home_key": "D",
            "active": trial,
        }
        ctx = BackingContext(
            source="custom_progression",
            source_label="Custom",
            active_song_id="custom::trial-orig-d",
            song_title="Trial Song",
            key="C",
            display_key="D",
            concert_key="D",
            bpm=100,
            style="Custom",
            groove="Pop",
            progression=["D", "G", "A"],
        )
        set_backing_context(session, ctx)
        self.assertEqual(resolve_custom_saved_original_key(session, trial), "D")
        ident = owned_backing_chart_identity(session, ctx)
        self.assertIsNotNone(ident)
        self.assertEqual(ident["original_key"], "D")
        self.assertEqual(ident["song_data"]["key"], "D")
        self.assertTrue(ident["song_data"].get("always_show_original_key"))
        from songs.backing_chart import render_backing_chord_chart

        html = render_backing_chord_chart(
            "Trial Song",
            ident["song_data"],
            {"A": ["D", "G", "A"]},
            display_key="D",
        )
        self.assertIn("(orig. D)", html)
        self.assertNotIn("(orig. C)", html)

    def test_remounted_cpl_original_c_does_not_clobber_trial_d(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            cpl_draft_written_key,
            sync_cpl_draft_widgets_to_active,
        )

        trial = {
            "id": "trial-orig-remount",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
        }
        session = {CPL_ACTIVE_KEY: dict(trial), "cpl_original_key": "C"}
        active = sync_cpl_draft_widgets_to_active(session, dict(trial))
        self.assertEqual(cpl_draft_written_key(active), "D")
        from custom_progression_lab import apply_pending_custom_original_key

        apply_pending_custom_original_key(session, active)
        self.assertTrue(str(session.get("cpl_original_key") or "").startswith("D"))

    def test_widget_d_writes_into_blob_c(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            cpl_draft_written_key,
            sync_cpl_draft_widgets_to_active,
        )

        trial = {
            "id": "trial-widget-d",
            "name": "Trial Song",
            "original_key_center": "C",
            "original_sections": {"A": [{"chord": "Em", "bars": 1}]},
        }
        session = {CPL_ACTIVE_KEY: dict(trial), "cpl_original_key": "D"}
        active = sync_cpl_draft_widgets_to_active(session, dict(trial))
        self.assertTrue(str(cpl_draft_written_key(active)).startswith("D"))
        self.assertTrue(bool(active.get("user_locked_home_key")))

    def test_remounted_c_with_stale_commit_c_keeps_trial_d(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            cpl_draft_written_key,
            sync_cpl_draft_widgets_to_active,
        )

        trial = {
            "id": "trial-commit-c",
            "name": "Trial Song",
            "original_key_center": "D",
            "user_locked_home_key": True,
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
        }
        session = {
            CPL_ACTIVE_KEY: dict(trial),
            "cpl_original_key": "C",
            "_cpl_original_key_commit": "C",
        }
        active = sync_cpl_draft_widgets_to_active(session, dict(trial))
        self.assertTrue(str(cpl_draft_written_key(active)).startswith("D"))

    def test_false_user_edit_remount_c_keeps_trial_d(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            cpl_draft_written_key,
            sync_cpl_draft_widgets_to_active,
        )

        trial = {
            "id": "trial-user-edit-c",
            "name": "Trial Song",
            "original_key_center": "D",
            "user_locked_home_key": True,
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
        }
        session = {
            CPL_ACTIVE_KEY: dict(trial),
            "cpl_original_key": "C",
            "_cpl_original_key_user_edit": True,
            "_cpl_original_key_commit": "C",
        }
        active = sync_cpl_draft_widgets_to_active(session, dict(trial))
        self.assertTrue(str(cpl_draft_written_key(active)).startswith("D"))
        from custom_progression_lab import apply_pending_custom_original_key

        apply_pending_custom_original_key(session, active)
        self.assertTrue(str(session.get("cpl_original_key") or "").startswith("D"))

    def test_chip_d_save_persists_trial_original_key(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            commit_user_original_key,
            cpl_draft_written_key,
            save_progression,
            start_new_progression,
            sync_cpl_draft_widgets_to_active,
            sync_written_home_key,
        )

        session = {
            CPL_ACTIVE_KEY: start_new_progression(),
            "cpl_title_input": "Trial Song",
            "cpl_original_key": "C",
        }
        session[CPL_ACTIVE_KEY]["name"] = "Trial Song"
        session[CPL_ACTIVE_KEY]["original_sections"] = {
            "Verse": [{"chord": "Em", "bars": 1}, {"chord": "D", "bars": 1}],
        }
        commit_user_original_key(session, "D", source="chip")
        self.assertTrue(str(cpl_draft_written_key(session[CPL_ACTIVE_KEY])).startswith("D"))
        session["cpl_original_key"] = "C"
        active = sync_cpl_draft_widgets_to_active(session, session[CPL_ACTIVE_KEY])
        self.assertTrue(str(cpl_draft_written_key(active)).startswith("D"))
        analyzed = sync_written_home_key(dict(active))
        self.assertTrue(str(cpl_draft_written_key(analyzed)).startswith("D"))
        saved: dict = {}
        save_progression(saved, "Trial Song", active)
        self.assertTrue(str(saved["Trial Song"]["original_key_center"]).startswith("D"))

    def test_remounted_my_progression_does_not_overwrite_trial_title(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            resolve_cpl_saved_title,
            sync_cpl_draft_widgets_to_active,
        )
        from songs.music_source import LAST_CUSTOM_STATE_KEY, snapshot_last_custom_state

        trial = {
            "id": "trial-title-1",
            "name": "Trial Song",
            "original_key_center": "D",
            "bpm": 100,
            "time_signature": "4/4",
            "progression_style": "Pop",
            "original_sections": {"Verse": [{"chord": "Em", "bars": 1}, {"chord": "D", "bars": 1}]},
        }
        session = {
            CPL_ACTIVE_KEY: dict(trial),
            "cpl_title_input": "My Progression",
            "custom_workspace_practice_key": "D",
        }
        active = sync_cpl_draft_widgets_to_active(session, dict(trial))
        self.assertEqual(active.get("name"), "Trial Song")
        self.assertEqual(resolve_cpl_saved_title(session, active), "Trial Song")
        snapshot_last_custom_state(session)
        snap = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str(snap.get("name") or ""), "Trial Song")
        self.assertTrue(str(snap.get("pick_key") or "").startswith("custom::"))
        self.assertTrue(str((snap.get("active") or {}).get("original_key_center") or "").startswith("D"))

    def test_save_uses_committed_title_when_widget_is_generic(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            CPL_TITLE_COMMIT,
            commit_user_original_key,
            commit_user_title,
            resolve_cpl_saved_title,
            save_progression,
            sync_cpl_draft_widgets_to_active,
        )
        from songs.music_source import LAST_CUSTOM_STATE_KEY, snapshot_last_custom_state

        trial = {
            "id": "trial-title-save",
            "name": "Trial Song",
            "original_key_center": "D",
            "bpm": 112,
            "time_signature": "4/4",
            "progression_style": "Pop",
            "original_sections": {"Verse": [{"chord": "Em", "bars": 1}]},
            "user_locked_home_key": True,
        }
        session = {
            CPL_ACTIVE_KEY: dict(trial),
            "cpl_title_input": "My Progression",
            CPL_TITLE_COMMIT: "Trial Song",
            "_pending_cpl_title": "Trial Song",
            "_pending_cpl_original_key": "D",
            "cpl_original_key": "C",
            "custom_workspace_practice_key": "D",
            "cpl_saved_progressions": {},
        }
        active = sync_cpl_draft_widgets_to_active(session, dict(trial))
        title = resolve_cpl_saved_title(session, active)
        self.assertEqual(title, "Trial Song")
        active = commit_user_title(session, title, active=active, assign_widget=False)
        active = commit_user_original_key(
            session, "D", active=active, source="save", assign_widget=False
        )
        saved: dict = {}
        save_progression(saved, title, active)
        self.assertIn("Trial Song", saved)
        self.assertNotIn("My Progression", saved)
        self.assertTrue(str(saved["Trial Song"]["original_key_center"]).startswith("D"))
        session[CPL_ACTIVE_KEY] = dict(saved["Trial Song"])
        snapshot_last_custom_state(session)
        snap = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str(snap.get("name") or ""), "Trial Song")
        self.assertTrue(str(snap.get("pick_key") or "").startswith("custom::"))

    def test_open_backing_pending_navigates_custom_trial_song(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            PENDING_CPL_OPEN_BACKING,
            apply_pending_cpl_open_backing,
        )
        from songs.music_source import LAST_CUSTOM_STATE_KEY, snapshot_last_custom_state

        trial = {
            "id": "trial-open-backing",
            "name": "Trial Song",
            "original_key_center": "D",
            "bpm": 100,
            "time_signature": "4/4",
            "progression_style": "Pop",
            "original_sections": {"Verse": [{"chord": "Em", "bars": 1}, {"chord": "D", "bars": 1}]},
            "user_locked_home_key": True,
        }
        session = {
            CPL_ACTIVE_KEY: dict(trial),
            "studio_page": "custom",
            "cpl_saved_progressions": {"Trial Song": dict(trial)},
            PENDING_CPL_OPEN_BACKING: True,
        }
        snapshot_last_custom_state(session)
        self.assertTrue(apply_pending_cpl_open_backing(session))
        self.assertEqual(session.get("studio_page"), "backing")
        self.assertFalse(session.get(PENDING_CPL_OPEN_BACKING))
        snap = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str(snap.get("name") or ""), "Trial Song")
        from backing_context import BACKING_PREF_CUSTOM, get_backing_context, get_backing_source_preference

        self.assertEqual(get_backing_source_preference(session), BACKING_PREF_CUSTOM)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(str(getattr(ctx, "source", "") or ""), "custom_progression")
        self.assertIn("Trial Song", str(getattr(ctx, "song_title", "") or ""))
        self.assertTrue(str(getattr(ctx, "key", "") or "").upper().startswith("D"))
        self.assertTrue(apply_pending_cpl_open_backing(session) is False)

    def test_library_membership_reveals_saved_song_without_flag(self) -> None:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            CPL_SAVED_KEY,
            cpl_library_saved_for_current_song,
        )

        trial = {
            "id": "trial-lib-1",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"Verse": [{"chord": "Em", "bars": 1}]},
        }
        session = {
            CPL_ACTIVE_KEY: dict(trial),
            CPL_SAVED_KEY: {"Trial Song": dict(trial)},
        }
        self.assertTrue(cpl_library_saved_for_current_song(session, trial))

    def test_selected_song_key_d_heals_clobbered_live_c(self) -> None:
        from creative_source_ownership_contract import resolve_custom_saved_original_key
        from songs.music_source import LAST_CUSTOM_STATE_KEY
        from songs.state import SELECTED_SONG_STATE_KEY

        trial = {
            "id": "trial-sel-d",
            "name": "Trial Song",
            "original_key_center": "C",
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
        }
        session = _shape_catalog_session(cpl_active_progression=dict(trial))
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-sel-d",
            "custom_home_key": "C",
            "active": dict(trial),
        }
        session[SELECTED_SONG_STATE_KEY] = {
            "pick_key": "custom::trial-sel-d",
            "title": "Trial Song",
            "key": "D",
            "source": "custom",
            "is_custom": True,
        }
        self.assertEqual(resolve_custom_saved_original_key(session, trial), "D")

    def test_generic_shell_c_does_not_beat_last_custom_d(self) -> None:
        from creative_source_ownership_contract import resolve_custom_saved_original_key
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        trial = {
            "id": "trial-orig-d2",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
        }
        session = _shape_catalog_session(
            cpl_active_progression={
                "name": "My Progression",
                "id": "shell",
                "original_key_center": "C",
                "original_sections": {},
            }
        )
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-orig-d2",
            "custom_home_key": "D",
            "active": trial,
        }
        self.assertEqual(resolve_custom_saved_original_key(session), "D")

    def test_inferred_snap_c_does_not_beat_live_trial_d(self) -> None:
        from creative_source_ownership_contract import resolve_custom_saved_original_key
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        trial = {
            "id": "trial-orig-d-live",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"A": [{"chord": "D", "bars": 4}, {"chord": "G", "bars": 4}, {"chord": "A", "bars": 4}]},
        }
        session = _shape_catalog_session(cpl_active_progression=dict(trial))
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-orig-d-live",
            "custom_home_key": "C",
            "active": {**trial, "original_key_center": "C"},
        }
        self.assertEqual(resolve_custom_saved_original_key(session, trial), "D")


class TestCustomGuitarDoesNotInheritPerfectG(unittest.TestCase):
    def test_trial_song_custom_parks_perfect_g_shape(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from guitar_capo import (
            isolate_jam_from_catalog_guitar_shape,
            live_capo_shape_source_id,
            owner_guitar_concert_key,
        )
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        trial = {
            "id": "trial-gtr-d",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
        }
        session = _shape_catalog_session(
            studio_page="backing",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            display_key="D",
            concert_key="D",
            instrument="Guitar",
            guitar_capo_enabled=False,
            guitar_capo_shape_key="G",
            guitar_capo_sounding_key="G",
            _capo_shape_seed_source_id=PERFECT_PICK,
            cpl_active_progression=trial,
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
        )
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-gtr-d",
            "custom_home_key": "D",
            "active": trial,
        }
        ctx = BackingContext(
            source="custom_progression",
            source_label="Custom",
            active_song_id="custom::trial-gtr-d",
            song_title="Trial Song",
            key="D",
            display_key="D",
            concert_key="D",
            bpm=100,
            style="Custom",
            groove="Pop",
            progression=["D"],
            sbi_material_kind="custom",
        )
        set_backing_context(session, ctx)
        live = live_capo_shape_source_id(session)
        self.assertTrue(str(live).startswith("custom::"), live)
        isolate_jam_from_catalog_guitar_shape(session)
        self.assertFalse(bool(session.get("guitar_capo_enabled")))
        sounding = owner_guitar_concert_key(session, fallback="G")
        self.assertTrue(str(sounding).startswith("D"), sounding)
        self.assertFalse(str(sounding).startswith("G"))


class TestJamCDoesNotInheritPerfectG(unittest.TestCase):
    def test_jam_c_guitar_sounding_is_c_not_perfect_g(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import apply_specialized_jam_practice_key, jam_owns_left_panel_key
        from guitar_capo import (
            isolate_jam_from_catalog_guitar_shape,
            live_capo_shape_source_id,
            owner_guitar_concert_key,
        )

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            display_key="G",
            concert_key="G",
            instrument="Guitar",
            guitar_capo_enabled=True,
            guitar_capo_shape_key="G",
            _capo_shape_seed_source_id=PERFECT_PICK,
            improv_entry_mode="Jam Session Generator",
            improv_intelligence_tab="Entry & Jam",
            improv_jam_key="C",
            improv_jam_session={"id": "jam-c-1", "key": "C"},
        )
        ctx = BackingContext(
            source="entry_jam",
            source_label="Jam",
            active_song_id="generated::Jam Session Generator::cmaj",
            song_title="Jam Session Generator",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=110,
            style="Jazz Swing",
            groove="Jazz Swing",
            progression=["C", "Am", "F", "G"],
            entry_mode="Jam Session Generator",
        )
        set_backing_context(session, ctx)
        self.assertTrue(str(live_capo_shape_source_id(session)).startswith("generated::jam"))
        isolate_jam_from_catalog_guitar_shape(session)
        self.assertTrue(bool(session.get("guitar_capo_enabled")))
        from guitar_capo import shape_tonic_only

        self.assertEqual(shape_tonic_only(str(session.get("guitar_capo_shape_key") or "")), "G")
        self.assertEqual(owner_guitar_concert_key(session, fallback="G"), "C")
        session["studio_page"] = "creative"
        self.assertTrue(jam_owns_left_panel_key(session))
        applied = apply_specialized_jam_practice_key(session, "Db")
        self.assertTrue(str(applied or session.get("improv_jam_key")).startswith("Db"))
        self.assertEqual(session.get("improv_jam_key"), "Db")
        self.assertEqual(session.get("concert_key"), "Db")
        # Musician-facing BaseWeb labels use Unicode flats — must seal Db, not D.
        applied_flat = apply_specialized_jam_practice_key(session, "D♭ major")
        self.assertTrue(str(applied_flat).startswith("Db"), applied_flat)
        self.assertEqual(session.get("concert_key"), "Db")
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK, get_practice_concert_key

        self.assertEqual(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK), "Db")
        session["improv_jam_key"] = "C"
        session["_streamlit_widgets_locked_this_run"] = True
        session.pop("_improv_jam_key_mounted_this_run", None)
        applied_locked = apply_specialized_jam_practice_key(session, "Db")
        self.assertTrue(str(applied_locked).startswith("Db"))
        self.assertEqual(session.get("concert_key"), "Db")
        self.assertEqual(session.get("improv_jam_key"), "Db")
        self.assertEqual(session.get("_pending_improv_jam_key"), "Db")
        from creative_key_sync import creative_entry_concert_key, flush_pending_creative_major_keys
        from guitar_capo import owner_guitar_concert_key

        session["display_key"] = "C"
        session["improv_jam_key"] = "C"
        flush_pending_creative_major_keys(session)
        self.assertEqual(session.get("improv_jam_key"), "Db")
        self.assertTrue(str(creative_entry_concert_key(session)).startswith("Db"))
        self.assertTrue(str(owner_guitar_concert_key(session, fallback="G")).startswith("Db"))

        session["improv_jam_key"] = "C"
        session["_improv_jam_key_mounted_this_run"] = True
        session["_pending_improv_jam_key"] = "Db"
        flush_pending_creative_major_keys(session)
        self.assertEqual(session.get("_pending_improv_jam_key"), "Db")
        from creative_key_sync import seed_jam_concert_widget_before_mount

        seeded = seed_jam_concert_widget_before_mount(session)
        self.assertTrue(str(seeded).startswith("Db"), seeded)
        self.assertTrue(str(session.get("improv_jam_key") or "").startswith("Db"))

    def test_jam_db_survives_hydrate_despite_perfect_catalog_g(self) -> None:
        """Refresh must keep Jam Db while Global Active Catalog stays Perfect G."""
        from creative_key_sync import (
            apply_specialized_jam_practice_key,
            restore_jam_visit_practice_key_after_hydrate,
        )
        from creative_session_state import (
            CREATIVE_SESSION_KEY,
            CreativeSession,
            hydrate_creative_session_after_restore,
        )
        from music_persistent_state import _reapply_core_practice_globals_from_payload
        from songs.key_state import PENDING_DISPLAY_KEY
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK, get_practice_concert_key

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            display_key="G",
            concert_key="G",
            improv_entry_mode="Jam Session Generator",
            improv_intelligence_tab="Entry & Jam",
            improv_jam_key="C",
            improv_jam_session={"id": "jam-db-1", "key": "C", "sections": {"Jam": ["C", "Am"]}},
            _jam_session_generator_session_id="jam-db-1",
        )
        session[CREATIVE_SESSION_KEY] = CreativeSession(
            session_id="jam-db-1",
            tool_type="jam_session_generator",
            entry_mode="Jam Session Generator",
            concert_key="C",
            display_key="C",
            style="Jazz Swing",
            sections={"Jam": ["C", "Am"]},
        ).to_dict()
        applied = apply_specialized_jam_practice_key(session, "Db")
        self.assertTrue(str(applied).startswith("Db"), applied)
        self.assertEqual(
            str(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK) or ""),
            "Db",
        )
        # Simulate reboot: catalog G is restored into core/live while jam tool persists.
        session["display_key"] = "G"
        session["concert_key"] = "G"
        session[PENDING_DISPLAY_KEY] = "G"
        session["improv_jam_key"] = "C"
        session.pop("_pending_improv_jam_key", None)
        session.pop("_pk_user_commit_token", None)
        hydrate_creative_session_after_restore(session)
        _reapply_core_practice_globals_from_payload(
            session, {"studio_page": "creative", "display_key": "G"}
        )
        restore_jam_visit_practice_key_after_hydrate(session)
        pending = str(session.get(PENDING_DISPLAY_KEY) or "").strip()
        self.assertTrue(pending.startswith("Db"), pending)
        self.assertTrue(str(session.get("improv_jam_key") or "").startswith("Db"))
        self.assertTrue(str(session.get("concert_key") or "").startswith("Db"))
        sticky = str(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK) or "")
        self.assertTrue(sticky.startswith("Db"), sticky)
        # H5: Global Active Catalog pick remains Perfect.
        self.assertEqual(session.get("active_catalog_pick_key"), PERFECT_PICK)
        self.assertEqual(session.get("song"), "Perfect")

    def test_leftover_style_jam_eb_does_not_beat_sealed_jam_db(self) -> None:
        from backing_practice_key_control import jam_generator_authoritative_concert_key
        from creative_key_sync import restore_jam_visit_practice_key_after_hydrate
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK, get_practice_concert_key

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            display_key="Eb",
            concert_key="Eb",
            improv_entry_mode="Jam Session Generator",
            improv_intelligence_tab="Entry & Jam",
            improv_jam_key="Db",
            improv_jam_session={"id": "jam-db-live", "key": "Db", "sections": {"Jam": ["Db", "Bbm"]}},
            _jam_session_generator_session_id="jam-db-live",
            _pending_improv_jam_key="Db",
            _pk_user_commit_token="Db",
        )
        session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
            "practice_key_token": "Eb",
            "key_owner": "style_jam",
            "entry_mode": "Style Jam Mode",
        }
        from songs.practice_key_state import set_practice_concert_key

        set_practice_concert_key(session, "Db", pick_key=CREATIVE_JAM_SESSION_PICK)
        tok = jam_generator_authoritative_concert_key(session)
        self.assertTrue(str(tok).startswith("Db"), tok)
        restore_jam_visit_practice_key_after_hydrate(session)
        self.assertTrue(str(session.get("improv_jam_key") or "").startswith("Db"))
        self.assertTrue(str(session.get("concert_key") or "").startswith("Db"))
        self.assertTrue(str(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK) or "").startswith("Db"))

    def test_refresh_style_jam_eb_cannot_beat_jam_owner_db(self) -> None:
        """First incorrect field on refresh: leftover Style Jam Eb becoming canonical."""
        from backing_practice_key_control import jam_generator_authoritative_concert_key
        from creative_key_sync import restore_jam_visit_practice_key_after_hydrate
        from creative_session_state import CreativeSession, set_creative_session
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK, get_practice_concert_key, set_practice_concert_key

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            display_key="Eb",
            concert_key="Eb",
            improv_entry_mode="Jam Session Generator",
            improv_intelligence_tab="Entry & Jam",
            improv_jam_key="Eb",
            improv_jam_session={"id": "jam-db-live", "key": "C", "sections": {"Jam": ["C", "Am"]}},
            _jam_session_generator_session_id="jam-db-live",
        )
        session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
            "practice_key_token": "Eb",
            "key_owner": "style_jam",
            "entry_mode": "Style Jam Mode",
        }
        session.pop("_pending_improv_jam_key", None)
        session.pop("_pk_user_commit_token", None)
        set_practice_concert_key(session, "Db", pick_key=CREATIVE_JAM_SESSION_PICK)
        set_creative_session(
            session,
            CreativeSession(
                session_id="jam-db-live",
                tool_type="jam_session_generator",
                entry_mode="Jam Session Generator",
                concert_key="Db",
                display_key="Db",
                style="Jazz Swing",
                sections={"Jam": ["Db", "Bbm"]},
            ),
        )
        tok = jam_generator_authoritative_concert_key(session)
        self.assertTrue(str(tok).startswith("Db"), tok)
        restore_jam_visit_practice_key_after_hydrate(session)
        self.assertTrue(str(session.get("improv_jam_key") or "").startswith("Db"))
        self.assertTrue(str(session.get("concert_key") or "").startswith("Db"))
        self.assertFalse(str(session.get("improv_jam_key") or "").startswith("Eb"))
        self.assertTrue(str(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK) or "").startswith("Db"))


class TestMotifFocusDropsLeftoverCustom(unittest.TestCase):
    def test_perfect_motif_does_not_caption_trial_song(self) -> None:
        from practice_focus_creative import format_creative_practice_focus_caption
        from songs.music_source import LAST_CUSTOM_STATE_KEY, SOURCE_CATALOG, ACTIVE_MUSIC_SOURCE_KEY

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            improv_intelligence_tab="Phrase / Motif",
            improv_entry_mode="Song-Based Improvisation",
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            focus="Strumming",
            cpl_active_progression={
                "name": "Trial Song",
                "id": "trial-focus-leftover",
                "original_key_center": "D",
            },
        )
        session[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-focus-leftover",
            "custom_home_key": "D",
            "active": session["cpl_active_progression"],
        }
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertNotIn("Trial Song", caption)
        self.assertNotIn(" · Custom · ", caption)
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))


class TestSbiCustomBackingActiveSongBanner(unittest.TestCase):
    def test_nested_sbi_custom_backing_banner_shows_trial_not_perfect(self) -> None:
        """Backing Jam from SBI Custom must not leave ACTIVE SONG as Catalog Perfect."""
        from backing_context import build_song_improv_context, set_backing_context
        from creative_source_ownership_contract import resolve_custom_saved_original_key
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            LAST_CUSTOM_STATE_KEY,
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            active_source_labels,
        )
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        trial = {
            "id": "trial-banner-1",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
            "bpm": 100,
        }
        session = _shape_catalog_session(
            studio_page="backing",
            display_key="D",
            concert_key="D",
            improv_entry_mode="Song-Based Improvisation",
            improv_song_source="Custom progression",
            sbi_preview_source="Custom progression",
            cpl_active_progression=dict(trial),
            active_catalog_pick_key=PERFECT_PICK,
        )
        session[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        session["song"] = "Perfect"
        session["_backing_explicit_handoff_source"] = "song_improv"
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-banner-1",
            "custom_home_key": "D",
            "active": trial,
        }
        ctx = build_song_improv_context(session)
        set_backing_context(session, ctx)
        self.assertEqual(ctx.source, "song_improv")
        self.assertEqual(ctx.sbi_material_kind, "custom")
        self.assertEqual(ctx.song_title, "Trial Song")
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(session))
        kind, detail = active_source_labels(
            session,
            catalog_title="Perfect",
            catalog_artist="Ed Sheeran",
            custom_name="Trial Song",
        )
        self.assertEqual(kind, "Custom Progression")
        self.assertIn("Trial Song", detail)
        self.assertNotIn("Perfect", detail)
        self.assertEqual(resolve_custom_saved_original_key(session), "D")

    def test_songs_page_still_shows_catalog_perfect_after_sbi_custom_preview(self) -> None:
        """H5: nested projection must not steal Songs ACTIVE SONG off Catalog."""
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            LAST_CUSTOM_STATE_KEY,
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            active_source_labels,
        )

        trial = {
            "id": "trial-h5",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"A": [{"chord": "D", "bars": 4}]},
        }
        session = _shape_catalog_session(
            studio_page="picker",
            improv_entry_mode="Song-Based Improvisation",
            improv_song_source="Custom progression",
            sbi_preview_source="Custom progression",
            cpl_active_progression=dict(trial),
            active_catalog_pick_key=PERFECT_PICK,
        )
        session[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-h5",
            "custom_home_key": "D",
            "active": trial,
        }
        kind, detail = active_source_labels(
            session,
            catalog_title="Perfect",
            catalog_artist="Ed Sheeran",
            custom_name="Trial Song",
        )
        self.assertEqual(kind, "Song")
        self.assertIn("Perfect", detail)
        self.assertNotIn("Trial Song", detail)


class TestSbiCustomRestoresTrialOriginalKeyD(unittest.TestCase):
    def test_new_song_skip_does_not_block_sbi_custom_last_custom_d(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY, start_new_progression
        from songs.music_source import (
            CPL_SKIP_LAST_CUSTOM_RESTORE_KEY,
            LAST_CUSTOM_STATE_KEY,
            install_last_custom_into_live_cpl,
        )

        trial = {
            "id": "trial-skip-d",
            "name": "Trial Song",
            "original_key_center": "D",
            "user_locked_home_key": True,
            "original_sections": {
                "Verse": [{"chord": "Em", "bars": 1}, {"chord": "D", "bars": 1}],
            },
        }
        session = _shape_catalog_session(
            studio_page="creative",
            improv_entry_mode="Song-Based Improvisation",
            improv_song_source="Custom progression",
            sbi_preview_source="Custom progression",
            cpl_active_progression=start_new_progression(),
        )
        session[CPL_SKIP_LAST_CUSTOM_RESTORE_KEY] = True
        session[LAST_CUSTOM_STATE_KEY] = {
            "name": "Trial Song",
            "pick_key": "custom::trial-skip-d",
            "custom_home_key": "D",
            "active": trial,
        }
        self.assertTrue(
            install_last_custom_into_live_cpl(
                session, reset_practice_key_to_original=False, ignore_new_song_skip=True
            )
        )
        live = session.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"))


class TestJamCIgnoresLeftoverCustomCommitD(unittest.TestCase):
    def test_jam_authoritative_c_not_custom_commit_d(self) -> None:
        from backing_practice_key_control import jam_generator_authoritative_concert_key

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            display_key="D",
            concert_key="D",
            _pk_user_commit_token="D",
            improv_entry_mode="Jam Session Generator",
            improv_intelligence_tab="Entry & Jam",
            improv_jam_key="C",
            improv_jam_session={"id": "jam-c-isolate", "key": "C"},
        )
        self.assertEqual(jam_generator_authoritative_concert_key(session), "C")

    def test_creative_jam_sidebar_c_to_db_writes_jam_key_before_refresh(self) -> None:
        from creative_key_sync import (
            apply_specialized_jam_practice_key,
            jam_owns_left_panel_key,
            sync_sidebar_creative_concert_key,
        )

        session = _shape_catalog_session(
            studio_page="creative",
            song="Perfect",
            selected_song={
                "title": "Perfect",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            active_catalog_pick_key=PERFECT_PICK,
            display_key="C",
            concert_key="C",
            improv_entry_mode="Jam Session Generator",
            improv_intelligence_tab="Entry & Jam",
            improv_jam_key="C",
            improv_jam_session={"id": "jam-c-db", "key": "C", "sections": {"Jam": ["C", "Am"]}},
        )
        self.assertTrue(jam_owns_left_panel_key(session))
        session["display_key"] = "Db"
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(session.get("improv_jam_key"), "Db")
        self.assertEqual(session.get("concert_key"), "Db")
        self.assertEqual(session.get("_pending_improv_jam_key"), "Db")
        apply_specialized_jam_practice_key(session, "Db")
        self.assertEqual(session.get("improv_jam_key"), "Db")


if __name__ == "__main__":
    unittest.main()
