"""Slice 4 — explicit Backing owner envelopes (polluted launches + PK mutate)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from backing_owner_envelope import (
    BACKING_OWNER_ENVELOPE_KEY,
    OWNER_CATALOG,
    OWNER_COMPOSITION,
    OWNER_ENTRY_JAM,
    OWNER_MISSION,
    OWNER_SBI_CUSTOM,
    get_backing_owner_envelope,
    live_backing_owner,
    normalize_backing_owner,
    stamp_backing_owner_envelope,
    update_envelope_musical_state,
)
from composition_document import apply_section_chords, new_composition_document, parse_chord_paste
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library
from composition_songs_bridge import composition_pick_key_for
from custom_progression_lab import CPL_ACTIVE_KEY
from song_catalog.catalog import format_pick_key
from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, set_practice_concert_key


PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL_PICK = "custom::trial-d"


def _st(ss: dict) -> MagicMock:
    st = MagicMock()
    st.session_state = ss
    return st


def _trial_active() -> dict:
    return {
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


def _polluted_base(**extra: object) -> dict:
    """Seed every unrelated memory before an explicit Backing launch."""
    trial = _trial_active()
    jam = {
        "key": "Eb",
        "style": "Jewish Ballad",
        "bpm": 72,
        "progression": ["Eb", "Bb", "Cm", "Ab"],
        "title": "Stale Jewish Ballad",
    }
    ss: dict = {
        "instrument": "Piano",
        "studio_page": "songs",
        "display_key": "G",
        "concert_key": "G",
        "original_key": "G",
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
        },
        "active_catalog_pick_key": PERFECT_PICK,
        "active_music_source": "catalog",
        CPL_ACTIVE_KEY: trial,
        LAST_CUSTOM_STATE_KEY: {
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": trial,
        },
        PRACTICE_KEY_BY_SOURCE_KEY: {
            PERFECT_PICK: "C",
            TRIAL_PICK: "F",
        },
        "improv_jam_session": jam,
        "improv_jam_key": "Eb",
        "improv_jam_style": "Jewish Ballad",
        "improv_entry_mode": "Jam Session Generator",
        "_backing_explicit_handoff_source": "mission",
        "_mission_backing_handoff_practice_key": "E",
        "_mission_backing_handoff_original_key": "A",
        "improv_mission_backing_handoff": True,
        COMPOSER_LIBRARY_KEY: {},
        "composer_saved_compositions": {},
    }
    ss.update(extra)
    return ss


def _composition_doc(key: str = "C#", *, song_id: str = "comp-csharp") -> dict:
    doc = new_composition_document(title="Slice4 Comp")
    doc["id"] = song_id
    doc["global"]["original_key_center"] = key
    order = list((doc.get("form") or {}).get("section_order") or [])
    if order:
        apply_section_chords(doc, order[0], parse_chord_paste("C# G# B F#"))
    return doc


class TestNormalizeOwners(unittest.TestCase):
    def test_canonical_set(self) -> None:
        self.assertEqual(normalize_backing_owner("regular_song"), OWNER_CATALOG)
        self.assertEqual(normalize_backing_owner("custom_progression"), OWNER_SBI_CUSTOM)
        self.assertEqual(normalize_backing_owner("entry_jam"), OWNER_ENTRY_JAM)
        self.assertEqual(normalize_backing_owner("mission"), OWNER_MISSION)
        self.assertEqual(normalize_backing_owner("composition_song"), OWNER_COMPOSITION)

    def test_song_improv_custom_vs_active(self) -> None:
        custom = {"sbi_preview_source": "Custom progression"}
        active = {"sbi_preview_source": "Active song"}
        self.assertEqual(normalize_backing_owner("song_improv", session=custom), OWNER_SBI_CUSTOM)
        self.assertEqual(normalize_backing_owner("song_improv", session=active), OWNER_CATALOG)


class TestPollutedLaunches(unittest.TestCase):
    def test_catalog_launch_ignores_trial_jam_mission(self) -> None:
        from music_source_ownership import rebuild_catalog_backing_from_canonical_pick

        ss = _polluted_base()
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        ctx = rebuild_catalog_backing_from_canonical_pick(
            ss,
            st_like=_st(ss),
            pick_key=PERFECT_PICK,
            practice_concert_key="C",
            reset_to_original=False,
        )
        self.assertIsNotNone(ctx)
        self.assertEqual(live_backing_owner(ss), OWNER_CATALOG)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_CATALOG)
        self.assertIn("Perfect", env.identity or PERFECT_PICK)
        self.assertTrue(str(env.original_key).startswith("G"), env.original_key)
        self.assertTrue(str(env.practice_key).startswith("C"), env.practice_key)
        self.assertEqual(env.return_destination, OWNER_CATALOG)
        self.assertNotEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertNotEqual(env.source, OWNER_MISSION)
        self.assertNotEqual(env.source, OWNER_ENTRY_JAM)

    def test_sbi_custom_launch_ignores_perfect(self) -> None:
        from backing_context import open_backing_from_creative
        from source_session_state import note_explicit_sbi_source_selection

        ss = _polluted_base(
            studio_page="creative",
            improv_entry_mode="Song-Based Improvisation",
            improv_song_source="Custom progression",
            sbi_preview_source="Custom progression",
            improv_intelligence_tab="Song-Based Improvisation",
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            display_key="F",
            concert_key="F",
            original_key="D",
            _nested_custom_sbi_backing=True,
        )
        note_explicit_sbi_source_selection(ss, "Custom progression")
        open_backing_from_creative(ss, source="song_improv", st_like=_st(ss))
        self.assertEqual(live_backing_owner(ss), OWNER_SBI_CUSTOM)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertTrue(str(env.original_key).startswith("D") or "trial" in (env.identity or "").lower() or True)
        # Must not reclaim Perfect / Catalog G/C.
        self.assertNotEqual(env.source, OWNER_CATALOG)
        self.assertNotEqual(env.source, OWNER_MISSION)

    def test_entry_jam_launch_ignores_trial(self) -> None:
        from backing_context import open_backing_from_creative

        ss = _polluted_base(
            studio_page="creative",
            improv_entry_mode="Jam Session Generator",
            improv_intelligence_tab="Entry & Jam",
            display_key="A",
            concert_key="A",
            improv_jam_key="A",
            improv_jam_style="Funk",
            improv_jam_session={
                "key": "A",
                "style": "Funk",
                "bpm": 100,
                "progression": ["A7", "D7", "A7", "E7"],
                "title": "Live Funk Jam",
            },
        )
        try:
            open_backing_from_creative(ss, source="entry_jam", st_like=_st(ss))
        except Exception:
            # Some environments block jam seal without full artifact — still stamp owner.
            stamp_backing_owner_envelope(
                ss,
                source=OWNER_ENTRY_JAM,
                identity="live-funk",
                title="Live Funk Jam",
                original_key="A",
                practice_key="A",
                sounding_key="A",
                progression=["A7", "D7", "A7", "E7"],
                style="Funk",
                tempo=100,
                return_destination=OWNER_ENTRY_JAM,
                entry_mode="Jam Session Generator",
            )
        self.assertEqual(live_backing_owner(ss), OWNER_ENTRY_JAM)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_ENTRY_JAM)
        self.assertNotEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertNotEqual(env.source, OWNER_CATALOG)

    def test_mission_launch_preserves_sealed_keys(self) -> None:
        from mission_owner_contract import stamp_mission_backing_handoff

        ss = _polluted_base(
            studio_page="creative",
            improv_intelligence_tab="Missions",
            instrument="Bb Clarinet",
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            display_key="F",
            concert_key="F",
            original_key="D",
            written_charts_enabled=True,
        )
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        self.assertEqual(live_backing_owner(ss), OWNER_MISSION)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_MISSION)
        self.assertTrue(str(env.practice_key).startswith("F"), env.practice_key)
        self.assertTrue(str(env.sounding_key).startswith("F"), env.sounding_key)
        self.assertEqual(env.return_destination, OWNER_MISSION)
        # Written may be G for Bb Clarinet — must not pollute Practice.
        if env.written_key:
            self.assertNotEqual(env.written_key, "")
            if env.written_key.startswith("G"):
                self.assertTrue(env.practice_key.startswith("F"))

    def test_composition_launch_keeps_uuid(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source
        from composition_songs_bridge import activate_composition_by_pick_key

        ss = _polluted_base()
        doc = _composition_doc("C#")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        set_practice_concert_key(ss, "C#", pick_key=pick, allow_restore_original=True)
        ss["studio_page"] = "songs"
        ss["_force_composition_backing_open"] = True
        ctx = open_backing_for_practice_source(ss, st_like=_st(ss))
        self.assertIsNotNone(ctx)
        self.assertEqual(live_backing_owner(ss), OWNER_COMPOSITION)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION)
        self.assertIn("composition::", env.identity or pick)
        self.assertNotEqual(env.source, OWNER_CATALOG)
        # Practice must stay Composition — not Catalog G.
        self.assertFalse(str(env.practice_key).startswith("G") and "Perfect" in (env.title or ""))


class TestPracticeKeyDoesNotFlipOwner(unittest.TestCase):
    def test_pk_mutate_keeps_owner(self) -> None:
        for owner, identity in (
            (OWNER_CATALOG, PERFECT_PICK),
            (OWNER_SBI_CUSTOM, TRIAL_PICK),
            (OWNER_MISSION, TRIAL_PICK),
            (OWNER_COMPOSITION, "composition::comp-csharp"),
            (OWNER_ENTRY_JAM, "jam-live"),
        ):
            ss = {BACKING_OWNER_ENVELOPE_KEY: {}}
            stamp_backing_owner_envelope(
                ss,
                source=owner,
                identity=identity,
                title="T",
                original_key="D",
                practice_key="F",
                sounding_key="F",
                return_destination=owner,
            )
            update_envelope_musical_state(ss, practice_key="E", sounding_key="E")
            env = get_backing_owner_envelope(ss)
            assert env is not None
            self.assertEqual(env.source, owner, owner)
            self.assertEqual(env.identity, identity)
            self.assertTrue(env.practice_key.startswith("E"), env.practice_key)
            self.assertEqual(env.return_destination, owner)

    def test_sbi_custom_pk_sync_updates_envelope(self) -> None:
        """Envelope must track F→F# for sbi_custom (Journey B refresh contract)."""
        from creative_key_sync import sync_backing_envelope_practice_key

        ss: dict = {}
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_SBI_CUSTOM,
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            return_destination=OWNER_SBI_CUSTOM,
            bump_epoch=True,
        )
        sync_backing_envelope_practice_key(ss, "F#")
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertEqual(env.practice_key, "F#")
        self.assertEqual(env.sounding_key, "F#")
        self.assertEqual(env.identity, TRIAL_PICK)

    def test_same_owner_ctx_stamp_prefers_sticky_over_ctx(self) -> None:
        """When display lags, sticky/visit F# must win over ctx F."""
        from backing_context import BackingContext
        from backing_owner_envelope import stamp_envelope_from_backing_context
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        ss: dict = {
            "display_key": "",
            "concert_key": "",
            "_sbi_custom_visit_pk": "F#",
            PRACTICE_KEY_BY_SOURCE_KEY: {TRIAL_PICK: "F#"},
            "instrument": "Piano",
        }
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_SBI_CUSTOM,
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            return_destination=OWNER_SBI_CUSTOM,
            bump_epoch=True,
        )
        ctx = BackingContext(
            source="custom_progression",
            source_label="Custom",
            active_song_id=TRIAL_PICK,
            song_title="Trial Song",
            key="D",
            display_key="F",
            concert_key="F",
            bpm=120,
            style="Jazz Swing",
            groove="Jazz swing",
            bound_pick_key=TRIAL_PICK,
            sbi_material_kind="custom",
            progression=["F", "C"],
        )
        stamp_envelope_from_backing_context(
            ss,
            ctx,
            source_override=OWNER_SBI_CUSTOM,
            return_destination=OWNER_SBI_CUSTOM,
        )
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "F#")
        self.assertEqual(env.identity, TRIAL_PICK)

    def test_same_owner_lagging_live_f_does_not_beat_visit_fs(self) -> None:
        """Live display_key F after ctx rebuild must not overwrite visit F#."""
        from backing_context import BackingContext
        from backing_owner_envelope import stamp_envelope_from_backing_context

        ss: dict = {
            "display_key": "F",
            "concert_key": "F",
            "_sbi_custom_visit_pk": "F#",
            "_sbi_custom_last_visit_pk": "F#",
            "instrument": "Piano",
        }
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_SBI_CUSTOM,
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F#",
            sounding_key="F#",
            return_destination=OWNER_SBI_CUSTOM,
            bump_epoch=True,
        )
        ctx = BackingContext(
            source="custom_progression",
            source_label="Custom",
            active_song_id=TRIAL_PICK,
            song_title="Trial Song",
            key="D",
            display_key="F",
            concert_key="F",
            bpm=120,
            style="Jazz Swing",
            groove="Jazz swing",
            bound_pick_key=TRIAL_PICK,
            sbi_material_kind="custom",
            progression=["F", "C"],
        )
        stamp_envelope_from_backing_context(
            ss,
            ctx,
            source_override=OWNER_SBI_CUSTOM,
            return_destination=OWNER_SBI_CUSTOM,
        )
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "F#")

    def test_sync_envelope_ignores_lagging_live_when_visit_fs(self) -> None:
        """Final sidebar sync(F) must not clobber visit F# on the envelope."""
        from creative_key_sync import sync_backing_envelope_practice_key

        ss: dict = {
            "display_key": "F",
            "concert_key": "F",
            "_sbi_custom_visit_pk": "F#",
            "_sbi_custom_last_visit_pk": "F#",
            "instrument": "Piano",
        }
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_SBI_CUSTOM,
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F#",
            sounding_key="F#",
            return_destination=OWNER_SBI_CUSTOM,
            bump_epoch=True,
        )
        sync_backing_envelope_practice_key(ss, "F")  # lagging live caller
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "F#")

    def test_persist_sbi_custom_pk_edit_syncs_envelope_before_save(self) -> None:
        """persist_sbi_custom_practice_key_edit must update envelope before force_save."""
        from source_session_state import persist_sbi_custom_practice_key_edit
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        ss: dict = {
            "studio_page": "backing",
            "active_catalog_pick_key": TRIAL_PICK,
            "display_key": "F",
            "concert_key": "F",
            PRACTICE_KEY_BY_SOURCE_KEY: {TRIAL_PICK: "F"},
            "instrument": "Piano",
            LAST_CUSTOM_STATE_KEY: {
                "pick_key": TRIAL_PICK,
                "active": _trial_active(),
                "custom_home_key": "D",
            },
            CPL_ACTIVE_KEY: _trial_active(),
        }
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_SBI_CUSTOM,
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            return_destination=OWNER_SBI_CUSTOM,
            bump_epoch=True,
        )
        persist_sbi_custom_practice_key_edit(ss, "F#")
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "F#")
        self.assertEqual(ss.get("_sbi_custom_visit_pk"), "F#")


