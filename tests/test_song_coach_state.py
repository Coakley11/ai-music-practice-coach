"""Song-Aware Coaching S3 — coaching-session state, context from the Creative page, projection, callbacks."""

from __future__ import annotations

import copy
import json
import unittest
from functools import lru_cache
from types import SimpleNamespace

from music_theory import transpose_sections_dict
from song_coach_context import SOURCE_COMPOSITION, SOURCE_CUSTOM
from song_coach_plan import FOCUS_CHORD_TONE, FOCUS_MELODIC, FOCUS_RHYTHMIC, KIND_IDEA
from song_coach_state import (
    NOTICE_CHART_CHANGED,
    NOTICE_OTHER_SONG,
    NOTICE_PLAN_STALE,
    PLAN_CACHE_KEY,
    SONG_COACH_STATE_KEY,
    CoachState,
    Selection,
    build_plan_for,
    commit,
    default_selection,
    done_stages,
    reconcile,
    with_built_plan,
    with_check,
    with_draft,
    with_stage,
)
from song_coach_ui import (
    FLASH_KEY,
    W_FROM,
    W_TO,
    W_FOCUS,
    W_LEVEL,
    W_SECTION,
    chart_key_label,
    creative_coach_context,
    on_build,
    on_check,
    on_selection_change,
    on_stage,
    projectors,
)


SAVE_REQUESTS: list[str] = []
_SAVE_PATCH = None


def setUpModule() -> None:
    """Never write a workspace to disk from unit tests: record the save request instead."""
    global _SAVE_PATCH
    from unittest import mock

    _SAVE_PATCH = mock.patch(
        "creative_context_snapshot_persistence.request_context_cloud_save",
        side_effect=lambda session, *, save_reason: SAVE_REQUESTS.append(save_reason) or True,
    )
    _SAVE_PATCH.start()


def tearDownModule() -> None:
    if _SAVE_PATCH is not None:
        _SAVE_PATCH.stop()


@lru_cache(maxsize=None)
def _record(title: str) -> dict:
    from song_catalog.catalog import curated_song_records

    return next(r for r in curated_song_records() if r["title"] == title)


def _catalog_session(title: str, *, key: str | None = None, instrument: str = "Piano", written: bool = False) -> tuple[dict, SimpleNamespace]:
    rec = copy.deepcopy(_record(title))
    concert = key or rec["key"]
    pick = f"{rec['genre']}\x1f{title} — {rec['artist']}"
    session = {
        "active_catalog_pick_key": pick,
        "active_music_source": "catalog_song",
        "selected_song": dict(rec, pick_key=pick),
        "instrument": instrument,
        "level": "Beginner",
        "focus": "Pentatonics",
        "display_key": concert,
        "concert_key": concert,
        "backing_track_bpm": 72,
        "improv_generated_sections": {"Section A (Jazz Swing)": ["Em7", "A7", "Dmaj7"]},
    }
    if written:
        session.update({"show_chart_in_instrument_key": True, "selected_transposing_instrument": "Alto Sax (E♭)"})
    chart = concert
    if instrument == "Saxophone" and written:
        from music_theory import transpose_chord

        chart = transpose_chord(concert, 9, reference_key=concert)
    improv = SimpleNamespace(
        key_center=concert, display_key=chart, instrument=instrument, sections=transpose_sections_dict(rec["sections"], rec["key"], concert),
        section_order=rec.get("section_order") or [], song_title=title, artist=rec["artist"], bpm=72,
    )
    return session, improv


def _ctx(title: str = "Perfect", **kw):
    session, improv = _catalog_session(title, **kw)
    return session, improv, creative_coach_context(session, improv)


