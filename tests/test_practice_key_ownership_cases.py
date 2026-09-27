"""Canonical Practice-Key ownership cases A / B / C + Mission-context release safety.

Case A — true active-source/song switch (normal mode): new source → Original PK.
Case B — fixed-family ON: new source → family member (not Original).
Case C — temporary Creative/SBI visit: park/restore underlying owner's last PK.

Mission-context reconstruction during release/hydrate must not mutate a mounted
``display_key`` widget (alternate path via ``maybe_reset_practice_key_on_source_activation``).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from active_song_transition import (
    TEMPORARY_WORKFLOW_OWNER,
    classify_active_song_transition,
    may_initialize_practice_key_from_original,
)
from music_source_ownership import (
    _release_creative_transport_authority,
    maybe_reset_practice_key_on_source_activation,
)
from song_catalog.catalog import format_pick_key
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    LAST_CUSTOM_STATE_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    commit_catalog_active_song,
    commit_custom_active_song,
    commit_explicit_music_source_choice,
)
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)
from source_session_state import (
    EXPLICIT_SBI_SOURCE_CLICK_KEY,
    SBI_ACTIVE_LEAVE_INTENT_KEY,
    set_sbi_preview_source,
)


PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")
SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")
TRIAL_ID = "trial-pk-ownership"
TRIAL_PICK = f"custom::{TRIAL_ID}"


class _FakeSt:
    def __init__(self, ss: dict) -> None:
        self.session_state = ss

    def rerun(self) -> None:
        return None


class _RejectDisplayKeyAssign(dict):
    """Fail like Streamlit when ``display_key`` is assigned after the widget mounts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked = False
        self.illegal_writes: list[str] = []

    def __setitem__(self, key, value):
        if self.locked and str(key) == "display_key":
            self.illegal_writes.append(f"display_key={value!r}")
            raise RuntimeError(
                f"StreamlitAPIException: cannot assign display_key after widget ({value!r})"
            )
        return super().__setitem__(key, value)


def _trial_active() -> dict:
    return {
        "id": TRIAL_ID,
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [{"chord": "D", "bars": 2}, {"chord": "A", "bars": 2}],
        },
        "bpm": 100,
        "practice_key": "D",
    }


def _catalog_perfect(practice: str = "D", **extra) -> dict:
    ss = {
        "studio_page": "practice",
        "instrument": "Guitar",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT,
        },
        "active_catalog_pick_key": PERFECT,
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        "original_key": "G",
        "display_key": practice,
        "concert_key": practice,
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT: practice, TRIAL_PICK: "F"},
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": _trial_active(),
        },
        "cpl_active_progression": _trial_active(),
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "improv_intelligence_tab": "Song-Based Improvisation",
    }
    ss.update(extra)
    return ss


def _click_sbi_custom(session: dict) -> None:
    session[EXPLICIT_SBI_SOURCE_CLICK_KEY] = "Custom progression"
    session["_sbi_preview_write_via"] = "after_sbi_source_radio_custom"
    set_sbi_preview_source(session, "Custom progression")


def _click_sbi_composition(session: dict) -> None:
    session[EXPLICIT_SBI_SOURCE_CLICK_KEY] = "Composition"
    session["_sbi_preview_write_via"] = "after_sbi_source_radio_composition"
    set_sbi_preview_source(session, "Composition")


def _click_sbi_active(session: dict) -> None:
    session.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
    session[SBI_ACTIVE_LEAVE_INTENT_KEY] = True
    session["_sbi_preview_write_via"] = "after_sbi_source_radio_active"
    set_sbi_preview_source(session, "Active song")


def _enable_fixed_e_cs(session: dict) -> None:
    from practice_key_mode import (
        FIXED_PRACTICE_KEY_FAMILY_ID,
        MODE_FIXED,
        PRACTICE_KEY_MODE_KEY,
        family_option_id,
    )

    session[PRACTICE_KEY_MODE_KEY] = MODE_FIXED
    session[FIXED_PRACTICE_KEY_FAMILY_ID] = family_option_id("E", "C#")
    session["practice_panel_fixed_practice_key"] = family_option_id("E", "C#")


def _make_composition_doc(ss: dict, *, title: str = "Sharp Major Comp", key: str = "C# major"):
    from composition_document import (
        apply_section_chords,
        apply_structure_template,
        bootstrap_from_vision,
        ordered_sections,
        parse_chord_paste,
    )
    from composition_session_state import save_document_to_library, set_active_document
    from composition_songs_bridge import composition_pick_key_for

    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="ownership cases",
        title=title,
        key=key,
        bpm=100,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(
        doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C# F# G#m B")
    )
    set_active_document(ss, doc, checkpoint=False)
    save_document_to_library(ss, doc)
    return doc, composition_pick_key_for(doc)


