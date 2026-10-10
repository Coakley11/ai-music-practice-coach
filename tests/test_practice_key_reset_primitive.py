"""The source-switch reset primitive must not destroy an explicit override.

``reset_practice_key_to_original_on_source_switch`` is the shared helper that
performs the "new source → Practice = Original/Home" reset. It has five callers,
and a store audit showed four separate destructive paths converging on the
``clear_practice_concert_key`` inside it. The durable-state invariant therefore
lives here rather than in a guard per caller.

Scope held deliberately narrow:
  * only an explicit *catalog* override is protected;
  * fixed-practice-key mode still supersedes an override on purpose (it calls
    ``clear_practice_key_user_override`` itself);
  * custom / composition / creative picks keep their existing semantics.
"""

from __future__ import annotations

import unittest

from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    catalog_pick_has_user_practice_key_override,
    get_practice_concert_key,
    mark_practice_key_user_override,
    reset_practice_key_to_original_on_source_switch,
    set_practice_concert_key,
)

IPANEMA = "Jazz\x1fThe Girl from Ipanema — Antonio Carlos Jobim"
SAY = "Pop\x1fSay — John Mayer"
CUSTOM_PICK = "custom::trial-song-uuid"
COMPOSITION_PICK = "composition::my-composition-uuid"
CREATIVE_PICK = "creative::entry_style_jam"


def _reset(session: dict, pick: str, original: str) -> str:
    return reset_practice_key_to_original_on_source_switch(
        session, pick_key=pick, original_key=original
    )


class TestOverriddenCatalogPickIsProtected(unittest.TestCase):
    def test_saved_override_survives_and_is_returned(self) -> None:
        session: dict = {}
        set_practice_concert_key(session, "G", pick_key=IPANEMA)
        mark_practice_key_user_override(session, IPANEMA)

        returned = _reset(session, IPANEMA, "F")

        self.assertEqual(returned, "G")
        self.assertEqual(get_practice_concert_key(session, IPANEMA, default=""), "G")
        self.assertTrue(catalog_pick_has_user_practice_key_override(session, IPANEMA))

    def test_no_clear_occurs_for_an_overridden_pick(self) -> None:
        session: dict = {}
        set_practice_concert_key(session, "G", pick_key=IPANEMA)
        mark_practice_key_user_override(session, IPANEMA)
        before = dict(session.get(PRACTICE_KEY_BY_SOURCE_KEY) or {})

        _reset(session, IPANEMA, "F")

        self.assertEqual(dict(session.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}), before)

    def test_live_display_fields_follow_the_saved_override(self) -> None:
        session: dict = {}
        set_practice_concert_key(session, "G", pick_key=IPANEMA)
        mark_practice_key_user_override(session, IPANEMA)

        _reset(session, IPANEMA, "F")

        # The switch must not leave the UI asserting Original.
        self.assertNotEqual(session.get("concert_key"), "F")
        self.assertIn("G", {session.get("concert_key"), session.get("display_key"),
                            session.get("_pending_display_key")})


class TestNonOverriddenCatalogPickStillResets(unittest.TestCase):
    def test_transient_value_is_cleared_and_original_returned(self) -> None:
        session: dict = {}
        set_practice_concert_key(session, "B", pick_key=SAY)
        self.assertFalse(catalog_pick_has_user_practice_key_override(session, SAY))

        returned = _reset(session, SAY, "G")

        self.assertEqual(returned, "G")
        self.assertEqual(get_practice_concert_key(session, SAY, default=""), "")

    def test_pick_with_no_saved_value_returns_original(self) -> None:
        session: dict = {}
        self.assertEqual(_reset(session, SAY, "G"), "G")


class TestOtherSourceKindsUnchanged(unittest.TestCase):
    """Custom / Composition / Creative keep existing reset semantics."""

    def test_custom_pick_still_resets_to_original(self) -> None:
        session: dict = {}
        set_practice_concert_key(session, "D", pick_key=CUSTOM_PICK)
        mark_practice_key_user_override(session, CUSTOM_PICK)

        returned = _reset(session, CUSTOM_PICK, "C")

        # Protection is catalog-scoped: custom routes through its own semantics.
        self.assertEqual(returned, "C")

    def test_composition_pick_still_resets_to_original(self) -> None:
        session: dict = {}
        set_practice_concert_key(session, "A", pick_key=COMPOSITION_PICK)
        mark_practice_key_user_override(session, COMPOSITION_PICK)

        self.assertEqual(_reset(session, COMPOSITION_PICK, "C"), "C")

    def test_creative_pick_still_resets_to_original(self) -> None:
        session: dict = {}
        set_practice_concert_key(session, "Eb", pick_key=CREATIVE_PICK)
        mark_practice_key_user_override(session, CREATIVE_PICK)

        self.assertEqual(_reset(session, CREATIVE_PICK, "F"), "F")


class TestFixedFamilyModeStillSupersedes(unittest.TestCase):
    def test_fixed_mode_branch_is_untouched_by_the_guard(self) -> None:
        """Fixed-family mode drops the override on purpose; keep it that way."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1] / "songs" / "practice_key_state.py"
        ).read_text(encoding="utf-8")
        body = source.split("def reset_practice_key_to_original_on_source_switch", 1)[1]
        # The fixed-family branch ends by returning its family token.
        fixed_branch, _, standard_branch = body.partition("            return target\n")
        # The deliberate override-drop stays in the fixed-family branch.
        self.assertIn("clear_practice_key_user_override", fixed_branch)
        # The guard lives in the standard branch only.
        self.assertIn("catalog_pick_has_user_practice_key_override", standard_branch)
        self.assertNotIn("catalog_pick_has_user_practice_key_override", fixed_branch)


if __name__ == "__main__":
    unittest.main()
