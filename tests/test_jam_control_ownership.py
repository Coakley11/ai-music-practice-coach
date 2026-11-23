"""Backing Engine 2.0 slice 2: each jam's controls and callbacks touch only that jam's own record.

Browser write trace 2026-11-23 (1500 px): Generator set to Rock trio / Rock / Gritty / Light / Advanced, then
Style Jam -> Generator. The redrawn controls started at their first options and the browser reported Style
Jam's displayed Difficulty as a change. Style Jam's callback chose its jam from the mode on screen (now the
Generator) and wrote the Generator's off-screen defaults (Jazz trio / Dark / Medium / Intermediate) into the
Generator's record; the next real edit then saved the displayed Beginner.
"""

from __future__ import annotations

import unittest
from unittest import mock

import streamlit

from music_workflow_pending_generated_progression import (
    consume_pending_generated_progression,
    queue_generated_progression_intent,
)

STYLE_FLAG = "_improv_style_key_mounted_this_run"
GEN_FLAG = "_improv_jam_key_mounted_this_run"

# What a redrawn control shows when nothing assigns it: Streamlit's first option, or the transient default.
GEN_TRANSIENT = {
    "improv_ensemble": "Jazz trio",
    "improv_jam_style": "Jazz swing",
    "improv_jam_mood": "Dark",
    "improv_jam_intensity": "Medium",
    "improv_jam_difficulty": "Intermediate",
}
STYLE_TRANSIENT = {"improv_style": "Bossa Nova", "improv_mood": "Bright", "improv_groove": "Light",
                   "improv_difficulty": "Beginner"}

STYLE_CHOICE = {"improv_style": "Funk", "improv_mood": "Dreamy", "improv_groove": "Light",
                "improv_difficulty": "Advanced", "improv_style_bpm": 104}
GEN_CHOICE = {"improv_ensemble": "Rock trio", "improv_jam_style": "Rock", "improv_jam_mood": "Gritty",
              "improv_jam_intensity": "Light", "improv_jam_difficulty": "Advanced", "improv_jam_bpm": 120}


def _both_jams() -> dict:
    """Style Jam generated with non-default settings, then the Generator, as the musician would."""
    s: dict = {
        "_suite_active_workspace_id": "daniel",
        "studio_page": "creative",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_entry_mode": "Style Jam Mode",
        "improv_style_key": "Bb",
        "improv_jam_key": "A",
        "display_key": "Eb",
        "concert_key": "Eb",
        STYLE_FLAG: True,
        **STYLE_CHOICE,
        **GEN_TRANSIENT,
    }
    queue_generated_progression_intent(s, owner="style_jam")
    assert consume_pending_generated_progression(s) == "done"
    s.pop(STYLE_FLAG, None)
    s["improv_entry_mode"] = "Jam Session Generator"
    s[GEN_FLAG] = True
    s.update(GEN_CHOICE)
    queue_generated_progression_intent(s, owner="jam_session_generator")
    assert consume_pending_generated_progression(s) == "done"
    return s


def _record(session: dict, owner: str) -> dict:
    """The owner's latest saved record, read raw from the store (works on every version)."""
    blobs = (session.get("_music_workflow_state_store") or {}).get("blobs") or {}
    mine = [b for b in blobs.values() if isinstance(b, dict) and b.get("workflow_owner") == owner]
    return max(mine, key=lambda b: int(b.get("updated_at_seq") or 0)) if mine else {}


def _gen_settings(rec: dict) -> tuple:
    return (rec.get("style"), rec.get("mood"), rec.get("play_level"), rec.get("play_intensity"), rec.get("ensemble"))


def _show_style_jam_then_click_generator(s: dict) -> None:
    """Run N shows Style Jam (Generator controls not drawn, so they fall to transient values); the musician
    then clicks the Generator mode. Callbacks for that click run before the next script run."""
    s.pop(GEN_FLAG, None)
    s.pop("_improv_jam_controls_mounted_last_run", None)
    s["improv_entry_mode"] = "Style Jam Mode"
    s[STYLE_FLAG] = True  # Style Jam's controls drawn in run N
    s.update(GEN_TRANSIENT)  # Generator widgets after a run without them
    s["improv_entry_mode"] = "Jam Session Generator"  # the click: entry mode already updated for callbacks


