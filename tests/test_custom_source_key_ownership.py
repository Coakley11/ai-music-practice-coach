"""A Custom source owns one harmonic context: Original Key, Practice Key and chart.

Repro (live app): SBI on Custom "Blues in F minor" (original Fm, Practice Fm,
Guitar capo 3 / D shapes). The Backing card showed Original Key C and the Lead
Sheet read "You're working in D minor · Key: Dm" over F minor audio.
"""

from __future__ import annotations

import unittest
from collections.abc import MutableMapping
from typing import Any

from backing_context import BackingContext, owned_backing_chart_identity
from custom_progression_lab import CPL_ACTIVE_KEY, default_active_progression, ensure_original_structure
from songs.backing_chart import render_backing_chord_chart


class _SessionLike(MutableMapping):
    """A Mapping that is not a dict, like Streamlit's SessionStateProxy."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._d = dict(data)

    def __getitem__(self, k: str) -> Any:
        return self._d[k]

    def __setitem__(self, k: str, v: Any) -> None:
        self._d[k] = v

    def __delitem__(self, k: str) -> None:
        del self._d[k]

    def __iter__(self):
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)


def _blues() -> dict[str, Any]:
    p = ensure_original_structure(default_active_progression())
    p.update({"id": "blues-1", "name": "Blues in F minor", "original_key_center": "Fm", "bpm": 140,
              "user_locked_home_key": True})
    p["original_sections"]["Verse"] = [{"chord": c, "bars": 1} for c in ("Fm6", "Fm6", "Db7", "C7")]
    return p


def _sbi_custom_ctx(key: str = "Fm") -> BackingContext:
    return BackingContext(
        source="song_improv",
        source_label="Song-Based Improvisation",
        active_song_id="custom::blues-1",
        song_title="Blues in F minor",
        key=key,
        display_key=key,
        concert_key=key,
        bpm=140,
        style="Pop",
        groove="Pop groove",
        sbi_material_kind="custom",
    )


class TestOwnedChartIdentityOriginalKey(unittest.TestCase):
    def test_streamlit_like_session_keeps_the_custom_original_key(self) -> None:
        session = _SessionLike({CPL_ACTIVE_KEY: _blues(), "instrument": "Guitar"})
        ident = owned_backing_chart_identity(session, _sbi_custom_ctx())
        self.assertEqual(ident["original_key"], "Fm")
        self.assertEqual(ident["song_data"]["key"], "Fm")
        self.assertEqual(ident["song_name"], "Blues in F minor")

    def test_plain_dict_session_is_unchanged(self) -> None:
        ident = owned_backing_chart_identity({CPL_ACTIVE_KEY: _blues()}, _sbi_custom_ctx())
        self.assertEqual(ident["original_key"], "Fm")

    def test_no_active_progression_keeps_the_context_key_not_generic_c(self) -> None:
        ident = owned_backing_chart_identity(_SessionLike({}), _sbi_custom_ctx("Fm"))
        self.assertEqual(ident["original_key"], "Fm")
        self.assertNotEqual(ident["song_data"]["key"], "C")

    def test_identity_carries_the_custom_tempo_and_title(self) -> None:
        ident = owned_backing_chart_identity(_SessionLike({CPL_ACTIVE_KEY: _blues()}), _sbi_custom_ctx())
        self.assertEqual(ident["bpm"], 140)
        self.assertEqual(ident["song_data"]["title"], "Blues in F minor")


def _prog(pid: str, name: str, key: str) -> dict[str, Any]:
    p = ensure_original_structure(default_active_progression())
    p.update({"id": pid, "name": name, "original_key_center": key, "user_locked_home_key": True})
    return p


class TestCustomPracticeKeyAliasesStayOnOneSong(unittest.TestCase):
    """A previous Custom's Practice Key must not become the next Custom's."""

    def _session(self) -> dict[str, Any]:
        from songs.practice_key_state import mark_practice_key_user_override, set_practice_concert_key

        blues, swing = _prog("blues-1", "Blues in F minor", "Fm"), _prog("swing-1", "Swing in Bb", "Bb")
        ss: dict[str, Any] = {
            "cpl_saved_progressions": {"Blues in F minor": blues, "Swing in Bb": swing},
            CPL_ACTIVE_KEY: swing,
            "sbi_custom_identity_pick": "custom::swing-1",
            "practice_key_by_source": {},
        }
        set_practice_concert_key(ss, "Fm", pick_key="custom::blues-1")
        mark_practice_key_user_override(ss, "custom::blues-1")
        set_practice_concert_key(ss, "Bb", pick_key="custom::swing-1")
        return ss

    def test_candidates_exclude_a_different_known_song(self) -> None:
        from source_session_state import _sbi_custom_practice_pick_candidates

        picks = _sbi_custom_practice_pick_candidates(self._session())
        self.assertIn("custom::swing-1", picks)
        self.assertNotIn("custom::blues-1", picks)

    def test_mirror_never_writes_onto_another_song(self) -> None:
        from songs.practice_key_state import get_practice_concert_key
        from source_session_state import mirror_custom_practice_key_aliases

        ss = self._session()
        mirror_custom_practice_key_aliases(ss, "C", primary_pick="custom::swing-1")
        self.assertEqual(get_practice_concert_key(ss, "custom::swing-1"), "C")
        self.assertEqual(get_practice_concert_key(ss, "custom::blues-1"), "Fm")

    def test_unknown_alias_ids_still_count_as_the_same_song(self) -> None:
        from source_session_state import _same_custom_song

        ss = self._session()
        self.assertTrue(_same_custom_song(ss, "custom::swing-1", "custom::seed-id-not-in-library"))
        self.assertFalse(_same_custom_song(ss, "custom::swing-1", "custom::blues-1"))


class TestGuitarShapeLeadSheetContract(unittest.TestCase):
    """The sheet gets the sounding key and concert cells; shapes are hints."""

    def _chart(self) -> str:
        return render_backing_chord_chart(
            "Blues in F minor",
            {"title": "Blues in F minor", "key": "Fm"},
            {"Verse": ["Fm6", "Fm6", "Db7", "C7"]},
            display_key="Fm",
            bpm=140,
            shape_sections={"Verse": ["Dm6", "Dm6", "Bb7", "A7"]},
            capo_fret=3,
            capo_shape_key="Dm",
        )

    def test_header_names_the_practice_key_and_the_shape_chart(self) -> None:
        html = self._chart()
        self.assertIn("Key: Fm", html)
        self.assertNotIn("Key: Dm", html)
        self.assertIn("Charts in D minor · capo 3", html)
        self.assertIn("working in F minor", html)

    def test_cells_are_concert_with_shape_hints(self) -> None:
        html = self._chart()
        self.assertIn("Fm6", html)
        self.assertIn("Db7", html)
        self.assertIn("Dm6 shape", html)
        self.assertIn("Bb7 shape", html)


if __name__ == "__main__":
    unittest.main()
