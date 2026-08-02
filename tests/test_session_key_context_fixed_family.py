"""Fixed family authoritative session keys — regression coverage."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from practice_key_mode import (
    MODE_FIXED,
    MODE_STANDARD,
    FIXED_PRACTICE_KEY_FAMILY_ID,
    family_option_id,
    on_fixed_practice_concert_key_change,
    resolve_practice_concert_key_for_song,
    set_fixed_practice_key_family,
    set_practice_key_mode,
)
from session_key_context import (
    resolve_active_object_mode,
    resolve_effective_session_key_context,
    sync_effective_session_keys_before_render,
)
from songs.key_state import get_authoritative_display_key, resolve_active_musical_key


def _fixed(session: dict, *, original_key: str = "G") -> dict:
    set_practice_key_mode(session, MODE_FIXED)
    set_fixed_practice_key_family(session, family_option_id("C", "A"))
    session.setdefault("selected_song", {"pick_key": "pk::1", "key": original_key, "title": "Test"})
    session.setdefault("active_catalog_pick_key", "pk::1")
    return session


class TestSessionKeyContextFixedFamily(unittest.TestCase):
    def test_c_a_major_catalog_song_resolves_c(self) -> None:
        session = _fixed({"display_key": "D#", "concert_key": "G"}, original_key="G")
        ctx = resolve_effective_session_key_context(session, original_key="G", apply_to_session=True)
        self.assertEqual(ctx.resolved_tonal_key, "C")
        self.assertEqual(session["concert_key"], "C")
        self.assertEqual(session["display_key"], "C")

    def test_c_a_minor_catalog_song_resolves_am(self) -> None:
        session = _fixed({"display_key": "D#"}, original_key="Em")
        ctx = resolve_effective_session_key_context(session, original_key="Em", apply_to_session=True)
        self.assertEqual(ctx.resolved_tonal_key, "Am")
        self.assertEqual(session["display_key"], "Am")

    def test_em_minor_not_inferred_as_major_from_g_metadata(self) -> None:
        session = _fixed(
            {
                "display_key": "G",
                "concert_key": "G",
                "selected_song": {"pick_key": "pk::1", "key": "Em", "title": "Minor tune"},
            },
            original_key="Em",
        )
        mode = resolve_active_object_mode(session, original_key="G")
        self.assertEqual(mode, "minor")
        self.assertEqual(
            resolve_practice_concert_key_for_song(session, "G", fallback="G"),
            "Am",
        )

    def test_stale_display_d_sharp_replaced(self) -> None:
        session = _fixed({"display_key": "D#", "practice_key": "D#"}, original_key="G")
        sync_effective_session_keys_before_render(session, original_key="G")
        self.assertEqual(session["display_key"], "C")
        self.assertEqual(session["practice_key"], "C")

    def test_instrument_change_does_not_alter_family(self) -> None:
        session = _fixed({"display_key": "C", "instrument": "Piano"}, original_key="G")
        sync_effective_session_keys_before_render(session, original_key="G", instrument="Piano")
        fam_before = session[FIXED_PRACTICE_KEY_FAMILY_ID]
        session["instrument"] = "Alto Sax (Eb)"
        session["display_key"] = "A"
        on_fixed_practice_concert_key_change(session, "A")
        sync_effective_session_keys_before_render(
            session, original_key="G", instrument="Alto Sax (Eb)"
        )
        self.assertEqual(session[FIXED_PRACTICE_KEY_FAMILY_ID], fam_before)
        self.assertEqual(session["concert_key"], "C")

    def test_written_chart_derives_from_concert_not_family_corruption(self) -> None:
        session = _fixed(
            {
                "display_key": "C",
                "concert_key": "C",
                "instrument": "Alto Sax (Eb)",
                "chart_in_instrument_key": True,
            },
            original_key="G",
        )
        sync_effective_session_keys_before_render(
            session, original_key="G", instrument="Alto Sax (Eb)"
        )
        musical = resolve_active_musical_key(session, instrument="Alto Sax (Eb)")
        self.assertEqual(musical.practice_concert_key, "C")
        self.assertNotEqual(musical.chart_key, session[FIXED_PRACTICE_KEY_FAMILY_ID])
        self.assertEqual(session[FIXED_PRACTICE_KEY_FAMILY_ID], family_option_id("C", "A"))

    def test_backing_target_uses_family(self) -> None:
        from backing_context import BackingContext, _live_backing_concert_keys

        session = _fixed({"display_key": "G"}, original_key="Bm")
        session["backing_context"] = {
            "source": "regular_song",
            "key": "Bm",
            "concert_key": "G",
            "display_key": "G",
        }
        sync_effective_session_keys_before_render(session, original_key="Bm")
        practice, _, _ = _live_backing_concert_keys(session)
        self.assertEqual(practice, "Am")

    def test_repeated_sync_keeps_family_result(self) -> None:
        session = _fixed({"display_key": "G"}, original_key="Em")
        sync_effective_session_keys_before_render(session, original_key="Em")
        sync_effective_session_keys_before_render(session, original_key="Em")
        self.assertEqual(session["display_key"], "Am")
        self.assertEqual(session["concert_key"], "Am")

    def test_pure_resolve_does_not_mutate_session(self) -> None:
        session = _fixed({"display_key": "G"}, original_key="G")
        before = dict(session)
        resolve_effective_session_key_context(session, original_key="G", apply_to_session=False)
        self.assertEqual(session.get("display_key"), before.get("display_key"))

    def test_disable_fixed_returns_song_key_path(self) -> None:
        session = _fixed({"display_key": "G"}, original_key="G")
        set_practice_key_mode(session, MODE_STANDARD)
        resolved = resolve_practice_concert_key_for_song(session, "G", fallback="G")
        self.assertEqual(resolved, "G")

    def test_authoritative_display_key_ignores_stale_override(self) -> None:
        session = _fixed({"display_key": "D#"}, original_key="G")
        self.assertEqual(get_authoritative_display_key(session, original_key="G"), "C")

    def test_restore_then_sync_recomputes_context(self) -> None:
        from music_persistent_state import apply_music_disk_state

        st = MagicMock()
        st.session_state = {"display_key": "G", "instrument": "Piano"}
        blob = {
            "session": {
                "practice_key_mode": MODE_FIXED,
                "fixed_practice_key_family_id": family_option_id("C", "A"),
            },
            "core": {"display_key": "G"},
        }
        apply_music_disk_state(st, blob, song_picker_catalog={}, song_library={}, authoritative_restore=True)
        sync_effective_session_keys_before_render(st.session_state, original_key="Em")
        self.assertEqual(st.session_state.get("display_key"), "Am")


if __name__ == "__main__":
    unittest.main()
