"""R11: Practice-Key lifecycle across the global source-activation boundary.

Two persistence scopes, per human-approved product rule:

A. While a source stays globally active, an explicit Practice-Key change
   persists -- across Creative tabs, refresh and ordinary reruns, and across a
   temporary Creative/SBI preview.

B. An explicit GLOBAL source activation starts that source fresh at its
   Original Key. A Practice-Key experiment from a previous activation session
   must not come back.

Navigation, refresh, Mission Backing round trips and temporary previews are
NOT activations and must not reset anything. A reboot is not an activation
either; the reboot tests in the sibling suites continue to assert that the
active session restores its saved Practice Key.

The canonical boundary is ``songs.state.activate_active_song_by_pick_key``
(documented as the canonical activation entry), which dispatches to
``activate_custom_by_pick_key`` / ``activate_composition_by_pick_key`` /
``apply_pick_key``; each reaches
``reset_practice_key_to_original_on_source_switch``, whose own contract already
reads "Practice = Original/Home for the new song/source (clears any previously
saved Practice Key for pick_key so hydration cannot restore a modified key
after leaving and returning). Same-source refresh/navigation must NOT call
this."

Defect fixed alongside these: the sidebar Practice-Key token fell back to a
hardcoded C on surfaces where ``catalog_song_should_own_sidebar_practice_key``
is False -- Deep Harmony, Entry & Jam, and an unset Creative tab -- so the
sidebar read C while the chord map was already projected to A (Perfect) or Eb
(My Composition).
"""

from __future__ import annotations

import unittest

from tests.test_r11_key_convergence_and_index import _Base, _FakeSt

PERFECT = ("Pop", "Perfect — Ed Sheeran")

ALL_CREATIVE_TABS = (
    "Missions",
    "Live Coach",
    "Harmony Map",
    "Deep Harmony",
    "Phrase / Motif",
    "Entry & Jam",
)


class _ActBase(_Base):
    """Shared assertions for "every surface agrees"."""

    def sidebar_token(self, session: dict) -> str:
        from sidebar_key_identity import resolve_sidebar_key_identity

        return str(resolve_sidebar_key_identity(session).selector_token or "")

    def assert_converged(
        self, session: dict, pick: str, original: str, practice: str, label: str
    ) -> None:
        """Original, saved Practice Key, sidebar and chord map must agree."""
        self.assertEqual(
            self.original_key(session), original, f"{label}: Original Key"
        )
        self.assertEqual(
            self.saved_practice(session, pick), practice, f"{label}: saved Practice Key"
        )
        self.assertEqual(
            self.root_of(self.sidebar_token(session)), self.root_of(practice),
            f"{label}: sidebar showed {self.sidebar_token(session)!r}, expected "
            f"{practice!r}",
        )
        self.assert_map_in_key(session, practice, label)

    def assert_converged_on_every_tab(
        self, session: dict, pick: str, original: str, practice: str
    ) -> None:
        for tab in ALL_CREATIVE_TABS:
            self.open_tab(session, tab)
            self.assert_converged(session, pick, original, practice, tab)