class CrossModeCallbackTests(unittest.TestCase):
    def test_style_jam_callback_during_the_switch_never_writes_the_generator(self) -> None:
        from creative_key_sync import on_improv_style_jam_setting_change

        s = _both_jams()
        before = _gen_settings(_record(s, "jam_session_generator"))
        self.assertEqual(before[0], "Rock")
        _show_style_jam_then_click_generator(s)
        s["improv_difficulty"] = "Beginner"  # the browser reports Style Jam's displayed first option
        with mock.patch.object(streamlit, "session_state", s):
            on_improv_style_jam_setting_change()
        after = _gen_settings(_record(s, "jam_session_generator"))
        self.assertEqual(after, before)
        self.assertEqual(after, ("Rock", "Gritty", "Advanced", "Light", "Rock trio"))

    def test_the_generator_backing_handoff_is_not_resealed_from_the_reset_widgets(self) -> None:
        from backing_context import get_backing_context
        from creative_key_sync import on_improv_style_jam_setting_change

        s = _both_jams()
        _show_style_jam_then_click_generator(s)
        with mock.patch.object(streamlit, "session_state", s):
            on_improv_style_jam_setting_change()
        ctx = get_backing_context(s)
        if ctx is not None and ctx.entry_mode == "Jam Session Generator":
            self.assertNotEqual((ctx.mood, ctx.difficulty, ctx.groove_intensity), ("Dark", "Intermediate", "Medium"))

    def test_a_generator_callback_whose_controls_were_off_screen_writes_nothing(self) -> None:
        from creative_key_sync import on_improv_jam_setting_change

        s = _both_jams()
        style_before = dict(_record(s, "style_jam"))
        gen_before = _gen_settings(_record(s, "jam_session_generator"))
        # Style Jam on screen; a late Generator callback arrives with the Generator's transient values.
        s.pop(GEN_FLAG, None)
        s["improv_entry_mode"] = "Style Jam Mode"
        s[STYLE_FLAG] = True
        s.update(GEN_TRANSIENT)
        with mock.patch.object(streamlit, "session_state", s):
            on_improv_jam_setting_change()
        self.assertEqual(_gen_settings(_record(s, "jam_session_generator")), gen_before)
        style_after = _record(s, "style_jam")
        for k in ("style", "mood", "groove", "play_level", "play_intensity", "tempo_bpm", "section_map"):
            self.assertEqual(style_after.get(k), style_before.get(k), k)


class LegitimateEditTests(unittest.TestCase):
    def test_a_generator_edit_reaches_its_record_and_backing_at_once(self) -> None:
        from backing_context import build_entry_jam_context
        from creative_key_sync import on_improv_jam_setting_change

        s = _both_jams()
        style_before = dict(_record(s, "style_jam"))
        s["improv_jam_difficulty"] = "Beginner"
        s["improv_jam_intensity"] = "Heavy"
        with mock.patch.object(streamlit, "session_state", s):
            on_improv_jam_setting_change()
        rec = _record(s, "jam_session_generator")
        self.assertEqual((rec.get("play_level"), rec.get("play_intensity"), rec.get("ensemble")),
                         ("Beginner", "Heavy", "Rock trio"))
        ctx = build_entry_jam_context(s)
        self.assertEqual((ctx.difficulty, ctx.groove_intensity, ctx.mood), ("Beginner", "Heavy", "Gritty"))
        self.assertEqual(_record(s, "style_jam").get("play_level"), style_before.get("play_level"))

    def test_a_style_jam_edit_reaches_its_record_and_never_the_generator(self) -> None:
        from creative_key_sync import on_improv_style_jam_setting_change

        s = _both_jams()
        gen_before = _gen_settings(_record(s, "jam_session_generator"))
        s.pop(GEN_FLAG, None)
        s["improv_entry_mode"] = "Style Jam Mode"
        s[STYLE_FLAG] = True
        s.update(STYLE_CHOICE)
        s["improv_mood"] = "Energetic"
        s["improv_difficulty"] = "Intermediate"
        with mock.patch.object(streamlit, "session_state", s):
            on_improv_style_jam_setting_change()
        rec = _record(s, "style_jam")
        self.assertEqual((rec.get("mood"), rec.get("play_level")), ("Energetic", "Intermediate"))
        self.assertEqual(_gen_settings(_record(s, "jam_session_generator")), gen_before)


