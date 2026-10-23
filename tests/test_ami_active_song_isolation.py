"""AMI must build against the song the app has active RIGHT NOW (Catalog, Custom Progression or Composition), never against a chart
cached from an earlier song, and must say so instead of guessing when the chart cannot be tied to the active song.

The sessions here are the app's own state shapes (explicit source commit, ``commit_composition_active_song``, the custom
progression lab dict, the catalog pick key), with the *leftovers* the app really keeps when a song is switched: the previous
catalog record in ``selected_song``, a cached AMI context describing the previous song, and an older practice snapshot. Every
assertion reads the generated notes and chords, not a displayed label.
"""

from __future__ import annotations

import copy
import unittest

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_session_state import save_document_to_library, set_active_document
from composition_songs_bridge import commit_composition_active_song
from custom_progression_lab import default_active_progression, ensure_original_structure
from music_coach_ami.chart_context_reader import live_active_source, resolve_coach_chart_snapshot
from music_coach_ami.exercise_model import GeneratedExercise
from music_coach_ami.exercise_scope import collapse_loop
from music_coach_ami.pipeline import run_coach_submit
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
    commit_explicit_music_source_choice,
    ensure_song_picker_catalog,
)

SOY_PICK = "Pop\x1fShape of You — Ed Sheeran"
SOY_VERSE = ["Bm", "Em", "G", "A"]
F_MINOR_PROG = ["Fm7", "Bbm7", "Dbmaj7", "Fm7"]
COMP_CHORDS = "Dm Gm A7 Dm"


class _St:
    def __init__(self, ss: dict):
        self.session_state = ss


def _composition_doc():
    doc = bootstrap_from_vision(genre="Pop", song_idea="isolation", title="Isolation Test Comp", key="D minor", bpm=96)
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste(COMP_CHORDS))
    return doc


def _custom_progression():
    active = ensure_original_structure(default_active_progression())
    active["name"] = "F Minor Prog"
    active["original_key_center"] = "Fm"
    active["original_sections"] = {**active["original_sections"], "Verse": [{"chord": c, "bars": 1} for c in F_MINOR_PROG]}
    return active


def fresh() -> dict:
    s: dict = {"instrument": "Piano", "level": "Intermediate", "studio_page": "creative", "backing_track_bpm": 100}
    ensure_song_picker_catalog(s)
    return s


def stale_ami_ctx() -> dict:
    """What a cached AMI context / practice snapshot says when Shape of You was the last song."""
    return {
        "active_song": {"title": "Shape of You", "artist": "Ed Sheeran", "genre": "Pop", "pick_key": SOY_PICK, "key": "Bm",
                        "sections": {"Verse 1": list(SOY_VERSE) * 4}, "chart_sections": {"Verse 1": list(SOY_VERSE) * 4}},
        "pick_key": SOY_PICK, "display_key": "Bm", "chart_sections": {"Verse 1": list(SOY_VERSE) * 4}, "chart_sections_key": "Bm",
        "practice_snapshot": {"pick_key": SOY_PICK, "display_key": "Bm", "title": "Shape of You"},
    }


