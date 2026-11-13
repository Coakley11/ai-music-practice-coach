"""Chord refinement: widget lifecycle (P1) and musically real proposals (P6)."""

from __future__ import annotations

import unittest

from composition_chord_refinements import (
    CHORD_REFINEMENT_INTENTS,
    functional_label,
    propose_chord_refinement,
    proposal_is_current,
)
from composition_chord_suggestions import symbols_to_entries
from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    section_by_id,
)

PROG = "Cmaj7 Fmaj7 D7 G7"


def _doc(key: str = "C", prog: str = PROG):
    doc = bootstrap_from_vision(genre="Pop", song_idea="Refine", key=key, bpm=100, meter="4/4")
    apply_structure_template(doc, "simple")
    secs = ordered_sections(doc)
    apply_section_chords(doc, str(secs[0]["id"]), parse_chord_paste(prog))
    apply_section_chords(doc, str(secs[1]["id"]), parse_chord_paste("Am F C G"))
    return doc


def _syms(entries):
    return [str(e["chord"]) for e in entries]


def _propose(prog: str, intent: str, key: str = "C", variant: int = 0):
    doc = {"global": {"original_key_center": key}}
    return propose_chord_refinement(
        doc, {"label": "Verse", "id": "s1"}, intent, entries=symbols_to_entries(prog.split()), variant=variant
    )


class TestMoreTensionExample(unittest.TestCase):
    def test_example_changes_and_is_exact(self) -> None:
        p = _propose(PROG, "more_tension")
        self.assertTrue(p["available"])
        self.assertEqual(p["source_symbols"], ["Cmaj7", "Fmaj7", "D7", "G7"])
        self.assertEqual(p["proposed_symbols"], ["Cmaj7", "Fmaj7", "D7", "G7b9"])
        self.assertNotEqual(p["source_symbols"], p["proposed_symbols"])
        self.assertEqual(_syms(p["chords"]), p["proposed_symbols"])
        self.assertEqual(len(p["changes"]), 1)
        ch = p["changes"][0]
        self.assertEqual((ch["index"], ch["before"], ch["after"]), (3, "G7", "G7b9"))
        self.assertEqual(ch["before_roman"], "V7")
        # Explanation only mentions what changed.
        self.assertIn("G7", p["why"])
        self.assertIn("G7b9", p["why"])
        for untouched in ("Cmaj7", "Fmaj7", "D7"):
            self.assertNotIn(untouched, p["why"])

    def test_variants_are_distinct_and_all_differ(self) -> None:
        seen = set()
        first = _propose(PROG, "more_tension")
        n = first["variant_count"]
        self.assertGreaterEqual(n, 4)
        for v in range(n):
            p = _propose(PROG, "more_tension", variant=v)
            self.assertNotEqual(p["proposed_symbols"], p["source_symbols"])
            seen.add(tuple(p["proposed_symbols"]))
        self.assertEqual(len(seen), n)
        self.assertEqual(_propose(PROG, "more_tension", variant=n)["proposed_symbols"], first["proposed_symbols"])

    def test_secondary_dominant_label(self) -> None:
        self.assertEqual(functional_label("D7", "C", "G7"), "V7/V")
        self.assertEqual(functional_label("G7", "C", "Cmaj7"), "V7")
        p = _propose(PROG, "more_tension", variant=1)  # b9 on D7
        self.assertEqual(p["proposed_symbols"], ["Cmaj7", "Fmaj7", "D7b9", "G7"])
        self.assertEqual(p["changes"][0]["before_roman"], "V7/V")
        self.assertIn("V7/V", p["why"])

    def test_tritone_variant_text_matches_music(self) -> None:
        found = {}
        for v in range(_propose(PROG, "more_tension")["variant_count"]):
            p = _propose(PROG, "more_tension", variant=v)
            ch = p["changes"][0]
            if ch["kind"] == "tritone":
                found[ch["index"]] = p
        # Last chord: nothing follows it inside the section, so no half-step claim.
        self.assertEqual(found[3]["proposed_symbols"][3], "Db7")
        self.assertNotIn("half step", found[3]["why"])
        # D7 is followed by G7: Ab7 sits a half step above G, so the claim is true.
        self.assertEqual(found[2]["proposed_symbols"][2], "Ab7")
        self.assertIn("half step above G7", found[2]["why"])

    def test_nothing_editable_returns_none(self) -> None:
        self.assertIsNone(_propose("N.C.", "more_tension"))


