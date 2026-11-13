"""AppTest coverage for the Custom Progressions "Suggested Next Chord" area (headless, no browser)."""

from __future__ import annotations

import copy
import unittest

from streamlit.testing.v1 import AppTest


def _page() -> None:
    from cpl_page_ui import render_custom_progression_lab_page

    render_custom_progression_lab_page()


def _run() -> AppTest:
    at = AppTest.from_function(_page, default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def _use(at: AppTest, section: str = "Verse"):
    return at.button(key=f"cpl_pick_suggest_use_{section}")


def _chords(at: AppTest, section: str = "Verse") -> list[str]:
    from custom_progression_lab import CPL_ACTIVE_KEY

    active = at.session_state[CPL_ACTIVE_KEY]
    return [str(e.get("chord")) for e in (active.get("original_sections") or {}).get(section) or []]


def _pending(at: AppTest, section: str = "Verse"):
    key = f"cpl_pending_chord_{section}"
    return at.session_state[key] if key in at.session_state else None


def _add(at: AppTest, bars: str = "1", section: str = "Verse") -> None:
    at.button(key=f"cpl_b{bars}_{section}").click().run()
    assert not at.exception, at.exception


class TestSuggestedNextChordArea(unittest.TestCase):
    def test_area_shows_a_reasoned_suggestion_for_an_empty_section(self) -> None:
        at = _run()
        self.assertEqual(_use(at).label, "Use C")
        self.assertIn("🎼 Suggested Next Chord", [e.label for e in at.expander])
        self.assertTrue(any("establishes C major" in str(c.value) for c in at.caption))
        self.assertEqual(_chords(at), [])

    def test_use_sets_a_pending_chord_without_touching_the_section_or_saved_data(self) -> None:
        from custom_progression_lab import CPL_SAVED_KEY, cpl_get_pending_chord

        at = _run()
        saved_before = copy.deepcopy(at.session_state[CPL_SAVED_KEY]) if CPL_SAVED_KEY in at.session_state else None
        _use(at).click().run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(_pending(at), "C")
        self.assertEqual(_chords(at), [], "no duration chosen yet: nothing committed, nothing guessed")
        self.assertTrue(_use(at).disabled, "cannot overwrite the pending chord")
        after = copy.deepcopy(at.session_state[CPL_SAVED_KEY]) if CPL_SAVED_KEY in at.session_state else None
        self.assertEqual(saved_before, after)

    def test_choosing_a_duration_commits_then_the_next_suggestion_follows_the_progression(self) -> None:
        at = _run()
        _use(at).click().run()
        _add(at, "1")
        self.assertEqual(_chords(at), ["C"])
        self.assertFalse(_use(at).disabled)
        first_next = _use(at).label
        self.assertNotEqual(first_next, "Use C")
        _use(at).click().run()
        _add(at, "2")
        self.assertEqual(_chords(at)[0], "C", "existing chord is never overwritten")
        self.assertEqual(len(_chords(at)), 2)
        self.assertEqual(_chords(at)[1], first_next.removeprefix("Use "))

    def test_repeated_acceptance_builds_a_whole_progression(self) -> None:
        at = _run()
        seen: list[str] = []
        for _ in range(4):
            label = _use(at).label.removeprefix("Use ")
            seen.append(label)
            _use(at).click().run()
            _add(at, "1")
            self.assertFalse(at.exception, at.exception)
        self.assertEqual(_chords(at), seen)
        self.assertEqual(len(seen), 4)

    def test_alternative_buttons_also_become_pending(self) -> None:
        at = _run()
        alt = at.button(key="cpl_pick_suggest_alt_Verse_0")
        name = alt.label
        alt.click().run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(_pending(at), name)

    def test_pending_chord_is_shown_in_the_area_and_suggestion_considers_it(self) -> None:
        at = _run()
        _use(at).click().run()
        self.assertTrue(any("Pending chord" in str(c.value) for c in at.caption))

    def test_switching_sections_keeps_each_sections_context(self) -> None:
        at = _run()
        for _ in range(3):
            _use(at).click().run()
            _add(at, "1")
        verse = _chords(at)
        at.selectbox(key="cpl_edit_section").select("Chorus").run()
        self.assertFalse(at.exception, at.exception)
        chorus_use = _use(at, "Chorus")
        self.assertTrue(chorus_use.label.startswith("Use "))
        self.assertEqual(_chords(at, "Chorus"), [])
        chorus_use.click().run()
        _add(at, "1", "Chorus")
        self.assertEqual(_chords(at, "Verse"), verse, "other section untouched")
        self.assertEqual(len(_chords(at, "Chorus")), 1)
        at.selectbox(key="cpl_edit_section").select("Verse").run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(_chords(at, "Verse"), verse)

    def test_style_changes_the_suggestion_text(self) -> None:
        at = AppTest.from_function(_page, default_timeout=120)
        at.run()
        at.session_state["cpl_style_early"] = "Jazz"
        at.run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(_use(at).label, "Use Cmaj7")


if __name__ == "__main__":
    unittest.main()
