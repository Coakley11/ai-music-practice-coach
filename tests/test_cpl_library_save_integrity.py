"""Custom library saves must never overwrite or lose a different song's data."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from custom_progression_lab import (
    delete_progression,
    save_progression,
    save_progression_named,
)

ROOT = Path(__file__).resolve().parents[1]


def _song(name: str, song_id: str, chords: list[tuple[str, float]]) -> dict:
    return {
        "id": song_id,
        "name": name,
        "original_key_center": "F",
        "time_signature": "6/8",
        "bpm": 137,
        "progression_style": "Jazz",
        "groove_style": "Auto",
        "original_sections": {
            "Verse": [{"chord": c, "bars": b} for c, b in chords],
            "Chorus": [{"chord": "Fm6/Ab", "bars": 2}],
        },
        "lyrics_by_section": {"Verse": "line one\nline two"},
    }


class TestSaveNeverOverwritesAnotherSong(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch("custom_song_library.upsert_custom_song_to_cloud", return_value=(True, "k", None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_same_name_different_id_is_kept_separately(self) -> None:
        store: dict = {}
        a = _song("My Progression", "id-a", [("C", 1), ("Am", 1)])
        b = _song("My Progression", "id-b", [("F", 2), ("Fm6", 0.5)])
        save_progression(store, "My Progression", a)
        name_b = save_progression_named(store, "My Progression", b)
        self.assertEqual(len(store), 2)
        self.assertEqual(store["My Progression"]["id"], "id-a")
        self.assertEqual(store[name_b]["id"], "id-b")
        self.assertNotEqual(name_b, "My Progression")
        self.assertEqual(
            [e["chord"] for e in store["My Progression"]["original_sections"]["Verse"]], ["C", "Am"]
        )
        self.assertEqual(store["My Progression"]["lyrics_by_section"]["Verse"], "line one\nline two")

    def test_resaving_same_song_updates_in_place(self) -> None:
        store: dict = {}
        song = _song("Tune", "id-1", [("C", 1)])
        save_progression(store, "Tune", song)
        song["original_sections"]["Verse"].append({"chord": "G7", "bars": 1})
        name = save_progression_named(store, "Tune", song)
        self.assertEqual(name, "Tune")
        self.assertEqual(len(store), 1)
        self.assertEqual(len(store["Tune"]["original_sections"]["Verse"]), 2)

    def test_third_collision_gets_next_free_name(self) -> None:
        store: dict = {}
        for i in range(3):
            save_progression(store, "Song", _song("Song", f"id-{i}", [("C", 1)]))
        self.assertEqual(len(store), 3)
        self.assertEqual({v["id"] for v in store.values()}, {"id-0", "id-1", "id-2"})

    def test_rename_does_not_leave_two_entries_with_one_id(self) -> None:
        store: dict = {}
        song = _song("Old Title", "id-x", [("C", 1), ("Dm", 1)])
        save_progression(store, "Old Title", song)
        renamed = copy.deepcopy(song)
        renamed["name"] = "New Title"
        save_progression(store, "New Title", renamed)
        ids = [v["id"] for v in store.values()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(store["New Title"]["id"], "id-x")
        self.assertIn("Old Title", store)  # nothing was deleted

    def test_delete_only_removes_the_named_song(self) -> None:
        store: dict = {}
        save_progression(store, "A", _song("A", "id-a", [("C", 1)]))
        save_progression(store, "B", _song("B", "id-b", [("D", 1)]))
        delete_progression(store, "A")
        self.assertEqual(list(store), ["B"])


class TestCloudFailureIsRecorded(unittest.TestCase):
    def test_failure_with_cloud_configured_is_reported(self) -> None:
        import custom_progression_lab as lab

        with mock.patch("custom_song_library.upsert_custom_song_to_cloud", return_value=(False, "", "boom")), mock.patch(
            "custom_song_library.cloud_enabled", return_value=True
        ):
            save_progression({}, "X", _song("X", "id-x", [("C", 1)]))
        self.assertTrue(lab.LAST_CLOUD_SAVE_RESULT["configured"])
        self.assertFalse(lab.LAST_CLOUD_SAVE_RESULT["ok"])
        self.assertEqual(lab.LAST_CLOUD_SAVE_RESULT["error"], "boom")

    def test_unconfigured_cloud_is_not_reported_as_failure(self) -> None:
        import custom_progression_lab as lab

        with mock.patch("custom_song_library.upsert_custom_song_to_cloud", return_value=(False, "", "cloud_disabled")), mock.patch(
            "custom_song_library.cloud_enabled", return_value=False
        ):
            save_progression({}, "X", _song("X", "id-x", [("C", 1)]))
        self.assertFalse(lab.LAST_CLOUD_SAVE_RESULT["configured"])


class TestFreshProcessRoundTrip(unittest.TestCase):
    def test_full_chord_data_survives_a_new_process(self) -> None:
        song = _song("Round Trip", "id-rt", [("C:3.5|Am:0.5p", 1), ("Fm6/Ab", 0.5), ("Db7", 4), ("%", 1)])
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "state.json"
            writer = (
                "import json,sys;from unittest import mock;"
                "from custom_progression_lab import save_progression;"
                f"song=json.loads({json.dumps(json.dumps(song))});store={{}};"
                "mock.patch('custom_song_library.upsert_custom_song_to_cloud',return_value=(True,'k',None)).start();"
                "save_progression(store,'Round Trip',song);"
                f"open({str(blob)!r},'w').write(json.dumps(store))"
            )
            subprocess.run([sys.executable, "-c", writer], cwd=ROOT, check=True)
            reader = (
                "import json;"
                f"d=json.loads(open({str(blob)!r}).read());e=d['Round Trip'];"
                "print(json.dumps({'v':[x['chord'] for x in e['original_sections']['Verse']],"
                "'b':[x['bars'] for x in e['original_sections']['Verse']],'ts':e['time_signature'],'bpm':e['bpm'],"
                "'id':e['id'],'ly':e['lyrics_by_section']}))"
            )
            out = subprocess.run([sys.executable, "-c", reader], cwd=ROOT, check=True, capture_output=True, text=True)
        got = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(got["v"], ["C:3.5|Am:0.5p", "Fm6/Ab", "Db7", "%"])
        self.assertEqual(got["b"], [1, 0.5, 4, 1])
        self.assertEqual((got["ts"], got["bpm"], got["id"]), ("6/8", 137, "id-rt"))
        self.assertEqual(got["ly"], {"Verse": "line one\nline two"})


if __name__ == "__main__":
    unittest.main()