class TestCaseATrueActiveSourceSwitchNormal(unittest.TestCase):
    def test_1_catalog_song_a_to_b_initializes_original(self) -> None:
        ss = _catalog_perfect(practice="D")
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=PERFECT,
            selected_song=dict(ss["selected_song"]),
            original_key="G",
            display_key="D",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        # Clear Shape sticky so a true switch initializes from Original.
        store = ss.get(PRACTICE_KEY_BY_SOURCE_KEY)
        if isinstance(store, dict):
            store.pop(SHAPE, None)

        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=SHAPE,
            selected_song={
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "key": "Bm",
                "pick_key": SHAPE,
            },
            original_key="Bm",
            display_key="Bm",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(ss.get("display_key") or ""), "Bm")
        self.assertEqual(get_practice_concert_key(ss, SHAPE) or "Bm", "Bm")
        self.assertNotEqual(str(ss.get("display_key") or ""), "D")

    def test_2_catalog_to_custom_true_switch_original(self) -> None:
        ss = _catalog_perfect(practice="D")
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        # Remove parked Custom F so true activation can init from Original D.
        store = ss.get(PRACTICE_KEY_BY_SOURCE_KEY)
        if isinstance(store, dict):
            store.pop(TRIAL_PICK, None)

        commit_custom_active_song(
            _FakeSt(ss),
            _trial_active(),
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_CUSTOM)
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK) or "D", "D")

    def test_3_custom_to_composition_true_switch_original(self) -> None:
        ss = _catalog_perfect(practice="D")
        commit_custom_active_song(
            _FakeSt(ss),
            _trial_active(),
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        set_practice_concert_key(ss, "F", pick_key=TRIAL_PICK, allow_restore_original=True)
        ss["display_key"] = "F"
        ss["concert_key"] = "F"

        from composition_songs_bridge import activate_composition_by_pick_key

        doc, pick = _make_composition_doc(ss)
        # No prior Composition sticky — true switch should take Original C#.
        store = ss.get(PRACTICE_KEY_BY_SOURCE_KEY)
        if isinstance(store, dict):
            store.pop(pick, None)

        ok = activate_composition_by_pick_key(_FakeSt(ss), pick)
        self.assertTrue(ok)
        self.assertEqual(str(ss.get("display_key") or ""), "C#")
        self.assertEqual(get_practice_concert_key(ss, pick) or "C#", "C#")
        self.assertNotEqual(str(ss.get("display_key") or ""), "F")
        self.assertNotEqual(str(ss.get("display_key") or ""), "D")
        self.assertEqual(str(doc.get("title") or ""), "Sharp Major Comp")


class TestCaseBFixedFamilyWinsOnTrueSwitch(unittest.TestCase):
    def test_4_catalog_to_shape_under_fixed_family(self) -> None:
        ss = _catalog_perfect(practice="E")
        _enable_fixed_e_cs(ss)
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=PERFECT,
            selected_song=dict(ss["selected_song"]),
            original_key="G",
            display_key="E",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        set_practice_concert_key(ss, "Bm", pick_key=SHAPE, allow_restore_original=True)

        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=SHAPE,
            selected_song={
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
                "pick_key": SHAPE,
            },
            original_key="Bm",
            display_key="Bm",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(ss.get("display_key") or ""), "C#m")
        self.assertEqual(get_practice_concert_key(ss, SHAPE), "C#m")
        self.assertNotEqual(str(ss.get("display_key") or ""), "Bm")

    def test_4b_catalog_to_custom_under_fixed_family(self) -> None:
        ss = _catalog_perfect(practice="E")
        _enable_fixed_e_cs(ss)
        set_practice_concert_key(ss, "F", pick_key=TRIAL_PICK, allow_restore_original=True)
        commit_custom_active_song(
            _FakeSt(ss),
            _trial_active(),
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        self.assertEqual(str(ss.get("display_key") or ""), "E")
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "E")
        self.assertNotEqual(str(ss.get("display_key") or ""), "D")
        self.assertNotEqual(str(ss.get("display_key") or ""), "F")