class TestCreativeContext(unittest.TestCase):
    def test_catalog_context_from_the_creative_page(self) -> None:
        session, _improv, ctx = _ctx()
        self.assertTrue(ctx.available, ctx.reason)
        self.assertEqual((ctx.song_title, ctx.concert_key, ctx.chart_key, ctx.written_key), ("Perfect", "G", "G", ""))
        self.assertEqual(ctx.chart_label, "Verified chord chart")  # from the catalog row, not selected_song
        self.assertEqual(chart_key_label(session, ctx), "")

    def test_meter_is_the_songs_own_unless_overridden_in_backing(self) -> None:
        session, improv = _catalog_session("Perfect")
        session["backing_time_signature"] = "4/4"  # not yet applied for this song: must be ignored
        self.assertEqual(creative_coach_context(session, improv).meter, "6/8")
        fp = creative_coach_context(session, improv).fingerprint
        session["backing_time_signature"] = "6/8"  # another page applying the song meter changes nothing
        self.assertEqual(creative_coach_context(session, improv).fingerprint, fp)
        session.update({"backing_time_signature_override": True, "backing_time_signature": "12/8"})
        self.assertEqual(creative_coach_context(session, improv).meter, "12/8")

    def test_simplified_chart_is_labelled_as_such(self) -> None:
        _s, _i, ctx = _ctx("The Girl from Ipanema")
        self.assertEqual(ctx.chart_label, "Simplified practice chart")

    def test_alto_sax_written_key(self) -> None:
        session, _improv, ctx = _ctx(instrument="Saxophone", written=True)
        self.assertEqual((ctx.concert_key, ctx.chart_key, ctx.written_key), ("G", "E", "E"))
        self.assertEqual(chart_key_label(session, ctx), "Written key")
        note, chord = projectors(ctx)
        self.assertEqual(note(SimpleNamespace(pc=7, name="G")), "E")
        self.assertEqual(note(SimpleNamespace(pc=6, name="F#")), "D#")
        self.assertEqual(chord("Cadd9"), "Aadd9")
        self.assertEqual(chord("D/F#"), "B/D#")

    def test_guitar_capo_is_a_shape_key(self) -> None:
        session, _improv, ctx = _ctx(instrument="Guitar")
        session["guitar_capo_enabled"] = True
        ctx2 = ctx.__class__(**{**ctx.__dict__, "chart_key": "E", "written_key": "E"})
        self.assertEqual(chart_key_label(session, ctx2), "Shape key")

    def test_concert_projection_keeps_plan_spelling(self) -> None:
        _s, _i, ctx = _ctx()
        note, chord = projectors(ctx)
        self.assertEqual(note(SimpleNamespace(pc=6, name="F#")), "F#")
        self.assertEqual(chord("D/F#"), "D/F#")

    def test_jam_or_stale_sections_never_coach(self) -> None:
        session, improv = _catalog_session("Perfect")
        improv.sections = session["improv_generated_sections"]
        self.assertFalse(creative_coach_context(session, improv).available)
        improv.sections = _record("The Girl from Ipanema")["sections"]
        self.assertFalse(creative_coach_context(session, improv).available)

    def test_custom_and_composition_contexts(self) -> None:
        from composition_document import new_composition_document

        cpl = {"id": "rev7", "name": "Trial Song", "original_key_center": "E", "time_signature": "4/4", "bpm": 90,
               "original_sections": {"Verse": [{"chord": "E", "bars": 2}, {"chord": "A", "bars": 1}, {"chord": "B7", "bars": 1}]}}
        session = {"active_catalog_pick_key": "custom::rev7", "active_music_source": "custom_progression", "cpl_active_progression": cpl}
        improv = SimpleNamespace(key_center="E", display_key="E", instrument="Guitar", sections={"Verse": ["E", "E", "A", "B7"]},
                                 section_order=["Verse"], song_title="Trial Song", artist="", bpm=90)
        ctx = creative_coach_context(session, improv)
        self.assertTrue(ctx.available, ctx.reason)
        self.assertEqual((ctx.source_kind, ctx.identity), (SOURCE_CUSTOM, "custom|custom::rev7"))

        doc = new_composition_document(title="My Song")
        doc["global"]["original_key_center"] = "D"
        sid = doc["form"]["section_order"][0]
        doc["form"]["sections"][sid]["chords"] = [{"chord": c, "bars": 1} for c in ("D", "G", "A7", "D")]
        label = doc["form"]["sections"][sid]["label"]
        session = {"active_catalog_pick_key": f"composition::{doc['id']}", "active_music_source": "composition_song",
                   "composer_active_document": doc}
        improv = SimpleNamespace(key_center="D", display_key="D", instrument="Piano", sections={label: ["D", "G", "A7", "D"]},
                                 section_order=[label], song_title="My Song", artist="", bpm=100)
        ctx = creative_coach_context(session, improv)
        self.assertTrue(ctx.available, ctx.reason)
        self.assertEqual(ctx.source_kind, SOURCE_COMPOSITION)

    def test_building_the_context_writes_nothing(self) -> None:
        session, improv = _catalog_session("Perfect", instrument="Saxophone", written=True)
        before = copy.deepcopy(session)
        creative_coach_context(session, improv)
        self.assertEqual(session, before)


