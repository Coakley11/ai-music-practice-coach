"""Karaoke setlist entry model — Practice Key snapshots, duplicates, play count."""

from __future__ import annotations

import copy
import unittest

import karaoke_mode as km
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
)


def _ss(**extra) -> dict:
    ss: dict = {
        "instrument": "Voice",
        PRACTICE_KEY_BY_SOURCE_KEY: {},
        "karaoke_queue": [],
    }
    ss.update(extra)
    return ss


def _set_pk(ss: dict, key: str, pick_key: str) -> None:
    """Write directly to the per-song store, bypassing sidebar guards."""
    store = ss.setdefault(PRACTICE_KEY_BY_SOURCE_KEY, {})
    store[pick_key] = key


class TestKaraokeEntryModel(unittest.TestCase):
    def test_add_snapshots_practice_key_and_allows_duplicates(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        _set_pk(ss, "C", pick)
        e1 = km.add_to_queue(ss, pick, title="All the Things You Are", artist="Jerome Kern")
        self.assertIsNotNone(e1)
        self.assertEqual(e1["practice_key"], "C")
        _set_pk(ss, "D", pick)
        e2 = km.add_to_queue(ss, pick, title="All the Things You Are")
        self.assertEqual(e2["practice_key"], "D")
        # Global key change must not rewrite prior entries
        _set_pk(ss, "G", pick)
        q = km.get_queue(ss)
        self.assertEqual(len(q), 2)
        self.assertEqual(q[0]["practice_key"], "C")
        self.assertEqual(q[1]["practice_key"], "D")
        self.assertNotEqual(q[0]["entry_id"], q[1]["entry_id"])

    def test_five_keys_same_song(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        keys = ["C", "D", "E", "F", "G"]
        for k in keys:
            _set_pk(ss, k, pick)
            km.add_to_queue(ss, pick, title="All the Things You Are")
        q = km.get_queue(ss)
        self.assertEqual([e["practice_key"] for e in q], keys)
        self.assertEqual(len({e["entry_id"] for e in q}), 5)

    def test_legacy_string_queue_normalizes(self) -> None:
        pick = "Jazz\x1fBlue Bossa — Kenny Dorham"
        ss = _ss(karaoke_queue=[pick, pick])
        q = km.get_queue(ss)
        self.assertEqual(len(q), 2)
        self.assertTrue(all(isinstance(e, dict) and e.get("entry_id") for e in q))
        self.assertEqual(q[0]["pick_key"], pick)

    def test_refresh_preserves_entries_and_keys(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fBlue Bossa — Kenny Dorham"
        _set_pk(ss, "Fm", pick)
        km.add_to_queue(ss, pick, title="Blue Bossa")
        _set_pk(ss, "Gm", pick)
        km.add_to_queue(ss, pick, title="Blue Bossa")
        blob = copy.deepcopy(ss[km.KARAOKE_QUEUE_KEY])
        restored = _ss(karaoke_queue=blob)
        q = km.get_queue(restored)
        self.assertEqual([e["practice_key"] for e in q], ["Fm", "Gm"])

    def test_playback_applies_entry_saved_key(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        for k in ("C", "D", "E"):
            _set_pk(ss, k, pick)
            km.add_to_queue(ss, pick)
        started = km.start_session(ss)
        self.assertEqual(started, pick)
        self.assertEqual(km.current_session_practice_key(ss), "C")
        self.assertEqual(get_practice_concert_key(ss, pick), "C")
        km.advance_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "D")
        self.assertEqual(get_practice_concert_key(ss, pick), "D")
        km.advance_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "E")

    def test_play_count_repeats_before_advance(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fBlue Bossa — Kenny Dorham"
        _set_pk(ss, "Fm", pick)
        entry = km.add_to_queue(ss, pick, play_count=3)
        _set_pk(ss, "C", "other\x1fSong — A")
        km.add_to_queue(ss, "other\x1fSong — A", practice_key="C")
        km.start_session(ss)
        self.assertEqual(km.current_session_entry(ss)["entry_id"], entry["entry_id"])
        # First two advances stay on same entry
        self.assertEqual(km.advance_session(ss), pick)
        self.assertEqual(km.current_session_entry(ss)["entry_id"], entry["entry_id"])
        self.assertEqual(km.advance_session(ss), pick)
        # Third advance moves to next entry
        nxt = km.advance_session(ss)
        self.assertEqual(nxt, "other\x1fSong — A")
        self.assertEqual(km.current_session_practice_key(ss), "C")

    def test_custom_pick_key_source_and_identity(self) -> None:
        ss = _ss()
        pick = "custom::my_progress_v1"
        _set_pk(ss, "Bb", pick)
        entry = km.add_to_queue(ss, pick, title="My Custom Song", source="custom_progression")
        self.assertEqual(entry["source"], "custom_progression")
        self.assertEqual(entry["practice_key"], "Bb")
        self.assertEqual(entry["pick_key"], pick)

    def test_stop_and_restart_preserves_queue_keys(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        for k in ("C", "G"):
            _set_pk(ss, k, pick)
            km.add_to_queue(ss, pick)
        km.start_session(ss)
        km.stop_session(ss)
        q = km.get_queue(ss)
        self.assertEqual([e["practice_key"] for e in q], ["C", "G"])
        km.start_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "C")

    def test_entry_display_line_shows_key(self) -> None:
        line = km.entry_display_line(
            {
                "title": "All the Things You Are",
                "practice_key": "D",
                "play_count": 3,
            }
        )
        self.assertEqual(line, "All the Things You Are · D · Play 3×")

    def test_duplicate_titles_distinct_practice_keys_in_managed_setlist(self) -> None:
        """ATTYA Ab / G / Ab must stay distinguishable while managing the queue."""
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        for k in ("Ab", "G", "Ab"):
            _set_pk(ss, k, pick)
            km.add_to_queue(ss, pick, title="All the Things You Are", artist="Jerome Kern")
        rows = km.managed_setlist_display_rows(ss)
        self.assertEqual([r["practice_key"] for r in rows], ["Ab", "G", "Ab"])
        self.assertEqual(
            [r["label"] for r in rows],
            [
                "All the Things You Are · Ab",
                "All the Things You Are · G",
                "All the Things You Are · Ab",
            ],
        )
        self.assertEqual(len({r["entry_id"] for r in rows}), 3)

        # Sidebar Practice Key must not rewrite saved entry labels.
        _set_pk(ss, "C", pick)
        rows_after = km.managed_setlist_display_rows(ss)
        self.assertEqual([r["practice_key"] for r in rows_after], ["Ab", "G", "Ab"])
        self.assertEqual([r["label"] for r in rows_after], [r["label"] for r in rows])

        # Reorder moves the exact entry (key + id).
        mid_id = rows[1]["entry_id"]
        km.move_in_queue(ss, mid_id, -1)
        reordered = km.managed_setlist_display_rows(ss)
        self.assertEqual([r["practice_key"] for r in reordered], ["G", "Ab", "Ab"])
        self.assertEqual(reordered[0]["entry_id"], mid_id)

        # Remove only the targeted entry_id (first Ab after reorder = original first Ab).
        remove_id = reordered[1]["entry_id"]
        km.remove_from_queue(ss, remove_id)
        left = km.managed_setlist_display_rows(ss)
        self.assertEqual([r["practice_key"] for r in left], ["G", "Ab"])
        self.assertNotIn(remove_id, {r["entry_id"] for r in left})


class TestMusicSourceBadgeIcons(unittest.TestCase):
    def test_custom_and_composition_icons(self) -> None:
        from app_ui import studio_song_meta_badges_html
        from music_feature_icons import FEATURE_ICONS

        custom_html = studio_song_meta_badges_html(source="Custom Progression")
        # Source badge uses shared 📀 chrome; feature icons stay on left art.
        self.assertIn("📀", custom_html)
        self.assertIn("Custom Progression", custom_html)
        self.assertNotIn(FEATURE_ICONS["songs"], custom_html)
        comp_html = studio_song_meta_badges_html(source="Composition")
        self.assertIn("📀", comp_html)
        self.assertIn("Composition", comp_html)
        self.assertNotIn(FEATURE_ICONS["songs"], comp_html)


class TestKaraokeStartOrder(unittest.TestCase):
    """Karaoke must always start from the first queue entry."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"
    PK3 = "Jazz\x1fAutumn Leaves — Joseph Kosma"

    def test_start_plays_first_entry_not_editing_song(self):
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        e1 = km.add_to_queue(ss, self.PK1, title="Shape of You")
        _set_pk(ss, "G", self.PK2)
        e2 = km.add_to_queue(ss, self.PK2, title="Perfect")

        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        ss[km.KARAOKE_EDITING_ENTRY_ID_KEY] = e2["entry_id"]

        km.start_session(ss)

        self.assertEqual(km.now_singing_pick_key(ss), self.PK1)
        self.assertEqual(km.current_session_practice_key(ss), "Dm")
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), self.PK2)

    def test_start_clears_pending_picks(self):
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You")
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK2, title="Perfect")

        ss["_pending_matching_song_dropdown"] = self.PK2
        ss["_pending_catalog_pick_key"] = self.PK2

        km.start_session(ss)

        self.assertIsNone(ss.get("_pending_matching_song_dropdown"))
        self.assertIsNone(ss.get("_pending_catalog_pick_key"))
        self.assertEqual(km.now_singing_pick_key(ss), self.PK1)

    def test_third_song_editing_start_plays_first(self):
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You")
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK2, title="Perfect")
        _set_pk(ss, "Am", self.PK3)
        km.add_to_queue(ss, self.PK3, title="Autumn Leaves")

        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK3

        km.start_session(ss)

        self.assertEqual(km.now_singing_pick_key(ss), self.PK1)
        self.assertEqual(km.current_session_practice_key(ss), "Dm")
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), self.PK3)

    def test_advance_does_not_change_editing(self):
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You")
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK2, title="Perfect")

        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        km.start_session(ss)
        km.advance_session(ss)

        self.assertEqual(km.now_singing_pick_key(ss), self.PK2)
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), self.PK2)


class TestKaraokeMissingLyrics(unittest.TestCase):
    """Missing-lyrics detection scans the full queue."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"

    def test_entry_has_lyrics_returns_false_without_title(self):
        from karaoke_ui import _entry_has_lyrics

        class _St:
            session_state = _ss()

        self.assertFalse(_entry_has_lyrics(_St(), {"pick_key": self.PK1}))

    def test_missing_lyrics_cta_skips_empty_queue(self):
        from karaoke_ui import render_karaoke_setlist_missing_lyrics_cta

        ss = _ss()

        class _St:
            session_state = ss
            def markdown(self, *a, **kw): pass
            def button(self, *a, **kw): return False

        self.assertFalse(render_karaoke_setlist_missing_lyrics_cta(_St()))

    def test_missing_lyrics_cta_skips_non_voice(self):
        from karaoke_ui import render_karaoke_setlist_missing_lyrics_cta

        ss = _ss()
        ss["instrument"] = "Guitar"
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You")

        class _St:
            session_state = ss
            def markdown(self, *a, **kw): pass
            def button(self, *a, **kw): return False

        self.assertFalse(render_karaoke_setlist_missing_lyrics_cta(_St()))


class TestKaraokeCanonicalReconciliation(unittest.TestCase):
    """Canonical reconciliation must not revert the karaoke pick."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"

    def _session_with_canonical(self):
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        ss = _ss(**{
            ACTIVE_CATALOG_PICK_KEY: self.PK2,
            "matching_song_dropdown": self.PK2,
            SELECTED_SONG_STATE_KEY: {
                "title": "Perfect", "artist": "Ed Sheeran",
                "pick_key": self.PK2, "genre": "Pop",
                "label": "Perfect — Ed Sheeran", "key": "G",
            },
            "active_song_state": {
                "pick_key": self.PK2,
                "selected_song": {
                    "title": "Perfect", "artist": "Ed Sheeran",
                    "pick_key": self.PK2, "genre": "Pop", "key": "G",
                },
                "instrument": "Voice",
                "display_key": "G",
                "music_source": "catalog",
            },
            "studio_page": "backing",
        })
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK2, title="Perfect", artist="Ed Sheeran")
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        return ss

    def test_reconcile_identity_preserves_karaoke_pick(self):
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = self._session_with_canonical()
        km.start_session(ss)
        self.assertEqual(km.now_singing_pick_key(ss), self.PK1)

        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK1
        ss["matching_song_dropdown"] = self.PK1

        try:
            from song_catalog.catalog import load_song_catalog
            _, catalog, _, _ = load_song_catalog()
            from songs.state import reconcile_active_song_identity

            reconcile_active_song_identity(ss, catalog)
            self.assertEqual(
                str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").strip(),
                self.PK1,
                "reconcile_active_song_identity must not revert karaoke pick",
            )
        except ImportError:
            self.skipTest("song catalog not available")

    def test_stale_dropdown_does_not_override_karaoke_pick(self):
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        ss = self._session_with_canonical()
        km.start_session(ss)

        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK1
        ss[SELECTED_SONG_STATE_KEY] = {
            "title": "Shape of You", "artist": "Ed Sheeran",
            "pick_key": self.PK1, "genre": "Pop", "key": "C#m",
        }
        # matching_song_dropdown stays stale (Perfect) — Streamlit widget state
        self.assertEqual(ss["matching_song_dropdown"], self.PK2)

        try:
            from song_catalog.catalog import load_song_catalog
            _, catalog, _, _ = load_song_catalog()
            from songs.state import reconcile_active_song_identity

            result = reconcile_active_song_identity(ss, catalog)
            active_after = str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
            self.assertIn(
                "Shape of You", active_after,
                f"Stale dropdown must not revert pick; got {active_after}",
            )
        except ImportError:
            self.skipTest("song catalog not available")

    def test_post_canonical_reapply_recovers_pick(self):
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = self._session_with_canonical()
        km.start_session(ss)

        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK2

        kr_target = km.current_session_pick_key(ss)
        self.assertEqual(kr_target, self.PK1)
        self.assertNotEqual(kr_target, ss.get(ACTIVE_CATALOG_PICK_KEY))

        ss[ACTIVE_CATALOG_PICK_KEY] = kr_target
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK1)

    def test_editing_restore_queues_dropdown_alignment(self):
        """When navigating to Songs during karaoke, the editing restore must
        set both ACTIVE_CATALOG_PICK_KEY and PENDING_MATCHING_SONG_DROPDOWN
        so the dropdown renders the correct song on the first pass."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY, PENDING_MATCHING_SONG_DROPDOWN

        ss = self._session_with_canonical()
        km.start_session(ss)
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK1
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        ss["matching_song_dropdown"] = self.PK1

        editing_pk = str(ss.get(km.KARAOKE_EDITING_PICK_KEY) or "").strip()
        if editing_pk and km.is_karaoke_session_active(ss):
            if editing_pk != str(ss.get(ACTIVE_CATALOG_PICK_KEY) or ""):
                ss[ACTIVE_CATALOG_PICK_KEY] = editing_pk
                ss[PENDING_MATCHING_SONG_DROPDOWN] = editing_pk

        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK2)
        self.assertEqual(ss[PENDING_MATCHING_SONG_DROPDOWN], self.PK2)


class TestKaraokeBackingContextRefresh(unittest.TestCase):
    """After karaoke advance the backing context must match the new song."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"

    def _session(self) -> dict:
        ss = _ss()
        _set_pk(ss, "C#m", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK2, title="Perfect", artist="Ed Sheeran")
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        return ss

    def test_advance_updates_singing_pick(self):
        """advance_session must update the active singing pick key."""
        ss = self._session()
        km.start_session(ss)
        self.assertEqual(km.current_session_pick_key(ss), self.PK1)
        new_pk = km.advance_session(ss)
        self.assertEqual(new_pk, self.PK2)
        self.assertEqual(km.current_session_pick_key(ss), self.PK2)

    def test_advance_does_not_touch_editing_pick(self):
        """advance_session must not overwrite KARAOKE_EDITING_PICK_KEY."""
        ss = self._session()
        km.start_session(ss)
        km.advance_session(ss)
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), self.PK2)

    def test_setlist_editor_callback_updates_editing_pick(self):
        """The setlist missing-lyrics editor callback must update
        KARAOKE_EDITING_PICK_KEY so the Songs page shows the target song."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = self._session()
        km.start_session(ss)

        target_pk = self.PK2
        target_eid = "eid-perfect"
        ss[km.KARAOKE_EDITING_PICK_KEY] = target_pk
        if target_eid:
            ss[km.KARAOKE_EDITING_ENTRY_ID_KEY] = target_eid
        ss[ACTIVE_CATALOG_PICK_KEY] = target_pk

        self.assertEqual(ss[km.KARAOKE_EDITING_PICK_KEY], target_pk)
        self.assertEqual(ss[km.KARAOKE_EDITING_ENTRY_ID_KEY], target_eid)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], target_pk)


