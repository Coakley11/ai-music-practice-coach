"""Style Jam and the Jam Session Generator each own their own key.

Live first wrong steps (Style Jam E, refresh, Style Jam Bb, then Generator Cm --
the Generator showed E on the sidebar and, after refresh, on its banner/card):

* On Creative, ``resolve_display_key_widget_owner_id`` took the jam owner from
  the Backing context -- the last *launched* jam (Style) -- over the workflow on
  screen (Generator), so the owner transition seeded the Style Jam's key.
* Two "heal the song pick from the live sidebar key" writes
  (``overlay_destination_practice_key`` and ``hydrate_backing_source_for_page``)
  were redirected by ``resolve_settings_pick_for_write`` into the jam's own store,
  so whatever the shared ``display_key`` held (the Style Jam's key) became the
  Generator's saved key.
* ``_stamp_style_jam_live_concert_key`` ran for a Generator context on Backing
  and stamped the Style Jam's key over it.
* ``stamp_envelope_from_backing_context`` treated Style Jam -> Generator (both
  ``entry_jam``) as a same-owner refresh, so the sealed envelope kept
  ``entry_mode = Style Jam Mode`` and bound the Backing key control to the
  Style Jam's widget.
* The Style Jam's key seal never wrote the Style Jam's own sticky (the
  Generator's does); it followed only through those heals, so with them closed
  a Style Jam G after a Generator jam kept showing the previous Bb.
"""

from __future__ import annotations

from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base

STYLE = "Style Jam Mode"
GENERATOR = "Jam Session Generator"


def _jam_ctx(entry_mode: str, key: str, jam_id: str):
    from backing_context import BackingContext

    return BackingContext(
        source="entry_jam",
        source_label="Entry & Jam",
        active_song_id="",
        song_title="",
        key=key,
        display_key=key,
        concert_key=key,
        bpm=95,
        style="Funk",
        groove="Funk groove",
        jam_id=jam_id,
        entry_mode=entry_mode,
    )


class TestStyleJamAndGeneratorOwnSeparateKeys(_Base):
    def _session(self, *, page: str, entry: str) -> dict:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        session["studio_page"] = page
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = entry
        return session

    def test_on_creative_the_workflow_on_screen_owns_the_display_key(self) -> None:
        from backing_context import set_backing_context
        from songs.key_state import resolve_display_key_widget_owner_id

        session = self._session(page="creative", entry=GENERATOR)
        set_backing_context(session, _jam_ctx(STYLE, "E", "style-1"))     # last launched: Style Jam
        self.assertTrue(resolve_display_key_widget_owner_id(session).startswith("entry_jam::"))
        session["improv_entry_mode"] = STYLE
        self.assertEqual(resolve_display_key_widget_owner_id(session), "style_jam::style-1")

    def test_on_backing_the_launched_jam_still_owns_the_display_key(self) -> None:
        from backing_context import set_backing_context
        from songs.key_state import resolve_display_key_widget_owner_id

        session = self._session(page="backing", entry=STYLE)
        set_backing_context(session, _jam_ctx(GENERATOR, "Cm", "gen-1"))
        self.assertEqual(resolve_display_key_widget_owner_id(session), "entry_jam::gen-1")

    def test_a_song_pick_heal_never_writes_a_jam_store(self) -> None:
        from music_workflow_pending_song_practice_key_edit import overlay_destination_practice_key
        from songs.practice_key_state import (
            CREATIVE_JAM_SESSION_PICK,
            PRACTICE_KEY_BY_SOURCE_KEY,
            get_practice_concert_key,
            heal_write_lands_in_creative_jam_store,
            resolve_settings_pick_for_write,
        )

        session = self._session(page="creative", entry=GENERATOR)
        session.setdefault(PRACTICE_KEY_BY_SOURCE_KEY, {})[CREATIVE_JAM_SESSION_PICK] = "Cm"
        session["display_key"] = "E"                                        # the Style Jam's key, still shared
        pick = session["active_catalog_pick_key"]
        self.assertEqual(
            heal_write_lands_in_creative_jam_store(session, pick),
            str(resolve_settings_pick_for_write(session, pick)).startswith("creative::"),
        )
        overlay_destination_practice_key(session)
        self.assertEqual(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK), "Cm")

    def test_the_style_jam_stamp_leaves_a_generator_context_alone(self) -> None:
        from backing_context import _stamp_style_jam_live_concert_key, get_backing_context, set_backing_context

        session = self._session(page="backing", entry=GENERATOR)
        set_backing_context(session, _jam_ctx(GENERATOR, "Cm", "gen-1"))
        session["improv_style_key"] = "E"
        session["display_key"] = "Cm"
        session["concert_key"] = "Cm"
        _stamp_style_jam_live_concert_key(session)
        self.assertEqual((session["display_key"], session["concert_key"]), ("Cm", "Cm"))
        self.assertEqual(get_backing_context(session).entry_mode, GENERATOR)

    def test_switching_jam_workflow_reseals_the_owner_envelope(self) -> None:
        from backing_owner_envelope import get_backing_owner_envelope, stamp_envelope_from_backing_context

        session = self._session(page="backing", entry=STYLE)
        session["display_key"] = "E"
        stamp_envelope_from_backing_context(session, _jam_ctx(STYLE, "E", "style-1"), source_override="entry_jam")
        self.assertEqual(get_backing_owner_envelope(session).entry_mode, STYLE)

        session["improv_entry_mode"] = GENERATOR                            # display_key still holds E
        stamp_envelope_from_backing_context(session, _jam_ctx(GENERATOR, "Cm", "gen-1"), source_override="entry_jam")
        env = get_backing_owner_envelope(session)
        self.assertEqual((env.entry_mode, env.practice_key), (GENERATOR, "Cm"))

    def test_each_jam_seal_moves_only_its_own_store(self) -> None:
        from music_workflow_generated_session import (
            finalize_generated_jam_session_key_seal,
            finalize_generated_style_jam_key_seal,
        )
        from songs.practice_key_state import (
            CREATIVE_JAM_SESSION_PICK,
            CREATIVE_STYLE_JAM_PICK,
            PRACTICE_KEY_BY_SOURCE_KEY,
            get_practice_concert_key,
        )

        session = self._session(page="creative", entry=STYLE)
        store = session.setdefault(PRACTICE_KEY_BY_SOURCE_KEY, {})
        store[CREATIVE_STYLE_JAM_PICK] = "Bb"
        store[CREATIVE_JAM_SESSION_PICK] = "Cm"
        finalize_generated_style_jam_key_seal(session, "G")
        self.assertEqual(get_practice_concert_key(session, CREATIVE_STYLE_JAM_PICK), "G")
        self.assertEqual(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK), "Cm")
        session["improv_entry_mode"] = GENERATOR
        finalize_generated_jam_session_key_seal(session, "Am")
        self.assertEqual(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK), "Am")
        self.assertEqual(get_practice_concert_key(session, CREATIVE_STYLE_JAM_PICK), "G")

    def test_a_sealed_style_jam_g_is_intent_not_a_remount_default(self) -> None:
        from backing_practice_key_control import style_jam_authoritative_concert_key
        from music_workflow_generated_session import finalize_generated_style_jam_key_seal

        session = self._session(page="creative", entry=STYLE)
        session["creative_session"] = {"tool_type": "entry_style_jam", "concert_key": "E", "display_key": "E"}
        finalize_generated_style_jam_key_seal(session, "G")
        self.assertEqual(style_jam_authoritative_concert_key(session), "G")