class OwnRecordTests(unittest.TestCase):
    def test_generation_records_the_chosen_mood_and_play_settings(self) -> None:
        s = _both_jams()
        self.assertEqual(_gen_settings(_record(s, "jam_session_generator")),
                         ("Rock", "Gritty", "Advanced", "Light", "Rock trio"))
        sj = _record(s, "style_jam")
        self.assertEqual((sj.get("mood"), sj.get("play_level")), ("Dreamy", "Advanced"))

    def test_redrawn_controls_start_from_their_own_record_over_many_switches(self) -> None:
        from jam_control_ownership import (
            note_controls_mounted,
            note_script_run_started,
            seed_jam_controls_before_mount,
        )

        s = _both_jams()
        for i in range(4):  # Generator -> Style Jam -> Generator -> ... with transient values between
            owner, other = ("style_jam", "jam_session_generator") if i % 2 == 0 else ("jam_session_generator", "style_jam")
            note_script_run_started(s)
            s.update(GEN_TRANSIENT if owner == "jam_session_generator" else STYLE_TRANSIENT)
            seed_jam_controls_before_mount(s, owner)
            note_controls_mounted(s, owner)
            want = GEN_CHOICE if owner == "jam_session_generator" else STYLE_CHOICE
            got = {k: s.get(k) for k in want}
            self.assertEqual(got, want, f"switch {i} to {owner}")
        self.assertEqual(_gen_settings(_record(s, "jam_session_generator")),
                         ("Rock", "Gritty", "Advanced", "Light", "Rock trio"))
        self.assertEqual(_record(s, "style_jam").get("play_level"), "Advanced")

    def test_controls_still_on_screen_are_never_overwritten_by_the_record(self) -> None:
        from jam_control_ownership import note_controls_mounted, note_script_run_started, seed_jam_controls_before_mount

        s = _both_jams()
        note_script_run_started(s)  # the Generator's controls were drawn last run
        note_controls_mounted(s, "jam_session_generator")
        note_script_run_started(s)
        s["improv_jam_difficulty"] = "Beginner"  # the musician's live choice, not yet committed
        self.assertEqual(seed_jam_controls_before_mount(s, "jam_session_generator"), {})
        self.assertEqual(s["improv_jam_difficulty"], "Beginner")

    def test_a_value_that_names_no_option_never_becomes_the_first_option(self) -> None:
        from jam_control_ownership import note_script_run_started, seed_jam_controls_before_mount

        s = _both_jams()
        note_script_run_started(s)
        note_script_run_started(s)  # two runs without the Generator's controls
        s["improv_jam_style"] = "Jazz swing"  # not an option (it is "Jazz Swing")
        seed_jam_controls_before_mount(s, "jam_session_generator")
        self.assertEqual(s["improv_jam_style"], "Rock")


class LiveTests(unittest.TestCase):
    def test_in_a_callback_only_the_run_the_musician_saw_counts(self) -> None:
        from jam_control_ownership import (
            creative_jam_controls_live,
            jam_callback_scope,
            note_controls_mounted,
            note_script_run_started,
        )

        s: dict = {}
        note_controls_mounted(s, "jam_session_generator")  # run N-1: Generator drawn
        note_script_run_started(s)
        note_controls_mounted(s, "style_jam")  # run N: Style Jam drawn
        with jam_callback_scope("style_jam"):
            self.assertTrue(creative_jam_controls_live(s, "style_jam"))
            self.assertFalse(creative_jam_controls_live(s, "jam_session_generator"))
        note_script_run_started(s)  # run N+1, before anything is drawn
        self.assertTrue(creative_jam_controls_live(s, "style_jam"))
        self.assertFalse(creative_jam_controls_live(s, "jam_session_generator"))
        note_script_run_started(s)  # run N+2: Backing, nothing drawn
        self.assertFalse(creative_jam_controls_live(s, "style_jam"))