class TestCatalogActivationResetsPracticeKey(_ActBase):
    """ACTKEY1-ACTKEY7."""

    def test_actkey1_activation_starts_at_original(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.assertEqual(self.original_key(session), "G")
        self.assert_map_in_key(session, "G", "ACTKEY1")

    def test_actkey2_explicit_change_takes_effect_immediately(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        self.assert_converged(session, pick, "G", "A", "ACTKEY2")

    def test_actkey3_every_creative_page_stays_at_a(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        self.enter_creative(session)
        self.assert_converged_on_every_tab(session, pick, "G", "A")

    def test_actkey4_refresh_on_the_same_source_keeps_a(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        self.enter_creative(session)
        for _ in range(3):
            self.converge(session)
            self.sidebar_token(session)
        self.assert_converged(session, pick, "G", "A", "ACTKEY4")

    def test_actkey5_temporary_preview_neither_resets_nor_contaminates(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        self.enter_creative(session)
        self.load_custom(session)
        self.assertEqual(self.preview_custom(session), "Custom progression")

        self.assertEqual(
            self.owner(session), "catalog",
            "a preview is not an activation",
        )
        self.assertEqual(self.original_key(session), "G")
        self.assertEqual(self.saved_practice(session, pick), "A")

        self.goto(session, "practice")
        self.assert_converged(
            session, pick, "G", "A",
            "ACTKEY5 after leaving the preview (must not reset to G)",
        )

    def test_actkey6_global_round_trip_resets_to_original(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        self.assertEqual(self.saved_practice(session, pick), "A")

        # A real global activation of another source, then back.
        self.activate_custom(session, chords=("C", "Am", "F", "G"))
        self.converge(session)
        pick2 = self.activate_catalog(session, *PERFECT)
        self.converge(session)

        self.assertEqual(self.original_key(session), "G")
        self.assertNotEqual(
            self.saved_practice(session, pick2), "A",
            "the A experiment from the previous activation session came back",
        )
        self.assert_map_in_key(session, "G", "ACTKEY6 after reactivation")
        self.assertEqual(self.root_of(self.sidebar_token(session)), self.root_of("G"))

    def _radio_back_to_catalog(self, session: dict) -> None:
        """The musician's own path: Songs page source radio -> Song Selection.

        In the live app this reactivates the remembered catalog song by itself
        (its search result then renders disabled), so the radio, not a search
        click, is the activation.
        """
        from songs.music_source import on_song_picker_source_change

        session["song_picker_active_source"] = "Song Selection (catalog song)"
        on_song_picker_source_change(
            _FakeSt(session),
            song_picker_catalog=self.picker,
            song_library=self.library,
            invalidate_backing=lambda _s: None,
            in_callback=True,
        )

    def test_actkey6b_radio_return_resets_even_an_explicit_override(self) -> None:
        """Live S6b: Perfect came back in A after Custom -> Song Selection radio.

        The live sidebar marks an explicit Practice-Key choice as a user override;
        the snapshot restore kept that override across the global switch.
        """
        from songs.practice_key_state import mark_practice_key_user_override

        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        mark_practice_key_user_override(session, pick)
        self.assertEqual(self.saved_practice(session, pick), "A")

        self.activate_custom(session, chords=("C", "Am", "F", "G"))
        self.converge(session)
        self.assertEqual(self.owner(session), "custom")
        self._radio_back_to_catalog(session)
        self.converge(session)

        self.assertEqual(self.owner(session), "catalog")
        self.assertEqual(self.original_key(session), "G")
        self.assertNotEqual(
            self.saved_practice(session, pick), "A",
            "the A override from the previous activation came back",
        )
        self.assertEqual(self.root_of(self.sidebar_token(session)), self.root_of("G"))
        self.assert_map_in_key(session, "G", "ACTKEY6b after radio reactivation")

    def test_actkey6c_override_survives_when_no_source_switch_happens(self) -> None:
        """Scope guard: the same override still survives navigation and refresh."""
        from songs.practice_key_state import mark_practice_key_user_override

        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        mark_practice_key_user_override(session, pick)
        self.enter_creative(session)
        self.goto(session, "practice")
        for _ in range(2):
            self.converge(session)
        self.assert_converged(session, pick, "G", "A", "ACTKEY6c")

    def test_actkey7_a_fresh_change_after_reactivation_sticks(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        self.activate_custom(session, chords=("C", "Am", "F", "G"))
        self.converge(session)
        pick2 = self.activate_catalog(session, *PERFECT)
        self.converge(session)

        self.set_practice(session, pick2, "F")
        self.enter_creative(session)
        self.assert_converged_on_every_tab(session, pick2, "G", "F")


class TestCompositionActivationResetsPracticeKey(_ActBase):
    """ACTKEY8-ACTKEY13."""

    def _composition(self):
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        pick, _doc = self.activate_composition(session)
        self.converge(session)
        return session, pick

    def test_actkey8_activation_starts_at_original_c(self) -> None:
        session, pick = self._composition()
        self.assert_converged(session, pick, "C", "C", "ACTKEY8")

    def test_actkey9_c_to_d(self) -> None:
        session, pick = self._composition()
        self.enter_creative(session)
        self.set_practice(session, pick, "D")
        self.assert_converged(session, pick, "C", "D", "ACTKEY9")

    def test_actkey10_d_to_eb_immediately(self) -> None:
        session, pick = self._composition()
        self.enter_creative(session)
        self.set_practice(session, pick, "D")
        self.set_practice(session, pick, "Eb")
        self.assert_converged(session, pick, "C", "Eb", "ACTKEY10")

    def test_actkey11_refresh_keeps_eb(self) -> None:
        session, pick = self._composition()
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        for _ in range(3):
            self.converge(session)
            self.sidebar_token(session)
        self.assert_converged(session, pick, "C", "Eb", "ACTKEY11")

    def test_actkey12_every_creative_page_stays_at_eb(self) -> None:
        session, pick = self._composition()
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        self.assert_converged_on_every_tab(session, pick, "C", "Eb")

    def test_actkey13_global_round_trip_resets_to_original_c(self) -> None:
        session, pick = self._composition()
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        self.assertEqual(self.saved_practice(session, pick), "Eb")

        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        pick2, _doc = self.activate_composition(session)
        self.converge(session)

        self.assertEqual(self.original_key(session), "C")
        self.assertNotEqual(
            self.saved_practice(session, pick2), "Eb",
            "the Eb experiment revived after an explicit reactivation",
        )
        self.assert_map_in_key(session, "C", "ACTKEY13 after reactivation")

    def test_actkey13_catalog_material_does_not_linger_as_composition(self) -> None:
        """The reverse direction of the same boundary."""
        session, pick = self._composition()
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        for tab in ALL_CREATIVE_TABS:
            self.open_tab(session, tab)

        pick2 = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.assertEqual(self.original_key(session), "G")
        self.assert_map_in_key(
            session, "G", "Perfect must not stay projected in the Composition's Eb"
        )
        del pick2


class TestCustomActivationResetsPracticeKey(_ActBase):
    """ACTKEY14-ACTKEY16."""

    def test_actkey14_and_15_change_persists_while_custom_stays_active(self) -> None:
        session = self.new_session()
        pick = self.activate_custom(session, chords=("C", "Am", "F", "G"))
        self.converge(session)
        self.assert_converged(session, pick, "C", "C", "ACTKEY14 activation")

        self.enter_creative(session)
        self.set_practice(session, pick, "D")
        self.assert_converged(session, pick, "C", "D", "ACTKEY14 after C->D")

        for _ in range(2):
            self.converge(session)
        self.assert_converged(session, pick, "C", "D", "ACTKEY15 refresh")
        self.assert_converged_on_every_tab(session, pick, "C", "D")

    def test_actkey16_global_round_trip_resets_to_original_c(self) -> None:
        session = self.new_session()
        pick = self.activate_custom(session, chords=("C", "Am", "F", "G"))
        self.converge(session)
        self.enter_creative(session)
        self.set_practice(session, pick, "D")
        self.assertEqual(self.saved_practice(session, pick), "D")

        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        pick2 = self.activate_custom(session, chords=("C", "Am", "F", "G"))
        self.converge(session)

        self.assertEqual(self.original_key(session), "C")
        self.assertNotEqual(
            self.saved_practice(session, pick2), "D",
            "the D experiment revived after an explicit reactivation",
        )
        self.assert_map_in_key(session, "C", "ACTKEY16 after reactivation")


class TestOriginalKeyIsImmutableSourceMetadata(_ActBase):
    """Original Key is never derived from a Practice, preview or display key."""

    def test_perfect_original_stays_g_through_everything(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)

        self.set_practice(session, pick, "A")
        self.assertEqual(self.original_key(session), "G", "after Practice A")

        self.enter_creative(session)
        self.load_custom(session)
        self.preview_custom(session)
        self.assertEqual(
            self.original_key(session), "G",
            "Custom's Original C leaked into Perfect during the preview",
        )
        self.goto(session, "creative")
        for tab in ALL_CREATIVE_TABS:
            self.open_tab(session, tab)
            self.assertEqual(self.original_key(session), "G", f"{tab}")

        self.set_practice(session, pick, "F")
        self.assertEqual(self.original_key(session), "G", "after Practice F")
        self.assertNotEqual(self.original_key(session), "C")

    def test_composition_original_stays_c(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        pick, _doc = self.activate_composition(session)
        self.converge(session)
        self.enter_creative(session)
        for key in ("D", "Eb"):
            self.set_practice(session, pick, key)
            self.assertEqual(self.original_key(session), "C", f"after Practice {key}")
        self.load_custom(session)
        self.preview_custom(session)
        self.assertEqual(self.original_key(session), "C")


class TestSidebarAgreesOnEverySurface(_ActBase):
    """The reported sidebar divergence, pinned per surface.

    ``catalog_song_should_own_sidebar_practice_key`` is False on Deep Harmony,
    Entry & Jam and an unset tab, which dropped the sidebar to a hardcoded C.
    """

    def test_catalog_sidebar_matches_on_every_tab_including_deep_harmony(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        self.enter_creative(session)
        for tab in ALL_CREATIVE_TABS:
            self.open_tab(session, tab)
            self.assertEqual(
                self.root_of(self.sidebar_token(session)), self.root_of("A"),
                f"{tab}: sidebar {self.sidebar_token(session)!r} != A",
            )

    def test_composition_sidebar_matches_with_no_tab_selected(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        pick, _doc = self.activate_composition(session)
        self.converge(session)
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        session.pop("improv_intelligence_tab", None)
        self.assertEqual(
            self.root_of(self.sidebar_token(session)), self.root_of("Eb"),
            f"sidebar {self.sidebar_token(session)!r} != Eb with no tab selected",
        )

    def test_sidebar_never_invents_c_for_an_owning_source(self) -> None:
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.set_practice(session, pick, "A")
        self.enter_creative(session)
        self.open_tab(session, "Deep Harmony")
        self.assertNotEqual(
            self.sidebar_token(session), "C",
            "the sidebar fell back to the hardcoded C default while Perfect "
            "owned the app at Practice Key A",
        )


if __name__ == "__main__":
    unittest.main()