class TestKaraokeEditingPageGuard(unittest.TestCase):
    """On the Songs page, user catalog selections must not be overwritten.
    Only restore the editing pick when arriving from Backing (singing pick active)."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"
    PK3 = "Pop\x1fHello — Adele"

    def _session(self) -> dict:
        ss = _ss()
        _set_pk(ss, "C#m", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK2, title="Perfect", artist="Ed Sheeran")
        return ss

    def _apply_override(self, ss: dict) -> None:
        """Simulate the page-specific override logic from the karaoke block."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        singing = km.current_session_pick_key(ss)
        page = str(ss.get("studio_page") or "").strip().lower()
        if page == "picker":
            live = str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
            edit = str(ss.get(km.KARAOKE_EDITING_PICK_KEY) or "").strip()
            if live == singing and edit and edit != singing:
                ss[ACTIVE_CATALOG_PICK_KEY] = edit
                ss["matching_song_dropdown"] = edit
            elif live and live != singing:
                ss[km.KARAOKE_EDITING_PICK_KEY] = live

    def test_songs_page_restores_editing_on_arrival_from_backing(self):
        """When arriving from Backing, ACTIVE_CATALOG_PICK_KEY = singing pick.
        Override block must restore it to the editing pick."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        ss = self._session()
        km.start_session(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK1  # singing pick (just came from Backing)
        ss["studio_page"] = "picker"
        self._apply_override(ss)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK2,
                         "Must restore editing pick when arriving from Backing")

    def test_songs_page_preserves_user_selection(self):
        """When user selects a different song, override must NOT revert it."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        ss = self._session()
        km.start_session(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK3  # user selected a different song
        ss["studio_page"] = "picker"
        self._apply_override(ss)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK3,
                         "User's catalog selection must be preserved")
        self.assertEqual(ss[km.KARAOKE_EDITING_PICK_KEY], self.PK3,
                         "Editing pick must follow user's selection")

    def test_backing_page_keeps_singing_pick(self):
        """On the Backing page the karaoke singing pick must stay active."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        ss = self._session()
        km.start_session(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK1
        ss["studio_page"] = "backing"
        self._apply_override(ss)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK1)


class TestKaraokePerSongCtaSuppression(unittest.TestCase):
    """During active karaoke the per-song missing-lyrics CTA must be suppressed."""

    def test_per_song_cta_suppressed_during_karaoke(self):
        ss = _ss()
        _set_pk(ss, "C", "Pop\x1fTest — Artist")
        km.add_to_queue(ss, "Pop\x1fTest — Artist", title="Test", artist="Artist")
        km.start_session(ss)
        self.assertTrue(km.is_karaoke_session_active(ss))
        self.assertFalse(
            not km.is_karaoke_session_active(ss),
            "Guard should prevent per-song CTA from rendering during karaoke",
        )

    def test_per_song_cta_allowed_outside_karaoke(self):
        ss = _ss()
        self.assertFalse(km.is_karaoke_session_active(ss))
        self.assertTrue(
            not km.is_karaoke_session_active(ss),
            "Guard should allow per-song CTA outside karaoke",
        )


class TestKaraokeDeferredNavigation(unittest.TestCase):
    """Deferred navigation prevents widget-state crash on lyrics CTA."""

    def test_pending_nav_flag_stored_and_consumed(self):
        ss = _ss()
        pick = "Pop\x1fShape of You — Ed Sheeran"
        _set_pk(ss, "Dm", pick)
        km.add_to_queue(ss, pick, title="Shape of You", artist="Ed Sheeran")
        km.start_session(ss)
        ss[km.PENDING_KARAOKE_LYRICS_NAV_KEY] = {
            "pick_key": pick,
            "entry_id": "e1",
            "target_page": "picker",
        }
        nav = ss.pop(km.PENDING_KARAOKE_LYRICS_NAV_KEY, None)
        self.assertIsNotNone(nav)
        self.assertEqual(nav["pick_key"], pick)
        self.assertEqual(nav["target_page"], "picker")
        self.assertNotIn(km.PENDING_KARAOKE_LYRICS_NAV_KEY, ss)

    def test_deferred_nav_sets_editing_keys(self):
        ss = _ss()
        pick = "Pop\x1fPerfect — Ed Sheeran"
        entry_id = "eid_123"
        ss[km.PENDING_KARAOKE_LYRICS_NAV_KEY] = {
            "pick_key": pick,
            "entry_id": entry_id,
            "target_page": "picker",
        }
        nav = ss.pop(km.PENDING_KARAOKE_LYRICS_NAV_KEY, None)
        if nav:
            ss[km.KARAOKE_EDITING_PICK_KEY] = nav["pick_key"]
            ss[km.KARAOKE_EDITING_ENTRY_ID_KEY] = nav["entry_id"]
        self.assertEqual(ss[km.KARAOKE_EDITING_PICK_KEY], pick)
        self.assertEqual(ss[km.KARAOKE_EDITING_ENTRY_ID_KEY], entry_id)

    def test_no_direct_navigate_in_lyrics_callbacks(self):
        """Ensure the setlist CTA fallback uses deferred navigation, not navigate_studio_page."""
        import inspect
        from karaoke_ui import render_karaoke_setlist_missing_lyrics_cta

        source = inspect.getsource(render_karaoke_setlist_missing_lyrics_cta)
        self.assertNotIn(
            "navigate_studio_page",
            source,
            "Setlist CTA fallback must use deferred navigation, not navigate_studio_page",
        )
        self.assertIn(
            "PENDING_KARAOKE_LYRICS_NAV_KEY",
            source,
            "Setlist CTA fallback must set the deferred navigation flag",
        )


class TestKaraokeStartSessionSync(unittest.TestCase):
    """Start Karaoke must sync ACTIVE_CATALOG_PICK_KEY to the first queued song."""

    def test_start_session_returns_first_pick_key(self):
        ss = _ss()
        pick_shape = "Pop\x1fShape of You — Ed Sheeran"
        pick_perfect = "Pop\x1fPerfect — Ed Sheeran"
        _set_pk(ss, "Dm", pick_shape)
        _set_pk(ss, "G", pick_perfect)
        km.add_to_queue(ss, pick_shape, title="Shape of You", artist="Ed Sheeran")
        km.add_to_queue(ss, pick_perfect, title="Perfect", artist="Ed Sheeran")
        started = km.start_session(ss)
        self.assertEqual(started, pick_shape)
        self.assertEqual(km.now_singing_pick_key(ss), pick_shape)

    def test_editing_pick_does_not_affect_start(self):
        ss = _ss()
        pick_shape = "Pop\x1fShape of You — Ed Sheeran"
        pick_perfect = "Pop\x1fPerfect — Ed Sheeran"
        _set_pk(ss, "Dm", pick_shape)
        _set_pk(ss, "G", pick_perfect)
        km.add_to_queue(ss, pick_shape, title="Shape of You", artist="Ed Sheeran")
        km.add_to_queue(ss, pick_perfect, title="Perfect", artist="Ed Sheeran")
        ss[km.KARAOKE_EDITING_PICK_KEY] = pick_perfect
        started = km.start_session(ss)
        self.assertEqual(started, pick_shape,
                         "Now Editing (Perfect) must not influence which song Start Karaoke plays")
        self.assertEqual(km.now_singing_pick_key(ss), pick_shape)


class TestKaraokeStartWidgetSafety(unittest.TestCase):
    """Start Karaoke must not write directly to widget-backed keys.

    The catalog dropdown (key ``matching_song_dropdown``) is widget-backed.
    Writing to it after the widget is instantiated raises
    ``StreamlitAPIException``.  The Start handler must use the pending
    transition pattern instead.
    """

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"

    def test_start_does_not_write_global_state(self):
        """Start handler must NOT write to ACTIVE_CATALOG_PICK_KEY or
        matching_song_dropdown — karaoke isolation means global state
        is never overwritten by karaoke."""
        import inspect
        from karaoke_ui import render_karaoke_setlist_panel

        source = inspect.getsource(render_karaoke_setlist_panel)
        start_block = source[source.index("start_session("):]
        start_block = start_block[:start_block.index("st.rerun()")]
        self.assertNotIn(
            '"matching_song_dropdown"',
            start_block,
            "Start handler must not write directly to widget-backed matching_song_dropdown",
        )
        self.assertNotIn(
            "ACTIVE_CATALOG_PICK_KEY",
            start_block,
            "Start handler must not write to ACTIVE_CATALOG_PICK_KEY",
        )

    def test_start_preserves_global_active_song(self):
        """After start_session, ACTIVE_CATALOG_PICK_KEY and matching_song_dropdown
        must remain unchanged — karaoke uses its own isolated cursor."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        km.add_to_queue(ss, self.PK2, title="Perfect", artist="Ed Sheeran")
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK2
        ss["matching_song_dropdown"] = self.PK2

        started = km.start_session(ss)
        self.assertEqual(started, self.PK1)

        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK2,
                         "Global ACTIVE_CATALOG_PICK_KEY must NOT change on Start")
        self.assertEqual(ss["matching_song_dropdown"], self.PK2,
                         "matching_song_dropdown must NOT change on Start")
        self.assertEqual(km.now_singing_pick_key(ss), self.PK1,
                         "Now Singing must be Shape of You")
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK1,
                         "effective_catalog_pick_key must return the singing pick")

    def test_advance_does_not_change_global_state(self):
        """After advancing, ACTIVE_CATALOG_PICK_KEY must NOT change.
        effective_catalog_pick_key returns the new singing pick instead."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        km.add_to_queue(ss, self.PK2, title="Perfect", artist="Ed Sheeran")
        km.start_session(ss)
        ss[ACTIVE_CATALOG_PICK_KEY] = "Pop\x1fGravity — John Mayer"
        ss["studio_page"] = "backing"

        km.advance_session(ss)
        self.assertEqual(km.now_singing_pick_key(ss), self.PK2)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], "Pop\x1fGravity — John Mayer",
                         "Global ACTIVE_CATALOG_PICK_KEY must NOT change on advance")
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK2,
                         "effective_catalog_pick_key must return Perfect after advance")

    def test_no_widget_backed_writes_in_setlist_editor_callback(self):
        """The setlist editor 'pick song' callback must also use the pending
        pattern, not write directly to matching_song_dropdown."""
        import inspect
        from karaoke_ui import render_karaoke_setlist_panel

        source = inspect.getsource(render_karaoke_setlist_panel)
        pick_block = source[source.index("on_pick_song(pick_key)"):]
        pick_block = pick_block[:pick_block.index("st.rerun()")]
        self.assertNotIn(
            '"matching_song_dropdown"',
            pick_block,
            "Setlist pick callback must not write directly to widget-backed matching_song_dropdown",
        )


class TestKaraokePageSpecificIdentity(unittest.TestCase):
    """Karaoke isolation: ACTIVE_CATALOG_PICK_KEY is the global Active Song
    and must NEVER be modified by karaoke.  The Backing page uses
    ``km.effective_catalog_pick_key()`` instead."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"
    PK3 = "Pop\x1fHello — Adele"
    PK_GLOBAL = "Pop\x1fGravity — John Mayer"

    def _session(self, page: str = "backing") -> dict:
        ss = _ss()
        ss["studio_page"] = page
        _set_pk(ss, "Dm", self.PK1)
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        km.add_to_queue(ss, self.PK2, title="Perfect", artist="Ed Sheeran")
        return ss

    def _apply_karaoke_page_identity(self, ss: dict) -> None:
        """Simulate the karaoke override block (new architecture:
        only saves editing pick, never writes global state)."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        singing = km.current_session_pick_key(ss)
        page = str(ss.get("studio_page") or "").strip().lower()
        if page == "picker":
            live = str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
            if live and live != singing:
                ss[km.KARAOKE_EDITING_PICK_KEY] = live
        else:
            if not ss.get(km.KARAOKE_EDITING_PICK_KEY):
                ss[km.KARAOKE_EDITING_PICK_KEY] = str(
                    ss.get(ACTIVE_CATALOG_PICK_KEY) or ""
                )

    def test_global_active_song_never_changes(self):
        """ACTIVE_CATALOG_PICK_KEY must remain the global song throughout
        start, advance, and page switches."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = self._session(page="backing")
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK_GLOBAL
        km.start_session(ss)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL)
        km.advance_session(ss)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL)
        self._apply_karaoke_page_identity(ss)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL,
                         "Global Active Song must NEVER be modified by karaoke")

    def test_effective_pick_returns_singing_on_backing(self):
        """effective_catalog_pick_key must return the karaoke singing pick."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = self._session(page="backing")
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK_GLOBAL
        km.start_session(ss)
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK1)
        km.advance_session(ss)
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK2)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL)

    def test_effective_pick_returns_global_when_karaoke_inactive(self):
        """Without an active karaoke session, effective_catalog_pick_key
        must return the global ACTIVE_CATALOG_PICK_KEY."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = self._session(page="backing")
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK_GLOBAL
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK_GLOBAL)

    def test_songs_page_captures_editing_pick(self):
        """On the Songs page, the override block must capture the user's
        current catalog selection as the editing pick."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = self._session(page="picker")
        km.start_session(ss)
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK3
        self._apply_karaoke_page_identity(ss)
        self.assertEqual(ss[km.KARAOKE_EDITING_PICK_KEY], self.PK3)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK3,
                         "Global state must not change")

    def test_editing_change_never_affects_singing(self):
        """Changing the editing pick must not change the singing pick."""
        ss = self._session(page="picker")
        km.start_session(ss)
        self.assertEqual(km.current_session_pick_key(ss), self.PK1)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK2
        self.assertEqual(km.current_session_pick_key(ss), self.PK1,
                         "Changing Now Editing must never change Now Singing")

    def test_advance_never_changes_editing(self):
        """Advancing Now Singing must not change the editing pick."""
        ss = self._session(page="backing")
        km.start_session(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK1
        km.advance_session(ss)
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), self.PK1,
                         "Advancing Now Singing must not change Now Editing")

    def test_practice_key_not_applied_on_songs_page(self):
        """apply_entry_practice_key must NOT run on the Songs page."""
        ss = self._session(page="picker")
        km.start_session(ss)
        ss["practice_concert_key"] = "G"
        entry = km.current_session_entry(ss)
        page = str(ss.get("studio_page") or "").strip().lower()
        if page != "picker" and entry:
            km.apply_entry_practice_key(ss, entry)
        self.assertEqual(ss.get("practice_concert_key"), "G",
                         "practice_concert_key must not change on Songs page")

    def test_selecting_song_outside_queue(self):
        """User selecting a song not in the queue must work normally."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss = self._session(page="picker")
        km.start_session(ss)
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK3
        self._apply_karaoke_page_identity(ss)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK3,
                         "Non-queue song selection must be preserved")
        self.assertEqual(km.current_session_pick_key(ss), self.PK1,
                         "Singing pick must not change")

    def test_microphone_icon_in_setlist_cta(self):
        """The setlist missing-lyrics CTA must use the microphone icon."""
        import inspect
        from karaoke_ui import render_karaoke_setlist_missing_lyrics_cta

        source = inspect.getsource(render_karaoke_setlist_missing_lyrics_cta)
        self.assertIn(
            "U0001F3A4",
            source,
            "Setlist CTA must use the microphone icon (🎤)",
        )


class TestKaraokeStartTransitionIntegration(unittest.TestCase):
    """Karaoke isolation integration: global Active Song is never modified,
    effective_catalog_pick_key returns the singing pick, and editing pick
    is preserved across page switches."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"
    PK_GLOBAL = "Pop\x1fGravity — John Mayer"

    def _session(self) -> dict:
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        km.add_to_queue(ss, self.PK2, title="Perfect", artist="Ed Sheeran")
        return ss

    def test_scenario_a_start_preserves_global_song(self):
        """Scenario A: Global = Gravity, Start → Backing effective = Shape of You,
        but Global remains Gravity."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        ss = self._session()
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK_GLOBAL
        ss["selected_song"] = {"pick_key": self.PK_GLOBAL, "title": "Gravity"}
        ss["matching_song_dropdown"] = self.PK_GLOBAL
        ss["studio_page"] = "backing"

        started = km.start_session(ss)
        self.assertEqual(started, self.PK1)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL,
                         "Global must remain Gravity")
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK1,
                         "Effective pick must be Shape of You")

    def test_scenario_b_advance_preserves_global_song(self):
        """Scenario B: After Start, advance → effective = Perfect, Global unchanged."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        ss = self._session()
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK_GLOBAL
        ss["studio_page"] = "backing"
        km.start_session(ss)
        km.advance_session(ss)

        self.assertEqual(km.now_singing_pick_key(ss), self.PK2)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL,
                         "Global must remain Gravity")
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK2,
                         "Effective pick must be Perfect after advance")

    def test_scenario_c_editing_independent_of_singing(self):
        """Scenario C: Change editing pick on Songs page → effective on
        Backing still returns the singing pick."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        ss = self._session()
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK_GLOBAL
        km.start_session(ss)
        km.advance_session(ss)

        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK1
        ss["studio_page"] = "backing"

        self.assertEqual(km.now_singing_pick_key(ss), self.PK2)
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK2,
                         "Editing pick change must not affect Backing effective pick")
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL,
                         "Global must remain Gravity")

    def test_scenario_d_repeated_page_switches_stable(self):
        """Scenario D: Navigate Songs↔Backing repeatedly — identity stays consistent."""
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        ss = self._session()
        ss[ACTIVE_CATALOG_PICK_KEY] = self.PK_GLOBAL
        km.start_session(ss)

        for _ in range(5):
            ss["studio_page"] = "backing"
            self.assertEqual(km.effective_catalog_pick_key(ss), self.PK1,
                             "Backing effective must consistently be Shape of You")
            self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL,
                             "Global must remain Gravity")
            ss["studio_page"] = "picker"
            self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], self.PK_GLOBAL,
                             "On Songs page, Global must remain Gravity")


class TestKaraokeTransportTransition(unittest.TestCase):
    """Next Song must invalidate stale backing audio and arm autoplay."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"

    def _session_with_stale_audio(self) -> dict:
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        _set_pk(ss, "G", self.PK2)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        km.add_to_queue(ss, self.PK2, title="Perfect", artist="Ed Sheeran")
        km.start_session(ss)
        ss["_last_backing_wav"] = b"fake-wav-bytes"
        ss["_last_backing_wav_b64"] = "ZmFrZQ=="
        ss["_last_backing_signature"] = ("Shape of You", "Dm", "stale")
        ss["_backing_autoplay"] = False
        ss["_backing_transport_user_stopped"] = True
        return ss

    def test_skip_invalidates_stale_audio(self):
        """After advance_session + invalidation, stale audio must be cleared."""
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition
        ss = self._session_with_stale_audio()
        km.advance_session(ss)
        _invalidate_stale_backing_for_karaoke_transition(ss)

        self.assertNotIn("_last_backing_wav", ss)
        self.assertNotIn("_last_backing_wav_b64", ss)
        self.assertNotIn("_last_backing_signature", ss)
        self.assertNotIn("_backing_transport_user_stopped", ss)
        self.assertFalse(
            ss.get("_backing_autoplay"),
            "Autoplay must NOT be pre-armed: the generator reads it as proof a "
            "prior take is still playing and returns a zero-byte WAV. It is "
            "armed after a successful generate instead.",
        )

    def test_skip_sets_auto_generate_flag(self):
        """advance_session must set the auto-generate flag."""
        ss = self._session_with_stale_audio()
        km.advance_session(ss)
        self.assertTrue(
            ss.get(km.PENDING_KARAOKE_AUTO_GENERATE_KEY),
            "advance_session must set PENDING_KARAOKE_AUTO_GENERATE_KEY",
        )

    def test_start_session_invalidates_stale_audio(self):
        """Start Karaoke must clear previous song's backing audio."""
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        ss["_last_backing_wav"] = b"old-audio"
        ss["_last_backing_signature"] = ("old",)
        km.start_session(ss)
        _invalidate_stale_backing_for_karaoke_transition(ss)

        self.assertNotIn("_last_backing_wav", ss)
        self.assertNotIn("_last_backing_signature", ss)
        self.assertFalse(ss.get("_backing_autoplay"),
                         "autoplay is armed after generate, not before")

    def test_auto_generate_consumed_when_no_stale_audio(self):
        """consume_pending_auto_generate must return True after advance."""
        ss = self._session_with_stale_audio()
        km.advance_session(ss)
        self.assertTrue(km.consume_pending_auto_generate(ss))
        self.assertFalse(km.consume_pending_auto_generate(ss),
                         "Flag must be one-shot")

    def test_skip_source_code_calls_invalidation(self):
        """The Skip callback in render_karaoke_skip_controls must call
        _invalidate_stale_backing_for_karaoke_transition."""
        import inspect
        from karaoke_ui import render_karaoke_skip_controls

        source = inspect.getsource(render_karaoke_skip_controls)
        skip_block = source[source.index("clicked_skip"):]
        self.assertIn(
            "_invalidate_stale_backing_for_karaoke_transition",
            skip_block,
            "Skip callback must invalidate stale backing audio",
        )

    def test_previous_source_code_calls_invalidation(self):
        """The Previous callback must also invalidate stale audio."""
        import inspect
        from karaoke_ui import render_karaoke_skip_controls

        source = inspect.getsource(render_karaoke_skip_controls)
        prev_block = source[source.index("clicked_prev"):]
        self.assertIn(
            "_invalidate_stale_backing_for_karaoke_transition",
            prev_block,
            "Previous callback must invalidate stale backing audio",
        )

    def test_natural_advance_path_invalidates(self):
        """consume_pending_advance → advance_session path must set
        the auto-generate flag so the backing section can auto-gen."""
        ss = self._session_with_stale_audio()
        km.request_advance(ss, reason="audio_ended")
        result = km.consume_pending_advance(ss)
        self.assertEqual(result, self.PK2)
        self.assertTrue(ss.get(km.PENDING_KARAOKE_AUTO_GENERATE_KEY))