if __name__ == "__main__":
    unittest.main()


# --------------------------------------------------------------------------------------------- reload
def _generator_jam_on_backing(style: str = "Bossa Nova") -> tuple[dict, object]:
    """A Generator jam (non-default settings) sealed and handed to Backing; returns (session, context)."""
    from backing_context import build_entry_jam_context, set_backing_context
    from generated_workflow_artifact import seal_backing_handoff_snapshot_for_creative_open

    s = _both_jams()
    s["improv_jam_style"] = style
    s["improv_ensemble"] = "Jazz trio"
    s["improv_jam_mood"] = "Dark"
    s["improv_jam_intensity"] = "Heavy"
    s["improv_jam_difficulty"] = "Advanced"
    queue_generated_progression_intent(s, owner="jam_session_generator")
    assert consume_pending_generated_progression(s) == "done"
    assert seal_backing_handoff_snapshot_for_creative_open(s)
    ctx = build_entry_jam_context(s)
    set_backing_context(s, ctx)
    return s, ctx


def _reload(s: dict) -> dict:
    """What a reload onto Backing restores (2026-11-23 trace): the persisted Backing context, a stale Creative
    workspace jam copy, transient control values -- no workflow record, pointer or sealed snapshot."""
    fresh: dict = {
        "_suite_active_workspace_id": "daniel",
        "studio_page": "backing",
        "display_key": "Eb",
        "concert_key": "Eb",
        "backing_context": s["backing_context"],
        "improv_jam_session": {"id": "Jazz swing", "mood": "Bright", "sections": {}},
        **GEN_TRANSIENT,
    }
    return fresh


