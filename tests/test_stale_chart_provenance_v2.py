"""v2 hardening of the stale-chart provenance fix (review defects 1-5).

1. Legacy (unstamped) snapshots are refreshed ONLY when they exactly equal a KNOWN PRIOR
   catalog revision of the same song (songs/chart_revision_table.py); transposed / capo /
   level-subset / custom-marked / unknown snapshots are kept and logged.
2. The identity-only legacy branch honours ``source: custom`` (and song_source / is_custom).
3. Transposed / capo / level-subset copies are kept (no normalisation implemented).
4. A stale ``selected_state`` nested under a mission is never touched.
5. Failures at the call sites are logged into the bounded ``_chart_provenance_log`` (never
   raised); the payload walker is copy-on-write (shared nested dicts are not mutated).
"""

from __future__ import annotations

import copy
import re
import unittest
from collections.abc import MutableMapping
from pathlib import Path
from unittest import mock

from songs import chart_provenance as cp
from songs.chart_revision_table import PRIOR_REVISIONS
from tests.test_stale_chart_provenance import _FIX, _pick, _resolve, _row, _stale_sel

DAY = "Day Tripper"
WAVE_TITLES = [
    "Photograph", "Don't Stop Believin'", "Day Tripper", "Imagine", "Californication", "So What",
    "Take the A Train", "All the Things You Are", "Satin Doll", "All of Me", "Misty", "Meditation",
    "Vienna", "Just the Way You Are", "Uptown Girl", "Careless Whisper", "We Are the Champions",
    "Kiss Me", "Thinking Out Loud", "Come Together", "Heal the World", "Wave", "How Insensitive",
    "So Nice (Summer Samba)", "Autumn Leaves", "Fly Me to the Moon",
]


def _transpose(chord: str, semis: int = 2) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    m = re.match(r"^([A-G]#?)(.*)$", chord)
    if not m:
        return chord
    return names[(names.index(m.group(1)) + semis) % 12] + m.group(2)


def _transposed(sections: dict) -> dict:
    return {k: [_transpose(c) for c in v] for k, v in sections.items()}


class _MappingSession(MutableMapping):
    """Mapping that is NOT a dict (like st.session_state)."""

    def __init__(self) -> None:
        self._d: dict = {}

    def __getitem__(self, k):
        return self._d[k]

    def __setitem__(self, k, v) -> None:
        self._d[k] = v

    def __delitem__(self, k) -> None:
        del self._d[k]

    def __iter__(self):
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)


class RevisionTableTests(unittest.TestCase):
    def test_table_covers_wave_songs(self) -> None:
        norm = lambda t: " ".join(t.replace("’", "'").lower().split())  # noqa: E731
        have = {k.split("|")[1] for k in PRIOR_REVISIONS}
        for t in WAVE_TITLES:
            self.assertIn(norm(t), have, t)

    def test_table_fingerprints_match_real_old_charts(self) -> None:
        for title in ("Day Tripper", "Imagine", "So What"):
            key = cp.revision_key(_row(title))
            fps = {sec for sec, _ in PRIOR_REVISIONS[key]}
            self.assertIn(cp.chart_fingerprint(_FIX[title]["old_sections"]), fps, title)
            self.assertNotIn(cp.chart_fingerprint(_FIX[title]["new_sections"]), fps, title)

    def test_generator_script_present_and_documented(self) -> None:
        script = Path(__file__).resolve().parent.parent / "scripts" / "gen_catalog_revision_table.py"
        text = script.read_text(encoding="utf-8")
        self.assertIn("--baseline-root", text)
        self.assertIn("PRIOR_REVISIONS", text)


