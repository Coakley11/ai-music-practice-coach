"""static/kc file lifetime: one session never deletes another live session's WAVs.

static/kc is shared by every session of the server (desktop + phone on one
account are two sessions). Cleaning the shared folder against one session's
keep set deleted the other session's current, prepared and Lead Sheet takes.
Each session now publishes into its own folder and only cleans that folder;
other folders go only when Streamlit no longer has the session active and the
folder has been idle past a grace period.
"""
from __future__ import annotations

import io
import os
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest import mock

import backing_key_cycle as kc


def _wav(seed: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(bytes([(seed + i) % 256 for i in range(4000)]))
    return buf.getvalue()


class _Sessions:
    """Publish/clean as session A or B against a temporary static/kc."""

    def __init__(self, root: Path, spill: Path) -> None:
        self.root, self.spill = root, spill
        self.owner = "A"
        self.active = {"A", "B"}

    def patches(self):
        return (
            mock.patch.object(kc, "_kc_static_root", lambda: self.root),
            mock.patch.object(kc, "_kc_static_owner", lambda: self.owner),
            mock.patch.object(kc, "_kc_session_active", lambda o: o in self.active),
        )

    def publish(self, owner: str, name: str, sig, seed: int) -> str:
        self.owner = owner
        src = self.spill / f"{owner}_{name}.wav"
        src.write_bytes(_wav(seed))
        return kc.publish_cycle_wav_static_url(str(src), signature=sig)

    def session(self, owner: str, seed: int) -> tuple[dict, dict]:
        cur = ("sig", owner, "A", 95)
        nxt = ("sig", owner, "Bb", 95)
        urls = {
            "current": self.publish(owner, "cur", cur, seed),
            "next": self.publish(owner, "next", nxt, seed + 1),
            "lead_sheet": self.publish(owner, "ls", ("lead_sheet", repr(cur)), seed + 2),
        }
        s = {
            "_kc_current_static_url": urls["current"],
            "_last_backing_signature": cur,
            kc.BACKING_KEY_CYCLE_PREPARED_KEY: {"Bb": {"signature": nxt, "static_url": urls["next"]}},
            "_backing_sheet_static_url": {"sig": repr(cur), "url": urls["lead_sheet"]},
        }
        return s, urls

    def prune(self, owner: str, session: dict) -> None:
        self.owner = owner
        kc._prune_cycle_static_files(session)


class StaticLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        base = Path(self._td.name)
        (base / "kc").mkdir()
        (base / "spill").mkdir()
        self.s = _Sessions(base / "kc", base / "spill")
        self._patches = self.s.patches()
        for p in self._patches:
            p.start()
        kc._kc_static_last_collect = 0.0

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()
        self._td.cleanup()

    def alive(self, urls: dict) -> dict:
        return {k: kc._kc_static_url_on_disk(u) for k, u in urls.items()}

    def test_each_session_publishes_into_its_own_folder(self) -> None:  # KCFILE1
        _, a = self.s.session("A", 10)
        _, b = self.s.session("B", 50)
        for urls, owner in ((a, "A"), (b, "B")):
            for url in urls.values():
                self.assertTrue(url.startswith(f"app/static/kc/{owner}/"), url)
        self.assertEqual(self.alive(a), dict.fromkeys(a, True))
        self.assertEqual(self.alive(b), dict.fromkeys(b, True))

    def test_one_sessions_cleanup_never_deletes_the_others_takes(self) -> None:  # KCFILE2/3
        sa, a = self.s.session("A", 10)
        sb, b = self.s.session("B", 50)
        self.s.prune("B", sb)
        self.assertEqual(self.alive(a), dict.fromkeys(a, True))
        self.s.prune("A", sa)
        self.assertEqual(self.alive(b), dict.fromkeys(b, True))

    def test_cleanup_keeps_current_prepared_and_lead_sheet_and_drops_own_obsolete(self) -> None:  # KCFILE5/6
        sa, a = self.s.session("A", 10)
        old = self.s.publish("A", "old", ("sig", "A", "G", 80), 90)
        self.assertTrue(kc._kc_static_url_on_disk(old))
        self.s.prune("A", sa)
        self.assertEqual(self.alive(a), dict.fromkeys(a, True))
        self.assertFalse(kc._kc_static_url_on_disk(old))

    def test_own_folder_cap_drops_only_the_oldest_own_takes(self) -> None:
        _, b = self.s.session("B", 50)
        urls = []
        for i in range(kc.KC_STATIC_OWN_MAX_FILES + 2):
            urls.append(self.s.publish("A", f"t{i}", ("sig", "A", i), 100 + i))
            time.sleep(0.01)
        on = [kc._kc_static_url_on_disk(u) for u in urls]
        self.assertEqual(on, [False, False] + [True] * kc.KC_STATIC_OWN_MAX_FILES)
        self.assertEqual(self.alive(b), dict.fromkeys(b, True))  # another session untouched

    def _age(self, owner: str, seconds: float) -> None:
        folder = self.s.root / owner
        t = time.time() - seconds
        os.utime(folder, (t, t))

    def test_active_session_folder_is_never_collected(self) -> None:
        _, b = self.s.session("B", 50)
        self._age("B", 10 * 3600)
        with mock.patch.object(kc, "KC_STATIC_BUDGET_BYTES", 1):  # even over budget
            self.s.owner = "A"
            kc._collect_inactive_static_dirs(force=True)
        self.assertEqual(self.alive(b), dict.fromkeys(b, True))

    def test_inactive_folder_survives_the_grace_period(self) -> None:  # phone dropped its socket
        _, b = self.s.session("B", 50)
        self.s.active = {"A"}
        self._age("B", kc.KC_STATIC_INACTIVE_GRACE_SEC - 60)
        self.s.owner = "A"
        kc._collect_inactive_static_dirs(force=True)
        self.assertEqual(self.alive(b), dict.fromkeys(b, True))

    def test_inactive_idle_folder_is_collected(self) -> None:
        _, b = self.s.session("B", 50)
        self.s.active = {"A"}
        self._age("B", kc.KC_STATIC_INACTIVE_GRACE_SEC + 60)
        self.s.owner = "A"
        kc._collect_inactive_static_dirs(force=True)
        self.assertFalse((self.s.root / "B").exists())

    def test_over_budget_collects_inactive_folders_after_the_short_grace(self) -> None:
        _, b = self.s.session("B", 50)
        self.s.active = {"A"}
        self._age("B", kc.KC_STATIC_PRESSURE_GRACE_SEC + 60)
        self.s.owner = "A"
        with mock.patch.object(kc, "KC_STATIC_BUDGET_BYTES", 1):
            kc._collect_inactive_static_dirs(force=True)
        self.assertFalse((self.s.root / "B").exists())

    def test_url_to_path_rejects_traversal(self) -> None:
        for bad in ("app/static/kc/../x.wav", "app/static/kc/a/../../x.wav", "app/static/kc/a/b/c.wav",
                    "/app/static/kc/A/x.wav", "app/static/kc/A/x.mp3"):
            self.assertIsNone(kc._kc_static_path(bad), bad)
        self.assertEqual(kc._kc_static_path("app/static/kc/A/x.wav"), self.s.root / "A" / "x.wav")


if __name__ == "__main__":
    unittest.main()