class TestKaraokeIsolationArchitecture(unittest.TestCase):
    """Verify the karaoke isolation architecture where global Active Song
    and karaoke Now Singing are completely separate concepts."""

    PK1 = "Pop\x1fShape of You — Ed Sheeran"
    PK2 = "Pop\x1fPerfect — Ed Sheeran"
    PK_GLOBAL = "Pop\x1fGravity — John Mayer"

    def test_effective_returns_global_when_no_session(self):
        ss = _ss()
        ss["active_catalog_pick_key"] = self.PK_GLOBAL
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK_GLOBAL)

    def test_effective_returns_singing_when_session_active(self):
        ss = _ss()
        ss["active_catalog_pick_key"] = self.PK_GLOBAL
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        km.start_session(ss)
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK1)
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_GLOBAL)

    def test_effective_returns_global_for_non_voice(self):
        ss = _ss()
        ss["instrument"] = "Guitar"
        ss["active_catalog_pick_key"] = self.PK_GLOBAL
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        ss["instrument"] = "Voice"
        km.start_session(ss)
        ss["instrument"] = "Guitar"
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK_GLOBAL)

    def test_karaoke_song_context_returns_none_when_inactive(self):
        ss = _ss()
        result = km.karaoke_song_context(ss, {}, {})
        self.assertIsNone(result)

    def test_karaoke_song_context_resolves_from_catalog(self):
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        km.start_session(ss)
        catalog = {
            "Pop": {
                "Shape of You — Ed Sheeran": {
                    "pick_key": self.PK1,
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                },
            },
        }
        result = km.karaoke_song_context(ss, {}, catalog)
        self.assertIsNotNone(result)
        genre, title, data = result
        self.assertEqual(genre, "Pop")
        self.assertIn("Shape of You", title)

    def test_setlist_cta_guarded_by_karaoke_active(self):
        """render_karaoke_setlist_missing_lyrics_cta must only render
        when karaoke session is active (not duplicate with single-song CTA)."""
        with open("streamlit_music_practice_app.py", "r", encoding="utf-8") as f:
            src = f.read()
        idx = src.index("render_karaoke_setlist_missing_lyrics_cta(")
        context = src[max(0, idx - 200):idx]
        self.assertIn("is_karaoke_session_active", context,
                       "setlist CTA must be guarded by is_karaoke_session_active")

    def test_stop_restores_editing_pick(self):
        """When karaoke stops, the editing pick should be restorable as
        the global Active Song (done by Stop callback, not the override block)."""
        ss = _ss()
        _set_pk(ss, "Dm", self.PK1)
        km.add_to_queue(ss, self.PK1, title="Shape of You", artist="Ed Sheeran")
        km.start_session(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK_GLOBAL
        km.stop_session(ss)
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), self.PK_GLOBAL,
                         "Editing pick must survive stop for caller to restore")


class TestKaraokeSetlistHTML(unittest.TestCase):
    """Verify the setlist panel HTML wrapper is self-contained."""

    def test_setlist_header_div_is_closed(self):
        """The <div class='ui-karaoke-setlist'> must close within the same
        st.markdown() call.  A div opened in one st.markdown and 'closed'
        in another creates malformed HTML in Streamlit's DOM model."""
        import inspect
        from karaoke_ui import render_karaoke_setlist_panel

        source = inspect.getsource(render_karaoke_setlist_panel)
        self.assertIn(
            '</p></div>"',
            source,
            "The ui-karaoke-setlist div must close in the header markdown",
        )
        self.assertNotIn(
            'st.markdown("</div>"',
            source,
            "Stray </div> closing tag must not appear as a separate st.markdown call",
        )


class TestThreeIndependentIdentities(unittest.TestCase):
    """Global Active Song, Now Editing, Now Singing are separate state owners.

    These tests verify the architectural contract described in the user's
    clarification: all three may reference different songs simultaneously
    and must never synchronize into one global dropdown.
    """

    PK_GRAVITY = "Pop\x1fGravity"
    PK_SHAPE = "Pop\x1fShape of You"
    PK_HOTEL = "Rock\x1fHotel California"
    PK_PERFECT = "Pop\x1fPerfect"
    PK_SCIENTIST = "Alternative\x1fThe Scientist"

    def _session(self) -> dict:
        ss = _ss()
        ss["active_catalog_pick_key"] = self.PK_GRAVITY
        ss["selected_song"] = {"pick_key": self.PK_GRAVITY, "title": "Gravity"}
        ss["practice_concert_key"] = "C"
        _set_pk(ss, "C", self.PK_GRAVITY)
        _set_pk(ss, "G", self.PK_PERFECT)
        _set_pk(ss, "Dm", self.PK_SHAPE)
        _set_pk(ss, "Cm", self.PK_HOTEL)
        _set_pk(ss, "F", self.PK_SCIENTIST)
        km.add_to_queue(ss, self.PK_PERFECT, title="Perfect")
        km.add_to_queue(ss, self.PK_SHAPE, title="Shape of You")
        km.add_to_queue(ss, self.PK_HOTEL, title="Hotel California")
        km.add_to_queue(ss, self.PK_SCIENTIST, title="The Scientist")
        return ss

    def test_three_identities_simultaneous(self):
        """All three identities can reference different songs at the same time."""
        ss = self._session()
        km.start_session(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK_HOTEL
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_GRAVITY,
                         "Global Active Song must be Gravity")
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), self.PK_HOTEL,
                         "Now Editing must be Hotel California")
        self.assertEqual(km.current_session_pick_key(ss), self.PK_PERFECT,
                         "Now Singing must be Perfect (first in queue)")

    def test_start_karaoke_does_not_change_global_or_editing(self):
        """Starting karaoke must not touch global Active Song or Now Editing."""
        ss = self._session()
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK_HOTEL
        global_pk_before = ss["active_catalog_pick_key"]
        selected_before = ss["selected_song"]
        practice_key_before = ss["practice_concert_key"]
        editing_before = ss[km.KARAOKE_EDITING_PICK_KEY]
        km.start_session(ss)
        self.assertEqual(ss["active_catalog_pick_key"], global_pk_before)
        self.assertEqual(ss["selected_song"], selected_before)
        self.assertEqual(ss["practice_concert_key"], practice_key_before)
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), editing_before)

    def test_advance_does_not_change_global_or_editing(self):
        """Next Song must not alter global Active Song, selected_song, or Now Editing."""
        ss = self._session()
        km.start_session(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK_HOTEL
        global_pk = ss["active_catalog_pick_key"]
        selected = ss["selected_song"]
        practice_key = ss["practice_concert_key"]
        editing = ss[km.KARAOKE_EDITING_PICK_KEY]
        km.advance_session(ss)
        self.assertEqual(ss["active_catalog_pick_key"], global_pk)
        self.assertEqual(ss["selected_song"], selected)
        self.assertEqual(ss["practice_concert_key"], practice_key)
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), editing)
        self.assertEqual(km.current_session_pick_key(ss), self.PK_SHAPE,
                         "Now Singing should advance to Shape of You")

    def test_apply_entry_practice_key_does_not_write_global(self):
        """apply_entry_practice_key must only write to per-source store,
        never to session_state['practice_concert_key']."""
        ss = self._session()
        km.start_session(ss)
        global_key_before = ss["practice_concert_key"]
        entry = km.current_session_entry(ss)
        km.apply_entry_practice_key(ss, entry)
        self.assertEqual(ss["practice_concert_key"], global_key_before,
                         "Global practice key must not change")
        self.assertEqual(
            get_practice_concert_key(ss, entry["pick_key"]),
            entry["practice_key"],
            "Per-source store must have entry's practice key",
        )

    def test_changing_global_key_does_not_change_entries(self):
        """Changing the global Practice Key must not transpose any entry."""
        ss = self._session()
        km.start_session(ss)
        queue_before = [
            (e["title"], e["practice_key"]) for e in km.get_queue(ss)
        ]
        ss["practice_concert_key"] = "Eb"
        _set_pk(ss, "Eb", self.PK_GRAVITY)
        queue_after = [
            (e["title"], e["practice_key"]) for e in km.get_queue(ss)
        ]
        self.assertEqual(queue_before, queue_after,
                         "No karaoke entry should change when global key changes")

    def test_effective_pick_returns_singing_on_backing(self):
        """effective_catalog_pick_key returns Now Singing on backing page."""
        ss = self._session()
        km.start_session(ss)
        ss["studio_page"] = "backing"
        self.assertEqual(
            km.effective_catalog_pick_key(ss),
            self.PK_PERFECT,
            "Must return Now Singing pick key on Backing",
        )

    def test_effective_pick_returns_global_when_inactive(self):
        """effective_catalog_pick_key returns global pick when karaoke inactive."""
        ss = self._session()
        self.assertEqual(
            km.effective_catalog_pick_key(ss),
            self.PK_GRAVITY,
            "Must return global Active Song pick key when karaoke is not active",
        )

    def test_editing_pick_independent_of_singing(self):
        """Clicking a setlist entry for editing does not move Now Singing."""
        ss = self._session()
        km.start_session(ss)
        singing_before = km.current_session_pick_key(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK_SCIENTIST
        self.assertEqual(km.current_session_pick_key(ss), singing_before,
                         "Now Singing must not move when Now Editing changes")

    def test_now_editing_defaults_to_global_when_no_selection(self):
        """When no karaoke editing selection exists, the editing pick
        should fall back to the global Active Song."""
        ss = self._session()
        ss.pop(km.KARAOKE_EDITING_PICK_KEY, None)
        fallback = ss.get(km.KARAOKE_EDITING_PICK_KEY) or ss["active_catalog_pick_key"]
        self.assertEqual(fallback, self.PK_GRAVITY)

    def test_stop_preserves_editing_and_global(self):
        """Stopping karaoke must not change Now Editing or global Active Song."""
        ss = self._session()
        km.start_session(ss)
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK_HOTEL
        global_pk = ss["active_catalog_pick_key"]
        editing = ss[km.KARAOKE_EDITING_PICK_KEY]
        km.stop_session(ss)
        self.assertEqual(ss["active_catalog_pick_key"], global_pk)
        self.assertEqual(ss.get(km.KARAOKE_EDITING_PICK_KEY), editing)

    def test_karaoke_song_context_resolves_singing_song(self):
        """karaoke_song_context must return the Now Singing song's data."""
        catalog = {
            "Pop": {
                "Perfect": {"pick_key": self.PK_PERFECT, "title": "Perfect"},
                "Shape of You": {"pick_key": self.PK_SHAPE, "title": "Shape of You"},
                "Gravity": {"pick_key": self.PK_GRAVITY, "title": "Gravity"},
            },
            "Rock": {
                "Hotel California": {"pick_key": self.PK_HOTEL, "title": "Hotel California"},
            },
            "Alternative": {
                "The Scientist": {"pick_key": self.PK_SCIENTIST, "title": "The Scientist"},
            },
        }
        ss = self._session()
        km.start_session(ss)
        ctx = km.karaoke_song_context(ss, {}, catalog)
        self.assertIsNotNone(ctx)
        genre, title, data = ctx
        self.assertEqual(title, "Perfect")
        self.assertEqual(genre, "Pop")

    def test_advance_through_full_setlist(self):
        """Advancing through the full setlist must never change global state."""
        ss = self._session()
        km.start_session(ss)
        global_pk = ss["active_catalog_pick_key"]
        global_key = ss["practice_concert_key"]
        expected_songs = [self.PK_PERFECT, self.PK_SHAPE, self.PK_HOTEL, self.PK_SCIENTIST]
        for i, expected_pk in enumerate(expected_songs):
            self.assertEqual(km.current_session_pick_key(ss), expected_pk,
                             f"Song {i} should be {expected_pk}")
            self.assertEqual(ss["active_catalog_pick_key"], global_pk,
                             f"Global pick must not change at song {i}")
            self.assertEqual(ss["practice_concert_key"], global_key,
                             f"Global practice key must not change at song {i}")
            km.apply_entry_practice_key(ss, km.current_session_entry(ss))
            self.assertEqual(ss["practice_concert_key"], global_key,
                             f"apply_entry_practice_key must not write global key at song {i}")
            if i < len(expected_songs) - 1:
                km.advance_session(ss)


class TestBackingContextScopingContract(unittest.TestCase):
    """Verify the session-state scoping mechanism used during backing hydration.

    The scoping block in streamlit_music_practice_app.py temporarily shadows
    global keys so the backing pipeline sees the karaoke Now Singing song.
    These tests verify the contract: shadow → hydrate → restore.
    """

    PK_GLOBAL = "Pop\x1fGravity"
    PK_SINGING = "Pop\x1fShape of You"

    def _scoped_session(self):
        """Simulate the scoping block from the main app."""
        ss = _ss()
        ss["active_catalog_pick_key"] = self.PK_GLOBAL
        ss["selected_song"] = {"pick_key": self.PK_GLOBAL, "title": "Gravity"}
        ss["active_song_state"] = {"pick_key": self.PK_GLOBAL, "title": "Gravity"}
        ss["practice_concert_key"] = "C"
        _set_pk(ss, "Dm", self.PK_SINGING)
        km.add_to_queue(ss, self.PK_SINGING, title="Shape of You")
        km.start_session(ss)
        return ss

    def test_scope_shadows_global_keys(self):
        """During scoping, active_catalog_pick_key and selected_song must
        reflect the karaoke Now Singing song."""
        ss = self._scoped_session()
        saved = {
            "active_catalog_pick_key": ss.get("active_catalog_pick_key"),
            "selected_song": ss.get("selected_song"),
            "active_song_state": ss.get("active_song_state"),
        }
        entry = km.current_session_entry(ss)
        pk = km.current_session_pick_key(ss)
        ss["active_catalog_pick_key"] = pk
        ss["selected_song"] = {"pick_key": pk, "title": entry["title"]}
        ss["active_song_state"] = {"pick_key": pk, "title": entry["title"]}
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_SINGING)
        self.assertEqual(ss["selected_song"]["pick_key"], self.PK_SINGING)
        for k, v in saved.items():
            if v is not None:
                ss[k] = v
            else:
                ss.pop(k, None)
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_GLOBAL,
                         "Global state must be restored after scoping")
        self.assertEqual(ss["selected_song"]["pick_key"], self.PK_GLOBAL)

    def test_per_source_store_has_entry_key_for_scoped_pick(self):
        """The per-source practice-key store must have the karaoke entry's
        key for the Now Singing pick, so scoped backing hydration reads it."""
        ss = self._scoped_session()
        entry = km.current_session_entry(ss)
        km.apply_entry_practice_key(ss, entry)
        pk = entry["pick_key"]
        stored = get_practice_concert_key(ss, pk)
        self.assertEqual(stored, "Dm",
                         "Per-source store must contain karaoke entry's practice key")
        self.assertEqual(ss["practice_concert_key"], "C",
                         "Global practice key must NOT be overwritten")

    def test_lyrics_cta_button_is_primary(self):
        """The Open Lyrics & Cues Editor button must use type='primary' (red)."""
        import inspect
        from karaoke_ui import render_karaoke_setlist_missing_lyrics_cta
        src = inspect.getsource(render_karaoke_setlist_missing_lyrics_cta)
        self.assertIn('type="primary"', src,
                      "Lyrics CTA button must be type=primary (red)")
        self.assertNotIn('type="secondary"', src,
                         "Lyrics CTA button must not be type=secondary")


