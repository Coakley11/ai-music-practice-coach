"""Per-identity Original/Practice Key contract: Composition, Perfect SBI, Trial Custom."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from composition_document import apply_section_chords, new_composition_document, parse_chord_paste
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library
from composition_songs_bridge import (
    activate_composition_by_pick_key,
    commit_composition_active_song,
    composition_pick_key_for,
    resolve_composition_canonical_keys,
)
from custom_progression_lab import CPL_ACTIVE_KEY
from song_catalog.catalog import format_pick_key
from songs.music_source import LAST_CUSTOM_STATE_KEY, resolve_active_song_keys
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    catalog_pick_has_user_practice_key_override,
    get_practice_concert_key,
    mark_practice_key_user_override,
    set_practice_concert_key,
)


PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")


def _st(ss: dict) -> MagicMock:
    st = MagicMock()
    st.session_state = ss
    return st


def _click_sbi_custom(ss: dict) -> None:
    """Stamp a genuine Song-source Custom click (Streamlit on_change runs first)."""
    from source_session_state import note_explicit_sbi_source_selection

    note_explicit_sbi_source_selection(ss, "Custom progression")


def _composition_in_key(key: str, *, title: str = "My Composition", song_id: str = "comp-g") -> dict:
    doc = new_composition_document(title=title)
    doc["id"] = song_id
    doc["global"]["original_key_center"] = key
    doc["global"]["progression_style"] = ""
    doc["global"]["groove_style"] = "Auto"
    order = list((doc.get("form") or {}).get("section_order") or [])
    if order:
        apply_section_chords(doc, order[0], parse_chord_paste("C Am F G"))
    return doc


def _custom_d_session() -> dict:
    trial = {
        "id": "trial-d",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [{"chord": "D", "bars": 1}, {"chord": "A", "bars": 1}],
        },
        "bpm": 120,
        "time_signature": "4/4",
        "progression_style": "Jazz Swing",
        "groove_style": "Jazz swing",
    }
    return {
        "instrument": "Piano",
        "studio_page": "songs",
        "display_key": "D",
        "concert_key": "D",
        "active_music_source": "custom_progression",
        "active_catalog_pick_key": "custom::trial-d",
        "explicit_music_source_choice": "custom_progression",
        CPL_ACTIVE_KEY: trial,
        LAST_CUSTOM_STATE_KEY: {
            "pick_key": "custom::trial-d",
            "custom_home_key": "D",
            "active": trial,
        },
        PRACTICE_KEY_BY_SOURCE_KEY: {"custom::trial-d": "D"},
        COMPOSER_LIBRARY_KEY: {},
        "backing_groove_style": "Jazz swing",
        "composer_saved_compositions": {},
    }


def _perfect_session(**extra: object) -> dict:
    session = {
        "studio_page": "creative",
        "instrument": "Piano",
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
        },
        "active_catalog_pick_key": PERFECT_PICK,
        "display_key": "G",
        "concert_key": "G",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "improv_intelligence_tab": "Song-Based Improvisation",
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "G"},
    }
    session.update(extra)
    return session


class TestCompositionOwnerKeys(unittest.TestCase):
    def test_custom_d_to_composition_g_opens_g_g(self) -> None:
        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        ok = activate_composition_by_pick_key(st, composition_pick_key_for(doc))
        self.assertTrue(ok)
        orig, practice = resolve_composition_canonical_keys(ss, doc)
        self.assertTrue(str(orig).startswith("G"), orig)
        self.assertTrue(str(practice).startswith("G"), practice)
        card_orig, card_pk, _written = resolve_active_song_keys(ss)
        self.assertTrue(str(card_orig).startswith("G"), card_orig)
        self.assertTrue(str(card_pk).startswith("G"), card_pk)
        self.assertFalse(str(ss.get("concert_key") or "").startswith("D"))

    def test_songs_sidebar_callback_persists_composition_db(self) -> None:
        from unittest.mock import patch

        import streamlit as st_mod
        from backing_practice_key_control import (
            OWNER_COMPOSITION,
            canonical_concert_key_for_owner,
            resolve_backing_pk_control_owner,
            seed_backing_practice_key_widget,
        )
        from creative_key_sync import on_sidebar_practice_concert_key_change
        from songs.practice_key_state import get_practice_concert_key

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc))
        pick = composition_pick_key_for(doc)
        ss["studio_page"] = "songs"
        ss["display_key"] = "Db"
        with patch.object(st_mod, "session_state", ss):
            on_sidebar_practice_concert_key_change()
        saved = str(get_practice_concert_key(ss, pick) or "")
        self.assertTrue(saved.startswith("Db") or saved.startswith("C#"), saved)
        orig, practice = resolve_composition_canonical_keys(ss, doc)
        self.assertTrue(str(orig).startswith("G"), orig)
        self.assertTrue(str(practice).startswith("Db") or str(practice).startswith("C#"), practice)

        ss["studio_page"] = "backing"
        self.assertEqual(resolve_backing_pk_control_owner(ss), OWNER_COMPOSITION)
        seeded = seed_backing_practice_key_widget(ss)
        self.assertTrue(str(seeded).startswith("Db") or str(seeded).startswith("C#"), seeded)
        canon = canonical_concert_key_for_owner(ss, OWNER_COMPOSITION)
        self.assertTrue(str(canon).startswith("Db") or str(canon).startswith("C#"), canon)

    def test_active_song_state_db_heals_stale_composition_pick_map(self) -> None:
        from backing_practice_key_control import WIDGET_COMPOSITION, seed_backing_practice_key_widget
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, get_practice_concert_key

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc))
        pick = composition_pick_key_for(doc)
        ss[PRACTICE_KEY_BY_SOURCE_KEY] = {pick: "G"}
        ss["practice_key_user_override_picks"] = [pick]
        ss["active_song_state"] = {
            "pick_key": pick,
            "display_key": "Db",
            "music_source": "composition_song",
        }
        ss["studio_page"] = "backing"
        ss["display_key"] = "G"
        ss[WIDGET_COMPOSITION] = "G"
        orig, practice = resolve_composition_canonical_keys(ss, doc)
        self.assertTrue(str(orig).startswith("G"), orig)
        self.assertTrue(str(practice).startswith("Db") or str(practice).startswith("C#"), practice)
        saved = str(get_practice_concert_key(ss, pick) or "")
        self.assertTrue(saved.startswith("Db") or saved.startswith("C#"), saved)
        seeded = seed_backing_practice_key_widget(ss)
        self.assertTrue(str(seeded).startswith("Db") or str(seeded).startswith("C#"), seeded)
        from backing_context import build_composition_song_context
        from session_widget_safe import apply_pending_widget_hydrates

        ss["display_key"] = "G"
        ss.pop("_streamlit_widgets_locked_this_run", None)
        apply_pending_widget_hydrates(ss)
        live = str(ss.get("display_key") or ss.get("concert_key") or "")
        self.assertTrue(live.startswith("Db") or live.startswith("C#"), live)
        ctx = build_composition_song_context(ss, doc=doc)
        self.assertTrue(
            str(ctx.concert_key).startswith("Db") or str(ctx.concert_key).startswith("C#"),
            ctx.concert_key,
        )

    def test_sbi_custom_reinstalls_trial_over_foreign_live_cpl(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from source_session_state import set_sbi_preview_source
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        ss = _custom_d_session()
        ss[CPL_ACTIVE_KEY] = {
            "id": "comp-shell",
            "name": "My Composition",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        trial = ss[LAST_CUSTOM_STATE_KEY]["active"]
        self.assertTrue(str(trial.get("original_key_center") or "").startswith("D"))
        set_sbi_preview_source(ss, "Custom progression")
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)

    def test_snapshot_does_not_replace_trial_with_generic_shell(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import LAST_CUSTOM_STATE_KEY, snapshot_last_custom_state

        ss = _custom_d_session()
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        snapshot_last_custom_state(ss)
        snap = ss.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str((snap.get("active") or {}).get("name") or snap.get("name") or ""), "Trial Song")
        self.assertTrue(str((snap.get("active") or {}).get("original_key_center") or "").startswith("D"))

    def test_snapshot_does_not_copy_catalog_display_key_onto_trial(self) -> None:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, snapshot_last_custom_state

        ss = _custom_d_session()
        ss["active_music_source"] = "catalog_song"
        ss["explicit_music_source_choice"] = "catalog_song"
        ss["display_key"] = "C"
        ss["concert_key"] = "C"
        ss.pop("custom_workspace_practice_key", None)
        snapshot_last_custom_state(ss)
        snap = ss.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertTrue(str(snap.get("custom_home_key") or "").startswith("D"), snap)
        practice = str(
            snap.get("practice_key") or (snap.get("active") or {}).get("practice_key") or ""
        )
        self.assertFalse(practice.startswith("C") and not practice.startswith("C#"), practice)

    def test_heal_last_custom_from_library_when_snapshot_missing(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from source_session_state import set_sbi_preview_source
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        ss = _custom_d_session()
        trial = dict(ss[LAST_CUSTOM_STATE_KEY]["active"])
        ss.pop(LAST_CUSTOM_STATE_KEY, None)
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        ss["cpl_saved_progressions"] = {"Trial Song": trial}
        ss["custom_recent_active_names"] = ["Trial Song"]
        set_sbi_preview_source(ss, "Custom progression")
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)

    def test_prime_sidebar_does_not_protect_leftover_original_g(self) -> None:
        from sidebar_key_identity import prime_sidebar_practice_key_from_identity
        from songs.practice_key_state import get_practice_concert_key

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "Db", pick_key=pick, allow_restore_original=True)
        mark_practice_key_user_override(ss, pick)
        ss["studio_page"] = "backing"
        ss["display_key"] = "G"
        ss["concert_key"] = "G"
        ss["_pending_display_key"] = "G"
        ss["_pending_display_key_source"] = ""
        ident = prime_sidebar_practice_key_from_identity(ss)
        self.assertEqual(ident.owner, "composition_song")
        saved = str(get_practice_concert_key(ss, pick) or "")
        self.assertTrue(saved.startswith("Db") or saved.startswith("C#"), saved)
        primed = str(ss.get("concert_key") or ss.get("_pending_display_key") or "")
        self.assertTrue(primed.startswith("Db") or primed.startswith("C#"), primed)

    def test_seed_backing_canonical_outranks_leftover_g_widget(self) -> None:
        from backing_practice_key_control import (
            OWNER_COMPOSITION,
            WIDGET_COMPOSITION,
            seed_backing_practice_key_widget,
        )

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "Db", pick_key=pick, allow_restore_original=True)
        mark_practice_key_user_override(ss, pick)
        ss["studio_page"] = "backing"
        ss["display_key"] = "G"
        ss[WIDGET_COMPOSITION] = "G"
        seeded = seed_backing_practice_key_widget(ss)
        self.assertTrue(str(seeded).startswith("Db") or str(seeded).startswith("C#"), seeded)
        self.assertTrue(
            str(ss.get(WIDGET_COMPOSITION) or "").startswith("Db")
            or str(ss.get(WIDGET_COMPOSITION) or "").startswith("C#"),
            ss.get(WIDGET_COMPOSITION),
        )
        self.assertEqual(ss.get("_backing_pk_control_owner") or OWNER_COMPOSITION, OWNER_COMPOSITION)

    def test_ensure_owns_uses_saved_g_not_generic_c(self) -> None:
        from songs.music_source import (
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            ensure_composition_owns_active_song,
            song_picker_composition_option_label,
        )

        ss = _custom_d_session()
        doc = _composition_in_key("G", title="Untitled Song", song_id="comp-g-real")
        save_document_to_library(ss, doc)
        ss[SONG_PICKER_ACTIVE_SOURCE_KEY] = song_picker_composition_option_label()
        ss["_composition_reset_practice_on_ensure"] = True
        owned = ensure_composition_owns_active_song(
            _st(ss), invalidate_backing=lambda _s: None
        )
        self.assertIsInstance(owned, dict)
        self.assertEqual(str(owned.get("id") or ""), "comp-g-real")
        orig, practice = resolve_composition_canonical_keys(ss, owned)
        self.assertTrue(str(orig).startswith("G"), orig)
        self.assertTrue(str(practice).startswith("G"), practice)
        card_orig, card_pk, _written = resolve_active_song_keys(ss)
        self.assertTrue(str(card_orig).startswith("G"), card_orig)
        self.assertTrue(str(card_pk).startswith("G"), card_pk)
        self.assertFalse(str(ss.get("concert_key") or "").startswith("D"))

    def test_composition_g_practice_db_keeps_original_and_survives_refresh(self) -> None:
        from backing_context import build_composition_song_context
        from music_restore_phase import begin_music_script_run
        from session_widget_safe import apply_pending_widget_hydrates

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "Db", pick_key=pick, allow_restore_original=True)
        mark_practice_key_user_override(ss, pick)
        ss["concert_key"] = "Db"
        ctx = build_composition_song_context(ss, doc=doc)
        self.assertTrue(str(ctx.key).startswith("G"), ctx.key)
        self.assertTrue(str(ctx.concert_key).startswith("Db") or str(ctx.concert_key).startswith("C#"), ctx.concert_key)
        orig, practice = resolve_composition_canonical_keys(ss, doc)
        self.assertTrue(str(orig).startswith("G"), orig)
        self.assertTrue(str(practice).startswith("Db") or str(practice).startswith("C#"), practice)

        ss["display_key"] = "G"
        begin_music_script_run(ss)
        apply_pending_widget_hydrates(ss)
        orig2, practice2 = resolve_composition_canonical_keys(ss, doc)
        self.assertTrue(str(orig2).startswith("G"), orig2)
        self.assertTrue(str(practice2).startswith("Db") or str(practice2).startswith("C#"), practice2)
        ctx2 = build_composition_song_context(ss, doc=doc)
        self.assertTrue(str(ctx2.key).startswith("G"), ctx2.key)
        self.assertTrue(str(ctx2.concert_key).startswith("Db") or str(ctx2.concert_key).startswith("C#"), ctx2.concert_key)

    def test_composition_practice_key_cycles_without_stale_banner(self) -> None:
        from backing_context import build_composition_song_context

        ss = {"instrument": "Piano", COMPOSER_LIBRARY_KEY: {}, PRACTICE_KEY_BY_SOURCE_KEY: {}}
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _s: None)
        pick = composition_pick_key_for(doc)
        for token in ("Db", "Eb", "F"):
            set_practice_concert_key(ss, token, pick_key=pick, allow_restore_original=True)
            mark_practice_key_user_override(ss, pick)
            ctx = build_composition_song_context(ss, doc=doc)
            self.assertTrue(str(ctx.key).startswith("G"), ctx.key)
            self.assertTrue(str(ctx.concert_key).startswith(token), ctx.concert_key)
            self.assertTrue(str(ctx.display_key).startswith(token), ctx.display_key)
            orig, practice, _written = resolve_active_song_keys(ss)
            self.assertTrue(str(orig).startswith("G"), orig)
            self.assertTrue(str(practice).startswith(token), practice)

    def test_composition_default_style_feel_is_auto(self) -> None:
        from backing_context import build_composition_song_context
        from backing_context_ui import render_backing_composition_song_context_card

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        commit_composition_active_song(
            st, doc, invalidate_backing=lambda _s: None, reset_practice_to_original=True
        )
        ctx = build_composition_song_context(ss, doc=doc)
        self.assertEqual(str(ctx.style or "Auto"), "Auto")
        self.assertEqual(str(ctx.groove or "Auto").lower(), "auto")
        self.assertNotIn("jazz", str(ctx.groove or "").lower())
        ui = MagicMock()
        render_backing_composition_song_context_card(
            ui, ctx, ss, applied_bpm=int(ctx.bpm or 96), applied_groove=str(ctx.groove or "Auto")
        )
        html_out = str(ui.markdown.call_args[0][0])
        self.assertIn("Auto", html_out)
        self.assertNotIn("Jazz swing", html_out)

    def test_composition_a_does_not_share_practice_key_with_b(self) -> None:
        ss = {"instrument": "Piano", COMPOSER_LIBRARY_KEY: {}, PRACTICE_KEY_BY_SOURCE_KEY: {}}
        doc_a = _composition_in_key("G", title="Comp A", song_id="comp-a")
        doc_b = _composition_in_key("C", title="Comp B", song_id="comp-b")
        save_document_to_library(ss, doc_a)
        save_document_to_library(ss, doc_b)
        st = _st(ss)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc_a))
        pick_a = composition_pick_key_for(doc_a)
        set_practice_concert_key(ss, "Db", pick_key=pick_a, allow_restore_original=True)
        mark_practice_key_user_override(ss, pick_a)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc_b))
        orig_b, pk_b = resolve_composition_canonical_keys(ss, doc_b)
        self.assertTrue(str(orig_b).startswith("C"), orig_b)
        self.assertTrue(str(pk_b).startswith("C"), pk_b)
        self.assertFalse(str(pk_b).startswith("Db"))
        orig_a, pk_a = resolve_composition_canonical_keys(ss, doc_a)
        self.assertTrue(str(orig_a).startswith("G"), orig_a)
        self.assertTrue(str(pk_a).startswith("Db") or str(pk_a).startswith("C#"), pk_a)

    def test_composition_catalog_custom_roundtrip_restores_owners(self) -> None:
        from songs.music_source import SOURCE_CATALOG, SOURCE_CUSTOM

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "Db", pick_key=pick, allow_restore_original=True)
        mark_practice_key_user_override(ss, pick)

        ss["active_catalog_pick_key"] = PERFECT_PICK
        ss["active_music_source"] = SOURCE_CATALOG
        ss["explicit_music_source_choice"] = SOURCE_CATALOG
        ss["selected_song"] = {"title": "Perfect", "key": "G", "pick_key": PERFECT_PICK}
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT_PICK)

        ss["active_catalog_pick_key"] = "custom::trial-d"
        ss["active_music_source"] = SOURCE_CUSTOM
        ss["explicit_music_source_choice"] = SOURCE_CUSTOM
        self.assertTrue(str(get_practice_concert_key(ss, "custom::trial-d") or "").startswith("D"))

        activate_composition_by_pick_key(st, pick)
        orig, practice = resolve_composition_canonical_keys(ss)
        self.assertTrue(str(orig).startswith("G"), orig)
        self.assertTrue(str(practice).startswith("Db") or str(practice).startswith("C#"), practice)
        self.assertTrue(str(get_practice_concert_key(ss, PERFECT_PICK) or "").startswith("C"))
        self.assertTrue(str(get_practice_concert_key(ss, "custom::trial-d") or "").startswith("D"))

    def test_no_post_widget_display_key_mutation(self) -> None:
        from backing_context import build_composition_song_context
        from session_widget_safe import reconcile_practice_key_fields

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        st = _st(ss)
        activate_composition_by_pick_key(st, composition_pick_key_for(doc))
        ss["_streamlit_widgets_locked_this_run"] = True
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "Db", pick_key=pick, allow_restore_original=True)
        mark_practice_key_user_override(ss, pick)
        reconcile_practice_key_fields(ss, authoritative="Db")
        self.assertEqual(ss.get("display_key"), "D")
        self.assertTrue(str(ss.get("_pending_display_key") or "").startswith("Db"))
        build_composition_song_context(ss, doc=doc)
        self.assertEqual(ss.get("display_key"), "D")


class TestPerfectSbiPracticeKey(unittest.TestCase):
    def test_perfect_g_to_c_refresh_stays_c_then_g(self) -> None:
        from music_restore_phase import begin_music_script_run
        from sbi_active_catalog_practice_key import (
            note_sbi_active_user_practice_key_edit,
            prepare_sbi_active_catalog_practice_key,
            sbi_active_canonical_practice_key,
        )
        from session_widget_safe import apply_pending_widget_hydrates

        session = _perfect_session()
        note_sbi_active_user_practice_key_edit(session, "C", pick=PERFECT_PICK)
        self.assertTrue(catalog_pick_has_user_practice_key_override(session, PERFECT_PICK))
        self.assertTrue(str(get_practice_concert_key(session, PERFECT_PICK) or "").startswith("C"))

        session["display_key"] = "G"
        session["concert_key"] = "G"
        begin_music_script_run(session)
        apply_pending_widget_hydrates(session)
        prepare_sbi_active_catalog_practice_key(session)
        self.assertTrue(str(sbi_active_canonical_practice_key(session, "G")).startswith("C"))
        self.assertTrue(
            str(session.get("display_key") or session.get("_pending_display_key") or "").startswith("C")
        )
        self.assertTrue(str(session.get("selected_song", {}).get("key") or "").startswith("G"))

        note_sbi_active_user_practice_key_edit(session, "G", pick=PERFECT_PICK)
        session["display_key"] = "C"
        begin_music_script_run(session)
        apply_pending_widget_hydrates(session)
        prepare_sbi_active_catalog_practice_key(session)
        self.assertTrue(str(sbi_active_canonical_practice_key(session, "C")).startswith("G"))
        self.assertTrue(
            str(session.get("display_key") or session.get("_pending_display_key") or "").startswith("G")
        )


class TestSbiCustomAndActiveTransition(unittest.TestCase):
    def test_resolve_custom_orig_heals_from_library_without_snapshot(self) -> None:
        from creative_source_ownership_contract import resolve_custom_saved_original_key
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        ss = _custom_d_session()
        trial = dict(ss[LAST_CUSTOM_STATE_KEY]["active"])
        ss.pop(LAST_CUSTOM_STATE_KEY, None)
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
        }
        ss["cpl_saved_progressions"] = {"Trial Song": trial}
        orig = resolve_custom_saved_original_key(ss)
        self.assertTrue(str(orig).startswith("D"), orig)
        from source_session_state import set_sbi_preview_source
        from creative_source_ownership_contract import resolve_custom_saved_original_key

        ss = _custom_d_session()
        ss["studio_page"] = "creative"
        ss["improv_entry_mode"] = "Song-Based Improvisation"
        ss["active_catalog_pick_key"] = PERFECT_PICK
        ss["selected_song"] = {"title": "Perfect", "key": "G", "pick_key": PERFECT_PICK}
        ss["display_key"] = "G"
        set_sbi_preview_source(ss, "Custom progression")
        orig = resolve_custom_saved_original_key(ss)
        self.assertTrue(str(orig).startswith("D"), orig)
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)

    def test_trial_custom_to_perfect_active_restores_perfect_not_d(self) -> None:
        from studio_page_state import apply_improv_song_source
        from sbi_active_catalog_practice_key import sbi_active_canonical_practice_key

        ss = _perfect_session(
            display_key="D",
            concert_key="D",
            improv_song_source="Custom progression",
            sbi_preview_source="Custom progression",
            _sbi_custom_sidebar_overlay=True,
            _sbi_custom_visit_pk="D",
        )
        ss[CPL_ACTIVE_KEY] = {
            "id": "trial-d",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
        }
        ss[PRACTICE_KEY_BY_SOURCE_KEY] = {
            PERFECT_PICK: "G",
            "custom::trial-d": "D",
        }
        apply_improv_song_source(
            ss,
            "Active song",
            set_catalog_source=lambda _s: None,
            set_custom_source=lambda _s: None,
        )
        token = sbi_active_canonical_practice_key(ss, "G")
        self.assertTrue(str(token).startswith("G"), token)
        self.assertFalse(str(token).startswith("D"))
        pending = str(ss.get("_pending_display_key") or ss.get("concert_key") or "")
        self.assertTrue(pending.startswith("G"), pending)

        ss2 = dict(ss)
        set_practice_concert_key(ss2, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss2, PERFECT_PICK)
        ss2["display_key"] = "D"
        ss2["sbi_preview_source"] = "Custom progression"
        ss2["improv_song_source"] = "Custom progression"
        apply_improv_song_source(
            ss2,
            "Active song",
            set_catalog_source=lambda _s: None,
            set_custom_source=lambda _s: None,
        )
        token2 = sbi_active_canonical_practice_key(ss2, "G")
        self.assertTrue(str(token2).startswith("C"), token2)

    def test_sync_custom_session_replaces_generic_shell_with_trial(self) -> None:
        from source_session_state import resolve_sbi_preview, sync_custom_session
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        ss = _custom_d_session()
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        ss["custom_session"] = {
            "pick_key": "custom::generic",
            "title": "My Progression",
            "original_key": "C",
            "display_key": "C",
            "sections": {"Verse": ["C"]},
        }
        ss["studio_page"] = "creative"
        ss["sbi_preview_source"] = "Custom progression"
        ss["improv_song_source"] = "Custom progression"
        blob = sync_custom_session(ss)
        self.assertEqual(str((blob or {}).get("title") or ""), "Trial Song")
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)
        preview = resolve_sbi_preview(ss)
        self.assertEqual(str(preview.get("title") or ""), "Trial Song")
        self.assertTrue(str(preview.get("original_key") or "").startswith("D"), preview)
        snap = ss.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str((snap.get("active") or {}).get("name") or ""), "Trial Song")

    def test_sbi_custom_on_change_outranks_leftover_follow_flag(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            note_explicit_sbi_source_selection,
            get_sbi_preview_source,
            set_sbi_preview_source,
        )

        ss = _custom_d_session()
        ss["studio_page"] = "creative"
        ss[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        ss["_last_improv_song_source"] = "Custom progression"
        ss["improv_song_source"] = "Custom progression"
        ss["sbi_preview_source"] = "Active song"
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        note_explicit_sbi_source_selection(ss, "Custom progression")
        set_sbi_preview_source(ss, "Custom progression")
        self.assertFalse(ss.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertEqual(get_sbi_preview_source(ss), "Custom progression")
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)


    def test_custom_d_leftover_db_does_not_survive_composition_activation(self) -> None:
        from songs.music_source import (
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            ensure_composition_owns_active_song,
            song_picker_composition_option_label,
        )

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        ss["active_catalog_pick_key"] = pick
        ss["explicit_music_source_choice"] = "composition_song"
        ss[SONG_PICKER_ACTIVE_SOURCE_KEY] = song_picker_composition_option_label()
        ss["display_key"] = "Db"
        ss["concert_key"] = "Db"
        ss["active_song_state"] = {
            "pick_key": pick,
            "display_key": "Db",
            "music_source": "composition_song",
        }
        ss[PRACTICE_KEY_BY_SOURCE_KEY][pick] = "Db"
        mark_practice_key_user_override(ss, pick)
        ss["_visited_custom_workspace"] = True
        owned = ensure_composition_owns_active_song(
            _st(ss), invalidate_backing=lambda _s: None
        )
        orig, practice = resolve_composition_canonical_keys(ss, owned)
        self.assertTrue(str(orig).startswith("G"), orig)
        self.assertTrue(str(practice).startswith("G"), practice)
        self.assertFalse(str(ss.get("concert_key") or "").startswith("D"))
        self.assertFalse(ss.get("_visited_custom_workspace"))

    def test_composition_default_feel_is_auto(self) -> None:
        from backing_context import build_composition_song_context

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        activate_composition_by_pick_key(_st(ss), composition_pick_key_for(doc))
        ctx = build_composition_song_context(ss, doc=doc)
        self.assertEqual(str(ctx.groove or "").strip().lower(), "auto")
        self.assertIn(str(ctx.style or "").strip().lower(), {"", "auto"})

    def test_composition_audio_uses_owner_sections_not_leftover_selection(self) -> None:
        from backing_context import (
            build_composition_song_context,
            sections_dict_from_backing_context,
            set_backing_context,
        )

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        activate_composition_by_pick_key(_st(ss), composition_pick_key_for(doc))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "Db", pick_key=pick, allow_restore_original=True)
        mark_practice_key_user_override(ss, pick)
        ctx = build_composition_song_context(ss, doc=doc)
        ctx.sections = ["Verse"]
        ctx.section = "Verse"
        set_backing_context(ss, ctx)
        sections = sections_dict_from_backing_context(ss, ctx)
        self.assertTrue(sections, sections)
        chords = [c for row in sections.values() for c in row]
        self.assertTrue(chords, sections)
        self.assertEqual(str(ctx.source), "composition_song")
        self.assertTrue(str(ctx.concert_key).startswith("Db") or str(ctx.concert_key).startswith("C#"), ctx.concert_key)

    def test_sbi_custom_installs_trial_before_widgets(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            install_sbi_custom_identity_before_widgets,
        )

        ss = _custom_d_session()
        ss["studio_page"] = "creative"
        ss[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        ss[SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY] = True
        ss["_last_improv_song_source"] = "Active song"
        ss["improv_song_source"] = "Custom progression"
        ss["sbi_preview_source"] = "Active song"
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        ss["_streamlit_widgets_locked_this_run"] = False
        _click_sbi_custom(ss)
        ok = install_sbi_custom_identity_before_widgets(ss)
        self.assertTrue(ok)
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)
        self.assertTrue(str(ss.get("_sbi_custom_visit_pk") or "").startswith("D"), ss.get("_sbi_custom_visit_pk"))
        self.assertTrue(str(ss.get("display_key_sbi_custom") or "").startswith("D"), ss.get("display_key_sbi_custom"))
        self.assertEqual(str(ss.get("creative_backing_song_source") or ""), "Custom progression")
        self.assertFalse(ss.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))

    def test_sbi_custom_storage_id_uses_trial_not_generic_shell(self) -> None:
        from music_workflow_song_practice import song_practice_storage_id
        from source_session_state import install_sbi_custom_identity_before_widgets
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        ss = _perfect_session()
        custom = _custom_d_session()
        ss[LAST_CUSTOM_STATE_KEY] = custom[LAST_CUSTOM_STATE_KEY]
        ss["improv_song_source"] = "Custom progression"
        ss["_last_improv_song_source"] = "Active song"
        ss["sbi_preview_source"] = "Active song"
        _click_sbi_custom(ss)
        self.assertTrue(install_sbi_custom_identity_before_widgets(ss))
        src, sid = song_practice_storage_id(ss)
        self.assertEqual(src, "custom")
        self.assertEqual(sid, "trial-d")
        self.assertNotEqual(sid, "custom")
        self.assertTrue(ss.get("_nested_custom_sbi_backing"))

    def test_nested_custom_sbi_owns_backing_over_lagged_catalog_ctx(self) -> None:
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        ss = _perfect_session()
        ss["studio_page"] = "backing"
        ss["_nested_custom_sbi_backing"] = True
        ss["_backing_released_specialized_context"] = True
        ss["sbi_preview_source"] = "Custom progression"
        ss["improv_song_source"] = "Custom progression"
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(ss))

    def test_pages_backing_from_sbi_custom_skips_catalog_hub(self) -> None:
        from backing_source_navigation import (
            BACKING_INTENT_FROM_CREATIVE,
            BACKING_OPEN_INTENT_KEY,
            BACKING_OPEN_PROVENANCE_KEY,
            BACKING_PROVENANCE_CREATIVE,
            BACKING_PROVENANCE_SONGS,
            prepare_global_backing_navigation,
        )
        from songs.music_source import (
            LAST_CUSTOM_STATE_KEY,
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
        )
        from source_session_state import install_sbi_custom_identity_before_widgets

        ss = _perfect_session()
        custom = _custom_d_session()
        ss[LAST_CUSTOM_STATE_KEY] = custom[LAST_CUSTOM_STATE_KEY]
        ss["active_music_source"] = SOURCE_CATALOG
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        ss["explicit_music_source_choice"] = SOURCE_CATALOG
        ss["song_picker_active_source"] = "Song Selection (catalog song)"
        ss["_backing_released_specialized_context"] = True
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT_PICK)
        ss["improv_song_source"] = "Custom progression"
        ss["_last_improv_song_source"] = "Active song"
        ss["sbi_preview_source"] = "Active song"
        _click_sbi_custom(ss)
        self.assertTrue(install_sbi_custom_identity_before_widgets(ss))
        self.assertFalse(ss.get("_backing_released_specialized_context"))
        prepare_global_backing_navigation(ss, from_page="creative")
        self.assertEqual(ss.get(BACKING_OPEN_INTENT_KEY), BACKING_INTENT_FROM_CREATIVE)
        self.assertEqual(ss.get(BACKING_OPEN_PROVENANCE_KEY), BACKING_PROVENANCE_CREATIVE)
        self.assertNotEqual(ss.get(BACKING_OPEN_PROVENANCE_KEY), BACKING_PROVENANCE_SONGS)
        saved = str(get_practice_concert_key(ss, PERFECT_PICK) or "")
        self.assertTrue(saved.startswith("C"), saved)

    def test_active_click_after_custom_does_not_reinstall_trial(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            install_sbi_custom_identity_before_widgets,
            stamp_sbi_active_leave_intent,
        )
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        ss = _perfect_session()
        custom = _custom_d_session()
        ss[LAST_CUSTOM_STATE_KEY] = custom[LAST_CUSTOM_STATE_KEY]
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT_PICK)
        ss["improv_song_source"] = "Custom progression"
        ss["_last_improv_song_source"] = "Active song"
        ss["sbi_preview_source"] = "Active song"
        _click_sbi_custom(ss)
        self.assertTrue(install_sbi_custom_identity_before_widgets(ss))
        ss[SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY] = True
        stamp_sbi_active_leave_intent(ss)
        self.assertFalse(install_sbi_custom_identity_before_widgets(ss))
        self.assertEqual(str(ss.get("improv_song_source") or ""), "Active song")
        self.assertFalse(ss.get("_sbi_custom_sidebar_overlay"))
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        self.assertFalse(custom_sbi_owns_sidebar_practice_key(ss))
        saved = str(get_practice_concert_key(ss, PERFECT_PICK) or "")
        self.assertTrue(saved.startswith("C"), saved)
        self.assertFalse(saved.startswith("D"))

    def test_clear_follow_active_keeps_widget_seen_after_custom(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            clear_sbi_follow_active_after_explicit_catalog,
            note_explicit_sbi_source_selection,
        )

        ss = {
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY: True,
        }
        clear_sbi_follow_active_after_explicit_catalog(ss)
        self.assertFalse(ss.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertTrue(ss.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY))
        ss[SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY] = True
        note_explicit_sbi_source_selection(ss, "Custom progression")
        self.assertTrue(ss.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY))

    def test_seed_honors_active_click_after_custom_radio_seen(self) -> None:
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            seed_sbi_custom_radio_before_render,
        )

        ss = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "improv_song_source": "Active song",
            "sbi_preview_source": "Custom progression",
            "_last_improv_song_source": "Custom progression",
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY: True,
            "creative_workspace_state": {RESTORE_SBI_CUSTOM_SOURCE_KEY: True},
        }
        self.assertEqual(seed_sbi_custom_radio_before_render(ss), "Active song")
        self.assertEqual(ss.get("improv_song_source"), "Active song")
        self.assertFalse(ss.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

    def test_seed_honors_active_click_after_flush_rewrites_last(self) -> None:
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            seed_sbi_custom_radio_before_render,
        )

        ss = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Active song",
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY: True,
            "creative_workspace_state": {RESTORE_SBI_CUSTOM_SOURCE_KEY: True},
        }
        self.assertEqual(seed_sbi_custom_radio_before_render(ss), "Active song")
        self.assertFalse(ss.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

    def test_seed_remount_active_without_seen_still_restores_custom(self) -> None:
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            seed_sbi_custom_radio_before_render,
        )

        ss = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "improv_song_source": "Active song",
            "sbi_preview_source": "Custom progression",
            "_last_improv_song_source": "Custom progression",
            "creative_workspace_state": {RESTORE_SBI_CUSTOM_SOURCE_KEY: True},
        }
        self.assertEqual(seed_sbi_custom_radio_before_render(ss), "Custom progression")
        self.assertEqual(ss.get("improv_song_source"), "Custom progression")
        self.assertTrue(ss.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

    def test_overlay_clear_pops_nested_after_active_flush(self) -> None:
        from source_session_state import clear_sbi_custom_sidebar_overlay_if_needed

        ss = _perfect_session()
        ss["_nested_custom_sbi_backing"] = True
        ss["_backing_explicit_handoff_source"] = "song_improv"
        ss["improv_song_source"] = "Active song"
        ss["sbi_preview_source"] = "Active song"
        ss["studio_page"] = "creative"
        clear_sbi_custom_sidebar_overlay_if_needed(ss)
        self.assertFalse(ss.get("_nested_custom_sbi_backing"))
        self.assertNotEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "song_improv")

    def test_shared_leak_does_not_clear_sealed_perfect_c(self) -> None:
        from music_workflow_song_practice import reconcile_practice_key_after_active_source_change

        ss = _perfect_session()
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT_PICK)
        ss["practice_key_by_source"]["custom::My Progression"] = "C"
        ss["_sbi_custom_sealed_catalog_pk"] = "C"
        ss["_sbi_custom_sealed_catalog_pick"] = PERFECT_PICK
        reconcile_practice_key_after_active_source_change(
            ss,
            pick_key=PERFECT_PICK,
            original_key="G",
            previous_pick_key="custom::My Progression",
            force_source_change=True,
        )
        saved = str(get_practice_concert_key(ss, PERFECT_PICK) or "")
        self.assertTrue(saved.startswith("C"), saved)

    def test_active_click_clears_overlay_and_keeps_perfect_c(self) -> None:
        from source_session_state import (
            clear_sbi_custom_sidebar_overlay_if_needed,
            install_sbi_custom_identity_before_widgets,
        )
        from songs.practice_key_state import get_practice_concert_key
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        ss = _perfect_session()
        custom = _custom_d_session()
        ss[LAST_CUSTOM_STATE_KEY] = custom[LAST_CUSTOM_STATE_KEY]
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT_PICK)
        ss["improv_song_source"] = "Custom progression"
        ss["_last_improv_song_source"] = "Active song"
        ss["sbi_preview_source"] = "Active song"
        _click_sbi_custom(ss)
        self.assertTrue(install_sbi_custom_identity_before_widgets(ss))
        ss["improv_song_source"] = "Active song"
        ss["sbi_preview_source"] = "Active song"
        clear_sbi_custom_sidebar_overlay_if_needed(ss)
        self.assertFalse(ss.get("_sbi_custom_sidebar_overlay"))
        self.assertFalse(ss.get("_nested_custom_sbi_backing"))
        saved = str(get_practice_concert_key(ss, PERFECT_PICK) or "")
        self.assertTrue(saved.startswith("C"), saved)

    def test_sbi_custom_overlay_installs_trial_over_my_progression_shell(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from source_session_state import prepare_sbi_custom_sidebar_display_key

        ss = _custom_d_session()
        ss["studio_page"] = "creative"
        ss["improv_song_source"] = "Custom progression"
        ss["sbi_preview_source"] = "Custom progression"
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        st = _st(ss)
        prepare_sbi_custom_sidebar_display_key(st, ss)
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)

    def test_sbi_custom_install_does_not_write_trial_d_into_perfect_store(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            install_sbi_custom_identity_before_widgets,
        )
        from songs.music_source import LAST_CUSTOM_STATE_KEY
        from songs.practice_key_state import get_practice_concert_key

        custom = _custom_d_session()
        ss = _perfect_session()
        ss[LAST_CUSTOM_STATE_KEY] = custom[LAST_CUSTOM_STATE_KEY]
        ss["studio_page"] = "creative"
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT_PICK)
        ss["improv_song_source"] = "Custom progression"
        ss["_last_improv_song_source"] = "Active song"
        ss[SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY] = True
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        ss["_streamlit_widgets_locked_this_run"] = False
        _click_sbi_custom(ss)
        ok = install_sbi_custom_identity_before_widgets(ss)
        self.assertTrue(ok)
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)
        saved = str(get_practice_concert_key(ss, PERFECT_PICK) or "")
        self.assertTrue(saved.startswith("C"), saved)
        self.assertFalse(saved.startswith("D"))
        self.assertFalse(str(ss.get("concert_key") or "").startswith("D"), ss.get("concert_key"))
        self.assertFalse(str(ss.get("display_key") or "").startswith("D"), ss.get("display_key"))
        self.assertTrue(str(ss.get("_sbi_custom_visit_pk") or "").startswith("D"), ss.get("_sbi_custom_visit_pk"))
        self.assertEqual(str(ss.get("_sbi_custom_sealed_catalog_pk") or "")[:1], "C")
        self.assertEqual(ss.get("_sbi_custom_sealed_catalog_pick"), PERFECT_PICK)

    def test_sbi_custom_same_run_widget_click_before_onchange_installs_trial(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            install_sbi_custom_identity_before_widgets,
        )
        from songs.practice_key_state import get_practice_concert_key

        ss = _perfect_session()
        custom = _custom_d_session()
        ss[LAST_CUSTOM_STATE_KEY] = custom[LAST_CUSTOM_STATE_KEY]
        ss[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        ss["_last_improv_song_source"] = "Custom progression"
        ss["improv_song_source"] = "Custom progression"
        ss["sbi_preview_source"] = "Active song"
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        _click_sbi_custom(ss)
        ok = install_sbi_custom_identity_before_widgets(ss)
        self.assertTrue(ok)
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)
        saved = str(get_practice_concert_key(ss, PERFECT_PICK) or "")
        self.assertFalse(saved.startswith("D"))

    def test_flush_same_run_custom_click_commits_owner_before_widgets(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            install_sbi_custom_identity_before_widgets,
        )
        from songs.practice_key_state import get_practice_concert_key
        from studio_page_state import flush_pending_improv_song_source

        ss = _perfect_session()
        custom = _custom_d_session()
        ss[LAST_CUSTOM_STATE_KEY] = custom[LAST_CUSTOM_STATE_KEY]
        ss[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        ss["_last_improv_song_source"] = "Custom progression"
        ss["improv_song_source"] = "Custom progression"
        ss["sbi_preview_source"] = "Active song"
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        flush_pending_improv_song_source(ss)
        self.assertEqual(str(ss.get("improv_song_source") or ""), "Custom progression")
        self.assertEqual(str(ss.get("sbi_preview_source") or ""), "Custom progression")
        self.assertFalse(ss.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        ok = install_sbi_custom_identity_before_widgets(ss)
        self.assertTrue(ok)
        live = ss.get(CPL_ACTIVE_KEY) or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertTrue(str(live.get("original_key_center") or "").startswith("D"), live)
        saved = str(get_practice_concert_key(ss, PERFECT_PICK) or "")
        self.assertFalse(saved.startswith("D"))

    def test_sbi_custom_follow_active_leftover_does_not_steal_perfect(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            install_sbi_custom_identity_before_widgets,
        )

        ss = _perfect_session()
        ss[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        ss["_last_improv_song_source"] = "Custom progression"
        ss["improv_song_source"] = "Custom progression"
        ss["sbi_preview_source"] = "Custom progression"
        ss[CPL_ACTIVE_KEY] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
        }
        ok = install_sbi_custom_identity_before_widgets(ss)
        self.assertFalse(ok)
        self.assertTrue(ss.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertEqual(str((ss.get(CPL_ACTIVE_KEY) or {}).get("name") or ""), "My Progression")

    def test_flush_leftover_custom_remount_stays_on_perfect_active(self) -> None:
        from source_session_state import SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY
        from studio_page_state import flush_pending_improv_song_source

        ss = _perfect_session()
        ss[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        ss["_last_improv_song_source"] = "Custom progression"
        ss["improv_song_source"] = "Custom progression"
        ss["sbi_preview_source"] = "Custom progression"
        flush_pending_improv_song_source(ss)
        self.assertEqual(str(ss.get("improv_song_source") or ""), "Active song")
        self.assertEqual(str(ss.get("sbi_preview_source") or ""), "Active song")

    def test_no_post_mount_display_key_mutation(self) -> None:
        from session_widget_safe import apply_pending_widget_hydrates, safe_session_assign

        ss = _custom_d_session()
        doc = _composition_in_key("G")
        save_document_to_library(ss, doc)
        activate_composition_by_pick_key(_st(ss), composition_pick_key_for(doc))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "Db", pick_key=pick, allow_restore_original=True)
        mark_practice_key_user_override(ss, pick)
        ss["display_key"] = "Db"
        ss["_streamlit_widgets_locked_this_run"] = True
        ss["_pending_display_key"] = "G"
        ss["_pending_display_key_source"] = "composition"
        apply_pending_widget_hydrates(ss)
        self.assertTrue(str(ss.get("display_key") or "").startswith("Db"), ss.get("display_key"))
        safe_session_assign(ss, "display_key", "G", widget_safe=True)
        self.assertTrue(str(ss.get("display_key") or "").startswith("Db"), ss.get("display_key"))


if __name__ == "__main__":
    unittest.main()