class TestReconcile(unittest.TestCase):
    def test_fresh_defaults_skip_the_intro(self) -> None:
        session, _i, ctx = _ctx()
        rec = reconcile(session, ctx, level="Beginner", focus=FOCUS_MELODIC)
        self.assertIsNone(rec.plan)
        self.assertEqual(rec.state.draft, Selection("verse-1", 1, 8, "Beginner", FOCUS_MELODIC))
        self.assertEqual((rec.state.identity, rec.state.fingerprint), (ctx.identity, ctx.fingerprint))
        self.assertEqual(rec.notice, "")

    def _built(self, ctx, session, sel=None):
        state = CoachState(identity=ctx.identity, fingerprint=ctx.fingerprint,
                           draft=sel or default_selection(ctx, level="Intermediate", focus=FOCUS_CHORD_TONE))
        plan, _scope = build_plan_for(ctx, state.draft)
        state = with_built_plan(state, plan)
        session[SONG_COACH_STATE_KEY] = state.to_dict()
        return state, plan

    def test_built_plan_is_rebuilt_and_verified(self) -> None:
        session, _i, ctx = _ctx()
        state, plan = self._built(ctx, session)
        session[SONG_COACH_STATE_KEY] = with_stage(state, 3, len(plan.challenges)).to_dict()
        rec = reconcile(session, ctx, level="Beginner", focus=FOCUS_MELODIC)
        self.assertEqual(rec.plan.plan_id, plan.plan_id)
        self.assertEqual(rec.state.stage, 3)
        self.assertEqual(rec.state.draft, state.draft)  # global level/focus do not overwrite the coach's choice

    def test_another_songs_plan_is_never_shown(self) -> None:
        session, _i, ctx = _ctx()
        self._built(ctx, session)
        stored = copy.deepcopy(session[SONG_COACH_STATE_KEY])
        session2, _i2, ipanema = _ctx("The Girl from Ipanema")
        session2[SONG_COACH_STATE_KEY] = stored
        rec = reconcile(session2, ipanema, level="Beginner", focus=FOCUS_MELODIC)
        self.assertIsNone(rec.plan)
        self.assertEqual(rec.notice, NOTICE_OTHER_SONG)
        self.assertEqual(rec.state.identity, ipanema.identity)
        self.assertEqual(session2[SONG_COACH_STATE_KEY], stored)  # reading never writes

    def test_practice_key_change_invalidates_the_plan_but_keeps_choices(self) -> None:
        session, _i, ctx = _ctx()
        state, _plan = self._built(ctx, session, Selection("chorus-1", 1, 8, "Advanced", FOCUS_RHYTHMIC))
        s2, _i2, moved = _ctx(key="A")
        s2[SONG_COACH_STATE_KEY] = session[SONG_COACH_STATE_KEY]
        rec = reconcile(s2, moved, level="Beginner", focus=FOCUS_MELODIC)
        self.assertIsNone(rec.plan)
        self.assertEqual(rec.notice, NOTICE_CHART_CHANGED)
        self.assertEqual(rec.state.draft, state.draft)
        self.assertEqual(rec.state.fingerprint, moved.fingerprint)

    def test_chart_edit_invalidates_too(self) -> None:
        session, improv = _catalog_session("Perfect")
        ctx = creative_coach_context(session, improv)
        self._built(ctx, session)
        edited = copy.deepcopy(_record("Perfect"))
        edited["sections"]["Chorus 1"][-1] = "D"
        session["selected_song"] = dict(edited, pick_key=session["active_catalog_pick_key"])
        improv.sections = edited["sections"]
        rec = reconcile(session, creative_coach_context(session, improv), level="Beginner", focus=FOCUS_MELODIC)
        self.assertEqual((rec.plan, rec.notice), (None, NOTICE_CHART_CHANGED))

    def test_instrument_change_keeps_plan_and_progress(self) -> None:
        session, _i, ctx = _ctx()
        state, plan = self._built(ctx, session)
        session[SONG_COACH_STATE_KEY] = with_check(with_stage(state, 2, len(plan.challenges)), 0, 0, True).to_dict()
        s2, _i2, sax = _ctx(instrument="Saxophone", written=True)
        s2[SONG_COACH_STATE_KEY] = session[SONG_COACH_STATE_KEY]
        rec = reconcile(s2, sax, level="Beginner", focus=FOCUS_MELODIC)
        self.assertIsNotNone(rec.plan)
        self.assertEqual((rec.state.stage, rec.state.checks), (2, {"0": (0,)}))
        self.assertEqual([c.kind for c in rec.plan.challenges], [c.kind for c in plan.challenges])
        self.assertEqual(rec.plan.anchors, plan.anchors)  # concert data untouched; only display projects

    def test_tampered_or_outdated_plan_is_cleared(self) -> None:
        session, _i, ctx = _ctx()
        self._built(ctx, session)
        session[SONG_COACH_STATE_KEY]["plan_id"] = "0000000000000000"
        rec = reconcile(session, ctx, level="Beginner", focus=FOCUS_MELODIC)
        self.assertEqual((rec.plan, rec.notice), (None, NOTICE_PLAN_STALE))
        session[SONG_COACH_STATE_KEY]["built"]["section_id"] = "no-such-section"
        self.assertEqual(reconcile(session, ctx, level="Beginner", focus=FOCUS_MELODIC).notice, NOTICE_PLAN_STALE)

    def test_state_round_trips_and_rejects_garbage(self) -> None:
        state = with_check(CoachState(identity="catalog|x", fingerprint="f", draft=Selection("a", 1, 4, "Beginner", FOCUS_MELODIC)), 1, 2, True)
        self.assertEqual(CoachState.from_dict(json.loads(json.dumps(state.to_dict()))), state)
        self.assertIsNone(CoachState.from_dict("nope"))
        self.assertIsNone(CoachState.from_dict({"stage": "x"}))

    def test_stage_and_checks(self) -> None:
        session, _i, ctx = _ctx()
        state, plan = self._built(ctx, session)
        self.assertEqual(with_stage(state, 99, len(plan.challenges)).stage, len(plan.challenges) - 1)
        self.assertEqual(with_stage(state, -3, len(plan.challenges)).stage, 0)
        ticked = state
        for i in range(len(plan.challenges[0].checklist)):
            ticked = with_check(ticked, 0, i, True)
        self.assertEqual(done_stages(ticked, plan), {0})
        self.assertEqual(done_stages(with_check(ticked, 0, 0, False), plan), set())


