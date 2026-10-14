"""Entry & Style Jam / Jam Session Generator -> Backing consistency.

Live first wrong steps fixed here:

* Generator key edit after a launch (C minor -> F#): every jam store moved to
  F# except the jam's own sticky Practice Key. The write was dropped because a
  lingering ``_specialized_practice_token_leaving`` made
  ``resolve_settings_pick_for_write`` return "" for every ``creative::`` pick,
  and the stale Cm sticky then outranked the rest in
  ``jam_generator_authoritative_concert_key``; the Concert Key control was
  re-seeded to the previous jam's key before it rendered.
* Generator key edit after a Style Jam launch: ``apply_specialized_jam_practice_key``
  read the jam owner from the Backing context (the launched Style Jam) instead of
  the entry mode on Creative, mutated the Style Jam workflow, and flipped the page
  back to Style Jam.
* Minor keys: ``_key_steps_to_center`` detected minor and did nothing, so a
  C minor jam played C major harmony (Am - Dm - G7 - C).
* Latin / Fusion / Modal Vamp / Lo-fi had no Backing groove and fell back to
  "Pop groove".
* Returning from a jam: the jam's play session survived the return, so the
  Catalog / Karaoke song came back at the jam's 70 BPM; a refresh then hit a
  RecursionError between three ownership predicates.
"""

from __future__ import annotations

from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base


def test_minor_key_jam_uses_minor_harmony_and_major_is_unchanged() -> None:
    from improvisation_intelligence import generate_style_progression

    cm = generate_style_progression(style="Latin", key_center="Cm", mood="Mellow", seed=7)
    c = generate_style_progression(style="Latin", key_center="C", mood="Mellow", seed=7)
    first_cm = next(iter(cm.values()))
    first_c = next(iter(c.values()))
    assert first_cm[:4] == ["Cm", "Fm", "Bb7", "Eb"]
    assert first_c[:4] == ["Am", "Dm", "G7", "C"]
    bm = generate_style_progression(style="Jazz Swing", key_center="B minor", mood="Mellow", seed=7)
    assert next(iter(bm.values()))[:3] == ["Em7", "A7", "Dmaj7"]       # ii-V-I of D (Bm's relative major)


def test_every_jam_style_maps_to_a_matching_backing_groove() -> None:
    from songs.playback_defaults import GROOVE_STYLE_CHOICES, normalize_groove_label

    want = {
        "Bossa Nova": "Bossa nova", "Jazz Swing": "Jazz swing", "Blues": "Blues groove",
        "Funk": "Funk groove", "Pop": "Pop groove", "Rock": "Rock groove",
        "Neo Soul": "Funk groove", "Fusion": "Funk groove", "Modal Vamp": "Jazz swing",
        "Lo-fi": "Ballad", "Latin": "Bossa nova",
    }
    for style, groove in want.items():
        assert normalize_groove_label(style) == groove, style
        assert groove in GROOVE_STYLE_CHOICES


class TestGeneratorKeyEdit(_Base):
    def _generator_on_creative(self) -> dict:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        session["studio_page"] = "creative"
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Jam Session Generator"
        session["improv_jam_key"] = "Cm"
        return session

    def test_an_edit_inside_the_jam_reaches_the_jam_sticky_despite_a_leave_flag(self) -> None:
        from songs.practice_key_state import (
            CREATIVE_JAM_SESSION_PICK,
            creative_jam_owns_practice_settings,
            resolve_settings_pick_for_write,
        )

        session = self._generator_on_creative()
        session["_specialized_practice_token_leaving"] = "Cm"
        if creative_jam_owns_practice_settings(session):
            self.assertEqual(resolve_settings_pick_for_write(session, CREATIVE_JAM_SESSION_PICK), CREATIVE_JAM_SESSION_PICK)
        session["studio_page"] = "songs"                         # really left the jam
        session["improv_entry_mode"] = ""
        self.assertEqual(resolve_settings_pick_for_write(session, CREATIVE_JAM_SESSION_PICK), "")

    def test_the_key_seal_moves_the_jam_sticky(self) -> None:
        from music_workflow_generated_session import finalize_generated_jam_session_key_seal
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK, PRACTICE_KEY_BY_SOURCE_KEY, get_practice_concert_key

        session = self._generator_on_creative()
        session.setdefault(PRACTICE_KEY_BY_SOURCE_KEY, {})[CREATIVE_JAM_SESSION_PICK] = "Cm"
        session["_specialized_practice_token_leaving"] = "Cm"
        session["improv_jam_session"] = {"key": "Cm", "sections": {"A": ["Cm", "Fm"]}}
        finalize_generated_jam_session_key_seal(session, "F#")
        self.assertEqual(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK), "F#")
        self.assertEqual(session["improv_jam_key"], "F#")

    def test_generator_edit_on_creative_is_not_taken_as_the_launched_style_jam(self) -> None:
        import inspect

        import creative_key_sync

        src = inspect.getsource(creative_key_sync.apply_specialized_jam_practice_key)
        # The Backing context may only decide the owner off Creative.
        i = src.index('entry = str(session.get("improv_entry_mode")')
        j = src.index("get_backing_context(session)", i)
        self.assertIn('!= "creative"', src[i:j])


class TestOwnershipPredicatesTerminate(_Base):
    def test_no_recursion_after_a_jam_return(self) -> None:
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY, generated_jam_owns_practice_key
        from musical_context_authority import catalog_song_should_own_sidebar_practice_key

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        session["studio_page"] = "backing"
        session["improv_entry_mode"] = "Style Jam Mode"
        session[GENERATED_JAM_KEY_CONTEXT_KEY] = {"key_owner": "style_jam", "practice_key_token": "F"}
        session.pop("improv_jam_session", None)
        session.pop("improv_generated_sections", None)
        session["improv_jam_key"] = ""
        session["improv_style_key"] = ""
        self.assertIsInstance(catalog_song_should_own_sidebar_practice_key(session), bool)
        self.assertIsInstance(generated_jam_owns_practice_key(session), bool)


class TestReturnEndsTheJamPlaySession(_Base):
    def test_return_to_regular_backing_drops_the_jam_tempo(self) -> None:
        from backing_play_session import BACKING_PLAY_SESSION_KEY, get_backing_play_session
        from backing_session_route import navigate_to_regular_backing

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        session["studio_page"] = "backing"
        session[BACKING_PLAY_SESSION_KEY] = {
            "play_session_id": "p1", "launch_id": "jam-1", "source_identity": "jam:entry",
            "expired": False, "defaults": {"bpm": 70}, "overrides": {"bpm": 70},
        }
        navigate_to_regular_backing(session)
        ps = get_backing_play_session(session) or {}
        self.assertTrue(ps.get("expired"))
        self.assertEqual(ps.get("overrides"), {})
        self.assertNotEqual((ps.get("defaults") or {}).get("bpm"), 70)
