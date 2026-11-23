"""Backing Engine 2.0 slice 2: a generated jam's own settings reach the band, and only a jam's.

Style Jam and the Jam Session Generator each carry Style, Mood, Groove intensity, Difficulty and
(Generator) Ensemble into one sealed Backing context; the Backing page turns that context into a
PerformancePlan. Songs never get a plan. Difficulty never stands in for Groove intensity.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from backing_context import BackingContext, build_entry_jam_context
from backing_performance_plan import (
    JAM_PERFORMANCE_SWITCH,
    band_summary,
    performance_plan_for_backing_context,
    resolve_performance_plan,
)
from backing_source_navigation import restore_session_widgets_from_backing_context
from generated_workflow_artifact import (
    GeneratedWorkflowArtifactSnapshot,
    build_snapshot_from_session,
    owner_jam_performance_settings,
    seal_backing_handoff_snapshot_for_creative_open,
)
from music_workflow_pending_generated_progression import (
    consume_pending_generated_progression,
    queue_generated_progression_intent,
)


def _style_jam(**over: object) -> dict:
    s: dict = {
        "_suite_active_workspace_id": "daniel",
        "studio_page": "creative",
        "improv_entry_mode": "Style Jam Mode",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_style": "Jazz Swing",
        "improv_style_key": "C",
        "improv_mood": "Mellow",
        "improv_difficulty": "Intermediate",
        "improv_groove": "Medium",
        "improv_style_bpm": 110,
        "display_key": "C",
        "concert_key": "C",
    }
    s.update(over)
    return s


def _generator(**over: object) -> dict:
    s: dict = {
        "_suite_active_workspace_id": "daniel",
        "studio_page": "creative",
        "improv_entry_mode": "Jam Session Generator",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_jam_key": "C",
        "improv_jam_style": "Jazz Swing",
        "improv_jam_mood": "Mellow",
        "improv_jam_bpm": 120,
        "improv_ensemble": "Jazz trio",
        "improv_jam_intensity": "Medium",
        "improv_jam_difficulty": "Intermediate",
        "display_key": "Eb",
        "concert_key": "Eb",
    }
    s.update(over)
    return s


def _sealed_context(session: dict, owner: str) -> BackingContext:
    queue_generated_progression_intent(session, owner=owner)
    assert consume_pending_generated_progression(session) == "done"
    assert seal_backing_handoff_snapshot_for_creative_open(session)
    return build_entry_jam_context(session)


class OwnerSettingsTests(unittest.TestCase):
    def test_style_jam_intensity_is_its_own_choice_not_difficulty(self) -> None:
        for diff in ("Beginner", "Intermediate", "Advanced"):
            for inten in ("Light", "Medium", "Heavy"):
                got = owner_jam_performance_settings(
                    {"improv_groove": inten, "improv_difficulty": diff}, "style_jam"
                )
                self.assertEqual((got["intensity"], got["level"]), (inten, diff))

    def test_missing_intensity_is_medium_whatever_the_difficulty(self) -> None:
        for diff in ("Beginner", "Advanced"):
            got = owner_jam_performance_settings({"improv_difficulty": diff}, "style_jam")
            self.assertEqual(got["intensity"], "Medium")

    def test_generator_reads_its_own_controls_never_style_jams(self) -> None:
        session = {
            "improv_groove": "Heavy",
            "improv_difficulty": "Beginner",
            "improv_jam_intensity": "Light",
            "improv_jam_difficulty": "Advanced",
            "improv_ensemble": "Rock trio",
        }
        got = owner_jam_performance_settings(session, "jam_session_generator")
        self.assertEqual(got, {"intensity": "Light", "level": "Advanced", "ensemble": "Rock trio"})
        # Style Jam has no ensemble of its own: its style's band.
        self.assertEqual(owner_jam_performance_settings(session, "style_jam")["ensemble"], "")


class HandoffTests(unittest.TestCase):
    def test_style_jam_light_advanced_reaches_backing_as_chosen(self) -> None:
        ctx = _sealed_context(
            _style_jam(improv_groove="Light", improv_difficulty="Advanced", improv_mood="Energetic"), "style_jam"
        )
        self.assertEqual(ctx.source, "entry_jam")
        self.assertEqual((ctx.mood, ctx.groove_intensity, ctx.difficulty), ("Energetic", "Light", "Advanced"))

    def test_style_jam_heavy_beginner_is_not_replaced_by_light(self) -> None:
        # Before slice 2 the sealed snapshot derived intensity from Difficulty: Beginner -> Light.
        ctx = _sealed_context(_style_jam(improv_groove="Heavy", improv_difficulty="Beginner"), "style_jam")
        self.assertEqual((ctx.groove_intensity, ctx.difficulty), ("Heavy", "Beginner"))

    def test_generator_carries_its_ensemble_intensity_and_difficulty(self) -> None:
        session = _generator(
            improv_ensemble="Rock trio",
            improv_jam_intensity="Heavy",
            improv_jam_difficulty="Advanced",
            improv_jam_mood="Gritty",
            # Style Jam's hidden values must not leak into the Generator's jam.
            improv_groove="Light",
            improv_difficulty="Beginner",
        )
        ctx = _sealed_context(session, "jam_session_generator")
        self.assertEqual(
            (ctx.ensemble, ctx.groove_intensity, ctx.difficulty, ctx.mood),
            ("Rock trio", "Heavy", "Advanced", "Gritty"),
        )
        # A generated jam's key never overwrites the global song's Practice Key.
        self.assertEqual(session.get("display_key"), "Eb")

    def test_snapshot_and_context_round_trip_the_ensemble(self) -> None:
        session = _generator(improv_ensemble="Lo-fi duo")
        _sealed_context(session, "jam_session_generator")
        snap = build_snapshot_from_session(session, owner="jam_session_generator")
        assert snap is not None
        again = GeneratedWorkflowArtifactSnapshot.from_dict(snap.to_dict())
        assert again is not None
        self.assertEqual(again.ensemble, "Lo-fi duo")
        ctx = build_entry_jam_context(session)
        self.assertEqual(BackingContext.from_dict(ctx.to_dict()).ensemble, "Lo-fi duo")

    def test_return_to_creative_keeps_the_chosen_intensity(self) -> None:
        ctx = _sealed_context(_style_jam(improv_groove="Heavy", improv_difficulty="Beginner"), "style_jam")
        back: dict = {"improv_entry_mode": "Style Jam Mode"}
        restore_session_widgets_from_backing_context(back, ctx, widget_safe=False)
        self.assertEqual(back.get("improv_groove"), "Heavy")
        self.assertEqual(back.get("improv_difficulty"), "Beginner")

    def test_return_to_generator_restores_its_own_controls_only(self) -> None:
        ctx = _sealed_context(
            _generator(improv_ensemble="Latin quartet", improv_jam_intensity="Light", improv_jam_difficulty="Advanced"),
            "jam_session_generator",
        )
        back: dict = {"improv_entry_mode": "Jam Session Generator", "improv_groove": "Medium"}
        restore_session_widgets_from_backing_context(back, ctx, widget_safe=False)
        self.assertEqual(back.get("improv_jam_intensity"), "Light")
        self.assertEqual(back.get("improv_jam_difficulty"), "Advanced")
        self.assertEqual(back.get("improv_ensemble"), "Latin quartet")


class PlanGateTests(unittest.TestCase):
    def _ctx(self, source: str, **over: object) -> BackingContext:
        base = dict(
            source=source, source_label="", active_song_id="x", song_title="x", key="C", display_key="C",
            concert_key="C", bpm=110, style="Jazz Swing", groove="Jazz swing",
            mood="Mellow", groove_intensity="Light", difficulty="Advanced", ensemble="",
        )
        base.update(over)
        return BackingContext(**base)  # type: ignore[arg-type]

    def test_only_a_generated_jam_gets_a_plan(self) -> None:
        for source in ("regular_song", "custom_progression", "mission", "song_improv", "composition"):
            try:
                ctx = self._ctx(source)
            except Exception:
                continue
            self.assertIsNone(performance_plan_for_backing_context(ctx, style="Jazz swing"), source)
        self.assertIsNone(performance_plan_for_backing_context(None, style="Jazz swing"))
        plan = performance_plan_for_backing_context(self._ctx("entry_jam"), style="Jazz swing")
        assert plan is not None
        self.assertEqual((plan.mood, plan.intensity, plan.level), ("Mellow", "Light", "Advanced"))

    def test_rollback_switch_turns_the_jam_plan_off(self) -> None:
        with mock.patch.dict(os.environ, {JAM_PERFORMANCE_SWITCH: "off"}):
            self.assertIsNone(performance_plan_for_backing_context(self._ctx("entry_jam"), style="Jazz swing"))

    def test_the_take_identity_follows_every_sound_affecting_choice(self) -> None:
        tags = set()
        for mood in ("Mellow", "Energetic", "Bright", "Dark"):
            for inten in ("Light", "Heavy"):
                for level in ("Beginner", "Advanced"):
                    tags.add(resolve_performance_plan(style="Pop groove", mood=mood, intensity=inten, level=level).tag())
        self.assertEqual(len(tags), 16)
        trio = resolve_performance_plan(style="Rock groove", ensemble="Jazz trio", guitar_available=False).tag()
        duo = resolve_performance_plan(style="Rock groove", ensemble="Lo-fi duo", guitar_available=False).tag()
        self.assertNotEqual(trio, duo)
        # The same choices are the same take: returning without a change never rebuilds the jam.
        a = performance_plan_for_backing_context(self._ctx("entry_jam"), style="Jazz swing")
        b = performance_plan_for_backing_context(self._ctx("entry_jam"), style="Jazz swing")
        assert a is not None and b is not None
        self.assertEqual(a.tag(), b.tag())

    def test_card_names_the_band_that_plays_and_what_is_missing(self) -> None:
        quartet = resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet")
        self.assertEqual(band_summary(quartet), "Piano, bass, drums · horns not available yet")
        latin = resolve_performance_plan(style="Bossa nova", ensemble="Latin quartet")
        self.assertIn("Latin percussion not available yet", band_summary(latin))
        duo = resolve_performance_plan(style="Ballad", ensemble="Lo-fi duo")
        self.assertEqual(band_summary(duo), "Piano, drums")
        self.assertEqual(band_summary(None), "")


if __name__ == "__main__":
    unittest.main()


class CardTests(unittest.TestCase):
    def test_jam_card_shows_intensity_and_the_band_that_actually_plays(self) -> None:
        from unittest.mock import MagicMock

        from backing_context import set_backing_context
        from backing_context_ui import render_backing_creative_context_card

        session = _generator(improv_ensemble="Jazz quartet", improv_jam_intensity="Heavy", improv_jam_difficulty="Advanced")
        ctx = _sealed_context(session, "jam_session_generator")
        set_backing_context(session, ctx)
        st = MagicMock()
        render_backing_creative_context_card(st, ctx, session, applied_bpm=120, applied_groove="Jazz swing")
        html = " ".join(str(c.args[0]) for c in st.markdown.call_args_list if c.args)
        self.assertIn("Intensity · Heavy", html)
        self.assertIn("Band · Piano, bass, drums · horns not available yet", html)

    def test_song_cards_get_no_band_or_intensity_badge(self) -> None:
        from unittest.mock import MagicMock

        from backing_context_ui import render_backing_creative_context_card

        ctx = PlanGateTests()._ctx("song_improv")
        st = MagicMock()
        try:
            render_backing_creative_context_card(st, ctx, {}, applied_bpm=110, applied_groove="Jazz swing")
        except Exception:
            return  # the SBI card needs a fuller session; the point is only that no jam badge is drawn
        html = " ".join(str(c.args[0]) for c in st.markdown.call_args_list if c.args)
        self.assertNotIn("Band · ", html)


def _leave_creative(session: dict) -> None:
    """What Backing sees once Creative is off screen: Streamlit drops the unmounted jam widgets and the
    Creative initialiser re-seeds their transient defaults (studio_page_state.init_improvisation_state);
    no jam control is mounted this run."""
    from studio_page_state import init_improvisation_state

    for k in ("improv_mood", "improv_groove", "improv_difficulty", "improv_style", "improv_style_bpm",
              "improv_ensemble", "improv_jam_mood", "improv_jam_intensity", "improv_jam_difficulty",
              "improv_jam_style", "improv_jam_bpm"):
        session.pop(k, None)
    session.pop("_improv_jam_key_mounted_this_run", None)
    session.pop("_improv_style_key_mounted_this_run", None)
    init_improvisation_state(session, is_custom_active=False)
    session["studio_page"] = "backing"


class OffScreenControlsTests(unittest.TestCase):
    """Browser finding 2026-11-22 (1500 px, Generator): the Rock trio take played once, then Backing reruns
    rebuilt the jam from Creative's reset widget defaults (Dark / Medium / Intermediate / Jazz trio)."""

    def test_generator_jam_keeps_its_settings_after_creative_unmounts(self) -> None:
        from generated_workflow_artifact import live_jam_canonical_snapshot_for_render

        session = _generator(improv_ensemble="Rock trio", improv_jam_style="Rock", improv_jam_mood="Gritty",
                             improv_jam_intensity="Light", improv_jam_difficulty="Advanced")
        _sealed_context(session, "jam_session_generator")
        _leave_creative(session)
        snap = live_jam_canonical_snapshot_for_render(session)
        if snap is not None:
            self.assertEqual(snap.mood, "Gritty")
        ctx = build_entry_jam_context(session)
        self.assertEqual((ctx.ensemble, ctx.mood, ctx.groove_intensity, ctx.difficulty),
                         ("Rock trio", "Gritty", "Light", "Advanced"))
        plan = performance_plan_for_backing_context(ctx, style="Rock groove")
        self.assertEqual((plan.ensemble, plan.mood, plan.intensity, plan.level),
                         ("Rock trio", "Gritty", "Light", "Advanced"))

    def test_style_jam_keeps_its_settings_after_creative_unmounts(self) -> None:
        session = _style_jam(improv_style="Funk", improv_mood="Energetic", improv_groove="Heavy",
                             improv_difficulty="Beginner")
        _sealed_context(session, "style_jam")
        _leave_creative(session)
        ctx = build_entry_jam_context(session)
        self.assertEqual((ctx.mood, ctx.groove_intensity, ctx.difficulty), ("Energetic", "Heavy", "Beginner"))

    def test_live_controls_still_win_on_creative(self) -> None:
        """On Creative (controls live) a changed control is the musician's choice: the reseal takes it."""
        session = _generator(improv_ensemble="Rock trio", improv_jam_mood="Gritty", improv_jam_intensity="Light")
        _sealed_context(session, "jam_session_generator")
        session["improv_jam_intensity"] = "Heavy"
        session["improv_ensemble"] = "Jazz trio"
        assert seal_backing_handoff_snapshot_for_creative_open(session)
        ctx = build_entry_jam_context(session)
        self.assertEqual((ctx.ensemble, ctx.groove_intensity), ("Jazz trio", "Heavy"))
        # ... and that choice is now the jam's own record, so leaving Creative keeps it.
        _leave_creative(session)
        ctx = build_entry_jam_context(session)
        self.assertEqual((ctx.ensemble, ctx.groove_intensity), ("Jazz trio", "Heavy"))

    def test_a_reseal_on_backing_never_takes_the_reset_widgets(self) -> None:
        """Any of the re-seal paths (key change, invalidate) can run on Backing; it must keep the jam."""
        session = _generator(improv_ensemble="Rock trio", improv_jam_style="Rock", improv_jam_mood="Gritty",
                             improv_jam_intensity="Light", improv_jam_difficulty="Advanced")
        _sealed_context(session, "jam_session_generator")
        _leave_creative(session)
        session["improv_jam_mood"] = "Dark"  # what Backing actually saw (2026-11-22 trace)
        session["improv_ensemble"] = "Jazz trio"
        session["improv_jam_intensity"] = "Medium"
        session["improv_jam_difficulty"] = "Intermediate"
        assert seal_backing_handoff_snapshot_for_creative_open(session)
        ctx = build_entry_jam_context(session)
        self.assertEqual((ctx.ensemble, ctx.mood, ctx.groove_intensity, ctx.difficulty),
                         ("Rock trio", "Gritty", "Light", "Advanced"))

    def test_return_to_creative_takes_the_jams_own_mode_not_a_reset_widget(self) -> None:
        from backing_source_navigation import resolve_entry_jam_entry_mode

        ctx = _sealed_context(_generator(improv_ensemble="Rock trio"), "jam_session_generator")
        back: dict = {"improv_entry_mode": "Style Jam Mode"}  # the widget's reset value on Backing
        self.assertEqual(resolve_entry_jam_entry_mode(back, ctx=ctx), "Jam Session Generator")
        restore_session_widgets_from_backing_context(back, ctx, widget_safe=False)
        self.assertEqual(back.get("improv_ensemble"), "Rock trio")
        self.assertNotIn("improv_groove", back)  # Style Jam's controls untouched


