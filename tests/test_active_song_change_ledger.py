"""Diagnostic ledger: which operation changed the active song, and why (user report 2026-11-19).

The ledger only observes: it never changes the active song, and a Custom / Composition song is
never named (hashed pick only).
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import active_song_change_ledger as asl

ROOT = Path(__file__).resolve().parents[1]
SHALLOW = "Pop\x1fShallow — Lady Gaga / Bradley Cooper"
BLACKBIRD = "Rock\x1fBlackbird — The Beatles"


def _catalog(pick: str, key: str) -> dict:
    return {"active_catalog_pick_key": pick, "selected_song": {"pick_key": pick}, "display_key": key}


class Labels(unittest.TestCase):
    def test_a_catalog_song_is_its_public_title_with_the_practice_key(self) -> None:
        self.assertEqual(asl.active_song_label(_catalog(BLACKBIRD, "E")), "Blackbird — The Beatles")
        self.assertIn("dk=E", asl.active_key_state(_catalog(BLACKBIRD, "E")))

    def test_custom_and_composition_songs_are_never_named(self) -> None:
        for pick, kind in (("custom::My Secret Song", "custom:"), ("composition::0d28-my-lyrics", "composition:")):
            with mock.patch("songs.practice_key_state.resolve_practice_source_pick", return_value=pick):
                label = asl.active_song_label({"display_key": "D"})
            self.assertTrue(label.startswith(kind), label)
            self.assertNotIn("Secret", label)
            self.assertNotIn("lyrics", label)
            self.assertRegex(label, r"^[a-z]+:[0-9a-f]{8}$")

    def test_no_active_song_is_an_empty_label(self) -> None:
        self.assertEqual(asl.active_song_label({}), "")


class Ledger(unittest.TestCase):
    def test_the_first_sight_only_stamps(self) -> None:
        s = _catalog(SHALLOW, "G")
        self.assertFalse(asl.note_active_song(s, "run_start"))
        self.assertEqual(asl.ledger_rows(s), [])

    def test_a_change_is_recorded_with_its_operation_and_reason_and_logged(self) -> None:
        s = _catalog(SHALLOW, "G")
        asl.note_active_song(s, "run_start")
        s.update(_catalog(BLACKBIRD, "E"))
        err = io.StringIO()
        with redirect_stderr(err):
            changed = asl.note_active_song(s, "workspace_apply", source="cloud",
                                           reasons="cloud_newer_than_applied", mid_session=1)
        self.assertTrue(changed)
        row = asl.ledger_rows(s)[-1]
        self.assertEqual(row["op"], "workspace_apply")
        self.assertTrue(row["from"].startswith("Shallow — Lady Gaga / Bradley Cooper [dk=G"), row["from"])
        self.assertTrue(row["to"].startswith("Blackbird — The Beatles [dk=E"), row["to"])
        self.assertIn("reasons=cloud_newer_than_applied", row["why"])
        self.assertIn('[music_active_song] op=workspace_apply from="Shallow', err.getvalue())

    def test_a_key_change_on_the_same_song_is_recorded(self) -> None:
        s = _catalog(SHALLOW, "G")
        asl.note_active_song(s, "run_start")
        s["display_key"] = "D"
        with redirect_stderr(io.StringIO()):
            self.assertTrue(asl.note_active_song(s, "set_practice_concert_key", key="D", caller="x.py:f:1"))
        row = asl.ledger_rows(s)[-1]
        self.assertIn("dk=G", row["from"]); self.assertIn("dk=D", row["to"])
        self.assertIn("caller=x.py:f:1", row["why"])

    def test_the_queued_display_key_alone_is_not_a_change(self) -> None:
        s = _catalog(SHALLOW, "G")
        asl.note_active_song(s, "run_start")
        s["_pending_display_key"] = "G"
        self.assertFalse(asl.note_active_song(s, "set_practice_concert_key"))
        s.pop("_pending_display_key")
        self.assertFalse(asl.note_active_song(s, "set_practice_concert_key"))
        self.assertEqual(asl.ledger_rows(s), [])

    def test_no_change_no_row_unless_marked(self) -> None:
        s = _catalog(SHALLOW, "G")
        asl.note_active_song(s, "run_start")
        self.assertFalse(asl.note_active_song(s, "backing_activate_catalog"))
        self.assertEqual(asl.ledger_rows(s), [])
        asl.note_active_song(s, "card_play", mark=True)
        self.assertEqual([r["op"] for r in asl.ledger_rows(s)], ["card_play"])
        self.assertFalse(asl.ledger_rows(s)[0]["changed"])

    def test_the_ledger_is_bounded(self) -> None:
        s = _catalog(SHALLOW, "G")
        for i in range(asl.LEDGER_MAX_ROWS + 15):
            asl.note_active_song(s, f"m{i}", mark=True)
        self.assertEqual(len(asl.ledger_rows(s)), asl.LEDGER_MAX_ROWS)

    def test_it_never_changes_the_active_song_and_never_raises(self) -> None:
        s = _catalog(SHALLOW, "G")
        before = dict(s)
        with mock.patch.object(asl, "active_song_label", side_effect=RuntimeError("boom")):
            self.assertFalse(asl.note_active_song(s, "x"))
        asl.note_active_song(s, "y", mark=True)
        for k in ("active_catalog_pick_key", "selected_song", "display_key"):
            self.assertEqual(s[k], before[k])

    def test_ledger_keys_are_not_saved_with_the_workspace(self) -> None:
        import music_persistent_state as mps

        self.assertNotIn(asl.LEDGER_KEY, mps._PERSIST_KEYS)
        self.assertNotIn(asl.LAST_LABEL_KEY, mps._PERSIST_KEYS)


class Hooks(unittest.TestCase):
    def test_the_song_activation_entry_points_record_a_change(self) -> None:
        import songs.state as ss

        self.assertTrue(getattr(ss.activate_active_song_by_pick_key, "__wrapped_for_ledger__", False))
        self.assertTrue(getattr(ss.apply_explicit_catalog_dropdown_pick, "__wrapped_for_ledger__", False))
        session = _catalog(SHALLOW, "G")
        asl.note_active_song(session, "run_start")

        def _fake(st, pick, *_a, **_k):
            st.session_state.update(_catalog(pick, "E"))
            return {"ok": True}

        observed = ss._ledger_observed(_fake, "activate_by_pick_key")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(observed(SimpleNamespace(session_state=session), BLACKBIRD, {}, origin="user"), {"ok": True})
        row = asl.ledger_rows(session)[-1]
        self.assertEqual(row["op"], "activate_by_pick_key")
        self.assertTrue(row["to"].startswith("Blackbird — The Beatles [dk=E"), row["to"])
        self.assertIn("origin=user", row["why"])

    def test_the_workspace_apply_backing_restore_karaoke_row_and_play_are_instrumented(self) -> None:
        sup = (ROOT / "suite_user_persistence.py").read_text(encoding="utf-8")
        self.assertIn('note_active_song(st.session_state, "before_workspace_apply")', sup)
        self.assertIn('"workspace_apply",', sup)
        ms = (ROOT / "songs" / "music_source.py").read_text(encoding="utf-8")
        self.assertIn('"backing_activate_catalog",', ms)
        app = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        for op in ('"run_start"', '"karaoke_setlist_row"', '"card_play", mark=True'):
            self.assertIn(op, app)
        dv = (ROOT / "music_deploy_verification.py").read_text(encoding="utf-8")
        self.assertIn("**Active song changes**", dv)
        import songs.key_state as ks
        import songs.practice_key_state as pks

        self.assertTrue(getattr(pks.set_practice_concert_key, "__wrapped_for_ledger__", False))
        self.assertTrue(getattr(ks.request_display_key, "__wrapped_for_ledger__", False))


if __name__ == "__main__":
    unittest.main()