class TestCommitAndCallbacks(unittest.TestCase):
    GLOBALS = ("display_key", "concert_key", "focus", "level", "instrument", "backing_track_bpm", "active_catalog_pick_key")

    def _globals(self, session):
        return {k: copy.deepcopy(session.get(k)) for k in self.GLOBALS}

    def test_commit_saves_through_the_creative_workspace_only(self) -> None:
        session, _i, ctx = _ctx()
        before = self._globals(session)
        SAVE_REQUESTS.clear()
        commit(session, CoachState(identity=ctx.identity, fingerprint=ctx.fingerprint), interaction="test")
        from creative_context_snapshot_persistence import SAVE_REASON_CONTEXT_SNAPSHOT

        self.assertEqual(SAVE_REQUESTS, [SAVE_REASON_CONTEXT_SNAPSHOT])  # an explicit user-event save
        self.assertEqual(session[SONG_COACH_STATE_KEY]["identity"], ctx.identity)
        self.assertIn(SONG_COACH_STATE_KEY, session["creative_workspace_state"])
        self.assertEqual(self._globals(session), before)

    def test_build_navigate_and_check(self) -> None:
        session, _i, ctx = _ctx()
        before = self._globals(session)
        on_build(session, ctx)
        state = CoachState.from_dict(session[SONG_COACH_STATE_KEY])
        self.assertTrue(state.has_plan)
        self.assertTrue(session[PLAN_CACHE_KEY])
        on_stage(session, ctx, 1)
        on_stage(session, ctx, 1)
        on_stage(session, ctx, -1)
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]).stage, 1)
        key = "chk"
        session[key] = True
        on_check(session, ctx, 1, 0, key)
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]).checks, {"1": (0,)})
        self.assertEqual(self._globals(session), before)

    def test_selection_changes_draft_but_keeps_the_built_plan(self) -> None:
        session, _i, ctx = _ctx()
        on_build(session, ctx)
        built = CoachState.from_dict(session[SONG_COACH_STATE_KEY])
        session.update({W_SECTION: built.draft.section_id, W_FROM: built.draft.start_bar, W_TO: built.draft.end_bar,
                        W_LEVEL: built.draft.level, W_FOCUS: built.draft.focus})
        on_selection_change(session, ctx)
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]), built)  # unchanged values: no write
        session[W_LEVEL] = "Advanced"
        on_selection_change(session, ctx)
        state = CoachState.from_dict(session[SONG_COACH_STATE_KEY])
        self.assertEqual(state.draft.level, "Advanced")
        self.assertEqual((state.built, state.plan_id), (built.built, built.plan_id))

    def test_section_change_picks_its_first_phrase_and_long_ranges_are_shortened(self) -> None:
        session, _i, ctx = _ctx()
        session.update({W_SECTION: "chorus-1", W_FROM: 1, W_TO: 8, W_LEVEL: "Beginner", W_FOCUS: FOCUS_MELODIC})
        on_selection_change(session, ctx)
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]).draft.section_id, "chorus-1")
        cpl = {"id": "long", "name": "Long", "original_key_center": "C",
               "original_sections": {"Solo": [{"chord": c, "bars": 1} for c in ["C", "F", "G", "C"] * 5]}}
        s2 = {"active_catalog_pick_key": "custom::long", "active_music_source": "custom_progression", "cpl_active_progression": cpl}
        improv = SimpleNamespace(key_center="C", display_key="C", instrument="Piano", sections={"Solo": ["C", "F", "G", "C"] * 5},
                                 section_order=["Solo"], song_title="Long", artist="", bpm=100)
        long_ctx = creative_coach_context(s2, improv)
        s2.update({W_SECTION: "solo", W_FROM: 1, W_TO: 8, W_LEVEL: "Beginner", W_FOCUS: FOCUS_MELODIC})
        on_selection_change(s2, long_ctx)
        s2[W_TO] = 20
        on_selection_change(s2, long_ctx)
        draft = CoachState.from_dict(s2[SONG_COACH_STATE_KEY]).draft
        self.assertEqual((draft.start_bar, draft.end_bar), (1, 16))
        self.assertIn("at most 16 bars", s2[FLASH_KEY])
        self.assertEqual((s2[W_FROM], s2[W_TO]), (1, 16))
        s2[W_FROM] = 18  # From moved past To: the previous length is kept from the new start
        on_selection_change(s2, long_ctx)
        draft = CoachState.from_dict(s2[SONG_COACH_STATE_KEY]).draft
        self.assertEqual((draft.start_bar, draft.end_bar), (18, 20))

    def test_plan_is_never_persisted_only_its_inputs(self) -> None:
        session, _i, ctx = _ctx()
        on_build(session, ctx)
        stored = json.dumps(session[SONG_COACH_STATE_KEY])
        self.assertLess(len(stored), 2000)
        self.assertNotIn("challenges", stored)
        self.assertEqual(json.loads(stored)["draft"]["section_id"], "verse-1")

    def test_first_challenge_is_the_idea(self) -> None:
        session, _i, ctx = _ctx()
        on_build(session, ctx)
        rec = reconcile(session, ctx, level="Beginner", focus=FOCUS_MELODIC)
        self.assertEqual(rec.plan.challenges[0].kind, KIND_IDEA)