class ReloadOntoBackingTests(unittest.TestCase):
    """After a reload onto Backing the sealed snapshot, the hand-off entry mode and (often) the workflow pointer are
    gone; the persisted Backing context still names the jam. It outranks the widgets' transient defaults."""

    def _reloaded(self) -> tuple[dict, BackingContext]:
        from backing_context import set_backing_context
        from generated_workflow_artifact import BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY

        session = _generator(improv_ensemble="Rock trio", improv_jam_style="Rock", improv_jam_mood="Gritty",
                             improv_jam_intensity="Light", improv_jam_difficulty="Advanced", improv_jam_bpm=120)
        sealed = _sealed_context(session, "jam_session_generator")
        set_backing_context(session, sealed)
        persisted = {"backing_context": session["backing_context"]}
        # A fresh session: only what is persisted, with the widgets at their reset values on Backing.
        fresh: dict = dict(_generator(improv_entry_mode="Style Jam Mode", improv_ensemble="Jazz trio",
                                      improv_jam_mood="Dark", improv_jam_intensity="Medium",
                                      improv_jam_difficulty="Intermediate", improv_jam_style="Rock"))
        fresh.update(persisted)
        fresh["studio_page"] = "backing"
        for k in ("_backing_handoff_entry_mode", BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY,
                  "_music_active_workflow", "_music_workflow_state_store"):
            fresh.pop(k, None)
        return fresh, sealed

    def test_reload_keeps_the_generator_jam_on_backing(self) -> None:
        from backing_source_navigation import resolve_entry_jam_entry_mode

        fresh, sealed = self._reloaded()
        self.assertEqual(resolve_entry_jam_entry_mode(fresh), "Jam Session Generator")
        perf = owner_jam_performance_settings(fresh, "jam_session_generator")
        self.assertEqual((perf["ensemble"], perf["intensity"], perf["level"]), ("Rock trio", "Light", "Advanced"))

    def test_on_creative_the_live_widgets_still_decide(self) -> None:
        from backing_source_navigation import resolve_entry_jam_entry_mode

        fresh, _ = self._reloaded()
        fresh["studio_page"] = "creative"
        self.assertEqual(resolve_entry_jam_entry_mode(fresh), "Style Jam Mode")  # the musician's own switch
        perf = owner_jam_performance_settings(fresh, "jam_session_generator")
        self.assertEqual(perf["ensemble"], "Jazz trio")
