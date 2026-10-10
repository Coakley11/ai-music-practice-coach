"""An explicit per-song Catalog Practice Key override is durable.

``apply_pick_key`` treats a pick change, catalog owner switch or fresh catalog
activation as "fresh activation = Original" and cleared the saved Practice Key
for both the incoming pick and the outgoing one. So an explicitly chosen key
was destroyed by merely moving between songs, and the Custom -> Catalog return
(a ``catalog_owner_switch`` with ``is_restore`` false) erased Ipanema's G and
re-derived Original F — which only reappeared on refresh, because the restore
path skips that block.

"Fresh activation = Original" now governs only a pick with no explicit saved
override.

Scope note: these drive the Song A -> Song B direction, which is what this unit
harness actually reaches (it provably clears the outgoing key without the
guard). The Custom -> Catalog owner-switch direction needs the full app session
and is covered by the persisted browser flow.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from song_catalog.catalog import format_pick_key
from songs.practice_key_state import (
    catalog_pick_has_user_practice_key_override,
    get_practice_concert_key,
    mark_practice_key_user_override,
    set_practice_concert_key,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, _LAST_PICK_KEY, apply_pick_key

PK_IPANEMA = format_pick_key("Jazz", "The Girl from Ipanema — Antonio Carlos Jobim")
PK_SAY = format_pick_key("Pop", "Say — John Mayer")

CATALOG = {
    "Jazz": {
        "The Girl from Ipanema — Antonio Carlos Jobim": {
            "title": "The Girl from Ipanema",
            "artist": "Antonio Carlos Jobim",
            "key": "F",
            "genre": "Jazz",
        }
    },
    "Pop": {
        "Say — John Mayer": {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "genre": "Pop",
        }
    },
}


def _commit(session: dict, pick: str, key: str) -> None:
    """What the sidebar Practice Key control does on an explicit choice."""
    set_practice_concert_key(session, key, pick_key=pick)
    mark_practice_key_user_override(session, pick)


def _apply(session: dict, pick: str) -> None:
    st = MagicMock(session_state=session)
    with patch("songs.state.persist_music_local_state"):
        apply_pick_key(st, pick, CATALOG, skip_activity_log=True)


class TestCatalogOverrideDurability(unittest.TestCase):
    def test_outgoing_override_survives_switching_to_another_song(self) -> None:
        """Ipanema's explicit G must still be parked after activating Say."""
        session: dict = {ACTIVE_CATALOG_PICK_KEY: PK_IPANEMA, _LAST_PICK_KEY: PK_IPANEMA}
        _commit(session, PK_IPANEMA, "G")

        _apply(session, PK_SAY)

        self.assertEqual(get_practice_concert_key(session, PK_IPANEMA, default=""), "G")
        self.assertTrue(catalog_pick_has_user_practice_key_override(session, PK_IPANEMA))

    def test_outgoing_residue_without_override_is_still_cleared(self) -> None:
        """The existing fresh-activation cleanup must keep working."""
        session: dict = {ACTIVE_CATALOG_PICK_KEY: PK_IPANEMA, _LAST_PICK_KEY: PK_IPANEMA}
        # Saved without marking an override: this is visit residue.
        set_practice_concert_key(session, "A", pick_key=PK_IPANEMA)
        self.assertFalse(catalog_pick_has_user_practice_key_override(session, PK_IPANEMA))

        _apply(session, PK_SAY)

        self.assertEqual(get_practice_concert_key(session, PK_IPANEMA, default=""), "")

    def test_two_overridden_songs_keep_their_own_keys_across_a_b_a(self) -> None:
        """A -> B -> A restores each song's own saved key."""
        session: dict = {ACTIVE_CATALOG_PICK_KEY: PK_IPANEMA, _LAST_PICK_KEY: PK_IPANEMA}
        _commit(session, PK_IPANEMA, "G")
        _commit(session, PK_SAY, "E")

        _apply(session, PK_SAY)
        self.assertEqual(get_practice_concert_key(session, PK_SAY, default=""), "E")
        self.assertEqual(get_practice_concert_key(session, PK_IPANEMA, default=""), "G")

        _apply(session, PK_IPANEMA)
        self.assertEqual(get_practice_concert_key(session, PK_IPANEMA, default=""), "G")
        self.assertEqual(get_practice_concert_key(session, PK_SAY, default=""), "E")

    def test_override_registry_is_the_only_authority_consulted(self) -> None:
        """The guard reads the shared registry, not a second persistence flag."""
        source = (
            __import__("pathlib").Path(__file__).resolve().parents[1] / "songs" / "state.py"
        ).read_text(encoding="utf-8")
        block = source.split("user_song_change = bool(", 1)[1].split("ACTIVE_CATALOG_PICK_KEY]", 1)[0]
        assert "catalog_pick_has_user_practice_key_override" in block
        # No bespoke flag invented alongside it.
        assert "_practice_key_user_committed" not in source


if __name__ == "__main__":
    unittest.main()