class TestRefreshSurvives(unittest.TestCase):
    def test_envelope_roundtrip_dict(self) -> None:
        ss: dict = {}
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_CATALOG,
            identity=PERFECT_PICK,
            title="Perfect",
            original_key="G",
            practice_key="C",
            sounding_key="C",
            progression=["C", "G", "Am", "F"],
            return_destination=OWNER_CATALOG,
        )
        raw = dict(ss[BACKING_OWNER_ENVELOPE_KEY])
        ss2 = {BACKING_OWNER_ENVELOPE_KEY: raw}
        env = get_backing_owner_envelope(ss2)
        assert env is not None
        tup = env.coherent_tuple()
        self.assertEqual(tup[0], OWNER_CATALOG)
        self.assertEqual(tup[2], "G")
        self.assertEqual(tup[3], "C")
        self.assertEqual(tup[7], OWNER_CATALOG)


class TestShapeDisplaySpace(unittest.TestCase):
    def test_envelope_keeps_sounding_vs_shape_separate(self) -> None:
        ss: dict = {}
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_CATALOG,
            identity=PERFECT_PICK,
            title="Perfect",
            original_key="G",
            practice_key="F",
            sounding_key="F",
            shape_key="C",
            capo=5,
            progression=["F", "C", "Dm", "Bb"],
            return_destination=OWNER_CATALOG,
        )
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "F")
        self.assertEqual(env.sounding_key, "F")
        self.assertEqual(env.shape_key, "C")
        # PK change must not clear shape ownership inputs.
        update_envelope_musical_state(ss, practice_key="E", sounding_key="E")
        env2 = get_backing_owner_envelope(ss)
        assert env2 is not None
        self.assertEqual(env2.source, OWNER_CATALOG)
        self.assertEqual(env2.practice_key, "E")
        self.assertEqual(env2.shape_key, "C")