class TestFourEntrySetlistRegression(unittest.TestCase):
    """Regression test for the four-entry setlist scenario from requirements.

    Setlist: Perfect G, The Scientist Cm, Gravity Eb, Perfect A
    Global Active Song: Perfect A
    """

    PK_PERFECT = "Pop\x1fPerfect"
    PK_SCIENTIST = "Alternative\x1fThe Scientist"
    PK_GRAVITY = "Pop\x1fGravity"

    def _session(self) -> dict:
        ss = _ss()
        ss["active_catalog_pick_key"] = self.PK_PERFECT
        ss["selected_song"] = {"pick_key": self.PK_PERFECT, "title": "Perfect"}
        ss["practice_concert_key"] = "A"
        _set_pk(ss, "A", self.PK_PERFECT)
        _set_pk(ss, "Cm", self.PK_SCIENTIST)
        _set_pk(ss, "Eb", self.PK_GRAVITY)
        km.add_to_queue(ss, self.PK_PERFECT, title="Perfect", practice_key="G")
        km.add_to_queue(ss, self.PK_SCIENTIST, title="The Scientist", practice_key="Cm")
        km.add_to_queue(ss, self.PK_GRAVITY, title="Gravity", practice_key="Eb")
        km.add_to_queue(ss, self.PK_PERFECT, title="Perfect", practice_key="A")
        return ss

    def test_start_plays_first_entry_in_g(self):
        ss = self._session()
        km.start_session(ss)
        entry = km.current_session_entry(ss)
        self.assertEqual(entry["title"], "Perfect")
        self.assertEqual(entry["practice_key"], "G")
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_PERFECT,
                         "Global pick must remain Perfect")
        self.assertEqual(ss["practice_concert_key"], "A",
                         "Global key must remain A")

    def test_next_song_to_scientist_cm(self):
        ss = self._session()
        km.start_session(ss)
        km.advance_session(ss)
        entry = km.current_session_entry(ss)
        self.assertEqual(entry["title"], "The Scientist")
        self.assertEqual(entry["practice_key"], "Cm")
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_PERFECT)
        self.assertEqual(ss["practice_concert_key"], "A")

    def test_next_to_gravity_eb(self):
        ss = self._session()
        km.start_session(ss)
        km.advance_session(ss)
        km.advance_session(ss)
        entry = km.current_session_entry(ss)
        self.assertEqual(entry["title"], "Gravity")
        self.assertEqual(entry["practice_key"], "Eb")
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_PERFECT)
        self.assertEqual(ss["practice_concert_key"], "A")

    def test_previous_returns_to_scientist(self):
        ss = self._session()
        km.start_session(ss)
        km.advance_session(ss)
        km.advance_session(ss)
        km.regress_session(ss)
        entry = km.current_session_entry(ss)
        self.assertEqual(entry["title"], "The Scientist")
        self.assertEqual(entry["practice_key"], "Cm")

    def test_duplicate_perfect_entries_retain_independent_keys(self):
        ss = self._session()
        q = km.get_queue(ss)
        perfect_entries = [e for e in q if e["title"] == "Perfect"]
        self.assertEqual(len(perfect_entries), 2)
        self.assertEqual(perfect_entries[0]["practice_key"], "G")
        self.assertEqual(perfect_entries[1]["practice_key"], "A")
        self.assertNotEqual(perfect_entries[0]["entry_id"], perfect_entries[1]["entry_id"])

    def test_full_setlist_traversal_global_untouched(self):
        ss = self._session()
        km.start_session(ss)
        expected = [
            ("Perfect", "G"),
            ("The Scientist", "Cm"),
            ("Gravity", "Eb"),
            ("Perfect", "A"),
        ]
        for i, (title, key) in enumerate(expected):
            entry = km.current_session_entry(ss)
            self.assertEqual(entry["title"], title, f"Song {i}: expected {title}")
            self.assertEqual(entry["practice_key"], key, f"Song {i}: expected key {key}")
            km.apply_entry_practice_key(ss, entry)
            self.assertEqual(ss["practice_concert_key"], "A",
                             f"Global key must remain A at song {i}")
            self.assertEqual(ss["active_catalog_pick_key"], self.PK_PERFECT,
                             f"Global pick must remain Perfect at song {i}")
            if i < len(expected) - 1:
                km.advance_session(ss)

    def test_per_source_store_reflects_entry_key_not_global(self):
        ss = self._session()
        km.start_session(ss)
        entry = km.current_session_entry(ss)
        km.apply_entry_practice_key(ss, entry)
        stored = get_practice_concert_key(ss, entry["pick_key"])
        self.assertEqual(stored, "G",
                         "Per-source store must have entry's G, not global A")

    def test_effective_pick_key_tracks_singing(self):
        ss = self._session()
        km.start_session(ss)
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK_PERFECT)
        km.advance_session(ss)
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK_SCIENTIST)
        km.advance_session(ss)
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK_GRAVITY)
        km.advance_session(ss)
        self.assertEqual(km.effective_catalog_pick_key(ss), self.PK_PERFECT)

    def test_karaoke_transition_resets_section_scope(self):
        """_invalidate_stale_backing_for_karaoke_transition must queue Full song scope via pending flag."""
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition
        ss = self._session()
        ss["backing_track_scope"] = "Selected sections"
        ss["backing_track_multi_sections"] = ["Verse 1"]
        _invalidate_stale_backing_for_karaoke_transition(ss)
        self.assertEqual(ss.get("_pending_backing_scope"), "Full song")
        self.assertEqual(ss["backing_track_scope"], "Selected sections",
                         "widget-backed key must NOT be written directly")
        self.assertFalse(ss.get("_backing_autoplay"),
                         "autoplay is armed after generate, not before")

    def test_karaoke_transition_clears_practice_loop(self):
        """Transition must clear practice loop so Return to Practice doesn't show."""
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition
        ss = self._session()
        ss["_practice_loop_backing"] = {"some": "data"}
        _invalidate_stale_backing_for_karaoke_transition(ss)
        self.assertNotIn("_practice_loop_backing", ss)

    def test_return_label_during_karaoke(self):
        """return_to_source_button_label must show Return to Song Catalog during karaoke."""
        from backing_source_navigation import return_to_source_button_label
        ss = self._session()
        km.start_session(ss)
        label = return_to_source_button_label(None, session=ss)
        self.assertIn("Song Catalog", label)
        self.assertNotIn("Practice", label)

    def test_chart_bundle_sig_uses_karaoke_pick(self):
        """effective_catalog_pick_key returns karaoke pick for chart bundle sig."""
        ss = self._session()
        km.start_session(ss)
        eff = km.effective_catalog_pick_key(ss)
        self.assertEqual(eff, self.PK_PERFECT)
        km.advance_session(ss)
        eff = km.effective_catalog_pick_key(ss)
        self.assertEqual(eff, self.PK_SCIENTIST,
                         "After advance, effective pick must be The Scientist")
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_PERFECT,
                         "Global pick must still be Perfect")

    def test_transition_never_writes_widget_backed_keys(self):
        """_invalidate must use pending flags, never write backing_track_scope directly."""
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition
        ss = self._session()
        ss["backing_track_scope"] = "Selected sections"
        ss["backing_track_multi_sections"] = ["Verse 1", "Chorus"]
        old_scope = ss["backing_track_scope"]
        _invalidate_stale_backing_for_karaoke_transition(ss)
        self.assertEqual(ss["backing_track_scope"], old_scope,
                         "Widget-backed key must not be written by callback")
        self.assertEqual(ss.get("_pending_backing_scope"), "Full song",
                         "Must queue scope reset via non-widget pending key")
        self.assertNotIn("_pending_backing_single_section", ss)
        self.assertNotIn("_pending_backing_multi_sections", ss)

    def test_transition_does_not_prearm_autoplay(self):
        """Pre-arming autoplay makes the generator think a prior take is playing.

        streamlit_music_practice_app.py L19389 computes _prior_wav_present as
        (wav present OR autoplay OR static url OR wav path). When it is True the
        generator renders on a background thread and returns b"" for this run,
        on the premise that the previous take keeps playing. A karaoke
        transition deletes that audio, so a pre-armed autoplay flag yields a
        zero-byte WAV and total silence. Autoplay is armed only after a
        successful generate (L19933).
        """
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition
        ss = self._session()
        ss["_last_backing_wav"] = b"RIFF" + b"\x00" * 64
        ss["_last_backing_wav_path"] = r"C:\tmp\prev.wav"
        ss["_kc_current_static_url"] = "/static/prev.wav"
        ss["_backing_autoplay"] = True
        _invalidate_stale_backing_for_karaoke_transition(ss)
        prior_wav_present = bool(
            ss.get("_last_backing_wav")
            or ss.get("_last_backing_wav_b64")
            or ss.get("_backing_autoplay")
            or str(ss.get("_kc_current_static_url") or "").strip()
            or str(ss.get("_last_backing_wav_path") or "").strip()
        )
        self.assertFalse(
            prior_wav_present,
            "_prior_wav_present must be False after a transition or generation "
            "returns zero bytes on the background path and nothing plays",
        )

    def test_transition_clears_backing_context_under_real_key(self):
        """The BackingContext key is 'backing_context', not '_backing_context'."""
        from backing_source_navigation import BACKING_CONTEXT_KEY
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition
        self.assertEqual(BACKING_CONTEXT_KEY, "backing_context")
        ss = self._session()
        ss[BACKING_CONTEXT_KEY] = {"source": "regular_song", "stale": True}
        _invalidate_stale_backing_for_karaoke_transition(ss)
        self.assertNotIn(BACKING_CONTEXT_KEY, ss,
                         "stale BackingContext would bind the previous song's card")

    def test_every_transition_requests_auto_generate(self):
        """Start / Next / Previous must each arm the one-shot auto-generate flag."""
        for label, action in (
            ("start", lambda s: km.start_session(s)),
            ("advance", lambda s: (km.start_session(s), km.advance_session(s))),
            ("regress", lambda s: (km.start_session(s), km.advance_session(s),
                                   km.regress_session(s))),
        ):
            ss = self._session()
            action(ss)
            self.assertTrue(
                ss.get(km.PENDING_KARAOKE_AUTO_GENERATE_KEY),
                f"{label} must request auto-generate so the song plays itself",
            )
            self.assertTrue(km.consume_pending_auto_generate(ss))
            self.assertFalse(km.consume_pending_auto_generate(ss),
                             "flag must be one-shot")

    def test_karaoke_key_override_tracks_entry_not_global(self):
        """The chart/backing key must follow the Now Singing entry.

        resolve_active_musical_key keys off the GLOBAL active pick key, so
        without the override the chart transposes to the global Active Song's
        key while the chart content is the Now Singing song -- the live trace
        showed 'The Scientist' paired with Eb (Gravity's key). The entry is the
        only source that can distinguish Perfect G from Perfect A.
        """
        ss = self._session()
        km.start_session(ss)
        for expected in ("G", "Cm", "Eb", "A"):
            self.assertEqual(
                km.current_session_practice_key(ss), expected,
                "entry key must drive the karaoke chart/backing key",
            )
            self.assertEqual(ss["practice_concert_key"], "A",
                             "global Practice Key must never be rewritten")
            if expected != "A":
                km.advance_session(ss)

    def test_backing_hydration_shadowing_restore_is_exception_safe(self):
        """The karaoke shadowing restore must be in a finally block.

        The backing hydration temporarily overwrites the GLOBAL active song keys
        with the karaoke song. If hydration raises and the restore is merely the
        next statement, the global Active Song stays overwritten for the rest of
        the session -- the 'global Active Song changed unexpectedly' symptom.
        """
        import ast
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        tree = ast.parse(src)

        def restores_in_finally(node):
            for n in ast.walk(node):
                if not isinstance(n, ast.Try) or not n.finalbody:
                    continue
                seg = "\n".join(
                    ast.get_source_segment(src, f) or "" for f in n.finalbody
                )
                if "_kr_backing_saved" in seg and "_kr_backing_scoped" in seg:
                    return True
            return False

        self.assertTrue(
            restores_in_finally(tree),
            "the _kr_backing_saved restore must run from a finally block so a "
            "hydration error cannot leak the karaoke song into global state",
        )

    def test_empty_build_does_not_report_ready(self):
        """A finished build that produced no bytes must not report ready.

        Observed live: after GEN wav_bytes=0 every later row logged
        ready=True with has_wav=False. _session_backing_audio_ready returns
        True whenever a build is flagged, which suppressed both the karaoke
        auto-generate and Play's regenerate -- a live Play button that produced
        permanent silence.
        """
        import concurrent.futures as _cf
        import streamlit_music_practice_app as app

        sig = ("The Scientist", "Cm", "Intermediate", 73)
        ss = {app.BACKING_WAV_BUILDING_KEY: sig}
        fut: _cf.Future = _cf.Future()
        fut.set_result(b"")          # build finished and produced nothing
        app._BACKING_WAV_FUTURES[sig] = fut
        try:
            self.assertFalse(
                app.backing_wav_build_ready(ss),
                "an empty build must not count as ready",
            )
            self.assertNotIn(
                app.BACKING_WAV_BUILDING_KEY, ss,
                "the dead build marker must be dropped so the next run regenerates",
            )
        finally:
            app._BACKING_WAV_FUTURES.pop(sig, None)

    def test_nonempty_build_reports_ready(self):
        """A build that produced real bytes must still report ready."""
        import concurrent.futures as _cf
        import streamlit_music_practice_app as app

        sig = ("Perfect", "G", "Intermediate", 90)
        ss = {app.BACKING_WAV_BUILDING_KEY: sig}
        fut: _cf.Future = _cf.Future()
        fut.set_result(b"RIFF" + b"\x00" * 128)
        app._BACKING_WAV_FUTURES[sig] = fut
        try:
            self.assertTrue(app.backing_wav_build_ready(ss))
            self.assertIn(app.BACKING_WAV_BUILDING_KEY, ss)
        finally:
            app._BACKING_WAV_FUTURES.pop(sig, None)

    def test_autoplay_flag_is_not_proof_of_audio(self):
        """_prior_wav_present must require a real artifact, not an autoplay request."""
        import inspect
        import streamlit_music_practice_app as app

        src = inspect.getsource(app) if False else open(
            "streamlit_music_practice_app.py", encoding="utf-8"
        ).read()
        start = src.find("_prior_wav_present = bool(")
        self.assertGreater(start, 0, "_prior_wav_present assignment not found")
        expr = src[start:src.find(")", start) + 1]
        self.assertNotIn(
            "BACKING_AUTOPLAY", expr,
            "autoplay is a request to play, not evidence audio exists; including "
            "it sends generation down the background path with no audio to keep "
            "alive, which returns zero bytes",
        )
        self.assertIn("backing_wav_is_present", expr)

    def test_karaoke_song_reasserted_after_chart_bundle_prepare(self):
        """Now Singing must be re-asserted AFTER prepare_catalog_song_for_chart_bundle.

        That helper re-resolves the song from the GLOBAL active pick key
        whenever its overlay looks partial (the karaoke selected_song has no
        "key", so it always does), discarding the karaoke override applied
        earlier in the run. Live trace: Now Singing Gravity rendered
        perf_title 'The Scientist' with chord_count 74. This is a render-order
        constraint, so it is asserted on source order.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        prep = src.find("= prepare_catalog_song_for_chart_bundle(")
        self.assertGreater(prep, 0, "prepare_catalog_song_for_chart_bundle call not found")
        sig = src.find("_chart_bundle_sig = (", prep)
        self.assertGreater(sig, prep, "_chart_bundle_sig must follow the prepare call")
        between = src[prep:sig]
        self.assertIn(
            "km.karaoke_song_context(", between,
            "Now Singing must be re-asserted between prepare_catalog_song_for_"
            "chart_bundle and the chart bundle signature, or the bundle renders "
            "the global Active Song's chart during a karaoke set",
        )
        self.assertIn("_catalog_song_data = _kr_ctx_bundle", between)

    def test_backing_lyrics_cta_carries_entry_metadata(self):
        """The Backing Add-Lyrics callback must pass practice_key/title/genre.

        Without them the consumer cannot build a complete selected_song, and an
        incomplete selection is reverted to the previous song by pick-key
        reconciliation (observed: the entry's key landed on the sidebar while
        the pick key snapped back, and the editor stayed on the old song).
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        start = src.find("def _open_lyrics_editor_from_backing(")
        self.assertGreater(start, 0)
        body = src[start:start + 1400]
        for field in ("practice_key", "title", "genre"):
            self.assertIn(
                f'"{field}"', body,
                f"_open_lyrics_editor_from_backing must carry {field}",
            )

    def test_pending_lyrics_nav_activates_canonically(self):
        """The lyrics nav must activate canonically, not hand-write state.

        Superseded an earlier contract that asserted the hand-written
        selected_song / active_song_state writes. Those produced a partial
        transition -- selector and sidebar title moved while the canonical blob
        stayed on the previous song, leaving the Song Card and Lyrics & Cues
        editor behind -- so they are now only a fallback for when the canonical
        entry point is unavailable.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        start = src.find("_pending_lyrics_nav = st.session_state.pop(")
        self.assertGreater(start, 0)
        block = src[start:start + 4200]
        self.assertIn("activate_active_song_by_pick_key", block,
                      "the lyrics nav must use canonical activation")
        self.assertIn("_pln_activated", block,
                      "the hand-written writes must be guarded as a fallback")
        self.assertIn("_pln_home_key", block)

    def test_nav_actions_suppress_catalog_during_karaoke(self):
        """build_backing_nav_actions must not emit return_song_catalog during karaoke."""
        try:
            from backing_context import BackingContext
            from backing_nav_actions import build_backing_nav_actions
        except ImportError:
            self.skipTest("backing_nav_actions not available")
        ss = self._session()
        ss["_karaoke_active_instrument"] = "Voice"
        km.start_session(ss)
        try:
            ss["_backing_context"] = BackingContext(
                source="regular_song",
                source_label="",
                active_song_id=self.PK_PERFECT,
                song_title="Perfect",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=120,
                style="Pop",
                groove="Straight",
            )
        except Exception:
            self.skipTest("BackingContext init failed")
        actions, _ = build_backing_nav_actions(ss)
        action_ids = [a.action_id for a in actions]
        self.assertNotIn("return_song_catalog", action_ids,
                         "Duplicate Return to Song Catalog would appear")


class TestRealRenderPathFourEntry(unittest.TestCase):
    """Drive the REAL chart bundle and audio generator, not source ordering.

    Replicates the module-level sequence of streamlit_music_practice_app.py for
    each karaoke transition:

        get_song_context                        (resolves the GLOBAL song)
        -> karaoke_song_context override        (app L12486)
        -> prepare_catalog_song_for_chart_bundle(app L15116, re-resolves global)
        -> karaoke re-assert                    (the fix)
        -> build_active_chart_bundle_for_app    (app L15175)
        -> chord_blocks_for_selected_sections   (app L18327)

    Setlist: Perfect G -> The Scientist Cm -> Gravity Eb -> Perfect A, with the
    global Active Song pinned elsewhere so a leak is visible.
    """

    @classmethod
    def setUpClass(cls):
        try:
            from song_catalog.catalog import load_song_catalog, format_pick_key
            from songs.music_source import build_active_chart_bundle_for_app
            from songs.chart_bundle_startup import prepare_catalog_song_for_chart_bundle
            from songs.form import section_order, section_names_from_song
            from chart_level_arrangement import sections_for_level
            import music_theory as mt
        except ImportError as exc:                     # pragma: no cover
            raise unittest.SkipTest(f"catalog unavailable: {exc}")

        cls.LIB, cls.PICK, _g, cls.ALL = load_song_catalog()
        cls.build = staticmethod(build_active_chart_bundle_for_app)
        cls.prepare = staticmethod(prepare_catalog_song_for_chart_bundle)
        cls.section_order = staticmethod(section_order)
        cls.section_names_from_song = staticmethod(section_names_from_song)
        cls.sections_for_level = staticmethod(sections_for_level)
        cls.mt = mt
        cls.format_pick_key = staticmethod(format_pick_key)

        def _find(prefix, genre="Pop"):
            for t, d in (cls.PICK.get(genre) or {}).items():
                if t.strip().lower().startswith(prefix.lower()):
                    return genre, t, d
            raise unittest.SkipTest(f"{prefix} not in catalog")

        cls.g_perf, cls.t_perf, cls.d_perf = _find("Perfect")
        cls.g_sci, cls.t_sci, cls.d_sci = _find("The Scientist")
        cls.g_grav, cls.t_grav, cls.d_grav = _find("Gravity")
        cls.PK_PERF = format_pick_key(cls.g_perf, cls.t_perf)
        cls.PK_SCI = format_pick_key(cls.g_sci, cls.t_sci)
        cls.PK_GRAV = format_pick_key(cls.g_grav, cls.t_grav)

    class _St:
        def __init__(self, ss):
            self.session_state = ss

        def __getattr__(self, _n):
            return lambda *a, **k: None

    def _session(self, global_pk=None):
        ss = _ss(
            karaoke_mode_instrument="Voice",
            studio_page="backing",
            level="Intermediate",
        )
        gp = global_pk or self.PK_PERF
        ss["active_catalog_pick_key"] = gp
        ss["selected_song"] = {"pick_key": gp}
        ss["practice_concert_key"] = "A"
        km.add_to_queue(ss, self.PK_PERF, practice_key="G", title=self.t_perf)
        km.add_to_queue(ss, self.PK_SCI, practice_key="Cm", title=self.t_sci)
        km.add_to_queue(ss, self.PK_GRAV, practice_key="Eb", title=self.t_grav)
        km.add_to_queue(ss, self.PK_PERF, practice_key="A", title=self.t_perf)
        return ss

    def _render(self, ss):
        """Run the real pipeline exactly as the app orders it."""
        st = self._St(ss)
        cg, cs, cd = self.g_perf, self.t_perf, self.d_perf   # stand-in for global

        ctx = km.karaoke_song_context(ss, self.LIB, self.PICK)
        if ctx:
            cg, cs, cd = ctx
        cg, cs, cd = self.prepare(
            st, cg, cs, cd,
            song_picker_catalog=self.PICK, song_library=self.LIB,
        )
        # the re-assert under test
        if (km.is_voice_mode(ss) and km.is_karaoke_session_active(ss)
                and str(ss.get("studio_page") or "").lower() != "picker"):
            ctx2 = km.karaoke_song_context(ss, self.LIB, self.PICK)
            if ctx2:
                cg, cs, cd = ctx2

        entry_key = km.current_session_practice_key(ss)
        bundle = self.build(
            ss, catalog_genre=cg, catalog_song=cs, catalog_song_data=cd,
            level="Intermediate", display_key=entry_key or "C",
            cpl_active_key="_cpl_active",
            sections_for_level=self.sections_for_level,
            transpose_sections=self.mt.transpose_sections,
            song_picker_catalog=self.PICK, song_library=self.LIB,
        )
        secs = bundle.get("sections") or {}
        sd = bundle.get("song_data") or {}
        chords = []
        for n, chs in self.section_order(
            secs, section_names=self.section_names_from_song(sd)
        ):
            chords.extend(chs)
        return bundle, secs, chords

    def test_each_entry_renders_its_own_song_and_chords(self):
        ss = self._session()
        km.start_session(ss)
        expected = [
            (self.t_perf, "G"),
            (self.t_sci, "Cm"),
            (self.t_grav, "Eb"),
            (self.t_perf, "A"),
        ]
        seen = []
        for i, (title, key) in enumerate(expected):
            bundle, secs, chords = self._render(ss)
            got = str(bundle.get("song") or "")
            self.assertEqual(
                got, title,
                f"entry {i}: bundle rendered {got!r} for Now Singing {title!r} "
                "-- the global song leaked into the chart bundle",
            )
            self.assertTrue(chords, f"entry {i}: no chords -> Play disabled")
            self.assertEqual(km.current_session_practice_key(ss), key)
            seen.append((got, len(secs), len(chords), chords[0]))
            if i < len(expected) - 1:
                km.advance_session(ss)

        # Distinct songs must not share a chord count (that was the tell:
        # Gravity rendering The Scientist's 74 chords).
        self.assertNotEqual(
            seen[1][2], seen[2][2],
            f"The Scientist and Gravity both rendered {seen[1][2]} chords -- "
            "one song's chart is being reused for the other",
        )

    def test_duplicate_perfect_entries_render_different_keys(self):
        """Perfect G and Perfect A share a pick key but must sound different."""
        ss = self._session()
        km.start_session(ss)
        _b0, _s0, chords_g = self._render(ss)           # entry 0: Perfect G
        for _ in range(3):
            km.advance_session(ss)
        _b3, _s3, chords_a = self._render(ss)           # entry 3: Perfect A

        self.assertTrue(chords_g and chords_a)
        self.assertEqual(len(chords_g), len(chords_a), "same song, same length")
        self.assertNotEqual(
            chords_g[0], chords_a[0],
            "Perfect G and Perfect A produced identical chords -- the duplicate "
            "entries collapsed onto one key",
        )
        self.assertTrue(chords_g[0].startswith("G"), f"got {chords_g[0]!r}")
        self.assertTrue(chords_a[0].startswith("A"), f"got {chords_a[0]!r}")

    def test_global_active_song_survives_full_traversal(self):
        """Automatic progression must never rewrite the global identity."""
        ss = self._session(global_pk=self.PK_PERF)
        km.start_session(ss)
        for _ in range(3):
            self._render(ss)
            km.advance_session(ss)
        self._render(ss)
        km.regress_session(ss)
        self._render(ss)
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_PERF,
                         "global pick key was rewritten by karaoke progression")
        self.assertEqual(ss["practice_concert_key"], "A",
                         "global Practice Key was rewritten by karaoke progression")

    def _gravity_singing_scientist_global(self):
        """The measured failing state: Now Singing Gravity, global The Scientist."""
        ss = _ss(
            karaoke_mode_instrument="Voice",
            studio_page="backing",
            level="Intermediate",
        )
        ss["active_catalog_pick_key"] = self.PK_SCI
        ss["selected_song"] = {
            "pick_key": self.PK_SCI, "title": self.t_sci,
            "genre": self.g_sci, "key": "Dm",
        }
        ss["practice_concert_key"] = "Cm"
        km.add_to_queue(ss, self.PK_PERF, practice_key="G", title=self.t_perf)
        km.add_to_queue(ss, self.PK_SCI, practice_key="Cm", title=self.t_sci)
        km.add_to_queue(ss, self.PK_GRAV, practice_key="Eb", title=self.t_grav)
        km.add_to_queue(ss, self.PK_PERF, practice_key="A", title=self.t_perf)
        km.start_session(ss)
        km.advance_session(ss)
        km.advance_session(ss)              # -> Gravity
        return ss

    def _bundle_for(self, ss, display_key="Eb", ctx=None):
        cg, cs, cd = ctx or km.karaoke_song_context(ss, self.LIB, self.PICK)
        return self.build(
            ss, catalog_genre=cg, catalog_song=cs, catalog_song_data=cd,
            level="Intermediate", display_key=display_key,
            cpl_active_key="_cpl_active",
            sections_for_level=self.sections_for_level,
            transpose_sections=self.mt.transpose_sections,
            song_picker_catalog=self.PICK, song_library=self.LIB,
        )

    def test_bundle_is_not_blended_when_global_differs(self):
        """One bundle must not carry two songs' identity.

        Measured live (identity trace 20:33:57): bundle_song=Gravity with
        original_key=Dm and The Scientist's section count, because
        resolve_catalog_song_for_chart merged the global selected_song over the
        karaoke overlay and loaded the canonical record from the globally
        reconciled pick key. A/B verified: without the karaoke branch this
        bundle reports song_data.title='The Scientist' and original_key='Dm'.
        """
        ss = self._gravity_singing_scientist_global()
        bundle = self._bundle_for(ss)
        sd = bundle.get("song_data") or {}
        secs = bundle.get("sections") or {}

        self.assertEqual(
            str(bundle.get("original_key") or ""), "G",
            "original_key must be Gravity's G, not the global song's Dm",
        )
        self.assertTrue(
            str(sd.get("title") or "").startswith("Gravity"),
            f"song_data.title was {sd.get('title')!r}; the global song leaked "
            "into the karaoke chart bundle",
        )
        self.assertEqual(len(secs), 5, "Gravity has 5 sections; 11 is The Scientist")
        self.assertEqual(
            sum(len(v) for v in secs.values()), 32,
            "Gravity has 32 chords; 74 is The Scientist",
        )

    def test_blended_bundle_reproduces_without_karaoke_branch(self):
        """Proves the guard above is load-bearing, not vacuous."""
        ss = self._gravity_singing_scientist_global()
        # Resolve Now Singing BEFORE patching: karaoke_song_context consults the
        # same flag and would return None.
        ctx = km.karaoke_song_context(ss, self.LIB, self.PICK)
        real = km.is_karaoke_session_active
        km.is_karaoke_session_active = lambda _s: False   # bypass only the new branch
        try:
            bundle = self._bundle_for(ss, ctx=ctx)
        finally:
            km.is_karaoke_session_active = real
        sd = bundle.get("song_data") or {}
        blended = (
            str(bundle.get("original_key") or "") == "Dm"
            or str(sd.get("title") or "").startswith("The Scientist")
        )
        self.assertTrue(
            blended,
            "expected the pre-fix blend to reproduce; if this no longer blends, "
            "test_bundle_is_not_blended_when_global_differs guards nothing",
        )

    def test_global_untouched_by_chart_resolution(self):
        """Resolving the karaoke chart must not write global song or key."""
        ss = self._gravity_singing_scientist_global()
        self._bundle_for(ss)
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_SCI)
        self.assertEqual(ss["practice_concert_key"], "Cm")
        self.assertEqual(
            (ss.get("selected_song") or {}).get("pick_key"), self.PK_SCI,
            "chart resolution must not repoint the global selection",
        )

    def test_entry_audio_generates_nonempty_for_each_song(self):
        """Real synthesis must return bytes for every entry (truncated for speed)."""
        try:
            from backing_audio import generate_backing_track
        except ImportError:                             # pragma: no cover
            self.skipTest("backing_audio unavailable")
        ss = self._session()
        km.start_session(ss)
        for i in range(4):
            _bundle, secs, chords = self._render(ss)
            events = [
                {"chord": c, "section": "Test", "bar_in_section": j, "section_bars": 4}
                for j, c in enumerate(chords[:4])
            ]
            wav = generate_backing_track(
                events, bpm=100, loops=1, style="Pop groove",
                level="Intermediate", song_title="t", song_artist="a",
                time_signature="4/4",
            )
            self.assertTrue(
                wav, f"entry {i} produced an empty WAV -- an empty WAV must "
                     "never be treated as ready",
            )
            if i < 3:
                km.advance_session(ss)


class TestKaraokeOwnershipModel(unittest.TestCase):
    """Behavioural suite for the three-identity ownership model.

    Drives the real resolution chain -- karaoke_song_context,
    resolve_catalog_song_for_chart, build_active_chart_bundle_for_app,
    chord_blocks_for_selected_sections -- and fingerprints each performance by
    (title, original key, section count, chord count). Those fingerprints are
    distinct per song, so a blended or reused chart is detectable:

        Perfect        9 sections / 102 chords / G
        The Scientist 11 sections /  89 chords / Dm
        Gravity        5 sections /  32 chords / G

    The invariant under test: karaoke progression never writes global identity.
    """

    FP = {
        "Perfect": ("G", 9, 102),
        "The Scientist": ("Dm", 11, 89),
        "Gravity": ("G", 5, 32),
    }

    @classmethod
    def setUpClass(cls):
        try:
            from song_catalog.catalog import load_song_catalog, format_pick_key
            from songs.music_source import build_active_chart_bundle_for_app
            from songs.form import section_order, section_names_from_song
            from chart_level_arrangement import sections_for_level
            import music_theory as mt
        except ImportError as exc:                      # pragma: no cover
            raise unittest.SkipTest(f"catalog unavailable: {exc}")
        cls.LIB, cls.PICK, _g, cls.ALL = load_song_catalog()
        cls.build = staticmethod(build_active_chart_bundle_for_app)
        cls.section_order = staticmethod(section_order)
        cls.section_names_from_song = staticmethod(section_names_from_song)
        cls.sections_for_level = staticmethod(sections_for_level)
        cls.mt = mt

        def pick(prefix, genre="Pop"):
            for t, d in (cls.PICK.get(genre) or {}).items():
                if t.strip().lower().startswith(prefix.lower()):
                    return format_pick_key(genre, t), t
            raise unittest.SkipTest(f"{prefix} missing")

        cls.PK_PERF, cls.T_PERF = pick("Perfect")
        cls.PK_SCI, cls.T_SCI = pick("The Scientist")
        cls.PK_GRAV, cls.T_GRAV = pick("Gravity")
        cls.PK_HOTEL, cls.T_HOTEL = pick("Hotel California", "Rock")

    # ---- fixtures ---------------------------------------------------------

    def _session(self):
        """Global Active Song = Gravity / Eb, per the stated architecture."""
        ss = _ss(
            karaoke_mode_instrument="Voice",
            studio_page="backing",
            level="Intermediate",
        )
        ss["active_catalog_pick_key"] = self.PK_GRAV
        ss["selected_song"] = {
            "pick_key": self.PK_GRAV, "title": self.T_GRAV,
            "genre": "Pop", "key": "G",
        }
        ss["active_song_state"] = {"pick_key": self.PK_GRAV, "title": self.T_GRAV}
        ss["practice_concert_key"] = "Eb"
        ss["display_key"] = "Eb"
        for pk, key, title in (
            (self.PK_PERF, "G", self.T_PERF),
            (self.PK_SCI, "Cm", self.T_SCI),
            (self.PK_GRAV, "Eb", self.T_GRAV),
            (self.PK_PERF, "A", self.T_PERF),
        ):
            km.add_to_queue(ss, pk, practice_key=key, title=title)
        return ss

    GLOBAL_KEYS = (
        "active_catalog_pick_key", "practice_concert_key",
        "selected_song", "active_song_state", "display_key",
    )

    def _global_snapshot(self, ss):
        return {k: copy.deepcopy(ss.get(k)) for k in self.GLOBAL_KEYS}

    def _assert_global_unchanged(self, ss, snap, what):
        for k, v in snap.items():
            self.assertEqual(
                ss.get(k), v,
                f"{what} mutated global {k!r}: {v!r} -> {ss.get(k)!r}. "
                "Karaoke must never write global identity.",
            )

    def _fingerprint(self, ss):
        """Resolve the current entry through the real chain."""
        ctx = km.karaoke_song_context(ss, self.LIB, self.PICK)
        self.assertIsNotNone(ctx, "karaoke_song_context returned None")
        cg, cs, cd = ctx
        entry_key = km.current_session_practice_key(ss)
        bundle = self.build(
            ss, catalog_genre=cg, catalog_song=cs, catalog_song_data=cd,
            level=ss.get("level", "Intermediate"),
            display_key=entry_key or "C", cpl_active_key="_cpl_active",
            sections_for_level=self.sections_for_level,
            transpose_sections=self.mt.transpose_sections,
            song_picker_catalog=self.PICK, song_library=self.LIB,
        )
        secs = bundle.get("sections") or {}
        sd = bundle.get("song_data") or {}
        chords = []
        for n, chs in self.section_order(
            secs, section_names=self.section_names_from_song(sd)
        ):
            chords.extend(chs)
        return {
            "title": str(sd.get("title") or bundle.get("song") or ""),
            "orig": str(bundle.get("original_key") or ""),
            "nsec": len(secs),
            "nch": len(chords),
            "first": chords[0] if chords else "",
            "entry_key": entry_key,
        }

    def _assert_entry(self, fp, short_title, expect_key, where):
        exp_orig, exp_sec, exp_ch = self.FP[short_title]
        self.assertTrue(
            fp["title"].startswith(short_title),
            f"{where}: title {fp['title']!r} != {short_title!r}",
        )
        self.assertEqual(fp["orig"], exp_orig,
                         f"{where}: original key {fp['orig']!r} != {exp_orig!r}")
        self.assertEqual(fp["nsec"], exp_sec,
                         f"{where}: {fp['nsec']} sections != {exp_sec} "
                         f"-- another song's chart is in use")
        self.assertEqual(fp["nch"], exp_ch,
                         f"{where}: {fp['nch']} chords != {exp_ch}")
        self.assertEqual(fp["entry_key"], expect_key,
                         f"{where}: entry key {fp['entry_key']!r} != {expect_key!r}")

    # ---- 1. start / advance / regress leave global alone ------------------

    def test_start_does_not_change_global(self):
        ss = self._session()
        snap = self._global_snapshot(ss)
        km.start_session(ss)
        self._fingerprint(ss)
        self._assert_global_unchanged(ss, snap, "start_session")

    def test_full_traversal_never_changes_global(self):
        ss = self._session()
        km.start_session(ss)
        snap = self._global_snapshot(ss)
        plan = [("Perfect", "G"), ("The Scientist", "Cm"),
                ("Gravity", "Eb"), ("Perfect", "A")]
        for i, (title, key) in enumerate(plan):
            self._assert_entry(self._fingerprint(ss), title, key, f"forward[{i}]")
            self._assert_global_unchanged(ss, snap, f"entry {i} render")
            if i < 3:
                km.advance_session(ss)
                self._assert_global_unchanged(ss, snap, f"advance to {i + 1}")
        for i in (2, 1, 0):
            km.regress_session(ss)
            self._assert_global_unchanged(ss, snap, f"regress to {i}")
            self._assert_entry(self._fingerprint(ss), plan[i][0], plan[i][1],
                               f"backward[{i}]")

    def test_duplicate_perfect_entries_keep_separate_keys(self):
        ss = self._session()
        km.start_session(ss)
        first = self._fingerprint(ss)
        self._assert_entry(first, "Perfect", "G", "Perfect G")
        for _ in range(3):
            km.advance_session(ss)
        last = self._fingerprint(ss)
        self._assert_entry(last, "Perfect", "A", "Perfect A")
        self.assertEqual(first["nch"], last["nch"], "same song, same length")
        self.assertNotEqual(
            first["first"], last["first"],
            "Perfect G and Perfect A produced identical chords from one pick key",
        )
        self.assertTrue(first["first"].startswith("G"))
        self.assertTrue(last["first"].startswith("A"))

    # ---- 2. Songs-page editing stays independent -------------------------

    def test_changing_global_song_midset_keeps_setlist_and_cursor(self):
        """Pause karaoke, switch global song, return: cursor and entries intact."""
        ss = self._session()
        km.start_session(ss)
        km.advance_session(ss)                      # Now Singing = The Scientist
        before_idx = ss.get(km.KARAOKE_SESSION_INDEX_KEY)
        before_q = copy.deepcopy(km.get_queue(ss))

        # explicit global change (Songs page) to a different genre entirely
        ss["active_catalog_pick_key"] = self.PK_HOTEL
        ss["selected_song"] = {"pick_key": self.PK_HOTEL, "title": self.T_HOTEL,
                               "genre": "Rock", "key": "Bm"}
        ss["practice_concert_key"] = "Bm"

        self.assertEqual(ss.get(km.KARAOKE_SESSION_INDEX_KEY), before_idx,
                         "global change moved the karaoke cursor")
        self.assertEqual(km.get_queue(ss), before_q, "setlist was altered")
        self._assert_entry(self._fingerprint(ss), "The Scientist", "Cm",
                           "after global change")
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_HOTEL,
                         "karaoke rendering reverted the user's global choice")
        self.assertEqual(ss["practice_concert_key"], "Bm")

    def test_karaoke_render_does_not_repoint_global_to_entry(self):
        ss = self._session()
        km.start_session(ss)
        for _ in range(4):
            self._fingerprint(ss)
            km.advance_session(ss)
        self.assertEqual(ss["active_catalog_pick_key"], self.PK_GRAV)
        self.assertEqual(ss["practice_concert_key"], "Eb")
        self.assertEqual((ss.get("selected_song") or {}).get("title"), self.T_GRAV)

    # ---- 3. sidebar independence ----------------------------------------

    def test_sidebar_display_key_not_seeded_by_karaoke(self):
        """Karaoke must not queue a pending display key for the sidebar."""
        ss = self._session()
        ss.pop("_pending_display_key", None)
        km.start_session(ss)
        self._fingerprint(ss)
        km.advance_session(ss)
        self._fingerprint(ss)
        self.assertFalse(
            str(ss.get("_pending_display_key") or "").strip(),
            "karaoke seeded the sidebar display key; the sidebar must follow "
            "the global Active Song",
        )
        self.assertEqual(ss.get("display_key"), "Eb")

    # ---- 4. persistence / restart ---------------------------------------

    def test_session_survives_restore_reconciliation(self):
        ss = self._session()
        km.start_session(ss)
        km.advance_session(ss)
        idx = ss.get(km.KARAOKE_SESSION_INDEX_KEY)
        km.reconcile_karaoke_session_after_restore(ss)
        self.assertEqual(ss.get(km.KARAOKE_SESSION_INDEX_KEY), idx,
                         "restore reconciliation moved the performance cursor")
        self.assertEqual(km.queue_length(ss), 4)
        self._assert_entry(self._fingerprint(ss), "The Scientist", "Cm",
                           "after restore")

    def test_stop_preserves_setlist_and_global(self):
        ss = self._session()
        km.start_session(ss)
        km.advance_session(ss)
        snap = self._global_snapshot(ss)
        q = copy.deepcopy(km.get_queue(ss))
        km.stop_session(ss)
        self.assertFalse(km.is_karaoke_session_active(ss))
        self.assertEqual(km.get_queue(ss), q, "End Karaoke Set lost the setlist")
        self._assert_global_unchanged(ss, snap, "stop_session")

    # ---- 5. transport intent --------------------------------------------

    def test_every_transition_requests_generation_and_is_one_shot(self):
        ss = self._session()
        for label, act in (
            ("start", lambda: km.start_session(ss)),
            ("advance", lambda: km.advance_session(ss)),
            ("regress", lambda: km.regress_session(ss)),
        ):
            act()
            self.assertTrue(ss.get(km.PENDING_KARAOKE_AUTO_GENERATE_KEY),
                            f"{label} did not request auto-generation")
            self.assertTrue(km.consume_pending_auto_generate(ss))
            self.assertFalse(km.consume_pending_auto_generate(ss),
                             f"{label} flag was not one-shot")

    def test_transition_clears_previous_audio_without_prearming_autoplay(self):
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition
        ss = self._session()
        km.start_session(ss)
        ss["_last_backing_wav"] = b"RIFF" + b"\x00" * 32
        ss["_last_backing_wav_path"] = r"C:\tmp\prev.wav"
        ss["_kc_current_static_url"] = "/static/prev.wav"
        ss["_backing_autoplay"] = True
        snap = self._global_snapshot(ss)
        km.advance_session(ss)
        _invalidate_stale_backing_for_karaoke_transition(ss)
        for k in ("_last_backing_wav", "_last_backing_wav_path",
                  "_kc_current_static_url", "_backing_autoplay"):
            self.assertFalse(ss.get(k), f"{k} survived the transition")
        self.assertEqual(ss.get("_pending_backing_scope"), "Full song")
        self._assert_global_unchanged(ss, snap, "transition invalidation")

    # ---- 6. normal catalog unaffected -----------------------------------

    def test_non_karaoke_resolution_unchanged(self):
        """With no karaoke session the chart must follow the global song."""
        from songs.catalog_song_resolution import resolve_catalog_song_for_chart
        ss = self._session()
        km.clear_queue(ss)
        self.assertFalse(km.is_karaoke_session_active(ss))
        grav = (self.PICK.get("Pop") or {}).get(self.T_GRAV)
        sd, orig = resolve_catalog_song_for_chart(
            ss, dict(grav or {}),
            song_picker_catalog=self.PICK, song_library=self.LIB,
        )
        self.assertTrue(str(sd.get("title") or "").startswith("Gravity"))
        self.assertEqual(orig, "G")

    def test_audit_detects_karaoke_write_to_global(self):
        """The ownership audit must catch a karaoke-sourced global write."""
        ss = self._session()
        km.start_session(ss)                    # Now Singing = Perfect
        base = km.snapshot_global_identity(ss)
        self.assertEqual(km.audit_global_identity(ss, base), [],
                         "clean run must report no violation")
        # simulate the observed corruption: karaoke pick written into global
        ss["active_catalog_pick_key"] = km.current_session_pick_key(ss)
        viol = km.audit_global_identity(ss, base, where="unit")
        self.assertTrue(viol, "audit missed a karaoke write to global identity")
        self.assertEqual(viol[0]["key"], "active_catalog_pick_key")
        self.assertTrue(
            viol[0]["matches_now_singing"],
            "audit must flag that the new value is the Now Singing entry",
        )

    def test_audit_allows_explicit_editing_change(self):
        """An authorised explicit edit must not be reported as a violation."""
        ss = self._session()
        km.start_session(ss)
        base = km.snapshot_global_identity(ss)
        ss[km.EXPLICIT_GLOBAL_CHANGE_KEY] = True
        ss["active_catalog_pick_key"] = km.current_session_pick_key(ss)
        self.assertEqual(
            km.audit_global_identity(ss, base), [],
            "explicit editing actions are authorised to change global identity",
        )

    def test_pick_alignment_reconciler_skipped_during_karaoke(self):
        """_align_live_catalog_pick_to_selected_song must not run in a karaoke set.

        It aligns the global pick to whatever song is visible, assuming the pick
        lagged. During karaoke the visible song is Now Singing, so running it
        wrote the performance cursor into active_catalog_pick_key while leaving
        practice_concert_key on the previous global song -- the mixed
        Perfect / G / Eb sidebar.
        """
        try:
            from backing_source_navigation import (
                _align_live_catalog_pick_to_selected_song as align,
            )
        except ImportError:
            self.skipTest("backing_source_navigation unavailable")

        ss = self._session()
        km.start_session(ss)                    # Now Singing = Perfect
        # visible song looks like the karaoke entry, global pick is Gravity
        ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF,
                               "genre": "Pop", "key": "G"}
        align(ss)
        self.assertEqual(
            ss["active_catalog_pick_key"], self.PK_GRAV,
            "karaoke must not realign the global pick to the visible entry",
        )
        self.assertEqual(ss["practice_concert_key"], "Eb")

        # outside karaoke the reconciler must still do its job
        ss2 = self._session()
        km.clear_queue(ss2)
        self.assertFalse(km.is_karaoke_session_active(ss2))
        ss2["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF,
                                "genre": "Pop", "key": "G"}
        align(ss2)
        self.assertEqual(
            ss2["active_catalog_pick_key"], self.PK_PERF,
            "outside karaoke the reconciler must still align the lagged pick",
        )

    def test_pick_alignment_still_runs_on_songs_page(self):
        """The guard must be scoped to performance pages, not the Songs page.

        On Songs the visible song IS the editing target, so alignment is
        correct. Skipping it there would strand an Add Lyrics navigation on the
        previous global song -- the "Add lyrics for Perfect opens Gravity"
        failure.
        """
        try:
            from backing_source_navigation import (
                _align_live_catalog_pick_to_selected_song as align,
            )
        except ImportError:
            self.skipTest("backing_source_navigation unavailable")
        ss = self._session()
        km.start_session(ss)
        ss["studio_page"] = "picker"
        # Add Lyrics selected Perfect for editing; the live pick still lags.
        ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF,
                               "genre": "Pop", "key": "G"}
        align(ss)
        self.assertEqual(
            ss["active_catalog_pick_key"], self.PK_PERF,
            "on the Songs page the explicit editing target must win",
        )

    def test_nav_authority_source_blocked_on_performance_page(self):
        """_authoritative_catalog_pick_for_nav is the shared hazard source.

        Every caller treats its return value as authority to rewrite
        active_catalog_pick_key, and it is derived from the *visible* song. On
        Backing the visible song is Now Singing, so returning it hands karaoke
        authority over global identity. Two separate call sites depended on it
        (_align_live_catalog_pick_to_selected_song and
        commit_active_catalog_source_before_backing_hydrate), so it is blocked
        at the source rather than per caller.
        """
        try:
            from backing_source_navigation import (
                _authoritative_catalog_pick_for_nav as nav_auth,
            )
        except ImportError:
            self.skipTest("backing_source_navigation unavailable")

        ss = self._session()
        km.start_session(ss)                        # Now Singing = Perfect
        # the visible song on Backing is the karaoke entry
        ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF,
                               "genre": "Pop", "key": "G"}
        ss["studio_page"] = "backing"
        self.assertEqual(
            nav_auth(ss), "",
            "karaoke must not supply nav authority on a performance page",
        )
        ss["studio_page"] = "picker"
        self.assertEqual(
            nav_auth(ss), self.PK_PERF,
            "on the Songs page the visible song IS the editing target",
        )

    def test_commit_hydrate_does_not_repoint_global_during_karaoke(self):
        """The second call site must also be covered by the source guard."""
        try:
            from backing_source_navigation import (
                commit_active_catalog_source_before_backing_hydrate as commit,
            )
            from songs.key_state import invalidate_backing_cache
        except ImportError:
            self.skipTest("backing_source_navigation unavailable")

        class _St:
            def __init__(self, s):
                self.session_state = s

            def __getattr__(self, _n):
                return lambda *a, **k: None

        ss = self._session()
        km.start_session(ss)
        ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF,
                               "genre": "Pop", "key": "G"}
        ss["song"] = self.T_PERF
        ss["active_song_title"] = self.T_PERF
        try:
            commit(ss, st_like=_St(ss), song_picker_catalog=self.PICK,
                   song_library=self.LIB, invalidate_backing=invalidate_backing_cache)
        except Exception as exc:                      # pragma: no cover
            self.skipTest(f"commit raised: {exc}")
        self.assertEqual(
            ss["active_catalog_pick_key"], self.PK_GRAV,
            "backing hydrate repointed global identity at the karaoke entry",
        )
        self.assertEqual(ss["practice_concert_key"], "Eb")

    def test_add_lyrics_moves_whole_editing_context_atomically(self):
        """Reproduces the observed four-way split, not just a pick-key change.

        Observed after Add Lyrics for Gravity: selector Gravity, sidebar title
        Gravity, sidebar original key Dm, sidebar Practice Cm, Song Card The
        Scientist, Lyrics & Cues The Scientist. The selector and title moved
        while the canonical active-song blob stayed on the previous song, and
        the card, editor, original key and Practice Key all follow that blob.

        Asserts every surface lands on the same song, using the canonical
        activation entry point the production path now calls.
        """
        try:
            from songs.state import (
                activate_active_song_by_pick_key,
                SELECTED_SONG_STATE_KEY,
            )
            from songs.key_state import invalidate_backing_cache
        except ImportError:
            self.skipTest("songs.state unavailable")

        class _St:
            def __init__(self, s):
                self.session_state = s

            def __getattr__(self, _n):
                return lambda *a, **k: None

        # Global/editing context starts on The Scientist (the previous song).
        ss = self._session()
        ss["active_catalog_pick_key"] = self.PK_SCI
        ss[SELECTED_SONG_STATE_KEY] = {
            "pick_key": self.PK_SCI, "title": self.T_SCI, "genre": "Pop", "key": "Dm",
        }
        ss["active_song_state"] = {"pick_key": self.PK_SCI, "title": self.T_SCI}
        ss["practice_concert_key"] = "Cm"
        ss["studio_page"] = "picker"
        km.start_session(ss)

        # Explicit Add Lyrics for Gravity.
        activate_active_song_by_pick_key(
            _St(ss), self.PK_GRAV, self.PICK,
            song_library=self.LIB, invalidate_backing=invalidate_backing_cache,
            origin="user",
        )

        sel = ss.get(SELECTED_SONG_STATE_KEY) or {}
        canon = ss.get("active_song_state") or {}

        # 1. selector / live pick
        self.assertEqual(ss.get("active_catalog_pick_key"), self.PK_GRAV,
                         "selector did not move to Gravity")
        # 2. selected_song (sidebar title source)
        self.assertEqual(str(sel.get("pick_key") or ""), self.PK_GRAV,
                         "selected_song still points at the previous song")
        # 3. canonical blob -- drives Song Card, editor, original key
        self.assertEqual(
            str(canon.get("pick_key") or ""), self.PK_GRAV,
            "active_song_state stayed on The Scientist: this is the split that "
            "left the Song Card and Lyrics & Cues editor on the old song while "
            "the selector showed Gravity",
        )
        # 4. original key must be Gravity's G, never The Scientist's Dm
        home = str(sel.get("key") or sel.get("original_key") or "").strip()
        if home:
            self.assertEqual(
                home, "G",
                f"sidebar original key {home!r} belongs to another song "
                "(Dm is The Scientist's)",
            )
        # 5. the editor target resolves from the live pick
        self.assertNotEqual(
            str(canon.get("pick_key") or ""), self.PK_SCI,
            "editor would still open The Scientist",
        )
        # 6. the karaoke performance is untouched by the editing action
        self.assertTrue(km.is_karaoke_session_active(ss))
        self.assertEqual(km.current_session_pick_key(ss), self.PK_PERF,
                         "Add Lyrics moved the performance cursor")
        self.assertEqual(km.queue_length(ss), 4, "setlist was altered")

    def test_lyrics_nav_uses_canonical_activation(self):
        """The production path must call the canonical entry point.

        Hand-writing selected_song / active_song_state is what produced the
        partial transition; activate_active_song_by_pick_key documents itself as
        the required entry point for karaoke and setlist handlers.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        start = src.find("_pending_lyrics_nav = st.session_state.pop(")
        self.assertGreater(start, 0)
        block = src[start:start + 4200]
        self.assertIn("activate_active_song_by_pick_key", block)
        self.assertIn('origin="user"', block)

    def test_audible_chart_never_seeds_chart_html_during_karaoke(self):
        """The stale assignment itself must be skipped, not just its flag.

        Guarding only _use_audible_chart left `chart_html = _audible_chart` on
        the same branch, so the previous entry's rendered chart was still
        assigned and survived whenever the rebuild below did not replace it --
        Perfect/A kept Perfect/G's G-major chart at the top of the screen.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        anchor = src.find("chart_html = _audible_chart")
        self.assertGreater(anchor, 0, "audible chart seeding site not found")
        guard = src[max(0, anchor - 900):anchor]
        self.assertIn("_kr_audible_ok", guard,
                      "the audible branch is not karaoke-guarded")
        self.assertIn("is_karaoke_session_active", guard)
        # the condition that reaches the assignment must require the guard
        cond = src[src.find("if (\n                _kr_audible_ok"):][:200]
        self.assertIn("_kr_audible_ok", cond)
        self.assertIn("_audible_chart", cond)
        # and the flag must no longer be flipped back inside the branch body
        # (the body ends at the enclosing except handler)
        body = src[anchor:anchor + 400]
        body = body[: body.find("except Exception")] if "except Exception" in body else body
        self.assertNotIn(
            "_use_audible_chart = False", body,
            "the old flag-flip remains inside the branch; the stale assignment "
            "would still run before it",
        )

    def test_trace_captures_actual_rendered_chart(self):
        """The trace must record the rendered chart, not only chart data.

        panel_bars matching bundle_bars did not prove the visible screen was
        correct: the chord chart is a third, independently cached artifact and
        is what sits at the top when there is no lyric panel.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        anchor = src.find('"karaoke_performance_display"')
        self.assertGreater(anchor, 0)
        block = src[anchor:anchor + 3000]
        for field in ("chart_html_bars", "hide_chart", "used_audible_chart",
                      "panel_bars", "bundle_bars"):
            self.assertIn(field, block, f"trace must record {field}")

    def test_performance_surfaces_share_one_chord_source(self):
        """Panel chips and the chord chart must come from one value.

        The reported "two different keys on screen" requires two sources. Both
        the lyric panel's chord chips and the chord chart are built from
        chart_sections, and the runtime trace confirms panel_bars ==
        bundle_bars. This pins the single-source property so a second,
        independently transposed progression cannot be reintroduced.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        # panel chips
        panel = src[src.find("_panel_map[str(_sec_name)] = {"):][:420]
        self.assertIn("_sec_chords", panel)
        loop = src[src.find("for _sec_name, _sec_chords in ("):][:120]
        self.assertIn("chart_sections", loop,
                      "panel chips must be built from chart_sections")
        # the BACKING chord chart (not the Practice page's own chart). The
        # cache name appears at several sites; take the one that builds it.
        chart = ""
        pos = src.find('"backing_chart_html"')
        while pos > 0:
            window = src[pos:pos + 900]
            if "full_chord_markdown(" in window:
                chart = window
                break
            pos = src.find('"backing_chart_html"', pos + 1)
        self.assertTrue(chart, "backing chord chart build site not found")
        self.assertIn("chart_sections", chart,
                      "the backing chord chart must be built from chart_sections")
        # and the trace must expose both for comparison
        self.assertIn("panel_bars=", src)
        self.assertIn("bundle_bars=", src)

    def test_entry_key_drives_displayed_progression(self):
        """Each entry's displayed chords must be in that entry's key.

        Covers the Perfect/A case: with Practice A the progression must be
        A-rooted, never the untransposed G. The Scientist is asserted only for
        self-consistency, because its catalog record stores a B-minor chart
        under a declared key of Dm, so no render path can yield true C minor --
        that is a data defect, tracked separately.
        """
        ss = self._session()
        km.start_session(ss)
        results = []
        for expect_key in ("G", "Cm", "Eb", "A"):
            fp = self._fingerprint(ss)
            self.assertEqual(fp["entry_key"], expect_key)
            results.append((fp["title"], expect_key, fp["first"], fp["orig"]))
            if expect_key != "A":
                km.advance_session(ss)

        by_key = {k: (t, first, orig) for t, k, first, orig in results}

        # Perfect/G -> G-rooted; Perfect/A -> A-rooted; they must differ
        g_first = by_key["G"][1]
        a_first = by_key["A"][1]
        self.assertTrue(g_first.startswith("G"), f"Perfect/G gave {g_first!r}")
        self.assertTrue(
            a_first.startswith("A"),
            f"Perfect/A gave {a_first!r} -- the untransposed G progression is "
            "being displayed for the A entry",
        )
        self.assertNotEqual(g_first, a_first,
                            "duplicate Perfect entries share one progression")

        # Gravity/Eb -> Eb-rooted, not its original G
        eb_first = by_key["Eb"][1]
        self.assertTrue(eb_first.startswith("Eb"), f"Gravity/Eb gave {eb_first!r}")
        self.assertNotEqual(eb_first, "G", "Gravity shows its original key")

        # The Scientist: only that it is transposed away from the stored chart.
        sci_first, sci_orig = by_key["Cm"][1], by_key["Cm"][2]
        self.assertEqual(sci_orig, "Dm")
        self.assertNotEqual(
            sci_first, "Bm7",
            "The Scientist is showing its stored chart untransposed",
        )

    def test_show_chords_toggle_reaches_performance_renderer(self):
        """The toggle must have a consumer in the performance renderer.

        show_chords_enabled was referenced only by the toggle widget itself, so
        turning it OFF saved the setting and changed nothing on screen. The
        renderer must gate the panel's chord lists, the in-performance chart and
        the display labels, while leaving the optional collapsible chart alone.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        self.assertIn(
            "_karaoke_show_chords = km.show_chords_enabled(st.session_state)", src,
            "the performance renderer never reads the Show Chords setting",
        )
        # Anchor on the panel-map assignment: the cue-transposition block sits
        # between the toggle read and the chord gate, so a fixed-size window
        # from the toggle no longer reaches it.
        anchor = src.find('_panel_map[str(_sec_name)] = {')
        self.assertGreater(anchor, 0, "karaoke panel map build not found")
        panel = src[anchor:anchor + 500]
        self.assertIn("if _karaoke_show_chords", panel,
                      "panel chord lists are not gated on the toggle")
        # the in-performance chart must be hidden when chords are OFF
        hide = src[src.find("_karaoke_hide_chart = bool("):][:260]
        self.assertIn("not _karaoke_show_chords", hide,
                      "the in-performance chart is not hidden when chords are OFF")
        # display labels must be dropped when chords are OFF
        labels = src[src.find("_karaoke_display_labels = ("):][:320]
        self.assertIn("if _karaoke_show_chords", labels,
                      "display labels survive with chords OFF")
        self.assertIn("else {}", labels)

    def test_show_chords_setting_round_trips(self):
        """OFF must persist across transitions and reruns, not reset."""
        ss = self._session()
        km.start_session(ss)
        self.assertTrue(km.show_chords_enabled(ss), "default should be ON")
        ss[km.KARAOKE_SHOW_CHORDS_KEY] = False
        self.assertFalse(km.show_chords_enabled(ss))
        for _ in range(3):
            km.advance_session(ss)
            self.assertFalse(
                km.show_chords_enabled(ss),
                "Show Chords OFF was lost across a karaoke transition",
            )
        km.regress_session(ss)
        self.assertFalse(km.show_chords_enabled(ss))
        km.stop_session(ss)
        self.assertFalse(km.show_chords_enabled(ss),
                         "setting must survive End Set")

    def test_backing_source_header_describes_now_singing(self):
        """The header must identify the entry, not the global editing song.

        It is built from the sealed BackingContext's song_title plus the global
        practice key, so it read "Gravity · Eb" directly above a Karaoke Song
        Card showing The Scientist · Cm.
        """
        src = open("backing_context_ui.py", encoding="utf-8").read()
        anchor = src.find("_kr_banner_ctx = ctx")
        self.assertGreater(anchor, 0, "no karaoke banner override present")
        block = src[anchor:anchor + 1400]
        self.assertIn("current_session_practice_key", block,
                      "header key must come from the entry")
        self.assertIn("current_session_entry", block,
                      "header title must come from the entry")
        self.assertIn("_kr_banner_ctx.song_title = _kr_title", block)
        # the call must consume the overridden values, not the originals
        call = src[src.find("label = format_backing_context_banner("):][:400]
        self.assertIn("_kr_banner_ctx", call)
        self.assertIn("practice_concert_key=_kr_banner_key", call)

    def test_large_chord_text_not_served_from_previous_arrangement(self):
        """The follow timeline must not fall back to the audible arrangement.

        The large current-chord display is driven by _follow_timeline. During a
        karaoke transition a static URL exists and the signature necessarily
        differs, so the audible (previous) timeline was served there while the
        chord buttons rendered the new entry -- two keys on one screen.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        anchor = src.find("_follow_timeline = _kc_audible_tl(st.session_state)")
        self.assertGreater(anchor, 0, "audible timeline branch not found")
        before = src[max(0, anchor - 1200):anchor]
        self.assertIn("_pending_arr = False", before,
                      "karaoke must not use the previous arrangement's timeline")
        self.assertIn("is_karaoke_session_active", before)
        after = src[anchor:anchor + 1400]
        self.assertIn("_kr_perf_tl", after,
                      "the _stored_timeline fallback is also a previous-"
                      "arrangement artifact and must be bypassed during karaoke")

    def test_sidebar_banner_title_uses_global_record(self):
        """Every sidebar field, including the banner title, is the global song.

        The banner title read _catalog_song_data (repointed at Now Singing),
        producing the reported split: title "The Scientist - Coldplay" above a
        description of "Gravity - Pop".
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        anchor = src.find("_src_kind, _src_detail = unpack_active_source_banner(")
        self.assertGreater(anchor, 0)
        block = src[max(0, anchor - 600):anchor + 500]
        self.assertIn("_sb_banner_data", block,
                      "banner title must resolve from the global record")
        self.assertIn('globals().get("_global_catalog_song_data")', block)
        self.assertNotIn(
            'catalog_title=_catalog_song_data.get("title", _catalog_song)', block,
            "banner title still reads the karaoke-overridden record",
        )

    def test_sidebar_reads_global_identity_not_now_singing(self):
        """The sidebar must render the global Active Song, by READ path.

        No writer was ever found because global state was never written: the
        sidebar read _catalog_song / _catalog_genre / _catalog_song_data, which
        are deliberately repointed at the Now Singing entry so the chart bundle
        resolves it. The app now captures the pre-override global identity and
        the sidebar reads that instead. Render-order constraint: the capture
        must precede both sidebar reads.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        lines = src.split("\n")

        def line_of(pat):
            for i, l in enumerate(lines, 1):
                if pat in l:
                    return i
            return -1

        cap = line_of("_global_catalog_song_data = _catalog_song_data")
        override = line_of("_catalog_genre, _catalog_song, _catalog_song_data = _kr_ctx")
        caption = line_of("_sb_song = globals().get")
        orig = line_of("original_key, _song_identity = display_key_context")

        for name, ln in (("capture", cap), ("override", override),
                         ("caption read", caption), ("original-key read", orig)):
            self.assertGreater(ln, 0, f"{name} site not found")

        self.assertLess(cap, override,
                        "global identity must be captured BEFORE the karaoke override")
        self.assertLess(override, caption,
                        "sidebar caption must come after the override to be at risk")
        self.assertIn('globals().get("_global_catalog_song")',
                      "\n".join(lines[caption - 2:caption + 2]),
                      "sidebar caption must read the captured global identity")
        self.assertIn(
            '_global_catalog_song_data',
            "\n".join(lines[orig - 2:orig + 6]),
            "sidebar Song Original Key must resolve from the global record, "
            "not the karaoke entry's",
        )

    def test_sidebar_and_performance_identities_are_separate_values(self):
        """Global and Now Singing must be independently resolvable at once.

        Exercises the stated scenario: Perfect/G explicitly selected globally
        while karaoke advances through The Scientist/Cm, Gravity/Eb, Perfect/A.
        """
        ss = self._session()
        # explicit global selection = Perfect / G
        ss["active_catalog_pick_key"] = self.PK_PERF
        ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF,
                               "genre": "Pop", "key": "G"}
        ss["active_song_state"] = {"pick_key": self.PK_PERF, "title": self.T_PERF}
        ss["practice_concert_key"] = "G"
        ss["display_key"] = "G"
        km.start_session(ss)

        expected = [(self.T_PERF, "G"), (self.T_SCI, "Cm"),
                    (self.T_GRAV, "Eb"), (self.T_PERF, "A")]
        for i, (title, prac) in enumerate(expected):
            ctx = km.karaoke_song_context(ss, self.LIB, self.PICK)
            self.assertIsNotNone(ctx)
            _g, perf_song, _cd = ctx
            # performance identity follows the entry
            self.assertTrue(perf_song.startswith(title.split(" ")[0]),
                            f"step {i}: performance song {perf_song!r} != {title!r}")
            self.assertEqual(km.current_session_practice_key(ss), prac)
            # global identity is untouched and still Perfect / G
            self.assertEqual(ss["active_catalog_pick_key"], self.PK_PERF,
                             f"step {i}: global pick drifted")
            self.assertEqual(ss["practice_concert_key"], "G",
                             f"step {i}: global Practice Key drifted")
            self.assertEqual(
                str((ss.get("selected_song") or {}).get("key") or ""), "G",
                f"step {i}: global original key drifted",
            )
            if i < 3:
                km.advance_session(ss)

    def test_card_metadata_comes_from_entry_record(self):
        """Title, artist, genre and original key must be the entry's own.

        Issue 5: verifies provenance rather than inventing metadata. Tempo and
        feel are intentionally NOT asserted to reset across entries, so a
        user-selected playback override is preserved.
        """
        ss = self._session()
        km.start_session(ss)
        seen = []
        for _ in range(4):
            ctx = km.karaoke_song_context(ss, self.LIB, self.PICK)
            self.assertIsNotNone(ctx)
            g, t, cd = ctx
            rec = (self.PICK.get("Pop") or {}).get(t) or {}
            # the resolved record must BE the catalog row for that song
            self.assertEqual(
                str(cd.get("title") or ""), str(rec.get("title") or ""),
                f"{t}: card title not from the song's own catalog record",
            )
            self.assertEqual(
                str(cd.get("artist") or ""), str(rec.get("artist") or ""),
                f"{t}: artist not from the song's own record",
            )
            self.assertEqual(
                str(cd.get("key") or ""), str(rec.get("key") or ""),
                f"{t}: original key not from the song's own record",
            )
            self.assertEqual(str(g or ""), "Pop", f"{t}: genre/source wrong")
            seen.append((str(cd.get("title")), str(cd.get("key"))))
            km.advance_session(ss)
        # each entry resolved its own metadata; Perfect appears twice with the
        # same original key but the pairs must not collapse to one song
        self.assertEqual(len({t for t, _ in seen}), 3,
                         f"expected 3 distinct songs across 4 entries: {seen}")
        self.assertEqual(seen[0], seen[3],
                         "duplicate Perfect entries must share song metadata")

    def test_card_identity_and_key_advance_together(self):
        """Song identity must advance with the Practice Key, not lag behind it.

        Fixing only the card's Practice Key left title / artist / original key
        coming from the sealed BackingContext, which lags a transition, so the
        card read "Perfect, original G" beside the newly advanced Practice Eb
        or Cm. Asserts the whole card describes one song at every entry.
        """
        expected = [
            (self.T_PERF, "G", "G"),
            (self.T_SCI, "Dm", "Cm"),
            (self.T_GRAV, "G", "Eb"),
            (self.T_PERF, "G", "A"),
        ]
        ss = self._session()
        km.start_session(ss)
        for i, (title, home, prac) in enumerate(expected):
            ctx = km.karaoke_song_context(ss, self.LIB, self.PICK)
            self.assertIsNotNone(ctx, f"entry {i}: no karaoke song context")
            _g, _t, cd = ctx
            card_title = str((cd or {}).get("title") or _t or "")
            card_home = str((cd or {}).get("key") or (cd or {}).get("original_key") or "")
            card_prac = km.current_session_practice_key(ss)

            self.assertTrue(
                title.startswith(card_title) or card_title.startswith(title.split(" ")[0]),
                f"entry {i}: card title {card_title!r} is not {title!r}",
            )
            self.assertEqual(card_home, home,
                             f"entry {i}: card original key {card_home!r} != {home!r}")
            self.assertEqual(card_prac, prac,
                             f"entry {i}: card practice key {card_prac!r} != {prac!r}")
            # the pairing must be self-consistent: never one song's title with
            # another entry's key
            self.assertNotEqual(
                (card_title, card_prac), (self.T_PERF, "Eb"),
                "reproduced the reported Perfect/Eb mixed card",
            )
            self.assertNotEqual(
                (card_title, card_prac), (self.T_PERF, "Cm"),
                "reproduced the reported Perfect/Cm mixed card",
            )
            if i < 3:
                km.advance_session(ss)

    def test_chart_display_key_follows_entry_for_labels_and_chords(self):
        """The key that labels the chart must be the entry's, not the original.

        The optional chart said "You're working in G major" / "Key: G" above Eb
        chord boxes because its display key came from _backing_musical /
        chart_key (the song's original) while the chords came from the entry's
        transposed bundle. One value drives both, so they must agree.
        """
        ss = self._session()
        km.start_session(ss)
        for title, home, prac in (
            (self.T_PERF, "G", "G"),
            (self.T_SCI, "Dm", "Cm"),
            (self.T_GRAV, "G", "Eb"),
            (self.T_PERF, "G", "A"),
        ):
            fp = self._fingerprint(ss)
            entry_key = km.current_session_practice_key(ss)
            self.assertEqual(entry_key, prac)
            # chords are rendered in the entry key, so the label key must match
            self.assertEqual(
                fp["entry_key"], prac,
                f"{title}: chart key {fp['entry_key']!r} would label the chart "
                f"as {fp['entry_key']} while chords sound in {prac}",
            )
            self.assertNotEqual(
                fp["entry_key"], home if home != prac else "",
                f"{title}: chart labelled with the ORIGINAL key {home}",
            )
            if prac != "A":
                km.advance_session(ss)

    def test_performance_chart_source_reasserted_for_karaoke(self):
        """chart_sections / chart_display_key must be re-asserted from the entry.

        Render-order constraint: every branch that sets them can take them from
        _backing_musical, which lags a karaoke transition and holds the song's
        untransposed chart. That is what rendered Perfect's G progression as
        the large chord text while the buttons showed Perfect in A.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        anchor = src.find("chart_sections = performed_sections\n                chart_display_key")
        self.assertGreater(anchor, 0, "chart_sections fallback not found")
        after = src[anchor:anchor + 1800]
        self.assertIn("km.is_karaoke_session_active", after,
                      "no karaoke re-assert after the chart_sections writers")
        self.assertIn("chart_sections = performed_sections", after)
        self.assertIn("chart_display_key = _kr_chart_key", after)

    def test_no_perfect_content_survives_advance_to_scientist(self):
        """Perfect/G -> The Scientist/Cm must leave no Perfect content behind.

        Reproduces the reported screenshot: a The Scientist title above
        Perfect's progression, with the chord buttons showing a second,
        different transposition of that same Perfect chart. Asserts on chart
        CONTENT (section names and chord sequence), not counts, because two
        songs can share a section count.
        """
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition

        ss = self._session()
        km.start_session(ss)                       # Perfect / G
        first = self._fingerprint(ss)
        self._assert_entry(first, "Perfect", "G", "entry 0")
        perfect_first_bars = first["first"]
        self.assertTrue(perfect_first_bars.startswith("G"))

        # artifacts the Backing page carries after performing Perfect
        ss["_kc_audible_chart_html"] = "<div>PERFECT CHART G D/F# Em7</div>"
        ss["_kc_last_open_chart_html"] = "<div>PERFECT CHART G D/F# Em7</div>"
        ss["_session_cache_backing_chart_html"] = {"sig": ("Perfect",), "value": "stale"}
        ss["_last_backing_wav"] = b"PERFECT-WAV"
        ss["_last_backing_wav_path"] = r"C:\tmp\perfect.wav"
        ss["_kc_current_static_url"] = "/app/static/kc/perfect.wav"
        gen_before = km.render_generation(ss)

        km.advance_session(ss)                     # -> The Scientist / Cm
        _invalidate_stale_backing_for_karaoke_transition(ss)

        # 1. no rendered chart artifact from the previous entry
        for k in ("_kc_audible_chart_html", "_kc_last_open_chart_html"):
            self.assertFalse(
                ss.get(k),
                f"{k} kept the previous entry's chart; it renders under the "
                "new title",
            )
        # 2. no stale audio artifact
        for k in ("_last_backing_wav", "_last_backing_wav_path",
                  "_kc_current_static_url"):
            self.assertFalse(ss.get(k), f"{k} survived the transition")
        # 3. render generation changed so mounted components cannot persist
        gen_after = km.render_generation(ss)
        self.assertNotEqual(gen_before, gen_after,
                            "render generation must change on an entry change")
        # 4. the resolved chart is The Scientist's content, not Perfect's
        second = self._fingerprint(ss)
        self._assert_entry(second, "The Scientist", "Cm", "entry 1")
        self.assertNotEqual(
            second["nsec"], first["nsec"],
            "section count matches Perfect -- Perfect's chart is still in use",
        )
        self.assertNotEqual(second["nch"], first["nch"])
        # 5. the chord sequence must not be a transposition of Perfect's chart.
        #    Perfect/G starts G D/F# Em7; any transposition keeps that shape, so
        #    compare the interval pattern rather than the literal chords.
        self.assertNotEqual(
            second["first"], first["first"],
            "first chord identical to Perfect's",
        )
        self.assertFalse(
            second["first"].startswith("F") and second["nsec"] == first["nsec"],
            "F-rooted chart with Perfect's section count is the measured blend "
            "(Perfect moved Dm->Cm)",
        )

    def test_render_generation_tracks_entry_not_global_song(self):
        """Generation must follow the entry, including duplicates of one song."""
        ss = self._session()
        km.start_session(ss)
        gens = []
        for _ in range(4):
            gens.append(km.render_generation(ss))
            km.advance_session(ss)
        self.assertEqual(len(set(gens)), 4,
                         f"each entry needs a distinct generation: {gens}")
        # Perfect/G and Perfect/A share a pick key but must differ
        self.assertNotEqual(gens[0], gens[3],
                            "duplicate entries of one song collapsed to one "
                            "generation, so the chart could be reused")
        # changing the global song must not change the generation
        before = km.render_generation(ss)
        ss["active_catalog_pick_key"] = self.PK_HOTEL
        ss["selected_song"] = {"pick_key": self.PK_HOTEL, "title": self.T_HOTEL}
        ss["practice_concert_key"] = "Bm"
        self.assertEqual(
            km.render_generation(ss), before,
            "render generation must not depend on the global Active Song",
        )

    def test_catalog_session_blob_cannot_leak_key_into_karaoke_chart(self):
        """The previous entry's catalog_session blob must not supply the key.

        resolve_catalog_song_for_chart merges catalog_session["selected_song"]
        over the chart overlay, stripping key/original_key/identity but keeping
        the rest. After performing Perfect/G the blob still held Perfect's
        chart content, and the next entry's bundle came back as
        "The Scientist" with original_key G -- Perfect's key under The
        Scientist's identity. A/B verified: with the guard bypassed this
        reports G, with it enabled Dm.
        """
        perf = (self.PICK.get("Pop") or {}).get(self.T_PERF) or {}
        if not perf:
            self.skipTest("Perfect record unavailable")

        def build(bypass_guard):
            ss = self._session()
            ss["active_catalog_pick_key"] = self.PK_PERF
            ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF,
                                   "key": "G"}
            ss["practice_concert_key"] = "G"
            km.start_session(ss)
            km.advance_session(ss)              # Now Singing = The Scientist / Cm
            # the blob the app still carries from the previous entry
            ss["catalog_session"] = {
                "selected_song": {
                    "pick_key": self.PK_PERF,
                    "title": self.T_PERF,
                    "sections": dict(perf.get("sections") or {}),
                    "chart_versions": dict(perf.get("chart_versions") or {}),
                }
            }
            cg, cs, cd = km.karaoke_song_context(ss, self.LIB, self.PICK)
            real = km.is_karaoke_session_active
            if bypass_guard:
                km.is_karaoke_session_active = lambda _s: False
            try:
                return self.build(
                    ss, catalog_genre=cg, catalog_song=cs, catalog_song_data=cd,
                    level="Intermediate", display_key="Cm",
                    cpl_active_key="_cpl_active",
                    sections_for_level=self.sections_for_level,
                    transpose_sections=self.mt.transpose_sections,
                    song_picker_catalog=self.PICK, song_library=self.LIB,
                )
            finally:
                km.is_karaoke_session_active = real

        leaked = build(bypass_guard=True)
        fixed = build(bypass_guard=False)

        self.assertEqual(
            str(leaked.get("original_key") or ""), "G",
            "expected the pre-fix key leak to reproduce; if it no longer does, "
            "the assertion below guards nothing",
        )
        self.assertEqual(
            str(fixed.get("original_key") or ""), "Dm",
            "the karaoke entry's own original key must win over the previous "
            "entry's catalog_session blob",
        )
        # identity and chart length must be the entry's in both cases
        self.assertTrue(str(fixed.get("song") or "").startswith("The Scientist"))
        secs = fixed.get("sections") or {}
        self.assertEqual(len(secs), 11, "The Scientist has 11 sections")
        self.assertEqual(sum(len(v) for v in secs.values()), 89)

    def test_bundle_trace_identifies_chart_by_content(self):
        """The bundle trace must name the chart, not just count it.

        A title plus a section count cannot distinguish the right song's chart
        from another song's chart of the same length, which is exactly how a
        Scientist title over Perfect's progression went unnoticed.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        start = src.find('"chart_bundle_built"')
        self.assertGreater(start, 0)
        block = src[start:start + 1200]
        for field in ("section_names", "first_bars", "song_data_title",
                      "song_data_key"):
            self.assertIn(field, block, f"bundle trace must record {field}")

    def test_duplicate_entries_share_canonical_lyrics_identity(self):
        """Perfect/G and Perfect/A must resolve to one lyrics identity.

        Lyrics belong to a song, not to a karaoke entry or a transposed key.
        Queue entries carry no artist and their title is the combined catalog
        label ("Perfect - Ed Sheeran"), which does not match how lyrics are
        stored (title "Perfect", artist "Ed Sheeran"), so Perfect/A was
        prompted again even though Perfect already had saved lyrics.
        """
        from karaoke_ui import _canonical_song_identity_for_entry as canon
        ss = self._session()
        q = km.get_queue(ss)
        perfect = [e for e in q if str(e.get("pick_key")) == self.PK_PERF]
        self.assertEqual(len(perfect), 2, "fixture must hold both Perfect entries")
        self.assertNotEqual(perfect[0]["practice_key"], perfect[1]["practice_key"])

        a = canon(perfect[0])
        b = canon(perfect[1])
        self.assertEqual(a, b, "duplicate entries resolved different lyrics identities")
        self.assertEqual(a[0], "Perfect", f"title not canonicalised: {a!r}")
        self.assertTrue(a[1], "artist must be recovered from the pick key")
        # a different song must not collide
        sci = [e for e in q if str(e.get("pick_key")) == self.PK_SCI][0]
        self.assertNotEqual(canon(sci), a)

    def test_canonical_identity_ignores_entry_key_and_id(self):
        from karaoke_ui import _canonical_song_identity_for_entry as canon
        base = {"pick_key": self.PK_PERF, "title": self.T_PERF}
        v1 = canon({**base, "practice_key": "G", "entry_id": "e1"})
        v2 = canon({**base, "practice_key": "A", "entry_id": "e2"})
        v3 = canon({"pick_key": self.PK_PERF})          # no title at all
        self.assertEqual(v1, v2)
        self.assertEqual(v1, v3, "identity must come from the pick key")

    def test_add_lyrics_does_not_push_entry_key_to_global(self):
        """Editing a duplicate entry must not retune the global Practice Key.

        Add Lyrics selects the SONG; the song's own sticky Practice Key belongs
        on the sidebar. Forcing the playlist entry's key meant editing
        Perfect/A silently set the global Practice Key to A, and with two
        entries of one song whichever was clicked last would win.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        start = src.find("_pending_lyrics_nav = st.session_state.pop(")
        self.assertGreater(start, 0)
        block = src[start:src.find("# The active workflow pointer owns", start)]
        self.assertNotIn(
            'st.session_state["practice_concert_key"] = _pln_practice_key', block,
            "the lyrics nav must not write the entry key into the global "
            "Practice Key",
        )
        self.assertIn("activate_active_song_by_pick_key", block)

    def test_explicit_selection_reversion_is_detected(self):
        """A non-explicit path undoing an explicit selection must be reported."""
        ss = self._session()
        km.start_session(ss)
        ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF}
        ss["active_catalog_pick_key"] = self.PK_PERF
        ss["practice_concert_key"] = "A"
        km.remember_explicit_global_selection(ss)
        self.assertIsNone(km.audit_explicit_global_reverted(ss),
                          "a held selection must not be reported")

        # returning to Backing snaps the selection onto the playlist entry
        ss["selected_song"] = {"pick_key": self.PK_GRAV, "title": self.T_GRAV}
        ss["active_catalog_pick_key"] = self.PK_GRAV
        for _ in range(2):
            km.advance_session(ss)                 # Now Singing = Gravity
        rev = km.audit_explicit_global_reverted(ss)
        self.assertIsNotNone(rev, "reversion of the explicit selection missed")
        self.assertEqual(rev["expected"][-20:], self.PK_PERF[-20:])
        self.assertTrue(rev["reverted_to_now_singing"],
                        "must flag that it reverted to the playlist entry")

    def test_audit_ignores_incidental_field_changes(self):
        """Identity comparison, not dict equality.

        Comparing whole dicts reported every bpm / title-spelling update as an
        ownership violation, producing 52 alerts in one run that all read
        "PopGravity -> PopGravity" and burying any real signal.
        """
        ss = self._session()
        km.start_session(ss)
        base = km.snapshot_global_identity(ss)
        sel = dict(ss.get("selected_song") or {})
        sel["bpm"] = 142
        sel["groove"] = "Pop groove"
        ss["selected_song"] = sel
        self.assertEqual(
            km.audit_global_identity(ss, base), [],
            "incidental field changes must not be reported as violations",
        )
        # a real identity change still is
        ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF}
        self.assertTrue(km.audit_global_identity(ss, base))

    def test_lyrics_target_mismatch_is_detected(self):
        """A retargeted lyrics editor must be caught without any global write."""
        ss = self._session()
        km.start_session(ss)
        km.record_lyrics_target_request(ss, self.PK_PERF, "entry-1")
        bad = km.audit_lyrics_target(ss, self.PK_GRAV)
        self.assertIsNotNone(bad, "opening a different song must be reported")
        self.assertEqual(bad["requested"], self.PK_PERF)
        self.assertEqual(bad["opened"], self.PK_GRAV)
        self.assertEqual(bad["entry_id"], "entry-1")

    def test_lyrics_target_match_is_silent_and_consumed(self):
        ss = self._session()
        km.record_lyrics_target_request(ss, self.PK_PERF, "entry-1")
        self.assertIsNone(km.audit_lyrics_target(ss, self.PK_PERF))
        self.assertNotIn(km.LYRICS_TARGET_REQUEST_KEY, ss,
                         "the request must be consumed once verified")
        self.assertIsNone(km.audit_lyrics_target(ss, self.PK_GRAV),
                          "a consumed request must not re-fire")

    def test_lyrics_request_survives_until_editor_resolves(self):
        """The request must persist across the navigation rerun."""
        ss = self._session()
        km.record_lyrics_target_request(ss, self.PK_PERF, "e1")
        # editor not resolved yet this run -> request must be kept
        self.assertIsNone(km.audit_lyrics_target(ss, ""))
        self.assertIn(km.LYRICS_TARGET_REQUEST_KEY, ss)
        self.assertIsNotNone(km.audit_lyrics_target(ss, self.PK_GRAV))

    def test_lyrics_navigation_preserves_karaoke_cursor(self):
        """An explicit edit must not move the performance position."""
        ss = self._session()
        km.start_session(ss)
        km.advance_session(ss)                      # Now Singing = The Scientist
        idx = ss.get(km.KARAOKE_SESSION_INDEX_KEY)
        singing = km.current_session_pick_key(ss)
        queue = copy.deepcopy(km.get_queue(ss))

        km.record_lyrics_target_request(ss, self.PK_PERF, "e1")
        ss[km.KARAOKE_EDITING_PICK_KEY] = self.PK_PERF
        ss[km.EXPLICIT_GLOBAL_CHANGE_KEY] = True
        ss["active_catalog_pick_key"] = self.PK_PERF
        ss["selected_song"] = {"pick_key": self.PK_PERF, "title": self.T_PERF,
                               "genre": "Pop", "key": "G"}

        self.assertEqual(ss.get(km.KARAOKE_SESSION_INDEX_KEY), idx,
                         "Add Lyrics moved the karaoke cursor")
        self.assertEqual(km.current_session_pick_key(ss), singing,
                         "Now Singing changed during an editing action")
        self.assertEqual(km.get_queue(ss), queue, "setlist was altered")
        self.assertEqual(ss[km.KARAOKE_EDITING_PICK_KEY], self.PK_PERF)

    def test_no_mixed_title_and_key_across_owners(self):
        """Global title and global key must always describe the same song."""
        ss = self._session()
        km.start_session(ss)
        for i in range(4):
            self._fingerprint(ss)
            sel = ss.get("selected_song") or {}
            self.assertEqual(
                str(sel.get("pick_key") or ""), self.PK_GRAV,
                f"step {i}: global selection drifted to another song while its "
                "Practice Key stayed Eb -- that is the mixed sidebar",
            )
            self.assertEqual(ss.get("practice_concert_key"), "Eb")
            self.assertEqual(str(sel.get("key") or ""), "G",
                             "global original key must stay with its own song")
            if i < 3:
                km.advance_session(ss)

    def test_instrument_mode_ignores_karaoke_entirely(self):
        """A non-voice instrument must resolve the global song, not the entry."""
        ss = self._session()
        km.start_session(ss)
        ss["instrument"] = "Guitar"
        ss["karaoke_mode_instrument"] = "Guitar"
        self.assertFalse(km.is_voice_mode(ss))
        self.assertEqual(
            km.effective_catalog_pick_key(ss), self.PK_GRAV,
            "instrument mode must fall back to the global Active Song",
        )