class TestAllIntentsRealOrHonest(unittest.TestCase):
    PROGS = {
        "C": [PROG, "Dm7 G7 Cmaj7", "C F G C", "A7 D7 A7 E7", "C"],
        "Am": ["Am F C G", "Am Am Am Am", "Am"],
    }

    def test_every_intent_changes_or_says_no(self) -> None:
        from backing_audio import chord_notes

        for key, progs in self.PROGS.items():
            for prog in progs:
                for intent, _label in CHORD_REFINEMENT_INTENTS:
                    p = _propose(prog, intent, key)
                    ctx = f"{key} {prog} {intent}"
                    self.assertIsNotNone(p, ctx)
                    self.assertTrue(p["why"], ctx)
                    if not p["available"]:
                        self.assertEqual(p["proposed_symbols"], p["source_symbols"], ctx)
                        self.assertEqual(p["changes"], [], ctx)
                        self.assertFalse(p["changed"], ctx)
                        continue
                    self.assertNotEqual(p["proposed_symbols"], p["source_symbols"], ctx)
                    self.assertEqual(len(p["proposed_symbols"]), len(p["source_symbols"]), ctx)
                    self.assertTrue(p["changes"], ctx)
                    for c in p["changes"]:
                        self.assertTrue(chord_notes(c["after"]), ctx)
                        self.assertNotEqual(list(chord_notes(c["before"])), list(chord_notes(c["after"])), ctx)
                        self.assertIn(c["after"], p["why"], ctx)
                    changed_idx = {c["index"] for c in p["changes"]}
                    for i, (a, b) in enumerate(zip(p["source_symbols"], p["proposed_symbols"])):
                        self.assertEqual(a != b, i in changed_idx, ctx)

    def test_known_honest_messages(self) -> None:
        p = _propose("C F G C", "simpler")
        self.assertFalse(p["available"])
        self.assertIn("simple", p["why"].lower())
        p = _propose("Am Am", "darker", "Am")
        self.assertFalse(p["available"])

    def test_ii_v_i_tension_and_resolution(self) -> None:
        p = _propose("Dm7 G7 Cmaj7", "more_tension")
        self.assertEqual(p["proposed_symbols"], ["Dm7", "G7b9", "Cmaj7"])
        self.assertIn("Cmaj7", p["why"])  # names the resolution target
        p = _propose("Dm7 G7 Cmaj7", "more_resolution")
        self.assertFalse(p["available"])  # already resolves; the dominant is not replaced

    def test_blues_and_vamps(self) -> None:
        self.assertEqual(
            _propose("A7 D7 A7 E7", "more_tension", "A")["proposed_symbols"], ["A7", "D7", "A7", "E7b9"]
        )
        p = _propose("Am Am Am Am", "more_tension", "Am")
        self.assertEqual(p["proposed_symbols"], ["Am", "Am", "Am", "Ammaj7"])
        p = _propose("C", "more_tension")
        self.assertEqual(p["proposed_symbols"], ["Csus4"])

    def test_repeat_entries_preserved(self) -> None:
        doc = {"global": {"original_key_center": "C"}}
        ents = [{"chord": "C", "bars": 1}, {"chord": "%", "repeat": True, "bars": 1}, {"chord": "G7", "bars": 1}]
        p = propose_chord_refinement(doc, {"label": "V", "id": "s"}, "more_tension", entries=ents)
        self.assertEqual(p["proposed_symbols"][1], "%")
        self.assertEqual(p["chords"][1].get("repeat"), True)

    def test_does_not_mutate_input(self) -> None:
        doc = _doc()
        sec = ordered_sections(doc)[0]
        before = [dict(c) for c in sec["chords"]]
        propose_chord_refinement(doc, sec, "more_tension")
        self.assertEqual(sec["chords"], before)

    def test_preview_parser_accepts_proposals(self) -> None:
        from composition_preview import generate_preview_wav

        doc = _doc()
        sec = ordered_sections(doc)[0]
        p = propose_chord_refinement(doc, sec, "more_tension")
        wav = generate_preview_wav(doc, section_id=str(sec["id"]), loops=1, chord_override=p["proposed_symbols"])
        self.assertTrue(wav)

    def test_proposal_is_current_guards(self) -> None:
        doc = _doc()
        sec = ordered_sections(doc)[0]
        p = propose_chord_refinement(doc, sec, "more_tension")
        sid = str(sec["id"])
        self.assertTrue(proposal_is_current(p, sid, sec["chords"], "C"))
        self.assertFalse(proposal_is_current(p, "other", sec["chords"], "C"))
        self.assertFalse(proposal_is_current(p, sid, sec["chords"], "D"))
        self.assertFalse(proposal_is_current(p, sid, symbols_to_entries(["Am"]), "C"))