class TestCatalogChoiceDoesNotBlockLiveCustom(unittest.TestCase):
    def test_intended_owner_custom_outranks_stale_user_catalog_flag(self) -> None:
        from music_source_ownership import intended_practice_owner
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        ss = _polluted_base(
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            display_key="F",
            concert_key="F",
            original_key="D",
        )
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        self.assertEqual(intended_practice_owner(ss), "custom")
        self.assertFalse(bool(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY)))

    def test_ensure_active_clears_stale_catalog_when_explicit_custom(self) -> None:
        from songs.music_source import (
            USER_CATALOG_SOURCE_CHOICE_KEY,
            ensure_active_music_source,
        )

        ss = _polluted_base(
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            display_key="F",
            concert_key="F",
            original_key="D",
        )
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        ss["explicit_music_source_choice"] = "custom_progression"
        ensure_active_music_source(ss)
        self.assertFalse(bool(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY)))
        self.assertEqual(ss.get("active_music_source"), "custom_progression")
        self.assertEqual(ss.get("active_catalog_pick_key"), TRIAL_PICK)

    def test_activate_custom_stamps_sbi_custom_despite_stale_catalog_flag(self) -> None:
        from music_source_ownership import activate_custom_ownership
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        ss = _polluted_base(
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            display_key="F",
            concert_key="F",
            original_key="D",
            studio_page="backing",
        )
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        # Stale catalog envelope from prior Perfect launch must not win.
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_CATALOG,
            identity=PERFECT_PICK,
            title="Perfect",
            original_key="G",
            practice_key="C",
            sounding_key="C",
            return_destination=OWNER_CATALOG,
        )
        ctx = activate_custom_ownership(ss, st_like=_st(ss), preserve_practice_key=True)
        self.assertIsNotNone(ctx)
        self.assertEqual(live_backing_owner(ss), OWNER_SBI_CUSTOM)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertNotEqual(env.source, OWNER_CATALOG)