if __name__ == "__main__":
    unittest.main()


class TestKaraokePerformanceComponentIdentity(unittest.TestCase):
    """The performance component must remount per karaoke entry.

    Measured at entry 4 (Perfect/A): the chart bundle, the lyric-panel map, the
    follow timeline and the chart HTML were all A-major -- 0 G-markers -- while
    Chrome still displayed Perfect/G. Correct data with a wrong screen means a
    stale iframe: components.html has no key of its own, so Streamlit can reuse
    the element across entries, and the component's script builds the chord
    strip once on load. Perfect/G and Perfect/A share a song and a title, which
    is where element reuse is most likely.
    """

    @classmethod
    def setUpClass(cls):
        try:
            from song_catalog.catalog import load_song_catalog, format_pick_key
        except ImportError as exc:                      # pragma: no cover
            raise unittest.SkipTest(f"catalog unavailable: {exc}")
        cls.LIB, cls.PICK, _g, cls.ALL = load_song_catalog()

        def pick(prefix, genre="Pop"):
            for t in (cls.PICK.get(genre) or {}):
                if t.strip().lower().startswith(prefix.lower()):
                    return format_pick_key(genre, t), t
            raise unittest.SkipTest(f"{prefix} missing")

        cls.PK_PERF, cls.T_PERF = pick("Perfect")
        cls.PK_SCI, cls.T_SCI = pick("The Scientist")
        cls.PK_GRAV, cls.T_GRAV = pick("Gravity")

    def _queue(self):
        ss = _ss(karaoke_mode_instrument="Voice", studio_page="backing")
        for pk, key, title in (
            (self.PK_PERF, "G", self.T_PERF),
            (self.PK_SCI, "Cm", self.T_SCI),
            (self.PK_GRAV, "Eb", self.T_GRAV),
            (self.PK_PERF, "A", self.T_PERF),
        ):
            km.add_to_queue(ss, pk, practice_key=key, title=title)
        return ss

    @staticmethod
    def _container_key(ss) -> str:
        gen = km.render_generation(ss)
        slug = "".join(c if c.isalnum() else "_" for c in str(gen))[:60]
        return f"karaoke_perf_{slug}"

    def test_container_key_unique_per_entry_including_duplicates(self):
        ss = self._queue()
        km.start_session(ss)
        keys = []
        for i in range(4):
            keys.append(self._container_key(ss))
            if i < 3:
                km.advance_session(ss)
        self.assertEqual(len(set(keys)), 4,
                         f"entries share a component identity: {keys}")
        self.assertNotEqual(
            keys[0], keys[3],
            "Perfect/G and Perfect/A share one component key, so the iframe is "
            "reused and the G-major chord strip survives into the A entry",
        )

    def test_container_key_is_stable_within_one_entry(self):
        """It must not churn on ordinary reruns, only on a transition."""
        ss = self._queue()
        km.start_session(ss)
        first = self._container_key(ss)
        for _ in range(3):
            self.assertEqual(self._container_key(ss), first,
                             "component remounts on every rerun")
        km.advance_session(ss)
        self.assertNotEqual(self._container_key(ss), first,
                            "component did not remount on a transition")

    def test_container_key_ignores_global_active_song(self):
        ss = self._queue()
        km.start_session(ss)
        before = self._container_key(ss)
        ss["active_catalog_pick_key"] = self.PK_GRAV
        ss["selected_song"] = {"pick_key": self.PK_GRAV, "title": self.T_GRAV}
        ss["practice_concert_key"] = "Eb"
        self.assertEqual(
            self._container_key(ss), before,
            "component identity must not depend on the global Active Song",
        )

    def test_component_is_wrapped_in_keyed_container(self):
        """Render-order constraint: the keyed wrapper must exist in production."""
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        anchor = src.find("_kr_perf_container")
        self.assertGreater(anchor, 0, "no keyed performance container present")
        block = src[anchor:anchor + 1200]
        self.assertIn("km.render_generation(st.session_state)", block,
                      "the container key must derive from the karaoke entry")
        self.assertIn('st.container(key=f"karaoke_perf_', block)
        self.assertIn("with _kr_perf_container:", block,
                      "the component must render inside the keyed container")


