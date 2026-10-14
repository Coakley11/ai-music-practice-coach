"""MC3.3 — an explicit Songs selection is a committed song activation.

Creative may restore the tab, Focus, Level and the new song's own settings, but never
the previous song: not through a leftover workflow hint, a stale Mission workflow, a
sealed Return destination or a Creative page snapshot.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
IPANEMA = "Jazz\x1fThe Girl from Ipanema — Antonio Carlos Jobim"
AUTUMN = "Jazz\x1fAutumn Leaves — Jazz Standard"


def _on(pick: str, title: str) -> dict:
    return {"active_catalog_pick_key": pick, "song": title, "active_music_source": "catalog_song"}


def _dest(pick: str, mission: str = "Voice-lead the guide tones") -> dict:
    return {
        "mission_id": mission,
        "song_pick_key": pick,
        "section_label": "A",
        "chord_symbol": "Gm7",
        "chord_index": 2,
        "creative_tab": "Missions",
    }


class TestExplicitActivationOwnsTheSong(unittest.TestCase):
    """1 — explicit activation changes the authoritative identity (and retires the old hint)."""

    def _switch(self, s: dict, *, from_owner: str, from_sid: str) -> None:
        from music_source_ownership import _activate_songs_hub_backing_workflow
        from music_workflow_state_store import ActiveWorkflowPointer, set_active_workflow_pointer
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        set_active_workflow_pointer(s, ActiveWorkflowPointer(from_owner, from_sid, 4), source="t")
        s[ACTIVE_WORKFLOW_OWNER_KEY] = from_owner
        _activate_songs_hub_backing_workflow(s, owner="regular_catalog_backing", activation_source="test")

    def test_switch_after_phrase_motif_lets_missions_activate_for_the_new_song(self) -> None:
        # The live repro: Phrase / Motif on Ipanema → Songs → Autumn Leaves → Creative Missions.
        from music_workflow_canonical_identity import validate_pre_activation_identity
        from music_workflow_mission_session import mission_blob_session_id
        from music_workflow_state_store import get_active_workflow_pointer
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        s = _on(IPANEMA, "The Girl from Ipanema")
        s["_explicit_song_activation"] = {"identity": f"catalog|{IPANEMA}"}
        s.update(_on(AUTUMN, "Autumn Leaves"))
        self._switch(s, from_owner="song_based_improvisation", from_sid=IPANEMA)
        ptr = get_active_workflow_pointer(s)
        self.assertEqual((ptr.workflow_owner, ptr.workflow_session_id), ("regular_catalog_backing", AUTUMN))
        self.assertEqual(s[ACTIVE_WORKFLOW_OWNER_KEY], "regular_catalog_backing")  # old hint retired
        for owner, sid in (("mission_jam", mission_blob_session_id(s)), ("song_based_improvisation", AUTUMN)):
            res = validate_pre_activation_identity(
                s, target_owner=owner, target_session_id=sid, ptr_before=ptr, activation_source="creative_pre_widget"
            )
            self.assertTrue(res.ok, (owner, res.violations))

    def test_switch_from_missions_also_retires_the_hint(self) -> None:
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        s = _on(AUTUMN, "Autumn Leaves")  # no prior record: decided from the previous pointer
        self._switch(s, from_owner="mission_jam", from_sid=f"mission|catalog|{IPANEMA}")
        self.assertEqual(s[ACTIVE_WORKFLOW_OWNER_KEY], "regular_catalog_backing")

    def test_reactivating_the_same_song_keeps_its_creative_hint(self) -> None:
        # 5 — current-song settings still restore: a Songs visit for the live song is not a switch.
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        s = _on(AUTUMN, "Autumn Leaves")
        self._switch(s, from_owner="song_based_improvisation", from_sid=AUTUMN)
        self.assertEqual(s[ACTIVE_WORKFLOW_OWNER_KEY], "song_based_improvisation")
        self._switch(s, from_owner="song_based_improvisation", from_sid=AUTUMN)  # recorded identity unchanged
        self.assertEqual(s[ACTIVE_WORKFLOW_OWNER_KEY], "song_based_improvisation")

    def test_catalog_to_custom_is_a_switch(self) -> None:
        from song_activation_authority import commit_explicit_song_activation
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        s = _on(AUTUMN, "Autumn Leaves")
        commit_explicit_song_activation(s, owner="regular_catalog_backing")
        s[ACTIVE_WORKFLOW_OWNER_KEY] = "mission_jam"
        s.update({"improv_song_source": "Custom progression", "custom_progression_id": "abc123"})
        with mock.patch("studio_page_state.resolve_improv_song_source", return_value="Custom progression"):
            changed = commit_explicit_song_activation(s, owner="regular_custom_backing")
        self.assertTrue(changed)
        self.assertEqual(s[ACTIVE_WORKFLOW_OWNER_KEY], "regular_custom_backing")


class TestStaleStateCannotOverwriteTheNewSong(unittest.TestCase):
    def test_stale_creative_snapshot_entries_are_not_restored(self) -> None:
        # 2 — a Creative page snapshot saved on Ipanema cannot put Ipanema back.
        from studio_page_persistence import apply_page_snapshot

        s = _on(AUTUMN, "Autumn Leaves")
        s["backing_context"] = {"source": "regular_song", "active_song_id": AUTUMN, "bound_pick_key": AUTUMN}
        snap = {
            "improv_intelligence_tab": "Phrase / Motif",
            "_mission_chord_snapshot": {"source_identity": IPANEMA, "chord": "Gm7"},
            "improv_mission_practice_context": {"pick_key": IPANEMA, "song_title": "The Girl from Ipanema"},
            "backing_context": {"source": "mission", "active_song_id": IPANEMA, "bound_pick_key": IPANEMA},
        }
        apply_page_snapshot(s, snap)
        self.assertEqual(s["active_catalog_pick_key"], AUTUMN)
        self.assertEqual(s["backing_context"]["active_song_id"], AUTUMN)
        self.assertNotIn("_mission_chord_snapshot", s)
        self.assertNotIn("improv_mission_practice_context", s)
        self.assertEqual(s.get("improv_intelligence_tab"), "Phrase / Motif")  # page-local settings still restore

    def test_own_song_snapshot_entries_still_restore(self) -> None:
        from studio_page_persistence import apply_page_snapshot

        s = _on(AUTUMN, "Autumn Leaves")
        apply_page_snapshot(s, {"_mission_chord_snapshot": {"source_identity": AUTUMN, "chord": "Cm7"}})
        self.assertEqual(s["_mission_chord_snapshot"]["chord"], "Cm7")

    def test_stale_mission_workflow_cannot_activate_over_the_new_song(self) -> None:
        # 3 — a Mission workflow session for Ipanema is rejected while Autumn is live.
        from music_workflow_canonical_identity import validate_pre_activation_identity
        from music_workflow_state_store import ActiveWorkflowPointer

        s = _on(AUTUMN, "Autumn Leaves")
        ptr = ActiveWorkflowPointer("regular_catalog_backing", AUTUMN, 7)
        res = validate_pre_activation_identity(
            s, target_owner="mission_jam", target_session_id=f"mission|catalog|{IPANEMA}", ptr_before=ptr,
            activation_source="creative_tab_change",
        )
        self.assertFalse(res.ok)
        self.assertEqual(s["active_catalog_pick_key"], AUTUMN)

    def test_return_destination_from_another_song_is_dropped(self) -> None:
        # 4 — a queued Return to Mission for Ipanema cannot restore Ipanema over Autumn.
        from music_workflow_pending_mission_return import (
            PENDING_MISSION_RETURN_KEY,
            consume_pending_mission_return_handoff,
        )

        s = _on(AUTUMN, "Autumn Leaves")
        s["improv_active_mission"] = "Improvise using only chord tones"
        s[PENDING_MISSION_RETURN_KEY] = {"consume_token": "t1", "return_destination": _dest(IPANEMA)}
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            phase = consume_pending_mission_return_handoff(s)
        activate.assert_not_called()
        self.assertEqual(phase, "skipped")
        self.assertNotIn(PENDING_MISSION_RETURN_KEY, s)
        self.assertEqual(s["active_catalog_pick_key"], AUTUMN)
        self.assertEqual(s["improv_active_mission"], "Improvise using only chord tones")

    def test_sealed_destination_from_another_song_is_not_applied(self) -> None:
        from mission_return_destination import apply_sealed_mission_return_destination

        s = _on(AUTUMN, "Autumn Leaves")
        self.assertFalse(apply_sealed_mission_return_destination(s, _dest(IPANEMA)))
        self.assertEqual(s["active_catalog_pick_key"], AUTUMN)
        self.assertNotIn("improv_active_mission", s)

    def test_own_song_return_destination_still_restores(self) -> None:
        # 5 — Return to the same song's Mission is unchanged.
        from music_workflow_pending_mission_return import _apply_return_destination_session_fields

        s = _on(AUTUMN, "Autumn Leaves")
        _apply_return_destination_session_fields(s, _dest(AUTUMN))
        self.assertEqual(s["improv_active_mission"], "Voice-lead the guide tones")
        self.assertEqual(s["ii_selected_chord"], "Gm7")

    def test_old_song_settings_return_only_after_explicit_reactivation(self) -> None:
        # 6 — Ipanema's sealed Mission is foreign while Autumn is live, and its own again
        # once the user explicitly re-selects Ipanema.
        from song_activation_authority import belongs_to_another_song

        s = _on(AUTUMN, "Autumn Leaves")
        self.assertTrue(belongs_to_another_song(s, IPANEMA))
        s.update(_on(IPANEMA, "The Girl from Ipanema"))
        self.assertFalse(belongs_to_another_song(s, IPANEMA))
        self.assertTrue(belongs_to_another_song(s, AUTUMN))

    def test_custom_and_composition_sources_are_not_mistaken_for_foreign_songs(self) -> None:
        from song_activation_authority import belongs_to_another_song

        custom = {"active_music_source": "custom_progression", "active_catalog_pick_key": AUTUMN}
        self.assertFalse(belongs_to_another_song(custom, IPANEMA))  # no catalog authority while Custom is live
        self.assertFalse(belongs_to_another_song(_on(AUTUMN, "Autumn Leaves"), "custom::abc123"))
        self.assertFalse(belongs_to_another_song(_on(AUTUMN, "Autumn Leaves"), ""))


class TestStartupRestoreKeepsTheExplicitSource(unittest.TestCase):
    """The live repro: a used session restored on Custom; Songs → Catalog → Autumn Leaves.

    The late startup guard re-applied the snapshot's ``custom_progression`` source after the
    explicit pick, so the next run's Catalog switch restored the last catalog song (Ipanema).
    """

    @staticmethod
    def _payload(source: str) -> dict:
        return {"music_workspace_state": {"active_song": {"music_source": source}}}

    def test_explicit_catalog_choice_outlives_the_hydrated_custom_source(self) -> None:
        from music_startup_canonical_align import align_authoritative_canonical_from_hydrated

        s = _on(AUTUMN, "Autumn Leaves")
        s["explicit_music_source_choice"] = "catalog_song"
        align_authoritative_canonical_from_hydrated(s, self._payload("custom_progression"))
        self.assertEqual(s["active_music_source"], "catalog_song")
        self.assertEqual(s["active_catalog_pick_key"], AUTUMN)

    def test_explicit_custom_choice_outlives_a_hydrated_catalog_source(self) -> None:
        from music_startup_canonical_align import align_authoritative_canonical_from_hydrated

        s = {"active_music_source": "custom_progression", "explicit_music_source_choice": "custom_progression",
             "active_catalog_pick_key": "custom::abc123"}
        align_authoritative_canonical_from_hydrated(s, self._payload("catalog_song"))
        self.assertEqual(s["active_music_source"], "custom_progression")

    def test_without_an_explicit_choice_the_snapshot_source_still_restores(self) -> None:
        from music_startup_canonical_align import align_authoritative_canonical_from_hydrated

        s = _on(AUTUMN, "Autumn Leaves")  # restored, untouched session
        align_authoritative_canonical_from_hydrated(s, self._payload("custom_progression"))
        self.assertEqual(s["active_music_source"], "custom_progression")


class TestSongSwitchAfterPhraseMotifApp(unittest.TestCase):
    """Real app: Ipanema span Mission → Backing → Return → Phrase / Motif → Songs → Autumn → Creative."""

    def test_new_song_activates_in_creative_without_a_conflict(self) -> None:
        from streamlit.testing.v1 import AppTest

        data_dir = tempfile.mkdtemp(prefix="mc33_switch_")
        prior = os.environ.get("MUSIC_APP_DATA_DIR")
        os.environ["MUSIC_APP_DATA_DIR"] = data_dir
        try:
            at = AppTest.from_file(str(ROOT / "streamlit_music_practice_app.py"), default_timeout=300)
            at.run(timeout=300)

            def click(key):
                btn = next((w for w in at.button if str(w.key) == key), None)
                if btn is None and key == "studio_quick_nav_btn_picker":
                    btn = next((w for w in at.button if str(w.key) == "sidebar_goto_song_selection"), None)
                self.assertIsNotNone(btn, (key, [str(e.value)[:300] for e in at.exception]))
                btn.click()
                at.run(timeout=300)

            def pick(needle):
                dd = at.selectbox(key="matching_song_dropdown")
                dd.set_value([o for o in dd.options if needle in o][0])
                at.run(timeout=300)

            def tab(name):
                opts = at.radio(key="improv_intelligence_tab").options
                at.radio(key="improv_intelligence_tab").set_value([o for o in opts if name in o][0])
                at.run(timeout=300)

            click("studio_quick_nav_btn_picker")
            pick("Ipanema")
            click("studio_quick_nav_btn_creative")
            try:
                at.selectbox(key="creative_lab_analysis_mode").set_value("Improvisation Intelligence")
                at.run(timeout=300)
            except Exception:
                pass
            tab("Mission")
            at.radio(key="improv_mission_target_scope").set_value("span3")
            at.run(timeout=300)
            click("improv_span_mission_gen")
            click("improv_span_mission_backing")
            ret = next((w for w in at.button if "Return to Mission" in str(w.label)), None)
            self.assertIsNotNone(ret, [str(w.label) for w in at.button][:40])
            ret.click()
            at.run(timeout=300)
            tab("Motif")
            self.assertEqual(at.session_state["_active_workflow_owner"], "song_based_improvisation")
            click("studio_quick_nav_btn_picker")
            pick("Autumn Leaves")
            # Creative reopens on Missions (as it does from a used, persisted session): the
            # first activation after the switch is the new song's Mission workflow.
            at.session_state["improv_intelligence_tab"] = "Missions"
            click("studio_quick_nav_btn_creative")
            ss = at.session_state
            self.assertEqual(ss["song"], "Autumn Leaves")
            self.assertEqual(ss["active_catalog_pick_key"], AUTUMN)
            self.assertNotIn("_music_workflow_activation_error", ss)
            alerts = [str(w.value) for w in list(at.warning) + list(at.error)]
            self.assertFalse([a for a in alerts if "identity conflict" in a], alerts)
            from music_workflow_state_store import MUSIC_ACTIVE_WORKFLOW_KEY

            ptr = dict(ss[MUSIC_ACTIVE_WORKFLOW_KEY])
            self.assertEqual(ptr.get("workflow_owner"), "mission_jam")
            self.assertIn("Autumn Leaves", str(ptr.get("workflow_session_id")))
            self.assertNotIn("Ipanema", str(ptr.get("workflow_session_id")))
        finally:
            if prior is None:
                os.environ.pop("MUSIC_APP_DATA_DIR", None)
            else:
                os.environ["MUSIC_APP_DATA_DIR"] = prior
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