class TestPersistenceRegistration(unittest.TestCase):
    def _lists(self):
        from creative_context_snapshot_persistence import CREATIVE_CONTEXT_CANONICAL_KEYS
        from creative_workspace_persistence import CREATIVE_WORKSPACE_KEYS
        from music_persistent_state import _PERSIST_KEYS
        from studio_page_persistence import _PAGE_LOCAL_KEYS

        return {
            "envelope": set(_PERSIST_KEYS),
            "creative_workspace": set(CREATIVE_WORKSPACE_KEYS),
            "creative_context": set(CREATIVE_CONTEXT_CANONICAL_KEYS),
            "creative_page_snapshot": set(_PAGE_LOCAL_KEYS["creative"]),
        }

    def test_coaching_state_persists_wherever_deep_harmony_does(self) -> None:
        for name, keys in self._lists().items():
            self.assertIn("deep_harmony_lesson_step", keys, name)
            self.assertIn(SONG_COACH_STATE_KEY, keys, name)

    def test_diagnostics_cache_and_widgets_are_session_only(self) -> None:
        from song_coach_state import LAST_COMMIT_KEY
        from song_coach_ui import CTX_DIAG_KEY, WIDGET_KEYS
        from studio_page_persistence import _PAGE_LOCAL_PREFIXES

        session_only = (LAST_COMMIT_KEY, CTX_DIAG_KEY, PLAN_CACHE_KEY, FLASH_KEY, *WIDGET_KEYS)
        for name, keys in self._lists().items():
            for key in session_only:
                self.assertNotIn(key, keys, (name, key))
        self.assertFalse(_PAGE_LOCAL_PREFIXES.get("creative"), "Creative snapshots are explicit keys only")

    def test_production_code_never_reads_the_diagnostics(self) -> None:
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        uses = []
        for path in root.glob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for literal in ("_song_coach_ctx_diag", "_song_coach_last_commit", "CTX_DIAG_KEY", "LAST_COMMIT_KEY"):
                if literal in text:
                    uses.append((path.name, text.count(literal)))
        # Only their definitions and their single write sites, in the coaching modules.
        self.assertEqual(sorted({name for name, _ in uses}), ["song_coach_state.py", "song_coach_ui.py"])
        state = (root / "song_coach_state.py").read_text(encoding="utf-8")
        ui = (root / "song_coach_ui.py").read_text(encoding="utf-8")
        self.assertEqual(state.count("LAST_COMMIT_KEY]"), 1)  # session[LAST_COMMIT_KEY] = ... (write only)
        self.assertEqual(ui.count("CTX_DIAG_KEY]"), 1)
        self.assertNotIn(".get(LAST_COMMIT_KEY", state + ui)
        self.assertNotIn(".get(CTX_DIAG_KEY", state + ui)


if __name__ == "__main__":
    unittest.main()