class LegacyRuleIsConservativeTests(unittest.TestCase):
    def _classify(self, snap: dict, title: str = DAY):
        return cp.classify_snapshot(snap, _row(title), pick_key=_pick(title))

    def test_known_prior_revision_still_refreshes(self) -> None:
        self.assertEqual(
            self._classify(_stale_sel(DAY)), (cp.REFRESH, "legacy_known_prior_catalog_revision")
        )
        for title in ("Imagine", "So What"):
            self.assertEqual(self._classify(_stale_sel(title), title)[0], cp.REFRESH, title)

    def test_transposed_snapshot_kept_and_logged(self) -> None:
        snap = _stale_sel(DAY)
        snap["sections"] = _transposed(snap["sections"])
        session: dict = {}
        out = cp.reconcile_snapshot(snap, _row(DAY), pick_key=_pick(DAY), session=session)
        self.assertEqual(out["sections"], snap["sections"])
        self.assertEqual(session[cp.PROVENANCE_LOG_KEY][-1]["reason"], "legacy_unknown_revision_kept")

    def test_transposed_current_catalog_chart_kept(self) -> None:
        snap = _stale_sel(DAY)
        snap["sections"] = _transposed(_FIX[DAY]["new_sections"])
        self.assertEqual(self._classify(snap), (cp.KEEP, "legacy_unknown_revision_kept"))

    def test_capo_shape_snapshot_kept(self) -> None:
        snap = _stale_sel(DAY, capo=2)
        snap["sections"] = {k: [_transpose(c, -2) for c in v] for k, v in snap["sections"].items()}
        self.assertEqual(self._classify(snap), (cp.KEEP, "legacy_unknown_revision_kept"))

    def test_level_subset_snapshot_kept(self) -> None:
        snap = _stale_sel(DAY)
        first = next(iter(snap["sections"]))
        snap["sections"] = {first: snap["sections"][first][:4]}
        self.assertEqual(self._classify(snap), (cp.KEEP, "legacy_unknown_revision_kept"))
        snap2 = _stale_sel(DAY)
        snap2["sections"] = {k: v for i, (k, v) in enumerate(snap2["sections"].items()) if i < 2}
        self.assertEqual(self._classify(snap2)[0], cp.KEEP)

    def test_old_sections_with_foreign_chart_versions_kept(self) -> None:
        snap = _stale_sel(DAY)
        # Day Tripper's recorded prior revision has chart_versions; an alien level map must not match
        key = cp.revision_key(_row(DAY))
        if any(v for _, v in PRIOR_REVISIONS[key]):
            snap["chart_versions"] = {"Beginner": {"Verse": ["E7", "A7"]}}
            self.assertEqual(self._classify(snap)[0], cp.KEEP)

    def test_custom_markers_keep_even_a_known_old_chart(self) -> None:
        for extra in (
            {"is_custom": True},
            {"composition_id": "c-123"},
            {"chart_status": "user_corrected"},
            {"user_chart": True},
            {"source": "custom"},
            {"song_source": "custom"},
        ):
            action, reason = self._classify(_stale_sel(DAY, **extra))
            self.assertEqual(action, cp.KEEP, (extra, reason))

    def test_identity_only_branch_respects_source_custom(self) -> None:
        # no pick key: only title/artist identity + the active catalog pick
        snap = {"title": DAY, "artist": _FIX[DAY]["artist"], "source": "custom",
                "sections": copy.deepcopy(_FIX[DAY]["old_sections"])}
        action, reason = cp.classify_snapshot(snap, _row(DAY), pick_key=_pick(DAY))
        self.assertEqual((action, reason), (cp.KEEP, "source_custom"))

    def test_identity_only_branch_refreshes_known_revision_only(self) -> None:
        known = {"title": DAY, "artist": _FIX[DAY]["artist"],
                 "sections": copy.deepcopy(_FIX[DAY]["old_sections"])}
        self.assertEqual(
            cp.classify_snapshot(known, _row(DAY), pick_key=_pick(DAY)),
            (cp.REFRESH, "legacy_identity_known_prior_catalog_revision"),
        )
        unknown = dict(known, sections={"Verse": ["E", "A", "B"]})
        self.assertEqual(
            cp.classify_snapshot(unknown, _row(DAY), pick_key=_pick(DAY)),
            (cp.KEEP, "legacy_unknown_revision_kept"),
        )

    def test_resolver_keeps_unknown_legacy_overlay(self) -> None:
        sel = _stale_sel(DAY)
        sel["sections"] = _transposed(sel["sections"])
        merged = _resolve(DAY, {"selected_song": sel})
        self.assertEqual(merged["sections"], sel["sections"])

    def test_stamped_stale_handling_unchanged(self) -> None:
        snap = _stale_sel(DAY)
        snap[cp.CHART_ORIGIN_KEY] = "catalog"
        snap[cp.CATALOG_REVISION_KEY] = cp.chart_fingerprint(snap["sections"])
        self.assertEqual(self._classify(snap), (cp.REFRESH, "provenance_unmodified_old_revision"))
        snap["sections"] = _transposed(snap["sections"])
        self.assertEqual(self._classify(snap)[1], "provenance_sections_modified_since_stamp")


class MissionNestedSnapshotTests(unittest.TestCase):
    def test_selected_song_nested_under_mission_untouched(self) -> None:
        stale = _stale_sel(DAY)
        blob = {
            "improv_active_mission": {"selected_song": copy.deepcopy(stale),
                                      "improv_song_concert_sections": copy.deepcopy(stale["sections"])},
            "mission_practice_context": {"selected_song": copy.deepcopy(stale)},
            "creative": {"mission_ctx": {"catalog_session": copy.deepcopy(stale)}},
        }
        before = copy.deepcopy(blob)
        with mock.patch.object(cp, "_canonical_for_pick", return_value=_row(DAY)):
            n = cp.reconcile_payload_chart_copies(blob)
        self.assertEqual(n, 0)
        self.assertEqual(blob, before)

    def test_non_mission_sibling_is_still_refreshed(self) -> None:
        stale = _stale_sel(DAY)
        blob = {"improv_active_mission": {"selected_song": copy.deepcopy(stale)},
                "active_song_state": {"selected_song": copy.deepcopy(stale)}}
        with mock.patch.object(cp, "_canonical_for_pick", return_value=_row(DAY)):
            cp.reconcile_payload_chart_copies(blob)
        self.assertEqual(blob["improv_active_mission"]["selected_song"]["sections"], stale["sections"])
        self.assertEqual(blob["active_song_state"]["selected_song"]["sections"], _FIX[DAY]["new_sections"])


