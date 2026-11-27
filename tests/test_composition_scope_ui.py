"""The editing-scope controls in Composition Studio.

The scope LOGIC is covered by test_composition_melody_passes. What is checked here is that the
page is wired to it, and wired in the ways that matter musically: the scope is chosen before
the edit and shown prominently, every refinement goes through the scoped path rather than the
old whole-melody one, and nothing on this panel writes the accepted melody.

These are source-level contracts. A render function needs a Streamlit script run, so the
browser round is what confirms how it looks; these say it is still connected.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from composition_melody_passes import SCOPE_BARS, SCOPE_ENTIRE, SCOPE_LABELS, SCOPE_ONE_PASS
from composition_studio_page import (
    _render_active_melody_inplace_tools,
    _render_phase_melody,
)

TOOLS = inspect.getsource(_render_active_melody_inplace_tools)


class TestTheScopeIsChosenBeforeTheEdit(unittest.TestCase):
    def test_the_selector_offers_all_three_scopes(self) -> None:
        self.assertIn('"Editing scope"', TOOLS)
        for scope in ("SCOPE_ENTIRE", "SCOPE_ONE_PASS", "SCOPE_BARS"):
            with self.subTest(scope=scope):
                self.assertIn(scope, TOOLS)

    def test_entire_section_is_the_default(self) -> None:
        self.assertIn("_scope_options = [SCOPE_ENTIRE]", TOOLS)
        self.assertIn("session_state[_scope_key] = SCOPE_ENTIRE", TOOLS)

    def test_one_pass_is_only_offered_when_the_section_repeats(self) -> None:
        self.assertIn("([SCOPE_ONE_PASS] if _passes > 1 else [])", TOOLS)

    def test_a_stale_scope_is_reseeded_before_the_widget_is_drawn(self) -> None:
        """Handing Streamlit a value its options no longer contain raises."""
        reseed = TOOLS.index("if session_state.get(_scope_key) not in _scope_options")
        widget = TOOLS.index('st.radio(\n        "Editing scope"')
        self.assertLess(reseed, widget)

    def test_the_scope_is_shown_prominently_not_as_a_caption(self) -> None:
        block = TOOLS[TOOLS.index('"Editing scope"') :]
        shown = block.index("scope_caption(scope, pass_index, _passes, bars)")
        self.assertIn("st.info(", block[:shown])

    def test_a_bar_range_is_selectable_in_bars(self) -> None:
        self.assertIn('"From bar"', TOOLS)
        self.assertIn('"To bar"', TOOLS)
        self.assertIn("bars = (int(_from), int(_to))", TOOLS)

    def test_the_pass_picker_names_the_pass_and_the_total(self) -> None:
        self.assertIn('f"Pass {i + 1} of {_passes}"', TOOLS)


class TestEveryRefinementGoesThroughTheScope(unittest.TestCase):
    def test_both_refinement_rows_call_the_scoped_path(self) -> None:
        self.assertEqual(TOOLS.count("_propose_scoped(rid, label)"), 2)

    def test_the_old_unscoped_call_is_gone(self) -> None:
        """A refinement that ignored the scope would silently edit the whole melody."""
        body = TOOLS[TOOLS.index("def _propose_scoped") + 40 :]
        self.assertNotIn("propose_melody_refinement(before, rid", body)

    def test_the_scoped_path_uses_apply_to_scope_with_all_four_inputs(self) -> None:
        for arg in ("scope=scope", "pass_index=pass_index", "bars=bars", "meter=_meter"):
            with self.subTest(arg=arg):
                self.assertIn(arg, TOOLS)

    def test_an_unchanged_refinement_says_so_instead_of_proposing(self) -> None:
        self.assertIn('if not said["changed"] or not after:', TOOLS)


class TestTheAcceptedMelodyIsNotTouched(unittest.TestCase):
    """Requirement: a proposal must never replace the accepted melody before Accept."""

    def test_the_scope_panel_writes_only_the_proposal_slot(self) -> None:
        panel = TOOLS[TOOLS.index("What an edit is allowed to touch") : TOOLS.index(
            "proposal = session_state.get(_refine_proposal_key(active_id))"
        )]
        self.assertIn("session_state[_refine_proposal_key(active_id)] = payload", panel)
        for forbidden in ("apply_melody_events(", "accept_full_melody(", "_save_doc("):
            with self.subTest(call=forbidden):
                self.assertNotIn(forbidden, panel)

    def test_the_proposal_records_which_scope_made_it(self) -> None:
        self.assertIn('"scope": scope,', TOOLS)
        self.assertIn('"scope_note": scope_caption(', TOOLS)

    def test_the_proposal_shows_its_scope_to_the_musician(self) -> None:
        self.assertIn('proposal.get("scope_note")', TOOLS)


class TestWorkingPassByPass(unittest.TestCase):
    def test_the_tools_appear_only_for_a_repeating_section(self) -> None:
        self.assertIn("if _passes > 1:", TOOLS)
        self.assertIn("Work pass by pass", TOOLS)

    def test_copy_names_a_source_and_explicit_targets(self) -> None:
        self.assertIn('"Copy this pass"', TOOLS)
        self.assertIn("st.multiselect(", TOOLS)

    def test_an_exact_repeat_is_offered_as_a_choice(self) -> None:
        """Repeating a phrase unchanged is a musical decision, not an oversight."""
        self.assertIn('"Exact copy"', TOOLS)
        self.assertIn('"Repeat with a variation"', TOOLS)

    def test_restoring_one_pass_is_available(self) -> None:
        self.assertIn("restore_pass(_current, _accepted, pass_index)", TOOLS)

    def test_restore_is_scoped_to_one_pass(self) -> None:
        """Restoring "this pass" with the whole section selected would be a trap."""
        self.assertIn("disabled=scope != SCOPE_ONE_PASS", TOOLS)

    def test_a_copy_that_changes_nothing_is_refused(self) -> None:
        self.assertIn("That copy would not change anything.", TOOLS)

    def test_the_copy_lands_as_a_proposal(self) -> None:
        # Bounded at the proposal block: everything after it is the Accept path, which is
        # SUPPOSED to write the melody.
        panel = TOOLS[
            TOOLS.index("Work pass by pass") : TOOLS.index(
                "proposal = session_state.get(_refine_proposal_key(active_id))"
            )
        ]
        self.assertIn("_scoped_proposal(_after,", panel)
        self.assertNotIn("apply_melody_events(", panel)

    def test_accept_is_still_the_only_thing_that_writes_the_melody(self) -> None:
        after = TOOLS[
            TOOLS.index("proposal = session_state.get(_refine_proposal_key(active_id))") :
        ]
        self.assertIn("Accept refinement", after)
        self.assertIn("apply_melody_events(", after)


class TestHarmonyAdaptationIsOptionalAndExplained(unittest.TestCase):
    def test_it_can_be_turned_off(self) -> None:
        self.assertIn("Adapt copied notes to the chords they land on", TOOLS)
        self.assertIn("fit_to_chords=bool(_adapt)", TOOLS)

    def test_the_help_says_what_is_left_alone(self) -> None:
        """The musician must know their chromatic writing is safe."""
        low = TOOLS.lower()
        for phrase in ("chromatic", "suspension", "tension"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, low)

    def test_each_adaptation_is_reported(self) -> None:
        self.assertTrue('proposal.get("harmony_changes")' in TOOLS, "changes are not read")
        self.assertTrue("note(s) adapted to the chords" in TOOLS, "changes are not shown")

    def test_every_change_is_listed_not_just_the_first_few(self) -> None:
        """A pitch change the musician did not see is one they did not agree to."""
        self.assertTrue("for _chg in _adapted:" in TOOLS, "the list is not iterated in full")
        self.assertFalse(
            'proposal.get("harmony_changes") or [])[:' in TOOLS, "the disclosure is truncated"
        )

    def test_the_changes_are_disclosed_before_accept(self) -> None:
        disclosed = TOOLS.index("note(s) adapted to the chords")
        accept = TOOLS.index("Accept refinement")
        self.assertLess(disclosed, accept, "Accept appears above the list of pitch changes")

    def test_the_help_does_not_call_an_out_of_key_note_a_mistake(self) -> None:
        """Outside the chord and the key is not the same as wrong."""
        low = TOOLS.lower()
        self.assertFalse("heard as a mistake" in low, "the help still calls the note a mistake")
        self.assertTrue("stand out" in low)

    def test_turning_adaptation_off_is_offered_in_the_help(self) -> None:
        self.assertTrue("repeat the phrase exactly as it is" in TOOLS)


class TestTruncationIsDistinguishedFromAPhraseEnding(unittest.TestCase):
    def test_the_panel_consults_the_coverage_report(self) -> None:
        self.assertIn("coverage_report(_events_now, _flat_chords, meter=_meter)", TOOLS)

    def test_only_a_truncated_melody_is_mentioned_at_all(self) -> None:
        self.assertTrue('_cov.get("verdict") == "truncated"' in TOOLS)
        self.assertFalse('"intended_ending"' in TOOLS, "a phrase ending is being commented on")

    def test_it_is_offered_as_an_observation_not_a_warning(self) -> None:
        """A long ending held open on purpose looks identical from here."""
        block = TOOLS[TOOLS.index('_cov.get("verdict") == "truncated"') :][:700]
        self.assertTrue("st.info(" in block, "truncation is still raised as a warning")
        self.assertFalse("st.warning(" in block)
        self.assertTrue("nothing needs doing" in block)

    def test_the_panel_never_repairs_a_truncated_melody(self) -> None:
        """Diagnosis only: no filling, no lengthening, no writing the melody."""
        block = TOOLS[TOOLS.index('_cov.get("verdict") == "truncated"') :][:700]
        for forbidden in ("apply_melody_events(", "_hold_last_note_to_span", "_fill_to_span"):
            with self.subTest(call=forbidden):
                self.assertFalse(forbidden in block)


class TestTheRelaxedAssertionsStillBite(unittest.TestCase):
    """The three adjusted tests must still fail if the panel order regresses.

    Dropping the leading ``**`` from a heading literal made those tests tolerant of the Melody
    glyph. That is only acceptable if they still catch the thing they were written for, so the
    same check is run here against a deliberately reordered source.
    """

    HEADINGS = (
        "Melody Feel & Notes**",
        "AI Melody Suggestions**",
        "Shape / refine active melody**",
    )

    def test_each_relaxed_heading_is_still_found_exactly_once(self) -> None:
        phase = inspect.getsource(_render_phase_melody)
        for heading in ("Melody Feel & Notes**", "AI Melody Suggestions**"):
            with self.subTest(heading=heading):
                self.assertEqual(phase.count(heading), 1, "the index() call is ambiguous")
        self.assertEqual(TOOLS.count("Shape / refine active melody**"), 1)

    def test_the_real_order_holds(self) -> None:
        phase = inspect.getsource(_render_phase_melody)
        feel_i = phase.index("Melody Feel & Notes**")
        ai_i = phase.index("AI Melody Suggestions**")
        self.assertLess(feel_i, ai_i)
        self.assertLess(phase.index("_render_hum_sing_panel"), ai_i)

    def test_the_check_fails_on_a_reordered_source(self) -> None:
        """Proof the relaxed literal still validates order rather than merely existing."""
        phase = inspect.getsource(_render_phase_melody)
        swapped = phase.replace("Melody Feel & Notes**", "@@FEEL@@").replace(
            "AI Melody Suggestions**", "Melody Feel & Notes**"
        ).replace("@@FEEL@@", "AI Melody Suggestions**")
        self.assertGreater(
            swapped.index("Melody Feel & Notes**"),
            swapped.index("AI Melody Suggestions**"),
            "swapping the headings did not change the order the assertion reads",
        )

    def test_the_glyph_is_what_made_the_relaxation_necessary(self) -> None:
        """The headings carry the shared glyph, which is why the old literal stopped matching."""
        self.assertIn('f"**{_melody_icon()} Shape / refine active melody**"', TOOLS)


class TestScopeLabelsAreReadable(unittest.TestCase):
    def test_every_scope_has_a_label_the_page_can_show(self) -> None:
        for scope in (SCOPE_ENTIRE, SCOPE_ONE_PASS, SCOPE_BARS):
            with self.subTest(scope=scope):
                self.assertTrue(SCOPE_LABELS[scope])
                self.assertNotIn("_", SCOPE_LABELS[scope])


if __name__ == "__main__":
    unittest.main()
