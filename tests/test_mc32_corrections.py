"""MC3.2 — ABC source UI removed, simpler rhythm-Mission pitches, truthful span Mission Backing
card (no stale one-chord fields, no duplicate progression, badges render as UI), and explicit
song activation outranking stale Creative / Mission workflow state."""

from __future__ import annotations

import logging
import re
import unittest
from pathlib import Path

from harmonic_span_analyzer import analyze_harmonic_spans
from mission_span_engine import MISSIONS_BY_ID, generate_mission_span_example, validate_mission_line
from span_motif_engine import _ctx
from tests.abc_pitch_decoder import decode_abc_midis

logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parents[1]
IPANEMA = "Jazz\x1fThe Girl from Ipanema — Antonio Carlos Jobim"
AUTUMN = "Jazz\x1fAutumn Leaves — Jazz Standard"


def span(chords, key):
    rows = [("A", list(chords) + ["Cmaj7"], list(chords) + ["Cmaj7"])]
    return analyze_harmonic_spans(rows, key_center=key, length=3, source_id="t")[0]


# --------------------------------------------------------------------------- 1. ABC source UI


class TestNoAbcSourceUi(unittest.TestCase):
    def test_no_user_facing_abc_source_control(self) -> None:
        for path in ROOT.glob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn('"ABC source', text, path.name)

    def test_sheet_music_still_renders_from_abc(self) -> None:
        import improvisation_intelligence_ui as ui

        captured = []

        class _St:
            def container(self):
                class _C:
                    def __enter__(self_inner):
                        return self_inner

                    def __exit__(self_inner, *a):
                        return False

                return _C()

            def expander(self, *a, **k):  # pragma: no cover — must not be called any more
                raise AssertionError("no ABC source expander")

        class _Comp:
            @staticmethod
            def html(doc, height=None, scrolling=None):
                captured.append(doc)

        orig = ui.components
        ui.components = _Comp
        try:
            abc = "X:1\nT:Motif\nM:4/4\nL:1/4\nK:C\nC D E F |"
            ui._render_motif_sheet_music(_St(), abc)
        finally:
            ui.components = orig
        self.assertEqual(len(captured), 1)
        self.assertIn("ABCJS.renderAbc", captured[0])
        self.assertIn("C D E F |", captured[0])
        self.assertEqual(decode_abc_midis(abc), [60, 62, 64, 65])


# --------------------------------------------------------------------------- 2. rhythm Mission


def _repeat_ratio(midi):
    return sum(1 for a, b in zip(midi, midi[1:]) if a == b) / max(1, len(midi) - 1)


def _per_chord(m):
    return [len(set(m["midi"][t["first_note"]: t["last_note"] + 1])) for t in m["chord_timeline"]]