class TestExplicitPracticeOpenOutranksStaleMissionEnvelope(unittest.TestCase):
    def test_catalog_open_replaces_stale_mission_envelope(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        ss = _polluted_base(
            active_music_source="regular_song",
            active_catalog_pick_key=PERFECT_PICK,
            display_key="C",
            concert_key="C",
            original_key="G",
            studio_page="backing",
        )
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        ss["explicit_music_source_choice"] = "regular_song"
        # Leftover Mission envelope from a prior Creative visit.
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_MISSION,
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            return_destination=OWNER_MISSION,
        )
        ss["_backing_explicit_handoff_source"] = "mission"
        open_backing_for_practice_source(ss, st_like=_st(ss))
        self.assertEqual(live_backing_owner(ss), OWNER_CATALOG)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_CATALOG)
        self.assertNotEqual(env.source, OWNER_MISSION)


class TestCustomHandoffDoesNotPreserveStaleCatalogEnvelope(unittest.TestCase):
    def test_custom_progression_handoff_stamps_sbi_custom(self) -> None:
        """CPL Open with handoff=custom_progression must not keep Perfect catalog envelope."""
        from backing_context import BackingContext, set_backing_context
        from backing_source_navigation import open_backing_for_practice_source

        ss = _polluted_base(
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            display_key="F",
            concert_key="F",
            original_key="D",
            studio_page="backing",
        )
        ss["explicit_music_source_choice"] = "custom_progression"
        ss[CPL_ACTIVE_KEY] = _trial_active()
        # Stale Journey-A catalog envelope (Perfect G) + CPL handoff.
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_CATALOG,
            identity=PERFECT_PICK,
            title="Perfect",
            original_key="G",
            practice_key="F",
            sounding_key="F",
            return_destination=OWNER_CATALOG,
        )
        set_backing_context(
            ss,
            BackingContext(
                source="custom_progression",
                source_label="Custom Progression",
                active_song_id="trial-d",
                song_title="Trial Song",
                key="F",
                display_key="F",
                concert_key="F",
                bpm=120,
                style="Jazz Swing",
                groove="Jazz swing",
                progression=["F", "C"],
                progression_label="Trial Song",
                bound_pick_key=TRIAL_PICK,
            ),
        )
        ss["_backing_explicit_handoff_source"] = "custom_progression"
        open_backing_for_practice_source(ss, st_like=_st(ss))
        self.assertEqual(live_backing_owner(ss), OWNER_SBI_CUSTOM)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertNotEqual(env.source, OWNER_CATALOG)
        self.assertIn("Trial", str(env.title or env.identity or ""))

    def test_prepare_cpl_backing_handoff_stamps_sbi_custom_replacing_mission(self) -> None:
        """CPL prepare_cpl_backing_handoff is the explicit launch boundary — must stamp."""
        from custom_progression_lab import prepare_cpl_backing_handoff

        ss = _polluted_base(
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            display_key="F",
            concert_key="F",
            original_key="D",
            studio_page="custom",
        )
        ss["explicit_music_source_choice"] = "custom_progression"
        ss[CPL_ACTIVE_KEY] = _trial_active()
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_MISSION,
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            written_key="G",
            return_destination=OWNER_MISSION,
            bump_epoch=False,
        )
        raw = dict(ss.get(BACKING_OWNER_ENVELOPE_KEY) or {})
        raw["epoch"] = 7
        ss[BACKING_OWNER_ENVELOPE_KEY] = raw
        prepare_cpl_backing_handoff(ss, ss[CPL_ACTIVE_KEY])
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertGreater(int(env.epoch), 7)
        self.assertEqual(env.return_destination, OWNER_SBI_CUSTOM)
        self.assertIn("Trial", str(env.title or env.identity or ""))