class FailureLoggingAndNonMutationTests(unittest.TestCase):
    def test_log_works_on_non_dict_session_and_is_bounded(self) -> None:
        sess = _MappingSession()
        for i in range(100):
            cp.log_failure(sess, f"w{i}", RuntimeError("x"))
        rows = sess[cp.PROVENANCE_LOG_KEY]
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[-1]["where"], "w99")
        self.assertEqual(rows[-1]["reason"], "exception")

    def test_log_failure_never_raises(self) -> None:
        class _Bad:
            def get(self, *_a):
                raise RuntimeError("no")

        cp.log_failure(_Bad(), "x", ValueError("y"))
        cp.log_failure(None, "x", ValueError("y"))

    def test_resolver_failure_logged_not_raised(self) -> None:
        session: dict = {"selected_song": _stale_sel(DAY)}
        with mock.patch.object(cp, "reconcile_snapshot", side_effect=RuntimeError("boom")):
            merged = _resolve(DAY, session)
        self.assertTrue(merged)
        last = session[cp.PROVENANCE_LOG_KEY][-1]
        self.assertEqual((last["where"], last["reason"]), ("resolve_catalog_song_for_chart", "exception"))
        self.assertIn("boom", last["error"])

    def test_apply_context_failure_logged(self) -> None:
        import active_song_state as ass

        session: dict = {}
        with mock.patch.object(cp, "reconcile_payload_chart_copies", side_effect=RuntimeError("kaboom")):
            try:
                ass._apply_context_to_session_keys(
                    session, {"selected_song": _stale_sel(DAY), "pick_key": _pick(DAY)}
                )
            except Exception:
                pass  # unrelated downstream behaviour; only the provenance log matters
        rows = [r for r in session.get(cp.PROVENANCE_LOG_KEY, []) if r.get("reason") == "exception"]
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["where"], "active_song_state.apply_context")

    def test_canonical_lookup_failure_logged(self) -> None:
        session: dict = {}
        blob = {"selected_song": _stale_sel(DAY)}
        with mock.patch("song_catalog.catalog.load_song_catalog", side_effect=RuntimeError("nocat")):
            n = cp.reconcile_payload_chart_copies(blob, session=session)
        self.assertEqual(n, 0)
        self.assertEqual(session[cp.PROVENANCE_LOG_KEY][-1]["where"], "canonical_for_pick")

    def test_walker_does_not_mutate_shared_nested_dicts(self) -> None:
        shared = _stale_sel(DAY)  # e.g. the same dict object held by st.session_state
        original = copy.deepcopy(shared)
        payload = {"active_song_state": {"selected_song": shared}, "other": [1]}
        inner = payload["active_song_state"]
        with mock.patch.object(cp, "_canonical_for_pick", return_value=_row(DAY)):
            new, n = cp.reconcile_payload(payload)
        self.assertEqual(n, 1)
        self.assertEqual(shared, original)  # shared dict untouched
        self.assertEqual(inner["selected_song"], original)  # input tree untouched
        self.assertEqual(payload["active_song_state"]["selected_song"], original)
        self.assertEqual(new["active_song_state"]["selected_song"]["sections"], _FIX[DAY]["new_sections"])
        self.assertIs(new["other"], payload["other"])  # unchanged subtree shared

    def test_in_place_wrapper_only_replaces_top_level_container(self) -> None:
        shared = _stale_sel(DAY)
        original = copy.deepcopy(shared)
        session_like = {"selected_song": shared}
        payload = dict(session_like)  # shallow copy shares the nested dict, like build_music_disk_state
        with mock.patch.object(cp, "_canonical_for_pick", return_value=_row(DAY)):
            cp.reconcile_payload_chart_copies(payload)
        self.assertEqual(payload["selected_song"]["sections"], _FIX[DAY]["new_sections"])
        self.assertEqual(session_like["selected_song"], original)
        self.assertIs(session_like["selected_song"], shared)

    def test_idempotent(self) -> None:
        blob = {"selected_song": _stale_sel(DAY)}
        with mock.patch.object(cp, "_canonical_for_pick", return_value=_row(DAY)):
            cp.reconcile_payload_chart_copies(blob)
            once = copy.deepcopy(blob)
            cp.reconcile_payload_chart_copies(blob)
        self.assertEqual(blob, once)


if __name__ == "__main__":
    unittest.main()