# ---------------------------------------------------------------- AppTest (headless, not a browser)


def _harness() -> None:
    import streamlit as st

    import composition_studio_page as csp
    from composition_document import section_by_id as _sb

    csp._save_doc = lambda _ss, _doc: None  # persistence is out of scope here
    ss = st.session_state
    doc = ss["h_doc"]
    sid = st.selectbox("Section", ss["h_ids"], key="h_section")
    if st.checkbox("Show panel", value=True, key="h_show"):
        csp._render_chord_refinement_panel(ss, doc, sid, _sb(doc, sid))


class TestRefinementPanelLifecycle(unittest.TestCase):
    def _at(self):
        from streamlit.testing.v1 import AppTest

        doc = _doc()
        ids = [str(s["id"]) for s in ordered_sections(doc)]
        at = AppTest.from_function(_harness, default_timeout=60)
        at.session_state["h_doc"] = doc
        at.session_state["h_ids"] = ids
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at, doc, ids

    @staticmethod
    def _btn(at, name: str, sid: str):
        return at.button(key=f"composer_refine_{name}_{sid}")

    @staticmethod
    def _has_card(at) -> bool:
        return any("composer-suggestion-card" in m.value for m in at.markdown)

    def _click(self, at, name: str, sid: str):
        """Click, then run again: AppTest stops a script run at st.rerun(), so the
        second run is the post-rerun render a browser would show."""
        self._btn(at, name, sid).click()
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])

    def _propose(self, at, sid: str, intent: str = "more_tension"):
        at.selectbox(key=f"composer_refine_intent_{sid}").select(intent)
        self._click(at, "propose", sid)

    def test_try_another_does_not_raise_and_cycles(self) -> None:
        at, doc, ids = self._at()
        sid = ids[0]
        self._propose(at, sid)
        self.assertTrue(self._has_card(at))
        cur = at.session_state[f"composer_refine_proposal_{sid}"]
        self.assertEqual(cur["proposed_symbols"], ["Cmaj7", "Fmaj7", "D7", "G7b9"])
        seen = [tuple(cur["proposed_symbols"])]
        for _ in range(cur["variant_count"] + 2):
            self._click(at, "another", sid)
            cur = at.session_state[f"composer_refine_proposal_{sid}"]
            self.assertNotEqual(cur["proposed_symbols"], cur["source_symbols"])
            seen.append(tuple(cur["proposed_symbols"]))
        self.assertGreater(len(set(seen)), 3)
        # the picked intent is untouched by Try another
        self.assertEqual(at.selectbox(key=f"composer_refine_intent_{sid}").value, "more_tension")

    def test_card_highlights_changes(self) -> None:
        at, doc, ids = self._at()
        self._propose(at, ids[0])
        card = next(m.value for m in at.markdown if "composer-suggestion-card" in m.value)
        self.assertIn("G7b9", card)
        self.assertIn("Bar 4", card)
        self.assertIn("V7", card)
        self.assertIn("line-through", card)
        self.assertIn("rgba(99,102,241", card)

    def test_use_this_applies_and_clears(self) -> None:
        at, doc, ids = self._at()
        sid = ids[0]
        self._propose(at, sid)
        self.assertEqual(_syms(section_by_id(doc, sid)["chords"]), ["Cmaj7", "Fmaj7", "D7", "G7"])
        self._click(at, "use", sid)
        self.assertEqual(_syms(section_by_id(doc, sid)["chords"]), ["Cmaj7", "Fmaj7", "D7", "G7b9"])
        self.assertFalse(self._has_card(at))
        self._propose(at, sid)
        cur = at.session_state[f"composer_refine_proposal_{sid}"]
        self.assertEqual(cur["source_symbols"], ["Cmaj7", "Fmaj7", "D7", "G7b9"])
        self.assertNotEqual(cur["proposed_symbols"], cur["source_symbols"])

    def test_dismiss_and_clear_do_not_change_chords(self) -> None:
        at, doc, ids = self._at()
        sid = ids[0]
        self._propose(at, sid)
        self._click(at, "dismiss", sid)
        self.assertFalse(self._has_card(at))
        self._propose(at, sid)
        self._click(at, "clear", sid)
        self.assertFalse(self._has_card(at))
        self.assertEqual(_syms(section_by_id(doc, sid)["chords"]), ["Cmaj7", "Fmaj7", "D7", "G7"])

    def test_phase_navigation_away_and_back(self) -> None:
        at, doc, ids = self._at()
        sid = ids[0]
        self._propose(at, sid)
        at.checkbox(key="h_show").uncheck().run()
        self.assertFalse(at.exception)
        self.assertFalse(self._has_card(at))
        at.checkbox(key="h_show").check().run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertTrue(self._has_card(at))
        self._click(at, "another", sid)

    def test_section_switch_does_not_leak_proposal(self) -> None:
        at, doc, ids = self._at()
        a, b = ids[0], ids[1]
        self._propose(at, a)
        at.selectbox(key="h_section").select(b).run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertFalse(self._has_card(at))
        self._propose(at, b, "darker")
        card_b = next(m.value for m in at.markdown if "composer-suggestion-card" in m.value)
        self.assertNotIn("G7b9", card_b)
        at.selectbox(key="h_section").select(a).run()
        self.assertFalse(at.exception)
        card_a = next(m.value for m in at.markdown if "composer-suggestion-card" in m.value)
        self.assertIn("G7b9", card_a)

    def test_stale_proposal_dropped_when_progression_changes(self) -> None:
        at, doc, ids = self._at()
        sid = ids[0]
        self._propose(at, sid)
        apply_section_chords(doc, sid, parse_chord_paste("Em Am Dm G"))
        at.run()
        self.assertFalse(at.exception)
        self.assertFalse(self._has_card(at))
        self.assertNotIn(f"composer_refine_proposal_{sid}", at.session_state)

    def test_no_change_shows_honest_message_without_use_button(self) -> None:
        at, doc, ids = self._at()
        sid = ids[1]
        apply_section_chords(doc, sid, parse_chord_paste("C F G C"))
        at.selectbox(key="h_section").select(sid).run()
        self._propose(at, sid, "simpler")
        self.assertFalse(self._has_card(at))
        self.assertTrue(any("Already as simple" in i.value for i in at.info))
        self.assertEqual(len([b for b in at.button if b.key == f"composer_refine_use_{sid}"]), 0)


if __name__ == "__main__":
    unittest.main()