class TestCaseCTemporarySbiPreservesParkedOwnerPk(unittest.TestCase):
    def test_5_catalog_d_survives_custom_sbi_roundtrip(self) -> None:
        ss = _catalog_perfect(practice="D")
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "D")
        _click_sbi_custom(ss)
        self.assertEqual(classify_active_song_transition(ss), TEMPORARY_WORKFLOW_OWNER)
        self.assertFalse(may_initialize_practice_key_from_original(ss))
        changed = maybe_reset_practice_key_on_source_activation(ss, surface="sbi_custom")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "D")
        # Temporary Custom visit may use Trial F locally without erasing Catalog D.
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "F")

        _click_sbi_active(ss)
        changed = maybe_reset_practice_key_on_source_activation(ss, surface="sbi_active")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "D")
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertNotEqual(str(ss.get("original_key") or ""), "D")  # Original stays G
        self.assertEqual(str(ss.get("original_key") or ""), "G")

    def test_6_catalog_d_survives_composition_sbi_roundtrip(self) -> None:
        ss = _catalog_perfect(practice="D")
        _make_composition_doc(ss)
        _click_sbi_composition(ss)
        self.assertEqual(classify_active_song_transition(ss), TEMPORARY_WORKFLOW_OWNER)
        self.assertFalse(may_initialize_practice_key_from_original(ss))
        changed = maybe_reset_practice_key_on_source_activation(ss, surface="sbi_composition")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "D")
        self.assertEqual(str(ss.get("original_key") or ""), "G")

        _click_sbi_active(ss)
        changed = maybe_reset_practice_key_on_source_activation(ss, surface="sbi_active")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "D")
        self.assertEqual(str(ss.get("display_key") or ""), "D")

    def test_7_custom_f_survives_composition_sbi_leave(self) -> None:
        ss = _catalog_perfect(practice="D")
        commit_custom_active_song(
            _FakeSt(ss),
            _trial_active(),
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        set_practice_concert_key(ss, "F", pick_key=TRIAL_PICK, allow_restore_original=True)
        ss["display_key"] = "F"
        ss["concert_key"] = "F"
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "F")

        _make_composition_doc(ss)
        _click_sbi_composition(ss)
        self.assertEqual(classify_active_song_transition(ss), TEMPORARY_WORKFLOW_OWNER)
        changed = maybe_reset_practice_key_on_source_activation(ss, surface="sbi_composition")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "F")

        # Leave Composition SBI for another Creative workspace (Active / Custom owner).
        _click_sbi_active(ss)
        changed = maybe_reset_practice_key_on_source_activation(ss, surface="creative")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "F")
        self.assertNotEqual(get_practice_concert_key(ss, TRIAL_PICK), "D")

    def test_8_temporary_sbi_does_not_rewrite_underlying_original_or_parked_pk(self) -> None:
        ss = _catalog_perfect(practice="D")
        before_original = str(ss.get("original_key") or "")
        before_catalog_pk = get_practice_concert_key(ss, PERFECT)
        _click_sbi_custom(ss)
        maybe_reset_practice_key_on_source_activation(ss, surface="sbi_custom")
        self.assertEqual(str(ss.get("original_key") or ""), before_original)
        self.assertEqual(get_practice_concert_key(ss, PERFECT), before_catalog_pk)
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_CATALOG)


class TestMissionContextReleaseViaMaybeReset(unittest.TestCase):
    def test_9_10_maybe_reset_release_path_does_not_mutate_mounted_display_key(self) -> None:
        """Alternate Cloud crash path: maybe_reset → release → sync → build_mission_context."""
        from backing_context import build_mission_context, _release_creative_backing_ownership
        from creative_session_state import sync_creative_session_from_session

        ss = _RejectDisplayKeyAssign(
            _catalog_perfect(
                practice="D",
                improv_active_mission="Outline chord tones on beat 1",
                improv_mission_pick="Outline chord tones on beat 1",
                improv_intelligence_tab="Missions",
                creative_improv_intelligence_tab="Missions",
                ii_selected_chord="G",
                ii_selected_section="Verse",
                improv_mission_concert_key="F",
                _mission_backing_handoff_practice_key="F",
                _mission_backing_handoff_written_key="G",
            )
        )
        # Widget already mounted before hydrate / source-activation release.
        ss.locked = True
        ss["_streamlit_widgets_locked_this_run"] = True
        catalog_before = ss["display_key"]

        try:
            # Temporary Creative residue present; Catalog still owns — not a committed switch.
            changed = maybe_reset_practice_key_on_source_activation(
                ss, st_like=SimpleNamespace(session_state=ss), surface="picker"
            )
            _release_creative_transport_authority(ss)
            _release_creative_backing_ownership(ss)
            sync_creative_session_from_session(ss)
            build_mission_context(ss)
        except RuntimeError as exc:
            self.fail(f"Streamlit-invalid display_key write on release path: {exc}")

        self.assertEqual(ss.illegal_writes, [])
        self.assertEqual(ss["display_key"], catalog_before)
        self.assertNotEqual(ss["display_key"], "F")
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
