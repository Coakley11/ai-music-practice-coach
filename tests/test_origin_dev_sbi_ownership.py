"""Phase B: Catalog/Custom SBI and Creative source ownership."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from active_song_transition import (
    COMMITTED_ACTIVE_SONG_CHANGE,
    PREVIEW_OR_EDIT,
    TEMPORARY_WORKFLOW_OWNER,
    classify_active_song_transition,
    mark_committed_active_song_change,
    may_initialize_practice_key_from_original,
)
from music_source_ownership import maybe_reset_practice_key_on_source_activation
from practice_focus_creative import format_creative_practice_focus_caption
from song_catalog.catalog import format_pick_key
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    LAST_CUSTOM_STATE_KEY,
    SOURCE_CATALOG,
    begin_explicit_catalog_selection,
    commit_catalog_active_song,
    commit_explicit_music_source_choice,
)
from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
from source_session_state import (
    EXPLICIT_SBI_SOURCE_CLICK_KEY,
    SBI_ACTIVE_LEAVE_INTENT_KEY,
    set_sbi_preview_source,
)

PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL_ID = "trial-phase-b-uuid"
TRIAL_PICK = f"custom::{TRIAL_ID}"


class _FakeSt:
    def __init__(self, ss: dict) -> None:
        self.session_state = ss

    def rerun(self) -> None:
        return None


class _LockedSession(dict):
    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self.illegal_writes: list[str] = []
        self.locked = False

    def __setitem__(self, key, value):  # type: ignore[override]
        if self.locked and key == "display_key":
            self.illegal_writes.append(str(value))
            raise RuntimeError("display_key cannot be modified after the widget is instantiated")
        super().__setitem__(key, value)


def _trial_active() -> dict:
    return {
        "id": TRIAL_ID,
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [{"chord": "D", "bars": 2}, {"chord": "A", "bars": 2}],
        },
        "bpm": 100,
    }


def _click_sbi_custom(session: dict) -> None:
    session[EXPLICIT_SBI_SOURCE_CLICK_KEY] = "Custom progression"
    session["_sbi_preview_write_via"] = "after_sbi_source_radio_custom"
    set_sbi_preview_source(session, "Custom progression")


def _click_sbi_active(session: dict) -> None:
    session.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
    session[SBI_ACTIVE_LEAVE_INTENT_KEY] = True
    session["_sbi_preview_write_via"] = "after_sbi_source_radio_active"
    set_sbi_preview_source(session, "Active song")


def _perfect_session(**extra: object) -> dict:
    session = {
        "studio_page": "creative",
        "instrument": "Guitar",
        "focus": "Tone",
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
        },
        "active_catalog_pick_key": PERFECT_PICK,
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        "original_key": "G",
        "display_key": "C",
        "concert_key": "C",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "improv_intelligence_tab": "Song-Based Improvisation",
        "practice_key_by_source": {PERFECT_PICK: "C", TRIAL_PICK: "F"},
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": _trial_active(),
        },
        "cpl_active_progression": {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 4}]},
        },
    }
    session.update(extra)
    return session


class TestTransitionStampFirst(unittest.TestCase):
    def test_leftover_switch_catalog_intent_is_not_committed(self) -> None:
        session = _perfect_session(_key_transition_intent="switch_catalog")
        self.assertEqual(classify_active_song_transition(session), PREVIEW_OR_EDIT)
        self.assertFalse(may_initialize_practice_key_from_original(session, surface="picker"))

    def test_page_alone_is_never_committed(self) -> None:
        session = _perfect_session(studio_page="practice")
        self.assertNotEqual(
            classify_active_song_transition(session, surface="practice"),
            COMMITTED_ACTIVE_SONG_CHANGE,
        )

    def test_sbi_custom_preview_is_temporary(self) -> None:
        session = _perfect_session()
        _click_sbi_custom(session)
        self.assertEqual(classify_active_song_transition(session), TEMPORARY_WORKFLOW_OWNER)
        self.assertFalse(may_initialize_practice_key_from_original(session))


class TestTrialUuidReplacesMyProgressionShell(unittest.TestCase):
    def test_sbi_custom_installs_trial_not_generic_shell(self) -> None:
        session = _perfect_session()
        _click_sbi_custom(session)
        live = session.get("cpl_active_progression") or {}
        self.assertEqual(str(live.get("name") or ""), "Trial Song")
        self.assertEqual(str(live.get("id") or ""), TRIAL_ID)
        self.assertEqual(str(live.get("original_key_center") or ""), "D")
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Trial Song", caption)
        self.assertIn("SBI Custom", caption)
        self.assertNotIn("My Progression", caption)
        self.assertNotIn("Perfect", caption)
        self.assertNotIn("Jam Generator", caption)

    def test_banner_uses_trial_uuid_not_my_progression_shell(self) -> None:
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY, active_source_labels

        session = _perfect_session()
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        _click_sbi_custom(session)
        kind, detail = active_source_labels(
            session,
            catalog_title="Perfect",
            catalog_artist="Ed Sheeran",
            custom_name="My Progression",
        )
        self.assertEqual(kind, "Custom Progression")
        self.assertIn("Trial Song", detail)
        self.assertNotIn("My Progression", detail)
        self.assertNotIn("Perfect", detail)

    def test_last_custom_trial_outranks_chordful_my_progression_shell(self) -> None:
        from creative_source_ownership_contract import resolve_custom_song_display_title

        session = _perfect_session()
        title = resolve_custom_song_display_title(session, fallback="My Progression")
        self.assertEqual(title, "Trial Song")

    def test_display_title_accepts_streamlit_session_state_mapping(self) -> None:
        """Regression: isinstance(st.session_state, dict) is False — must not empty the session."""
        from creative_source_ownership_contract import resolve_custom_song_display_title

        class _FakeSessionState:
            def __init__(self, data: dict) -> None:
                object.__setattr__(self, "_data", dict(data))

            def get(self, key, default=None):
                return self._data.get(key, default)

            def __getitem__(self, key):
                return self._data[key]

            def __setitem__(self, key, value):
                self._data[key] = value

            def __contains__(self, key):
                return key in self._data

            def pop(self, key, default=None):
                return self._data.pop(key, default)

        raw = _perfect_session()
        _click_sbi_custom(raw)
        # Leave live CPL as the generic shell so LAST_CUSTOM must supply Trial.
        raw["cpl_active_progression"] = {
            "id": "generic-shell",
            "name": "My Progression",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 4}]},
        }
        session = _FakeSessionState(raw)
        self.assertNotIsInstance(session, dict)
        title = resolve_custom_song_display_title(session, fallback="My Progression")
        self.assertEqual(title, "Trial Song")


class TestPerfectGcSurvivesTemporaryTrial(unittest.TestCase):
    def test_temporary_sbi_custom_does_not_reset_perfect_c(self) -> None:
        session = _perfect_session()
        _click_sbi_custom(session)
        changed = maybe_reset_practice_key_on_source_activation(session, surface="sbi_custom")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(session, PERFECT_PICK), "C")
        self.assertEqual(get_practice_concert_key(session, TRIAL_PICK), "F")
        _click_sbi_active(session)
        changed = maybe_reset_practice_key_on_source_activation(session, surface="sbi_active")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(session, PERFECT_PICK), "C")
        self.assertEqual(get_practice_concert_key(session, TRIAL_PICK), "F")
        self.assertEqual(str(session.get("display_key") or ""), "C")


class TestGenuineActiveSongChangeResets(unittest.TestCase):
    def test_reactivate_perfect_after_committed_trial_returns_to_original_g(self) -> None:
        session = _perfect_session(studio_page="songs")
        commit_catalog_active_song(
            _FakeSt(session),
            pick_key=PERFECT_PICK,
            selected_song=dict(session["selected_song"]),
            original_key="G",
            display_key="C",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        set_practice_concert_key(session, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        session["display_key"] = "C"
        session["concert_key"] = "C"
        from songs.music_source import commit_custom_active_song

        commit_custom_active_song(
            _FakeSt(session),
            _trial_active(),
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        begin_explicit_catalog_selection(session)
        commit_catalog_active_song(
            _FakeSt(session),
            pick_key=PERFECT_PICK,
            selected_song={
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            original_key="G",
            display_key="F",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(session.get("display_key") or ""), "G")
        self.assertEqual(get_practice_concert_key(session, PERFECT_PICK) or "G", "G")

    def test_committed_stamp_without_saved_pk_initializes_original(self) -> None:
        session = _perfect_session()
        session["practice_key_by_source"] = {TRIAL_PICK: "F"}
        session["display_key"] = "F"
        session["concert_key"] = "F"
        mark_committed_active_song_change(session)
        changed = maybe_reset_practice_key_on_source_activation(session, surface="songs")
        self.assertTrue(changed)
        self.assertEqual(str(session.get("display_key") or session.get("concert_key") or ""), "G")


class TestRefreshPreservesSbiSubmode(unittest.TestCase):
    def test_custom_preview_survives_classify_after_refresh_like_remount(self) -> None:
        session = _perfect_session()
        _click_sbi_custom(session)
        remount = dict(session)
        remount.pop("_committed_active_song_change", None)
        self.assertEqual(str(remount.get("sbi_preview_source") or ""), "Custom progression")
        self.assertEqual(classify_active_song_transition(remount), TEMPORARY_WORKFLOW_OWNER)
        self.assertFalse(maybe_reset_practice_key_on_source_activation(remount, surface="refresh"))
        self.assertEqual(get_practice_concert_key(remount, PERFECT_PICK), "C")
        self.assertEqual(get_practice_concert_key(remount, TRIAL_PICK), "F")


class TestJamFocusMetadataRelease(unittest.TestCase):
    def test_sbi_custom_trial_does_not_keep_jewish_ballad(self) -> None:
        session = _perfect_session(
            improv_entry_mode="Jam Session Generator",
            improv_jam_style="Jewish ballad",
            improv_intelligence_tab="Song-Based Improvisation",
        )
        _click_sbi_custom(session)
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Trial Song", caption)
        self.assertIn("SBI Custom", caption)
        self.assertNotIn("Jam Generator", caption)
        self.assertNotIn("Jewish ballad", caption)
        self.assertNotIn("Perfect", caption)

    def test_return_to_sbi_active_perfect_drops_trial_and_jam(self) -> None:
        session = _perfect_session(
            improv_entry_mode="Jam Session Generator",
            improv_jam_style="Jewish ballad",
            improv_intelligence_tab="Song-Based Improvisation",
        )
        _click_sbi_custom(session)
        _click_sbi_active(session)
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertIn("SBI Catalog", caption)
        self.assertNotIn("Trial Song", caption)
        self.assertNotIn("Jam Generator", caption)
        self.assertNotIn("Jewish ballad", caption)


class TestPollutedJamBalladFocusDoesNotStealSbiActive(unittest.TestCase):
    """Combined-matrix Gate 2: stale Jam Ballad must not win Focus after SBI Active Perfect."""

    def _polluted_jam_ballad(self, **extra: object) -> dict:
        session = _perfect_session(
            improv_intelligence_tab="Entry & Jam",
            improv_entry_mode="Song-Based Improvisation",
            improv_jam_style="Ballad",
            improv_jam_key="C",
            improv_jam_session={
                "id": "Ballad",
                "style": "Ballad",
                "key": "C",
                "ensemble": "Jazz trio",
                "bpm": 70,
            },
            _jam_session_generator_session_id="Ballad",
            _generated_jam_key_owner_active=True,
            _generated_jam_key_context={
                "generated_session_id": "Ballad",
                "practice_tonic": "C",
                "practice_mode": "major",
                "practice_key_token": "C",
                "key_owner": "jam_session_generator",
                "entry_mode": "Jam Session Generator",
            },
        )
        session.update(extra)
        return session

    def test_sbi_active_perfect_focus_not_jam_generator_ballad(self) -> None:
        session = self._polluted_jam_ballad()
        # Missions-clear remount pollution: Entry & Jam hosts Play Song-Based with
        # a leftover Jam Session Generator entry string.
        session["improv_entry_mode"] = "Jam Session Generator"
        from creative_session_state import CreativeSession, set_creative_session

        set_creative_session(
            session,
            CreativeSession(
                session_id="polluted-sbi-active",
                tool_type="song_based_improvisation",
                entry_mode="Song-Based Improvisation",
                song_source="Active song",
            ),
        )
        _click_sbi_active(session)
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertNotIn("Jam Generator", caption)
        self.assertNotIn("Ballad", caption)
        self.assertEqual(str(session.get("original_key") or ""), "G")
        self.assertEqual(str(session.get("display_key") or ""), "C")

    def test_practice_key_c_does_not_project_stale_jam_into_focus(self) -> None:
        from creative_key_sync import apply_specialized_jam_practice_key, jam_owns_left_panel_key
        from sbi_active_catalog_practice_key import sbi_active_catalog_owns_practice_key

        session = self._polluted_jam_ballad()
        self.assertTrue(sbi_active_catalog_owns_practice_key(session))
        self.assertFalse(jam_owns_left_panel_key(session))
        # Sidebar Practice Key C must seal Catalog Perfect, not project Jam Ballad.
        applied = apply_specialized_jam_practice_key(session, "C")
        self.assertEqual(applied, "")
        self.assertEqual(str(session.get("improv_entry_mode") or ""), "Song-Based Improvisation")
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertNotIn("Jam Generator", caption)
        self.assertNotIn("Ballad", caption)

    def test_legitimate_jam_owner_still_shows_ballad(self) -> None:
        session = self._polluted_jam_ballad(
            improv_entry_mode="Jam Session Generator",
            improv_jam_style="Ballad",
        )
        from creative_session_state import CreativeSession, set_creative_session

        set_creative_session(
            session,
            CreativeSession(
                session_id="legit-jam",
                tool_type="jam_session_generator",
                entry_mode="Jam Session Generator",
            ),
        )
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Jam Generator", caption)
        self.assertIn("Ballad", caption)

    def test_jam_to_sbi_active_clears_jam_focus_authority(self) -> None:
        session = self._polluted_jam_ballad(improv_entry_mode="Jam Session Generator")
        from creative_session_state import CreativeSession, set_creative_session

        set_creative_session(
            session,
            CreativeSession(
                session_id="switch-jam",
                tool_type="jam_session_generator",
                entry_mode="Jam Session Generator",
            ),
        )
        self.assertIn("Jam Generator", format_creative_practice_focus_caption(session))
        _click_sbi_active(session)
        session["improv_entry_mode"] = "Song-Based Improvisation"
        set_creative_session(
            session,
            CreativeSession(
                session_id="switch-sbi",
                tool_type="song_based_improvisation",
                entry_mode="Song-Based Improvisation",
                song_source="Active song",
            ),
        )
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertNotIn("Jam Generator", caption)
        self.assertNotIn("Ballad", caption)

    def test_return_to_jam_restores_legitimate_ballad_focus(self) -> None:
        session = self._polluted_jam_ballad()
        _click_sbi_active(session)
        session["improv_entry_mode"] = "Jam Session Generator"
        from creative_session_state import CreativeSession, set_creative_session

        set_creative_session(
            session,
            CreativeSession(
                session_id="return-jam",
                tool_type="jam_session_generator",
                entry_mode="Jam Session Generator",
            ),
        )
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Jam Generator", caption)
        self.assertIn("Ballad", caption)


class TestPhraseMotifSidebarOwnership(unittest.TestCase):
    def test_phrase_motif_keeps_perfect_not_trial(self) -> None:
        from sidebar_key_identity import resolve_sidebar_key_identity

        session = _perfect_session(
            improv_intelligence_tab="Phrase / Motif",
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
        )
        ident = resolve_sidebar_key_identity(session)
        self.assertNotEqual(str(ident.owner or ""), "custom_progression")
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertNotIn("Trial Song", caption)
        self.assertNotIn("Jam Generator", caption)


class TestNoLateMountedWidgetWrites(unittest.TestCase):
    def test_unstamped_maybe_reset_does_not_write_locked_display_key(self) -> None:
        session = _LockedSession(_perfect_session())
        session["_streamlit_widgets_locked_this_run"] = True
        session.locked = True
        st_like = SimpleNamespace(session_state=session)
        changed = maybe_reset_practice_key_on_source_activation(
            session, st_like=st_like, surface="picker"
        )
        self.assertFalse(changed)
        self.assertEqual(session.illegal_writes, [])
        self.assertEqual(session.get("display_key"), "C")
        self.assertEqual(get_practice_concert_key(session, PERFECT_PICK), "C")

    def test_same_pick_committed_remount_keeps_saved_c(self) -> None:
        session = _perfect_session()
        commit_explicit_music_source_choice(session, SOURCE_CATALOG)
        changed = maybe_reset_practice_key_on_source_activation(session, surface="picker")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(session, PERFECT_PICK), "C")
        self.assertEqual(str(session.get("display_key") or ""), "C")


class TestMissionsLeftoverCustomDoesNotOwn(unittest.TestCase):
    def test_missions_tab_reclaims_catalog_perfect(self) -> None:
        session = _perfect_session(
            improv_intelligence_tab="Missions",
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
        )
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Perfect", caption)
        self.assertNotIn("Trial Song", caption)


class TestSidebarOriginalKeySbiCustomNotCatalogG(unittest.TestCase):
    """Polluted Perfect G must not win the sidebar Original Key under SBI Custom Trial."""

    def test_polluted_perfect_g_does_not_force_over_trial_d(self) -> None:
        from source_session_state import (
            resolve_sidebar_original_key_for_caption,
            sidebar_force_catalog_original_key,
        )

        session = _perfect_session()
        # Stale Catalog Perfect G remains in session / selected_song.
        self.assertEqual(session["selected_song"]["key"], "G")
        self.assertEqual(session["active_catalog_pick_key"], PERFECT_PICK)
        _click_sbi_custom(session)
        session["display_key"] = "D"
        session["concert_key"] = "D"
        session["cpl_active_progression"] = _trial_active()
        session["active_catalog_pick_key"] = TRIAL_PICK
        session["_sbi_custom_sidebar_overlay"] = True
        # Remount pollution: radio flaps toward Active while Custom still owns Trial.
        session["improv_song_source"] = "Active song"
        session["sbi_preview_source"] = "Custom progression"

        self.assertFalse(sidebar_force_catalog_original_key(session))
        caption = resolve_sidebar_original_key_for_caption(session, current_original="G")
        self.assertEqual(caption, "D")
        self.assertNotEqual(caption, "G")

    def test_sbi_custom_original_d_practice_f(self) -> None:
        from source_session_state import resolve_sidebar_original_key_for_caption

        session = _perfect_session()
        _click_sbi_custom(session)
        session["cpl_active_progression"] = _trial_active()
        session["display_key"] = "F"
        session["concert_key"] = "F"
        set_practice_concert_key(
            session, "F", pick_key=TRIAL_PICK, allow_restore_original=True, commit_catalog_practice_key=True
        )
        caption = resolve_sidebar_original_key_for_caption(session, current_original="G")
        self.assertEqual(caption, "D")
        self.assertEqual(get_practice_concert_key(session, TRIAL_PICK), "F")

    def test_switch_back_to_catalog_perfect_restores_original_g(self) -> None:
        from source_session_state import (
            resolve_sidebar_original_key_for_caption,
            sidebar_force_catalog_original_key,
        )

        session = _perfect_session()
        _click_sbi_custom(session)
        session["cpl_active_progression"] = _trial_active()
        self.assertEqual(
            resolve_sidebar_original_key_for_caption(session, current_original="G"),
            "D",
        )
        _click_sbi_active(session)
        session["improv_song_source"] = "Active song"
        session["active_catalog_pick_key"] = PERFECT_PICK
        session.pop("_sbi_custom_sidebar_overlay", None)
        session["display_key"] = "C"
        session["concert_key"] = "C"
        session["catalog_session"] = {
            "pick_key": PERFECT_PICK,
            "original_key": "G",
            "selected_song": dict(session["selected_song"]),
        }
        self.assertTrue(sidebar_force_catalog_original_key(session))
        caption = resolve_sidebar_original_key_for_caption(session, current_original="D")
        self.assertEqual(caption, "G")

    def test_return_to_sbi_custom_restores_trial_original_and_practice(self) -> None:
        from source_session_state import resolve_sidebar_original_key_for_caption

        session = _perfect_session()
        _click_sbi_custom(session)
        session["cpl_active_progression"] = _trial_active()
        set_practice_concert_key(
            session, "F", pick_key=TRIAL_PICK, allow_restore_original=True, commit_catalog_practice_key=True
        )
        _click_sbi_active(session)
        session["improv_song_source"] = "Active song"
        session.pop("_sbi_custom_sidebar_overlay", None)
        # Return to Custom Trial.
        _click_sbi_custom(session)
        session["cpl_active_progression"] = _trial_active()
        session["display_key"] = "F"
        session["concert_key"] = "F"
        caption = resolve_sidebar_original_key_for_caption(session, current_original="G")
        self.assertEqual(caption, "D")
        self.assertEqual(get_practice_concert_key(session, TRIAL_PICK), "F")


if __name__ == "__main__":
    unittest.main()