def activate_catalog(s: dict) -> None:
    commit_explicit_music_source_choice(s, SOURCE_CATALOG)
    s[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
    s.update(active_catalog_pick_key=SOY_PICK, song="Shape of You", artist="Ed Sheeran", display_key="Bm", concert_key="Bm",
             selected_song={"pick_key": SOY_PICK, "title": "Shape of You", "artist": "Ed Sheeran", "genre": "Pop", "key": "Bm"},
             improv_song_concert_sections={"Verse 1": list(SOY_VERSE) * 4})


def activate_custom(s: dict, chords=None) -> None:
    commit_explicit_music_source_choice(s, SOURCE_CUSTOM)
    s[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
    prog = _custom_progression()
    if chords is not None:
        prog["original_sections"] = {k: [] for k in prog["original_sections"]}
        if chords:
            prog["original_sections"]["Verse"] = [{"chord": c, "bars": 1} for c in chords]
    s["cpl_active_progression"] = prog
    s.update(active_catalog_pick_key="custom::F Minor Prog", song="F Minor Prog", display_key="Fm", concert_key="Fm",
             improv_song_concert_sections={"Verse": list(chords if chords is not None else F_MINOR_PROG)})
    # leftovers the app keeps: the previous catalog record stays in selected_song


def activate_composition(s: dict) -> dict:
    doc = _composition_doc()
    set_active_document(s, doc, checkpoint=False)
    save_document_to_library(s, doc)
    commit_composition_active_song(_St(s), doc, reset_practice_to_original=True)
    s["improv_song_concert_sections"] = {"Verse": COMP_CHORDS.split()}
    return doc


def ask(question: str, session: dict, ami_ctx: dict | None = None):
    req, resp = run_coach_submit(question, session, ami_ctx=stale_ami_ctx() if ami_ctx is None else ami_ctx)
    raw = ((resp.diagnostics if resp else None) or {}).get("generated_exercise")
    return resp, (GeneratedExercise.from_dict(raw) if raw else None)


def chord_pcs(chord: str, key: str) -> list[int]:
    from improvisation_motif import _midi_from_note, chord_tone_names

    return [_midi_from_note(n, 4) % 12 for n in (chord_tone_names(chord, reference_key=key) or [])]


def assert_notes_fit_chord(tc: unittest.TestCase, ex: GeneratedExercise) -> None:
    pcs = chord_pcs(ex.chord, ex.context.concert_key)
    targets = [m for m, r in zip(ex.midi, ex.chord_roles) if r]
    tc.assertTrue(targets, (ex.chord, ex.notes))
    tc.assertTrue(all(m % 12 in pcs for m in targets), (ex.chord, ex.notes))


EXPECT = {
    "catalog": ({"Bm7", "Bm"}, "Bm"),
    "custom": ({"Fm7"}, "Fm"),
    "composition": ({"Dm", "Dm7"}, "Dm"),
}
ACTIVATE = {"catalog": activate_catalog, "custom": activate_custom, "composition": lambda s: activate_composition(s)}


class TestSourceTransitions(unittest.TestCase):
    def _step(self, s: dict, name: str) -> None:
        ACTIVATE[name](s)
        self.assertEqual(live_active_source(s)[0], name)
        chords, key = EXPECT[name]
        snap = resolve_coach_chart_snapshot(s, ami_ctx=stale_ami_ctx(), active_section="")
        self.assertTrue(snap["chart_verified"], snap.get("chart_unverified_reason"))
        first = snap["active_section_chords"][0]
        self.assertIn(first, chords | {c.replace("7", "") for c in chords}, (name, snap["active_section_chords"]))
        resp, ex = ask("Give me an enclosure over this chord.", s)
        self.assertIsNotNone(ex, (name, resp.direct_answer[:200]))
        self.assertIn(ex.chord, chords, (name, ex.chord, ex.notes))
        self.assertEqual(ex.context.concert_key, key, name)
        assert_notes_fit_chord(self, ex)

    def test_catalog_custom_composition_catalog(self) -> None:
        s = fresh()
        for name in ("catalog", "custom", "composition", "catalog"):
            with self.subTest(step=name):
                self._step(s, name)

    def test_catalog_composition_catalog(self) -> None:
        s = fresh()
        for name in ("catalog", "composition", "catalog"):
            with self.subTest(step=name):
                self._step(s, name)

    def test_custom_to_catalog_and_composition_to_catalog(self) -> None:
        for start in ("custom", "composition"):
            with self.subTest(start=start):
                s = fresh()
                self._step(s, start)
                self._step(s, "catalog")

    def test_every_pair_in_both_directions(self) -> None:
        names = ("catalog", "custom", "composition")
        for a in names:
            for b in names:
                if a != b:
                    with self.subTest(a=a, b=b):
                        s = fresh()
                        self._step(s, a)
                        self._step(s, b)

    def test_the_composition_never_borrows_the_catalogs_bm(self) -> None:
        """The reported bug: Composition active in C, AMI answered on Shape of You's Bm."""
        for leftover in (False, True):
            with self.subTest(selected_song_left_on_shape_of_you=leftover):
                s = fresh()
                activate_catalog(s)
                catalog_record = dict(s["selected_song"])
                activate_composition(s)
                if leftover:       # the catalog record the app can leave behind while Composition is active
                    s["selected_song"] = catalog_record
                resp, ex = ask("Give me an enclosure over this chord.", s)
                self.assertNotIn(ex.chord, {"Bm", "Bm7"})
                self.assertIn(ex.chord, {"Dm", "Dm7"})
                self.assertEqual(ex.context.concert_key, "Dm")

    def test_a_cached_context_cannot_overlay_the_previous_songs_sections(self) -> None:
        s = fresh()
        activate_catalog(s)
        activate_custom(s)
        snap = resolve_coach_chart_snapshot(s, ami_ctx=stale_ami_ctx(), active_section="")
        flat = [c for ch in snap["chart_sections"].values() for c in ch]
        self.assertEqual(set(flat), set(F_MINOR_PROG))
        self.assertEqual(snap["chart_source"], "custom.original_sections")


class TestReloadAndKeys(unittest.TestCase):
    def test_after_a_reload_the_live_song_still_wins(self) -> None:
        for name in ("custom", "composition", "catalog"):
            with self.subTest(song=name):
                s = fresh()
                activate_catalog(s)
                ACTIVATE[name](s)
                reloaded = {k: copy.deepcopy(v) for k, v in s.items() if not k.startswith(("music_ami", "_ami_", "practice_snapshot"))}
                resp, ex = ask("Give me an enclosure over this chord.", reloaded, ami_ctx={})
                self.assertIsNotNone(ex, resp.direct_answer[:200])
                self.assertIn(ex.chord, EXPECT[name][0])

    def test_a_practice_key_change_transposes_the_live_song_only(self) -> None:
        s = fresh()
        activate_custom(s)
        s["display_key"] = s["concert_key"] = "Gm"
        resp, ex = ask("Give me an enclosure over this chord.", s)
        self.assertEqual((ex.chord, ex.context.concert_key), ("Gm7", "Gm"))
        assert_notes_fit_chord(self, ex)
        s2 = fresh()
        activate_catalog(s2)
        s2["display_key"] = s2["concert_key"] = "Am"
        resp, ex = ask("Give me an enclosure over this chord.", s2)
        self.assertEqual((ex.chord, ex.context.concert_key), ("Am7", "Am"))

    def test_capo_state_is_neither_read_as_the_key_nor_changed(self) -> None:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        for enabled, shape in ((False, "B"), (True, "A")):
            with self.subTest(capo=enabled):
                s = fresh()
                s["instrument"] = "Guitar"
                activate_catalog(s)
                s[CAPO_ENABLED_KEY], s[CAPO_SHAPE_KEY] = enabled, shape
                before = {k: copy.deepcopy(s.get(k)) for k in (CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, "display_key", "concert_key")}
                resp, ex = ask("Give me an enclosure over this chord.", s)
                # the sounding key is the Practice Key whatever the shape key is; AMI never turns capo mode on or off
                self.assertEqual(resp.diagnostics["practice_concert_key"], "Bm")
                self.assertEqual({k: s.get(k) for k in before}, before)
                if enabled:
                    # Stage 2 has no verified written (shape-key) version of a single-chord technique exercise yet: it says so
                    # rather than showing shape-key notes as if they sounded
                    self.assertTrue(ex is None or ex.context.concert_key == "Bm")
                else:
                    self.assertEqual(ex.context.concert_key, "Bm")
                    self.assertIn(ex.chord, {"Bm7", "Bm"})
                    self.assertTrue(resp.diagnostics["guitar_tab_present"])

    def test_the_next_two_chords_follow_the_live_song_for_missions_and_backing(self) -> None:
        s = fresh()
        activate_catalog(s)
        activate_composition(s)
        resp, ex = ask("Give me an enclosure over the next two chords.", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(ex.chords, ["Dm", "Gm"])
        self.assertEqual(ex.context.concert_key, "Dm")
        # the span the card opens in Missions is the same span id the Missions page would offer for this song
        from music_coach_ami.exercise_span import open_exercise_in_missions

        result = open_exercise_in_missions(s, resp.diagnostics["open_in_missions"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(s["improv_span_mission"]["example"]["span_chords"], ["Dm", "Gm"])


class TestUnverifiedCharts(unittest.TestCase):
    def test_a_custom_progression_without_chords_is_refused_not_guessed(self) -> None:
        s = fresh()
        activate_catalog(s)
        activate_custom(s, chords=[])
        resp, ex = ask("Give me an enclosure over this chord.", s)
        self.assertIsNone(ex)
        self.assertIn("no chords", resp.direct_answer)
        self.assertNotIn("Bm", resp.direct_answer)

    def test_a_catalog_pick_that_cannot_be_read_is_refused(self) -> None:
        s = fresh()
        activate_catalog(s)
        s["active_catalog_pick_key"] = "Pop\x1fA Song That Is Not In The Catalog"
        s["selected_song"] = {"pick_key": s["active_catalog_pick_key"], "title": "A Song That Is Not In The Catalog"}
        resp, ex = ask("Give me an enclosure over this chord.", s)
        self.assertIsNone(ex)
        self.assertNotIn(ex.chord if ex else "", {"Bm7"})

    def test_a_chord_the_player_names_always_works(self) -> None:
        s = fresh()
        activate_custom(s, chords=[])
        resp, ex = ask("Give me an enclosure targeting the third of G7.", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(ex.chord, "G7")


class TestSectionScopeHonesty(unittest.TestCase):
    def _catalog(self) -> dict:
        s = fresh()
        activate_catalog(s)
        s["home_sections"] = {"Verse 1": list(SOY_VERSE) * 4}
        return s

    def test_over_the_verse_does_not_become_one_chord(self) -> None:
        s = self._catalog()
        resp, ex = ask("Give me an enclosure over the verse.", s)
        self.assertIsNone(ex)
        text = resp.direct_answer
        self.assertIn("Verse 1", text)
        self.assertIn("Bm7", text.replace("♭", "b")) if "Bm7" in text else self.assertIn("Bm", text)
        self.assertIn("repeated 4 times", text)
        self.assertIn("16 chords", text)
        self.assertIn("2 or 3 consecutive chords", text)
        self.assertEqual(resp.notation_abc, "")
        self.assertTrue(any("first two chords of the verse" in step for step in resp.practice_steps))

    def test_a_repeated_loop_is_not_called_the_whole_verse(self) -> None:
        unit, times = collapse_loop(list(SOY_VERSE) * 4)
        self.assertEqual((unit, times), (SOY_VERSE, 4))
        self.assertEqual(collapse_loop(["C", "Am", "F", "G", "C"])[1], 1)
        s = self._catalog()
        resp, _ex = ask("Give me an enclosure over the verse.", s)
        self.assertNotIn("covers the whole verse", resp.direct_answer.lower())

    def test_the_whole_song_is_said_not_truncated(self) -> None:
        s = self._catalog()
        s["home_sections"] = {"Verse 1": list(SOY_VERSE) * 4, "Chorus 1": ["G", "A", "Bm", "Bm"]}
        resp, ex = ask("Give me an enclosure over the whole song.", s)
        self.assertIsNone(ex)
        self.assertIn("whole song", resp.direct_answer)
        self.assertIn("2 or 3 consecutive chords", resp.direct_answer)

    def test_the_offered_two_chord_phrasing_builds_the_verses_first_two_chords(self) -> None:
        s = self._catalog()
        resp, ex = ask("Give me an enclosure over the first two chords of the verse.", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(ex.chords, ["Bm", "Em"])

    def test_one_chord_when_the_player_says_one_chord(self) -> None:
        s = self._catalog()
        resp, ex = ask("Give me an enclosure over the first chord of the verse.", s)
        self.assertIsNotNone(ex, resp.direct_answer[:200])
        self.assertEqual(len(ex.chords), 1)

    def test_existing_supported_scopes_are_unchanged(self) -> None:
        s = self._catalog()
        for q, n in (("Give me an enclosure over this chord.", 1), ("Give me an enclosure over the next two chords.", 2),
                     ("Give me an enclosure over the next three chords.", 3)):
            resp, ex = ask(q, s)
            self.assertIsNotNone(ex, (q, resp.direct_answer[:160]))
            self.assertEqual(len(ex.chords), n, q)


if __name__ == "__main__":
    unittest.main()