class TestRhythmMissionPitches(unittest.TestCase):
    SPANS = (span(["Gm7", "C7", "Fmaj7"], "F"), span(["Dm7", "G7", "Cmaj7"], "C"), span(["C", "Am", "F"], "C"))

    def _examples(self, mid, level):
        for sp in self.SPANS:
            for style in ("jazz", "pop", "ballad"):
                for idea in range(3):
                    yield sp, style, generate_mission_span_example(MISSIONS_BY_ID[mid], sp, level=level, style=style, idea=idea)

    def test_much_more_repetition_and_a_tiny_vocabulary(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            rhythm = list(self._examples("rhythm_over_notes", level))
            ordinary = list(self._examples("target_each_change", level))
            r_rep = sum(_repeat_ratio(e["motif"]["midi"]) for *_x, e in rhythm) / len(rhythm)
            o_rep = sum(_repeat_ratio(e["motif"]["midi"]) for *_x, e in ordinary) / len(ordinary)
            self.assertGreaterEqual(r_rep, 0.45, level)
            self.assertGreaterEqual(r_rep - o_rep, 0.4, level)
            cap = 3 if level == "Advanced" else 2
            for sp, style, e in rhythm:
                self.assertTrue(all(n <= cap for n in _per_chord(e["motif"])), (level, style, e["motif"]["display"]))
                self.assertLessEqual(len(set(e["motif"]["midi"])), 5, e["motif"]["display"])
            r_line = sum(len(set(e["motif"]["midi"])) for *_x, e in rhythm) / len(rhythm)
            o_line = sum(len(set(e["motif"]["midi"])) for *_x, e in ordinary) / len(ordinary)
            self.assertLess(r_line, o_line - 1.0, level)

    def test_changes_stay_harmonically_valid_and_rhythm_stays_the_exercise(self) -> None:
        from melodic_rhythm_engine import events_from_json

        for level in ("Beginner", "Intermediate", "Advanced"):
            for sp, style, e in self._examples("rhythm_over_notes", level):
                self.assertTrue(e["valid"], (level, style, e["problems"]))
                m = e["motif"]
                for t in m["chord_timeline"]:
                    ctx = _ctx(sp.key_center, t["chord"])
                    self.assertIn(m["midi"][t["first_note"]] % 12, ctx.chord_pcs)
                durs = {ev.duration for ev in events_from_json(m["rhythm_events"]) if not ev.rest}
                self.assertGreaterEqual(len(durs), 2, m["rhythm"])

    def test_harder_makes_the_rhythm_harder_not_the_pitches(self) -> None:
        from span_motif_engine import rhythm_profile

        for level in ("Intermediate", "Advanced"):
            normal = generate_mission_span_example(MISSIONS_BY_ID["rhythm_over_notes"], self.SPANS[0], level=level, style="jazz")
            harder = generate_mission_span_example(MISSIONS_BY_ID["rhythm_over_notes"], self.SPANS[0], level=level,
                                                   style="jazz", variant="harder")
            self.assertTrue(harder["valid"], harder["problems"])
            self.assertGreaterEqual(_repeat_ratio(harder["motif"]["midi"]), 0.45, harder["motif"]["display"])
            cap = 3 if level == "Advanced" else 2
            self.assertTrue(all(n <= cap for n in _per_chord(harder["motif"])), harder["motif"]["display"])
            # Harder = a denser rhythm on the same pitch cell (splits repeat the note).
            self.assertGreater(len(harder["motif"]["midi"]), len(normal["motif"]["midi"]))
            self.assertLessEqual(set(m % 12 for m in harder["motif"]["midi"]) - set(m % 12 for m in normal["motif"]["midi"]),
                                 set())
            self.assertIsNotNone(rhythm_profile(harder["motif"]["rhythm_events"], "4/4"))

    def test_common_tone_is_kept_across_a_change(self) -> None:
        # Gm7 → C7: B♭ is the 3rd of Gm7 and the 7th of C7 — nothing needs to move.
        e = generate_mission_span_example(MISSIONS_BY_ID["rhythm_over_notes"], self.SPANS[0], level="Intermediate", style="jazz")
        m = e["motif"]
        tl = m["chord_timeline"]
        a0, a1 = m["midi"][tl[0]["first_note"]], m["midi"][tl[1]["first_note"]]
        if a0 % 12 in _ctx("F", "C7").chord_pcs:
            self.assertEqual(a0, a1, m["display"])


# --------------------------------------------------------------------------- 3–6. span Mission Backing card


def _staged_session(*, instrument="Clarinet"):
    from mission_span_ui import start_span_mission_backing

    sp = span(["D7", "Dm7", "Db7"], "C")
    e = generate_mission_span_example(MISSIONS_BY_ID["enclose_next_target"], span(["Dm7", "Db7", "Cmaj7"], "C"),
                                      level="Advanced", style="jazz")
    e["handoff"]["practice_key"] = "C"
    s = {"instrument": instrument, "concert_key": "C", "display_key": "C", "song": "The Girl from Ipanema",
         "active_catalog_pick_key": IPANEMA,
         "improv_mission_pick": "Improvise using only chord tones", "improv_active_mission": "Improvise using only chord tones",
         "ii_selected_chord": "Gm7", "ii_selected_section": "A", "ii_selected_chord_index": 0}
    start_span_mission_backing(s, example=e, heading="Span", section_label="A", practice_key="C", with_practice_lick=True,
                               instrument=instrument, level="Advanced", style="jazz", focus="", bpm=100,
                               relationship_label="ii–subV–I")
    return s, e, sp


def _card_html(s):
    from backing_context import build_mission_context
    from backing_context_ui import render_backing_creative_context_card

    out = []

    class _St:
        def markdown(self, text, **_k):
            out.append(text)

    ctx = build_mission_context(s)
    render_backing_creative_context_card(_St(), ctx, s, applied_bpm=100, applied_groove="Jazz swing", practice_key="C")
    return out[-1]


def _visible(html):
    return re.sub(r"<[^>]+>", "", html)


class TestSpanMissionBackingCard(unittest.TestCase):
    def test_span_mission_wins_over_stale_one_chord_fields(self) -> None:
        s, e, _sp = _staged_session()
        text = _visible(_card_html(s))
        self.assertIn("The Girl from Ipanema · Enclose the next target · A", text)
        self.assertIn("Progression: Dm7 → Db7 → Cmaj7", text)
        self.assertNotIn("Improvise using only chord tones", text)
        self.assertNotIn("Gm7", text)
        self.assertEqual(text.count("Dm7 → Db7 → Cmaj7"), 1)  # never printed twice

    def test_badges_render_as_markup_never_as_text(self) -> None:
        s, _e, _sp = _staged_session(instrument="Clarinet")
        html = _card_html(s)
        text = _visible(html)
        for bad in ("<svg", "<path", "class=", "&lt;", "viewBox", "instrument-icon"):
            self.assertNotIn(bad, text, bad)
        self.assertIn('<svg class="ui-instrument-icon-clarinet"', html)  # the real icon, rendered
        for badge in ("Style · Jazz swing", "Concert key · C major", "BPM · 100", "Meter · 4/4",
                      "Instrument · Clarinet", "Section · A"):
            self.assertIn(badge, text)

    def test_every_backing_badge_uses_the_trusted_icon_path(self) -> None:
        from backing_context_ui import _themed_badge
        from music_feature_icons import CLARINET_ICON_SVG

        badge = _themed_badge(CLARINET_ICON_SVG, "Instrument", "Clarinet <b>")
        self.assertIn(CLARINET_ICON_SVG, badge)
        self.assertIn("Clarinet &lt;b&gt;", badge)  # values stay escaped
        app_ui = (ROOT / "app_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("html.escape(instrument_icon(", app_ui)
        self.assertNotIn('html.escape(semantic_field_icon("written_key"', app_ui)

    def test_one_chord_card_is_unchanged(self) -> None:
        from mission_span_backing import clear_span_backing

        s, _e, _sp = _staged_session()
        clear_span_backing(s)
        text = _visible(_card_html(s))
        self.assertIn("Improvise using only chord tones", text)
        self.assertIn("Gm7", text)

    def test_lick_card_lists_mission_span_section_once(self) -> None:
        from mission_span_backing import render_span_lick_on_backing

        s, _e, _sp = _staged_session()
        out = []

        class _St:
            def markdown(self, text, **_k):
                out.append(text)

            def caption(self, *_a, **_k):
                pass

            def code(self, *_a, **_k):
                pass

        import improvisation_intelligence_ui as ui

        orig = ui._render_motif_sheet_music
        ui._render_motif_sheet_music = lambda *_a, **_k: None
        try:
            self.assertTrue(render_span_lick_on_backing(_St(), s, applied_bpm=100, concert_key="C"))
        finally:
            ui._render_motif_sheet_music = orig
        card = _visible(next(t for t in out if "mc-span-lick-card" in t))
        self.assertIn("Mission: Enclose the next target", card)
        self.assertIn("Span: Dm7 → Db7 → Cmaj7 · ii–subV–I", card)
        self.assertIn("Section: A · Advanced", card)
        self.assertEqual(card.count("Dm7 → Db7 → Cmaj7"), 1)

    def test_span_payload_never_survives_a_song_switch(self) -> None:
        from mission_span_backing import active_span_backing

        s, _e, _sp = _staged_session()
        self.assertIsNotNone(active_span_backing(s))
        s["active_catalog_pick_key"] = AUTUMN
        s["song"] = "Autumn Leaves"
        self.assertIsNone(active_span_backing(s))
        text = _visible(_card_html(s))
        self.assertNotIn("Enclose the next target", text)

    def test_span_rows_follow_a_mission_practice_key_change(self) -> None:
        import improvisation_intelligence_ui as ui

        # The song's cached sections are still spelled in F while the Mission key is now G.
        s = {"selected_song": {"key": "F"}}
        stale = [("A", ["Gm7", "C7", "Fmaj7"], ["Gm7", "C7|C7", "Fmaj7"])]
        self.assertEqual(ui._rows_in_concert_key(s, stale, "G"),
                         [("A", ["Am7", "D7", "Gmaj7"], ["Am7", "D7|D7", "Gmaj7"])])
        in_flight = [("A", ["Am7", "D7", "Gmaj7"], ["Am7", "D7", "Gmaj7"])]
        self.assertEqual(ui._rows_in_concert_key(s, in_flight, "G"), in_flight)  # never twice
        self.assertEqual(ui._rows_in_concert_key(s, stale, "F"), stale)
        self.assertEqual(ui._rows_in_concert_key({}, stale, "G"), stale)  # no known key: never guessed

    def test_projected_span_follows_the_mission_practice_key(self) -> None:
        from mission_span_backing import span_backing_summary

        from effective_practice_context import musician_facing_chord

        s, _e, _sp = _staged_session()
        self.assertEqual(span_backing_summary(s, "C")["chords"], "Dm7 → Db7 → Cmaj7")
        # Moved to D through the app's own chord projection (its spelling, e.g. D♯7 in D).
        expected = " → ".join(musician_facing_chord(c, concert_key="C", chart_key="D") for c in ("Dm7", "Db7", "Cmaj7"))
        self.assertEqual(span_backing_summary(s, "D")["chords"], expected)
        self.assertTrue(expected.startswith("Em7 → "))


# --------------------------------------------------------------------------- 7–9. song switching


class TestSongActivationOutranksStaleCreative(unittest.TestCase):
    def test_songs_activation_outranks_a_stale_mission_hint(self) -> None:
        from music_source_ownership import _activate_songs_hub_backing_workflow
        from music_workflow_canonical_identity import validate_pre_activation_identity
        from music_workflow_mission_session import mission_blob_session_id
        from music_workflow_state_store import ActiveWorkflowPointer, get_active_workflow_pointer, set_active_workflow_pointer
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        s = {"active_catalog_pick_key": IPANEMA, "song": "The Girl from Ipanema"}
        set_active_workflow_pointer(s, ActiveWorkflowPointer("mission_jam", f"mission|catalog|{IPANEMA}", 3), source="t")
        s[ACTIVE_WORKFLOW_OWNER_KEY] = "mission_jam"
        s["active_catalog_pick_key"] = AUTUMN
        _activate_songs_hub_backing_workflow(s, owner="regular_catalog_backing", activation_source="test")
        self.assertEqual(get_active_workflow_pointer(s).workflow_owner, "regular_catalog_backing")
        ok = validate_pre_activation_identity(s, target_owner="mission_jam", target_session_id=mission_blob_session_id(s),
                                              ptr_before=get_active_workflow_pointer(s), activation_source="creative_tab_change")
        self.assertTrue(ok.ok, ok.violations)  # the stale mission_jam hint no longer blocks Creative
        self.assertIn("healed_legacy_owner_mismatch", ok.diagnostics)

    def test_missions_pointer_on_an_older_song_is_not_kept(self) -> None:
        from music_workflow_creative_nav import _song_based_pointer_matches_live
        from music_workflow_mission_session import mission_blob_session_id
        from music_workflow_state_store import ActiveWorkflowPointer

        s = {"active_catalog_pick_key": AUTUMN, "song": "Autumn Leaves"}
        live = mission_blob_session_id(s)
        stale = ActiveWorkflowPointer("mission_jam", f"mission|catalog|{IPANEMA}", 5)
        fresh = ActiveWorkflowPointer("mission_jam", live, 5)
        self.assertFalse(_song_based_pointer_matches_live(s, stale, "mission_jam"))
        self.assertTrue(_song_based_pointer_matches_live(s, fresh, "mission_jam"))

    def test_identity_check_allows_the_switch_to_the_live_song_mission(self) -> None:
        from music_workflow_canonical_identity import validate_pre_activation_identity
        from music_workflow_mission_session import mission_blob_session_id
        from music_workflow_state_store import ActiveWorkflowPointer

        s = {"active_catalog_pick_key": AUTUMN, "song": "Autumn Leaves"}
        ptr = ActiveWorkflowPointer("mission_jam", f"mission|catalog|{IPANEMA}", 5)
        live = mission_blob_session_id(s)
        ok = validate_pre_activation_identity(s, target_owner="mission_jam", target_session_id=live, ptr_before=ptr,
                                              activation_source="creative_tab_change")
        self.assertTrue(ok.ok, ok.violations)
        other = validate_pre_activation_identity(s, target_owner="mission_jam", target_session_id="mission|catalog|Something else",
                                                 ptr_before=ptr, activation_source="creative_tab_change")
        self.assertFalse(other.ok)  # only the live song's Mission session is allowed, never an arbitrary one

    def test_cross_source_mission_sessions_follow_the_active_source(self) -> None:
        from music_workflow_creative_nav import _song_based_pointer_matches_live
        from music_workflow_mission_session import mission_blob_session_id
        from music_workflow_state_store import ActiveWorkflowPointer

        catalog = {"active_catalog_pick_key": IPANEMA, "song": "The Girl from Ipanema"}
        cat_ptr = ActiveWorkflowPointer("mission_jam", mission_blob_session_id(catalog), 2)
        self.assertTrue(_song_based_pointer_matches_live(catalog, cat_ptr, "mission_jam"))
        try:
            from songs.music_source import SOURCE_CUSTOM
        except ImportError:  # pragma: no cover
            SOURCE_CUSTOM = "custom"
        custom = {"active_music_source": SOURCE_CUSTOM, "custom_progression_id": "abc123", "song": "My Progression",
                  "active_catalog_pick_key": "custom::abc123"}
        cust_sid = mission_blob_session_id(custom)
        self.assertNotEqual(cust_sid, cat_ptr.workflow_session_id)
        self.assertFalse(_song_based_pointer_matches_live(custom, cat_ptr, "mission_jam"))  # Catalog → Custom
        cust_ptr = ActiveWorkflowPointer("mission_jam", cust_sid, 3)
        self.assertFalse(_song_based_pointer_matches_live(catalog, cust_ptr, "mission_jam"))  # Custom → Catalog


class TestSongSwitchIntoCreativeApp(unittest.TestCase):
    """Real app run: Ipanema Missions span example → Songs → Autumn Leaves → Creative."""

    def test_explicit_song_survives_entry_into_creative(self) -> None:
        import os
        import shutil
        import tempfile

        from streamlit.testing.v1 import AppTest

        data_dir = tempfile.mkdtemp(prefix="mc32_switch_")
        prior = os.environ.get("MUSIC_APP_DATA_DIR")
        os.environ["MUSIC_APP_DATA_DIR"] = data_dir
        try:
            at = AppTest.from_file(str(ROOT / "streamlit_music_practice_app.py"), default_timeout=300)
            at.run(timeout=300)

            def click(key):
                btn = next((w for w in at.button if str(w.key) == key), None)
                if btn is None and key == "studio_quick_nav_btn_picker":
                    # A restored start page can hide the tile row; the sidebar Songs button is always there.
                    btn = next((w for w in at.button if str(w.key) == "sidebar_goto_song_selection"), None)
                self.assertIsNotNone(btn, (key, [str(w.key) for w in at.button][:20],
                                           [str(e.value)[:300] for e in at.exception]))
                btn.click()
                at.run(timeout=300)

            def pick(needle):
                dd = at.selectbox(key="matching_song_dropdown")
                at.selectbox(key="matching_song_dropdown").set_value([o for o in dd.options if needle in o][0])
                at.run(timeout=300)

            click("studio_quick_nav_btn_picker")
            pick("Ipanema")
            click("studio_quick_nav_btn_creative")
            try:
                at.selectbox(key="creative_lab_analysis_mode").set_value("Improvisation Intelligence")
                at.run(timeout=300)
            except Exception:
                pass
            opts = at.radio(key="improv_intelligence_tab").options
            at.radio(key="improv_intelligence_tab").set_value([o for o in opts if "Mission" in o][0])
            at.run(timeout=300)
            at.radio(key="improv_mission_target_scope").set_value("span3")
            at.run(timeout=300)
            click("improv_span_mission_gen")
            click("studio_quick_nav_btn_picker")
            pick("Autumn Leaves")
            click("studio_quick_nav_btn_creative")
            ss = at.session_state
            self.assertEqual(ss["song"], "Autumn Leaves")
            self.assertNotIn("_music_workflow_activation_error", ss)  # no aborted activation
            alerts = [str(w.value) for w in list(at.warning) + list(at.error)]
            self.assertFalse([a for a in alerts if "identity conflict" in a], alerts)
            captions = " ".join(str(c.value) for c in at.caption)
            self.assertIn("Autumn Leaves", captions)
            self.assertNotIn("Ipanema", captions)
            from music_workflow_state_store import MUSIC_ACTIVE_WORKFLOW_KEY as ACTIVE_WORKFLOW_POINTER_KEY

            ptr = dict(ss[ACTIVE_WORKFLOW_POINTER_KEY])
            self.assertEqual(ptr.get("workflow_owner"), "mission_jam")
            sid = str(ptr.get("workflow_session_id") or "")
            self.assertTrue(sid.startswith("mission|"), sid)
            self.assertIn("Autumn Leaves", sid)  # the Mission session belongs to the new song
            self.assertNotIn("Ipanema", sid)
        finally:
            if prior is None:
                os.environ.pop("MUSIC_APP_DATA_DIR", None)
            else:
                os.environ["MUSIC_APP_DATA_DIR"] = prior
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