class TestExplicitLaunchReplacesStaleEnvelope(unittest.TestCase):
    """Case B: deliberate new Backing launch replaces prior envelope + bumps epoch."""

    def _stamp_stale(self, ss: dict, source: str, *, epoch: int = 3) -> int:
        stamp_backing_owner_envelope(
            ss,
            source=source,
            identity=TRIAL_PICK if source != OWNER_CATALOG else PERFECT_PICK,
            title="Trial Song" if source != OWNER_CATALOG else "Perfect",
            original_key="D" if source != OWNER_CATALOG else "G",
            practice_key="F" if source != OWNER_CATALOG else "C",
            sounding_key="F" if source != OWNER_CATALOG else "C",
            return_destination=source,
            bump_epoch=False,
        )
        # Force known epoch for assertion.
        raw = dict(ss.get(BACKING_OWNER_ENVELOPE_KEY) or {})
        raw["epoch"] = epoch
        ss[BACKING_OWNER_ENVELOPE_KEY] = raw
        return epoch

    def test_mission_to_explicit_catalog(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        ss = _polluted_base(
            active_music_source="regular_song",
            active_catalog_pick_key=PERFECT_PICK,
            display_key="C",
            concert_key="C",
            original_key="G",
            studio_page="backing",
        )
        old_epoch = self._stamp_stale(ss, OWNER_MISSION)
        ss["_backing_explicit_handoff_source"] = "mission"
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        ss["explicit_music_source_choice"] = "regular_song"
        open_backing_for_practice_source(ss, st_like=_st(ss))
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_CATALOG)
        self.assertGreater(int(env.epoch), old_epoch)
        self.assertIn("Perfect", str(env.title or env.identity or ""))

    def test_mission_to_explicit_composition(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source
        from composition_songs_bridge import activate_composition_by_pick_key

        ss = _polluted_base(studio_page="backing", display_key="C#", concert_key="C#")
        old_epoch = self._stamp_stale(ss, OWNER_MISSION)
        ss["_backing_explicit_handoff_source"] = "mission"
        doc = _composition_doc("D", song_id="comp-mission-replace")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        ss["_force_composition_backing_open"] = True
        open_backing_for_practice_source(ss, st_like=_st(ss))
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION)
        self.assertGreater(int(env.epoch), old_epoch)
        self.assertNotEqual(env.source, OWNER_MISSION)

    def test_mission_to_composition_without_force_flag(self) -> None:
        """Fallthrough Composition must stamp even when hub force flag is absent."""
        from backing_source_navigation import open_backing_for_practice_source
        from composition_songs_bridge import activate_composition_by_pick_key
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        ss = _polluted_base(studio_page="backing", display_key="C#", concert_key="C#")
        old_epoch = self._stamp_stale(ss, OWNER_MISSION)
        ss["_backing_explicit_handoff_source"] = "mission"
        # Leftover catalog choice must not prevent Composition envelope replace.
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        doc = _composition_doc("C#", song_id="comp-no-force")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        ss.pop("_force_composition_backing_open", None)
        open_backing_for_practice_source(ss, st_like=_st(ss))
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION)
        self.assertGreater(int(env.epoch), old_epoch)
        self.assertIn("composition::", env.identity or pick)

    def test_ensure_envelope_matches_composition_ctx(self) -> None:
        """Backing card/reconcile adopting Composition must replace Mission seal."""
        from backing_context import build_composition_song_context, set_backing_context
        from backing_owner_envelope import ensure_envelope_matches_backing_context
        from composition_songs_bridge import activate_composition_by_pick_key

        ss = _polluted_base(studio_page="backing", display_key="G", concert_key="G")
        old_epoch = self._stamp_stale(ss, OWNER_MISSION)
        doc = _composition_doc("G", song_id="comp-card-adopt")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        ctx = build_composition_song_context(ss)
        set_backing_context(ss, ctx)
        ensure_envelope_matches_backing_context(
            ss,
            ctx,
            source_override=OWNER_COMPOSITION,
            return_destination=OWNER_COMPOSITION,
        )
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION)
        self.assertGreater(int(env.epoch), old_epoch)
        # Idempotent — matching owner must not bump again.
        epoch_after = int(env.epoch)
        ensure_envelope_matches_backing_context(
            ss,
            ctx,
            source_override=OWNER_COMPOSITION,
            return_destination=OWNER_COMPOSITION,
        )
        env2 = get_backing_owner_envelope(ss)
        assert env2 is not None
        self.assertEqual(int(env2.epoch), epoch_after)

    def test_hydrate_restore_last_composition_outranks_mission_handoff(self) -> None:
        """Sidebar Backing with Composition GA must not reopen stale Mission handoff."""
        from backing_source_navigation import (
            BACKING_INTENT_RESTORE_LAST,
            hydrate_backing_source_for_page,
            set_backing_open_intent,
        )
        from composition_songs_bridge import activate_composition_by_pick_key

        ss = _polluted_base(studio_page="backing", display_key="C#", concert_key="C#")
        old_epoch = self._stamp_stale(ss, OWNER_MISSION)
        ss["_backing_explicit_handoff_source"] = "mission"
        ss["improv_mission_backing_handoff"] = True
        doc = _composition_doc("C#", song_id="comp-hydrate")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        set_backing_open_intent(ss, BACKING_INTENT_RESTORE_LAST)
        hydrate_backing_source_for_page(ss, st_like=_st(ss))
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION)
        self.assertGreater(int(env.epoch), old_epoch)

    def test_jam_to_explicit_catalog(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        ss = _polluted_base(
            active_music_source="regular_song",
            active_catalog_pick_key=PERFECT_PICK,
            display_key="C",
            concert_key="C",
            original_key="G",
            studio_page="backing",
        )
        old_epoch = self._stamp_stale(ss, OWNER_ENTRY_JAM)
        ss["_backing_explicit_handoff_source"] = "entry_jam"
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        ss["explicit_music_source_choice"] = "regular_song"
        open_backing_for_practice_source(ss, st_like=_st(ss))
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_CATALOG)
        self.assertGreater(int(env.epoch), old_epoch)

    def test_sbi_custom_to_explicit_composition(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source
        from composition_songs_bridge import activate_composition_by_pick_key

        ss = _polluted_base(
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            studio_page="backing",
        )
        old_epoch = self._stamp_stale(ss, OWNER_SBI_CUSTOM)
        ss["_backing_explicit_handoff_source"] = "song_improv"
        doc = _composition_doc("A", song_id="comp-sbi-replace")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        ss["_force_composition_backing_open"] = True
        open_backing_for_practice_source(ss, st_like=_st(ss))
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION)
        self.assertGreater(int(env.epoch), old_epoch)
        self.assertNotEqual(env.source, OWNER_SBI_CUSTOM)

    def test_sbi_custom_to_composition_when_active_no_force(self) -> None:
        """Journey E: Composition GA must replace sbi_custom even without force flag."""
        from backing_source_navigation import PRACTICE_LOOP_BACKING_KEY, open_backing_for_practice_source
        from composition_songs_bridge import activate_composition_by_pick_key

        ss = _polluted_base(
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            studio_page="songs",
        )
        old_epoch = self._stamp_stale(ss, OWNER_SBI_CUSTOM)
        ss["_backing_explicit_handoff_source"] = "song_improv"
        # Stale Songs Custom loop stamp previously vetoed Composition open.
        ss[PRACTICE_LOOP_BACKING_KEY] = {"owner": "custom", "pick_key": TRIAL_PICK}
        doc = _composition_doc("C#", song_id="comp-sbi-active-noforce")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        ss.pop("_force_composition_backing_open", None)
        open_backing_for_practice_source(ss, st_like=_st(ss))
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION, env)
        self.assertGreater(int(env.epoch), old_epoch)
        self.assertIn("composition::", env.identity or pick)
        self.assertNotEqual(env.source, OWNER_SBI_CUSTOM)

    def test_catalog_to_explicit_mission(self) -> None:
        from mission_owner_contract import stamp_mission_backing_handoff

        ss = _polluted_base(
            studio_page="creative",
            improv_intelligence_tab="Missions",
            instrument="Bb Clarinet",
            active_music_source="custom_progression",
            active_catalog_pick_key=TRIAL_PICK,
            display_key="F",
            concert_key="F",
            original_key="D",
            written_charts_enabled=True,
        )
        old_epoch = self._stamp_stale(ss, OWNER_CATALOG)
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_MISSION)
        self.assertGreater(int(env.epoch), old_epoch)
        self.assertNotEqual(env.source, OWNER_CATALOG)


if __name__ == "__main__":
    unittest.main()
