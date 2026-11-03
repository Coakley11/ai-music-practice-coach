"""Provenance-aware stale chart handling.

An old saved copy of a CATALOG chart must not override a corrected catalog entry
(Day Tripper 159 -> 94 bars, Imagine 109 -> 60, So What 24 -> 32), while edited,
custom, composition and user-override charts stay intact.

Fixture ``fixtures/stale_chart_catalog_revisions.json`` holds the real
before (origin/dev 3de1117b) and after (integration/w1-16-candidate) effective
Advanced sections for the three songs.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from song_catalog.catalog import format_pick_key
from songs import chart_provenance as cp
from songs.music_source import resolve_catalog_song_for_chart
from songs.state import ACTIVE_CATALOG_PICK_KEY

_FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "stale_chart_catalog_revisions.json").read_text(encoding="utf-8")
)
EXPECT_BARS = {"Day Tripper": (159, 94), "Imagine": (109, 60), "So What": (24, 32)}


def _bars(sections: dict) -> int:
    return sum(len(v) for v in sections.values())


def _label(title: str) -> str:
    return f"{title} — {_FIX[title]['artist']}"


def _row(title: str, *, sections=None, extra=None) -> dict:
    f = _FIX[title]
    row = {"title": title, "artist": f["artist"], "genre": f["genre"], "key": f["key"],
           "sections": copy.deepcopy(sections or f["new_sections"])}
    row.update(extra or {})
    return row


def _catalog(title: str, **kw) -> dict:
    f = _FIX[title]
    return {f["genre"]: {_label(title): _row(title, **kw)}}


def _pick(title: str) -> str:
    return format_pick_key(_FIX[title]["genre"], _label(title))


def _stale_sel(title: str, **extra) -> dict:
    sel = {"pick_key": _pick(title), "title": title, "artist": _FIX[title]["artist"],
           "genre": _FIX[title]["genre"], "key": _FIX[title]["key"],
           "sections": copy.deepcopy(_FIX[title]["old_sections"])}
    sel.update(extra)
    return sel


def _resolve(title: str, session: dict, overlay: dict | None = None, catalog: dict | None = None) -> dict:
    cat = catalog or _catalog(title)
    session.setdefault(ACTIVE_CATALOG_PICK_KEY, _pick(title))
    merged, _ = resolve_catalog_song_for_chart(
        session, overlay or {}, song_picker_catalog=cat, song_library=cat
    )
    return merged


class FixtureSanityTests(unittest.TestCase):
    def test_real_bar_counts(self) -> None:
        for title, (old, new) in EXPECT_BARS.items():
            self.assertEqual(_bars(_FIX[title]["old_sections"]), old)
            self.assertEqual(_bars(_FIX[title]["new_sections"]), new)


class StaleCatalogCopyReplacedTests(unittest.TestCase):
    def test_selected_song_stale_copy_replaced_all_three_songs(self) -> None:
        for title, (_old, new) in EXPECT_BARS.items():
            with self.subTest(title=title):
                merged = _resolve(title, {"selected_song": _stale_sel(title)})
                self.assertEqual(_bars(merged["sections"]), new)
                self.assertEqual(merged["sections"], _FIX[title]["new_sections"])

    def test_catalog_session_stale_copy_replaced(self) -> None:
        for title, (_old, new) in EXPECT_BARS.items():
            with self.subTest(title=title):
                stale = _stale_sel(title)
                session = {
                    "catalog_session": {"pick_key": _pick(title), "selected_song": stale,
                                        "sections": copy.deepcopy(stale["sections"])},
                    "selected_song": {"pick_key": _pick(title), "title": title,
                                      "artist": _FIX[title]["artist"], "genre": _FIX[title]["genre"]},
                }
                self.assertEqual(_bars(_resolve(title, session)["sections"]), new)

    def test_bundle_overlay_stale_copy_replaced(self) -> None:
        title = "Day Tripper"
        overlay = _row(title, sections=_FIX[title]["old_sections"])
        overlay["pick_key"] = _pick(title)
        merged = _resolve(title, {}, overlay)
        self.assertEqual(_bars(merged["sections"]), 94)

    def test_session_copies_are_healed_incl_improv_concert_sections(self) -> None:
        """Load Last Song / song switching: every stored copy follows the catalog."""
        title = "Day Tripper"
        old = copy.deepcopy(_FIX[title]["old_sections"])
        session = {
            "selected_song": _stale_sel(title),
            "catalog_session": {"pick_key": _pick(title), "selected_song": _stale_sel(title),
                                "sections": copy.deepcopy(old)},
            "improv_song_concert_sections": copy.deepcopy(old),
            "home_sections": copy.deepcopy(old),
        }
        _resolve(title, session)
        new = _FIX[title]["new_sections"]
        self.assertEqual(session["selected_song"]["sections"], new)
        self.assertEqual(session["catalog_session"]["sections"], new)
        self.assertEqual(session["catalog_session"]["selected_song"]["sections"], new)
        self.assertEqual(session["improv_song_concert_sections"], new)
        self.assertEqual(session["home_sections"], new)
        self.assertTrue(session[cp.PROVENANCE_LOG_KEY])

    def test_other_song_improv_sections_not_touched(self) -> None:
        title = "Day Tripper"
        other = copy.deepcopy(_FIX["Imagine"]["old_sections"])
        session = {"selected_song": _stale_sel(title), "improv_song_concert_sections": other}
        _resolve(title, session)
        self.assertEqual(session["improv_song_concert_sections"], other)

    def test_cross_song_snapshot_not_used_to_replace(self) -> None:
        """A snapshot whose title/pick belongs to another song is kept by classify."""
        canon = _row("Day Tripper")
        snap = _stale_sel("Imagine")
        self.assertEqual(cp.classify_snapshot(snap, canon, pick_key=_pick("Day Tripper"))[0], cp.KEEP)


class EditedAndOverrideChartsPreservedTests(unittest.TestCase):
    def test_user_chart_override_in_canonical_beats_stale_copy(self) -> None:
        title = "Day Tripper"
        edited = {"Verse": ["E7", "A7", "B7", "E7"]}
        cat = _catalog(title, sections=edited, extra={"user_override": {"status": "user_corrected"},
                                                      "chart_status": "user_corrected"})
        merged = _resolve(title, {"selected_song": _stale_sel(title)}, catalog=cat)
        self.assertEqual(merged["sections"], edited)  # user's saved chords, not stale, not pristine

    def test_user_override_applied_from_real_override_store(self) -> None:
        from song_catalog import user_overrides as uo

        title = "Imagine"
        base = _row(title)
        entry = {"sections": {"Verse": ["C", "F"]}, "chart_versions": {}, "section_order": ["Verse"],
                 "override_status": uo.USER_CORRECTED, "saved_at": "2026-01-01",
                 "catalog_snapshot": {"sections": _FIX[title]["old_sections"]}}
        with mock.patch.object(uo, "get_user_override", return_value=entry):
            rec = uo.apply_user_override_to_record(base)
        self.assertEqual(rec["sections"], {"Verse": ["C", "F"]})
        # catalog moved on since the edit: flagged, never silently dropped
        self.assertTrue(rec["user_override"]["catalog_changed_since_edit"])
        cat = {_FIX[title]["genre"]: {_label(title): rec}}
        merged = _resolve(title, {"selected_song": _stale_sel(title)}, catalog=cat)
        self.assertEqual(merged["sections"], {"Verse": ["C", "F"]})

    def test_explicitly_customized_arrangement_snapshot_kept(self) -> None:
        canon = _row("Day Tripper")
        custom_secs = {"Verse": ["E7", "E7", "A7", "A7"]}
        for marker in ({"user_edited": True}, {"arrangement_customized": True},
                       {"edited_level": "Advanced"}, {"chart_origin": "user_edited"}):
            with self.subTest(marker=marker):
                snap = _stale_sel("Day Tripper", **marker)
                snap["sections"] = copy.deepcopy(custom_secs)
                out = cp.reconcile_snapshot(snap, canon, pick_key=_pick("Day Tripper"))
                self.assertEqual(out["sections"], custom_secs)

    def test_provenance_snapshot_modified_after_stamp_is_kept(self) -> None:
        canon = _row("Day Tripper")
        snap = _stale_sel("Day Tripper")
        snap[cp.CHART_ORIGIN_KEY] = "catalog"
        snap[cp.CATALOG_REVISION_KEY] = cp.chart_fingerprint(_FIX["Day Tripper"]["old_sections"])
        snap["sections"] = {"Verse": ["E7", "G7"]}  # changed after it was stamped
        out = cp.reconcile_snapshot(snap, canon, pick_key=_pick("Day Tripper"))
        self.assertEqual(out["sections"], {"Verse": ["E7", "G7"]})


class NonCatalogChartsPreservedTests(unittest.TestCase):
    def test_custom_song_same_title_kept(self) -> None:
        canon = _row("Day Tripper")
        custom = {"pick_key": "custom::abc123", "title": "Day Tripper", "artist": "Me",
                  "source_type": "custom", "sections": {"Verse": ["A", "D"]}}
        self.assertEqual(cp.reconcile_snapshot(custom, canon, pick_key=_pick("Day Tripper")), custom)
        blob = {"active_song_state": {"selected_song": copy.deepcopy(custom)}}
        self.assertEqual(cp.reconcile_payload_chart_copies(blob), 0)
        self.assertEqual(blob["active_song_state"]["selected_song"], custom)

    def test_custom_pick_key_resolver_path_untouched(self) -> None:
        title = "Day Tripper"
        sel = {"pick_key": "custom::abc123", "title": title, "artist": "Me",
               "source_type": "custom", "sections": {"Verse": ["A", "D"]}}
        merged = _resolve(title, {ACTIVE_CATALOG_PICK_KEY: _pick(title), "selected_song": sel})
        # source_type custom + custom pick_key: snapshot is not a catalog copy
        self.assertEqual(cp.classify_snapshot(sel, _row(title), pick_key=_pick(title))[0], cp.KEEP)
        self.assertTrue(merged["sections"])

    def test_composition_song_kept(self) -> None:
        canon = _row("Imagine")
        comp = {"pick_key": "composition::c1", "title": "Imagine", "source_type": "composition",
                "sections": {"A": ["C", "F"]}}
        self.assertEqual(cp.reconcile_snapshot(comp, canon, pick_key=_pick("Imagine")), comp)
        blob = {"session": {"composer_active_document": {"form": {"sections": {"A": ["C"]}}},
                            "selected_song": copy.deepcopy(comp)}}
        before = copy.deepcopy(blob)
        cp.reconcile_payload_chart_copies(blob)
        self.assertEqual(blob, before)

    def test_mission_creative_contexts_kept(self) -> None:
        canon = _row("So What")
        mission = _stale_sel("So What", mission_type="Chord Tones", mission_chord="Dm7")
        mission["sections"] = {"Span": ["Dm7"]}
        self.assertEqual(cp.reconcile_snapshot(mission, canon, pick_key=_pick("So What")), mission)
        creative = _stale_sel("So What", source_type="creative")
        self.assertEqual(cp.reconcile_snapshot(creative, canon, pick_key=_pick("So What")), creative)
        # a dict outside the snapshot containers is never walked
        blob = {"improv_mission_example": {"pick_key": _pick("So What"), "sections": {"Span": ["Dm7"]}}}
        before = copy.deepcopy(blob)
        cp.reconcile_payload_chart_copies(blob)
        self.assertEqual(blob, before)


class LegacyAndProvenanceTests(unittest.TestCase):
    def test_legacy_snapshot_without_provenance_refreshes_and_is_stamped(self) -> None:
        canon = _row("Day Tripper")
        legacy = _stale_sel("Day Tripper")
        self.assertNotIn(cp.CHART_ORIGIN_KEY, legacy)
        out = cp.reconcile_snapshot(legacy, canon, pick_key=_pick("Day Tripper"))
        self.assertEqual(out["sections"], _FIX["Day Tripper"]["new_sections"])
        self.assertEqual(out[cp.CHART_ORIGIN_KEY], "catalog")
        self.assertEqual(out[cp.CATALOG_REVISION_KEY], cp.chart_fingerprint(canon["sections"]))

    def test_ambiguous_legacy_snapshot_kept_and_logged(self) -> None:
        canon = _row("Day Tripper")
        session: dict = {}
        ambiguous = {"sections": copy.deepcopy(_FIX["Day Tripper"]["old_sections"])}
        out = cp.reconcile_snapshot(ambiguous, canon, session=session)
        self.assertEqual(out["sections"], _FIX["Day Tripper"]["old_sections"])
        self.assertEqual(session[cp.PROVENANCE_LOG_KEY][-1]["reason"], "legacy_ambiguous")

    def test_provenance_old_revision_refreshes(self) -> None:
        canon = _row("Imagine")
        snap = _stale_sel("Imagine")
        snap[cp.CHART_ORIGIN_KEY] = "catalog"
        snap[cp.CATALOG_REVISION_KEY] = cp.chart_fingerprint(snap["sections"])
        action, reason = cp.classify_snapshot(snap, canon, pick_key=_pick("Imagine"))
        self.assertEqual((action, reason), (cp.REFRESH, "provenance_unmodified_old_revision"))

    def test_verbatim_current_copy_is_stamped_not_changed(self) -> None:
        canon = _row("So What")
        snap = _stale_sel("So What")
        snap["sections"] = copy.deepcopy(canon["sections"])
        out = cp.reconcile_snapshot(snap, canon, pick_key=_pick("So What"))
        self.assertEqual(out["sections"], canon["sections"])
        self.assertEqual(out[cp.CATALOG_REVISION_KEY], cp.chart_fingerprint(canon["sections"]))


class CloudHydratedBlobTests(unittest.TestCase):
    def _blob(self) -> dict:
        title = "Day Tripper"
        old = _FIX[title]["old_sections"]
        sel = _stale_sel(title)
        cat = {"pick_key": _pick(title), "original_key": "E", "selected_song": copy.deepcopy(sel),
               "sections": copy.deepcopy(old)}
        return {
            "active_song_state": {"selected_song": copy.deepcopy(sel)},
            "session": {"catalog_session": copy.deepcopy(cat),
                        "improv_song_concert_sections": copy.deepcopy(old)},
            "creative_workspace_state": {"catalog_session": copy.deepcopy(cat)},
            "music_workspace_state": {"creative_workspace_state": {"catalog_session": copy.deepcopy(cat)}},
        }

    def test_cloud_blob_stale_copies_refreshed_everywhere(self) -> None:
        blob = self._blob()
        row = _row("Day Tripper")
        with mock.patch.object(cp, "_canonical_for_pick", return_value=row):
            n = cp.reconcile_payload_chart_copies(blob, where="test")
        self.assertGreaterEqual(n, 4)
        new = _FIX["Day Tripper"]["new_sections"]
        self.assertEqual(blob["active_song_state"]["selected_song"]["sections"], new)
        self.assertEqual(blob["session"]["catalog_session"]["sections"], new)
        self.assertEqual(blob["session"]["catalog_session"]["selected_song"]["sections"], new)
        self.assertEqual(blob["session"]["improv_song_concert_sections"], new)
        self.assertEqual(blob["creative_workspace_state"]["catalog_session"]["sections"], new)
        self.assertEqual(
            blob["music_workspace_state"]["creative_workspace_state"]["catalog_session"]["sections"], new
        )

    def test_cloud_blob_with_user_edited_snapshot_untouched(self) -> None:
        blob = self._blob()
        blob["active_song_state"]["selected_song"]["user_edited"] = True
        blob["active_song_state"]["selected_song"]["sections"] = {"Verse": ["E7", "A7"]}
        keep = copy.deepcopy(blob["active_song_state"]["selected_song"])
        with mock.patch.object(cp, "_canonical_for_pick", return_value=_row("Day Tripper")):
            cp.reconcile_payload_chart_copies(blob)
        self.assertEqual(blob["active_song_state"]["selected_song"], keep)

    def test_apply_music_disk_state_refreshes_payload_before_restore(self) -> None:
        import music_persistent_state as mps

        blob = self._blob()
        seen: dict = {}

        class _Stop(Exception):
            pass

        class _St:
            session_state: dict = {}

        def _boom(*_a, **_k):
            seen["sel"] = copy.deepcopy(blob["active_song_state"]["selected_song"]["sections"])
            raise _Stop

        with mock.patch.object(cp, "_canonical_for_pick", return_value=_row("Day Tripper")), \
                mock.patch.dict("sys.modules", {}), \
                mock.patch("mission_pending_upload_analysis.envelope_from_session_or_canonical", _boom,
                           create=True):
            try:
                mps.apply_music_disk_state(_St(), blob, song_picker_catalog={}, song_library={})
            except _Stop:
                pass
            except Exception:
                pass
        self.assertEqual(seen.get("sel"), _FIX["Day Tripper"]["new_sections"])

    def test_save_path_stamps_provenance_and_never_persists_stale_copy(self) -> None:
        state = self._blob()
        with mock.patch.object(cp, "_canonical_for_pick", return_value=_row("Day Tripper")):
            cp.reconcile_payload_chart_copies(state, where="build_music_disk_state")
        sel = state["active_song_state"]["selected_song"]
        self.assertEqual(sel[cp.CHART_ORIGIN_KEY], "catalog")
        self.assertEqual(sel[cp.CATALOG_REVISION_KEY], cp.chart_fingerprint(_FIX["Day Tripper"]["new_sections"]))


if __name__ == "__main__":
    unittest.main()