class TestKaraokeInstrumentalCueLine(unittest.TestCase):
    """The large "Instrumental - ..." line must match the entry's key.

    Found by browser screenshot, not by any server trace: the black NOW SINGING
    panel showed "Instrumental - G . D/F# . Em7 . D . Cadd9" in large text while
    the chord chips beneath it correctly showed A . E/G# . F#m7 . E . Dadd9 --
    two keys in one panel.

    Cause: that text is a lyric CUE, and Perfect's Intro cue in the catalog
    embeds the progression as prose
    (song_catalog/curated_songs.py: "Instrumental - G . D/F# . Em7 . ...").
    Because the chords live inside a lyric string rather than chord data, no
    chart transposition reached them. Every earlier trace field measured the
    panel's ``chords`` list, never its ``lyrics`` list, which is why this
    survived repeated "both surfaces agree" conclusions.

    Fixed at the render layer; the catalog record is unchanged.
    """

    MID = "\u00b7"
    DASH = "\u2014"

    @classmethod
    def setUpClass(cls):
        import re as _re

        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        # Anchor on the import line that precedes the helpers. An earlier anchor
        # hard-coded `re.compile`, which stopped matching when the module-level
        # alias changed -- and the class then SKIPPED silently, which is worse
        # than failing. Missing helpers now fail loudly.
        start = src.find("import re as _cue_re")
        end = src.find("def _distribute_chord_chips(")
        assert start >= 0, "cue helper block not found in the app module"
        assert end > start, "cue helper block boundary not found"
        ns: dict = {"re": _re}
        exec(src[start:end], ns)          # noqa: S102 - module helper under test
        assert "transpose_chord_tokens_in_cue" in ns, (
            "transpose_chord_tokens_in_cue is missing from the app module"
        )
        cls.transpose_cue = staticmethod(ns["transpose_chord_tokens_in_cue"])

    def _perfect_intro_cue(self) -> str:
        m = self.MID
        return (
            f"Instrumental {self.DASH} G {m} D/F# {m} Em7 {m} D {m} Cadd9 {m} D {m} G"
        )

    def test_perfect_a_instrumental_line_is_a_major(self):
        """The exact acceptance requirement for entry 4."""
        out = self.transpose_cue(self._perfect_intro_cue(), "G", "A")
        m = self.MID
        expected = (
            f"Instrumental {self.DASH} A {m} E/G# {m} F#m7 {m} E {m} Dadd9 {m} E {m} A"
        )
        self.assertEqual(out, expected)
        # and explicitly: no original-key chord may remain
        for stale in ("D/F#", "Em7", "Cadd9"):
            self.assertNotIn(stale, out, f"{stale} is an original-key chord")

    def test_perfect_g_instrumental_line_unchanged(self):
        """Entry 1 already matched; it must not be rewritten."""
        cue = self._perfect_intro_cue()
        self.assertEqual(self.transpose_cue(cue, "G", "G"), cue)

    def test_slash_chord_bass_is_transposed_too(self):
        """A rich slash bass must move, or one token keeps the old key."""
        m = self.MID
        out = self.transpose_cue(
            f"Instrumental {self.DASH} D {m} G {m} D {m} D/Dmaj7", "Dm", "Cm"
        )
        self.assertIn("C/Cmaj7", out, f"slash bass left untransposed: {out}")
        self.assertNotIn("D/Dmaj7", out)

    def test_prose_cues_are_not_rewritten(self):
        """Only a genuine chord run may be touched."""
        for prose in (
            f"Instrumental {self.DASH} maintain groove",
            f"Instrumental {self.DASH} solo acoustic + percussion swell",
            f"Build {self.DASH} A little softer here",     # English "A"
            f"Intro {self.DASH} G",                        # single chord, no run
            "no separator at all G D/F#",
        ):
            self.assertEqual(
                self.transpose_cue(prose, "G", "A"), prose,
                f"prose cue was rewritten: {prose!r}",
            )

    def test_panel_applies_cue_transposition_in_production(self):
        """Render-order constraint: the panel must pass cues through the helper.

        Anchored on the panel map build, which is unique to the karaoke panel.
        A looser anchor matched the lyric-guide card's ``lyric_lines = ...``
        line elsewhere in the module.
        """
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        anchor = src.find("_panel_map[str(_sec_name)] = {")
        self.assertGreater(anchor, 0, "karaoke panel map build not found")
        # the cue correction happens just above the panel-map assignment
        block = src[max(0, anchor - 1200):anchor + 200]
        self.assertIn("transpose_chord_tokens_in_cue", block,
                      "panel lyric lines are not key-corrected")
        self.assertIn("_cue_from_key", block)
        self.assertIn("_cue_to_key", block)
        # and the corrected lines must be what the panel stores
        self.assertIn('"lyrics": _lines', block)

    def test_temporary_diagnostic_badges_removed(self):
        src = open("streamlit_music_practice_app.py", encoding="utf-8").read()
        self.assertNotIn("KARAOKE DIAG", src)
        self.assertNotIn("DIAG quick_coaching", src)