class ReloadTests(unittest.TestCase):
    def test_reload_restores_identity_sections_settings_and_take_identity(self) -> None:
        from backing_context import build_entry_jam_context
        from generated_workflow_artifact import restore_generated_jam_from_backing_context
        from music_workflow_compatibility import legacy_session_id_for_owner
        from music_workflow_state_store import get_active_workflow_pointer

        s, before = _generator_jam_on_backing()
        sid = get_active_workflow_pointer(s).workflow_session_id
        sections = dict(_record(s, "jam_session_generator")["section_map"])
        self.assertEqual(len(sections), 3)

        fresh = _reload(s)
        self.assertTrue(restore_generated_jam_from_backing_context(fresh))
        ptr = get_active_workflow_pointer(fresh)
        self.assertEqual((ptr.workflow_owner, ptr.workflow_session_id), ("jam_session_generator", sid))
        rec = _record(fresh, "jam_session_generator")
        self.assertEqual(rec["section_map"], sections)
        self.assertEqual((rec["mood"], rec["play_level"], rec["play_intensity"], rec["ensemble"]),
                         ("Dark", "Advanced", "Heavy", "Jazz trio"))
        jam = fresh["improv_jam_session"]
        self.assertEqual((jam["id"], jam["sections"]), (sid, sections))
        self.assertEqual(legacy_session_id_for_owner(fresh, "jam_session_generator"), sid)

        after = build_entry_jam_context(fresh)
        self.assertEqual(after.jam_id, before.jam_id)  # same take identity: no re-render, same plan
        self.assertEqual(list(after.progression), list(before.progression))
        self.assertEqual(list(after.sections), list(before.sections))
        self.assertEqual((after.entry_mode, after.mood, after.difficulty, after.groove_intensity, after.ensemble,
                          after.style, after.bpm, after.concert_key),
                         (before.entry_mode, before.mood, before.difficulty, before.groove_intensity,
                          before.ensemble, before.style, before.bpm, before.concert_key))
        self.assertEqual(fresh["display_key"], "Eb")  # the catalog song's Practice Key is untouched

    def test_return_after_reload_shows_the_jams_own_mood_and_sections(self) -> None:
        from backing_context import get_backing_context
        from backing_source_navigation import restore_session_widgets_from_backing_context
        from generated_workflow_artifact import restore_generated_jam_from_backing_context

        s, _ = _generator_jam_on_backing()
        sections = dict(_record(s, "jam_session_generator")["section_map"])
        fresh = _reload(s)
        restore_generated_jam_from_backing_context(fresh)
        restore_session_widgets_from_backing_context(fresh, get_backing_context(fresh), widget_safe=False)
        self.assertEqual((fresh["improv_jam_mood"], fresh["improv_jam_difficulty"], fresh["improv_ensemble"]),
                         ("Dark", "Advanced", "Jazz trio"))
        self.assertEqual(fresh["improv_jam_session"]["sections"], sections)

    def test_a_flat_progression_never_replaces_the_saved_sections(self) -> None:
        from backing_context import get_backing_context
        from backing_source_navigation import restore_session_widgets_from_backing_context

        s, _ = _generator_jam_on_backing()
        sections = dict(_record(s, "jam_session_generator")["section_map"])
        fresh = _reload(s)  # no record restored at all: only the context
        restore_session_widgets_from_backing_context(fresh, get_backing_context(fresh), widget_safe=False)
        self.assertEqual(fresh["improv_jam_session"]["sections"], sections)

    def test_an_existing_record_for_the_jam_is_kept(self) -> None:
        from generated_workflow_artifact import restore_generated_jam_from_backing_context

        s, _ = _generator_jam_on_backing()
        rec = dict(_record(s, "jam_session_generator"))
        s["improv_jam_mood"] = "Dreamy"  # a newer Creative change, already in the jam's own record
        s["_improv_jam_key_mounted_this_run"] = True
        from creative_key_sync import on_improv_jam_setting_change

        with mock.patch.object(streamlit, "session_state", s):
            on_improv_jam_setting_change()
        self.assertEqual(_record(s, "jam_session_generator")["mood"], "Dreamy")
        restore_generated_jam_from_backing_context(s)
        self.assertEqual(_record(s, "jam_session_generator")["mood"], "Dreamy")
        self.assertEqual(_record(s, "jam_session_generator")["section_map"], rec["section_map"])

    def test_backing_never_overrides_another_live_workflow(self) -> None:
        from generated_workflow_artifact import restore_generated_jam_from_backing_context
        from music_workflow_state_store import ActiveWorkflowPointer, get_active_workflow_pointer, set_active_workflow_pointer

        s, _ = _generator_jam_on_backing()
        style_sid = _record(s, "style_jam")["workflow_session_id"]
        set_active_workflow_pointer(s, ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=style_sid))
        self.assertFalse(restore_generated_jam_from_backing_context(s))
        self.assertEqual(get_active_workflow_pointer(s).workflow_owner, "style_jam")

    def test_only_generated_jam_contexts_carry_a_sealed_jam(self) -> None:
        from backing_context import BackingContext

        song = BackingContext(source="regular_song", source_label="", active_song_id="x", song_title="x", key="Eb",
                              display_key="Eb", concert_key="Eb", bpm=72, style="Jazz swing", groove="")
        self.assertNotIn("sealed_jam_snapshot", song.to_dict())
        self.assertEqual(BackingContext.from_dict({**song.to_dict(), "sealed_jam_snapshot": {"a": 1}}).sealed_jam_snapshot, {})


# --------------------------------------------------------------------------- the other jam after a reload
# Browser write trace 2026-11-23 (H4, 1500 px): the reload restores only the Generator's record. (1) The jam-key
# restore saw a stale "Style Jam Mode" entry and put the Generator's key A in Style Jam's slot. (2) Switching to
# Style Jam rebuilt its record from the shared style meta, which the Generator had written last (Dreamy / Heavy /
# 120), and projected that onto Style Jam's controls.
GEN_META = {"style": "Rock", "bpm": 120, "groove": "Heavy", "groove_intensity": "Heavy", "key": "A",
            "mood": "Gritty", "difficulty": "Intermediate", "meter": "4/4", "entry_mode": "Jam Session Generator"}


def _style_jam_after_generator_reload() -> dict:
    """After the reload: only the Generator's record; Style Jam's controls back from the page snapshot; the
    style meta last written by the Generator."""
    s = _both_jams()
    store = s["_music_workflow_state_store"]
    store["blobs"] = {k: v for k, v in store["blobs"].items() if v.get("workflow_owner") != "style_jam"}
    for k in (STYLE_FLAG, GEN_FLAG, "_improv_style_controls_mounted_last_run", "_improv_jam_controls_mounted_last_run"):
        s.pop(k, None)
    s.update(STYLE_CHOICE)
    s["improv_style_key"] = "Bb"
    s["improv_style_meta"] = dict(GEN_META)
    s["improv_entry_mode"] = "Style Jam Mode"
    return s


class OtherJamAfterReloadTests(unittest.TestCase):
    def test_the_reload_key_restore_fills_the_restored_jams_own_slot(self) -> None:
        from creative_key_sync import restore_jam_visit_practice_key_after_hydrate
        from creative_session_state import CreativeSession, set_creative_session

        s = {
            "_suite_active_workspace_id": "daniel",
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",  # stale: restored from the workspace before the session
            "improv_style_key": "Bb",
            "improv_jam_key": "A",
            "display_key": "Eb",
            "concert_key": "Eb",
        }
        set_creative_session(s, CreativeSession(session_id="gen-1", tool_type="jam_session_generator",
                                                entry_mode="Jam Session Generator", concert_key="A", display_key="A",
                                                style="Rock", sections={"Riff": ["A", "D"]}))
        restore_jam_visit_practice_key_after_hydrate(s)
        self.assertEqual(s.get("improv_style_key"), "Bb")
        self.assertNotEqual(s.get("_pending_improv_style_key"), "A")
        self.assertTrue(str(s.get("improv_jam_key") or s.get("_pending_improv_jam_key") or "").startswith("A"))

    def test_a_rebuilt_style_jam_record_never_takes_the_generators_meta(self) -> None:
        from music_workflow_compatibility import build_workflow_blob_from_legacy

        s = _style_jam_after_generator_reload()
        blob = build_workflow_blob_from_legacy(s, "style_jam")
        self.assertEqual((blob.mood, blob.groove, blob.tempo_bpm), ("Dreamy", "Light", 104))
        self.assertEqual(blob.keys.practice_tonic, "Bb")

    def test_style_jams_own_meta_still_feeds_its_record(self) -> None:
        from music_workflow_compatibility import build_workflow_blob_from_legacy

        s = _style_jam_after_generator_reload()
        s["improv_style_meta"] = dict(GEN_META, style="Funk", mood="Energetic", groove="Heavy", bpm=96,
                                      entry_mode="Style Jam Mode")
        blob = build_workflow_blob_from_legacy(s, "style_jam")
        self.assertEqual((blob.mood, blob.groove, blob.tempo_bpm), ("Energetic", "Heavy", 96))

    def test_switching_to_style_jam_after_the_reload_keeps_its_own_settings(self) -> None:
        from jam_control_ownership import seed_jam_controls_before_mount
        from music_workflow_activation import ActivateWorkflowRequest, activate_workflow

        s = _style_jam_after_generator_reload()
        gen_before = _gen_settings(_record(s, "jam_session_generator"))
        res = activate_workflow(s, ActivateWorkflowRequest(target_owner="style_jam", target_session_id="Funk",
                                                           activation_source="test_entry_mode_switch"))
        self.assertTrue(res.ok, res)
        rec = _record(s, "style_jam")
        self.assertEqual((rec["mood"], rec["groove"], rec["tempo_bpm"]), ("Dreamy", "Light", 104))
        seed_jam_controls_before_mount(s, "style_jam")
        self.assertEqual({k: s.get(k) for k in STYLE_CHOICE}, STYLE_CHOICE)
        self.assertEqual(s.get("improv_style_key"), "Bb")
        self.assertEqual(_gen_settings(_record(s, "jam_session_generator")), gen_before)
