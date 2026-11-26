"""The media catalog's cloud row is read by its own key, never found by scanning a short list (2026-11-25).

The catalog is one ``suite_saved_items`` row per workspace (item type ``music_media``, key
``workspace_media_catalog``). The read used to list the newest 10 rows of that type and look for the key; a row that
was not among them read as "no catalog" with no error, and the next save replaced it with this device's list.
These tests run against an in-memory table with the same unique key and newest-first ordering; no cloud is used.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

import media_persistence as mp

KEY, TYPE = mp.MEDIA_ITEM_KEY, mp.MEDIA_ITEM_TYPE


class Table:
    """suite_saved_items for one user and workspace: unique (item_type, item_key), listed newest first."""

    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}
        self.clock = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.fail_reads = False

    def put(self, item_type, item_key, payload, *, valid=True):
        self.clock += timedelta(seconds=1)
        self.rows[(item_type, item_key)] = {"item_type": item_type, "item_key": item_key, "payload": copy.deepcopy(payload),
                                            "valid": valid, "updated_at": self.clock.isoformat()}

    # the suite_account functions the app calls
    def load_saved_items(self, *, app=None, item_type=None, limit=100, **_k):
        if self.fail_reads:
            raise RuntimeError("503 simulated outage")
        rows = [r for r in self.rows.values() if r["valid"] and (item_type is None or r["item_type"] == item_type)]
        return [copy.deepcopy(r) for r in sorted(rows, key=lambda r: r["updated_at"], reverse=True)[:int(limit)]]

    def load_saved_item_state(self, item_type, item_key, *, app=None):
        if self.fail_reads:
            raise RuntimeError("503 simulated outage")
        r = self.rows.get((item_type, item_key))
        return copy.deepcopy(r) if r else None

    def remember_saved_item(self, app, item_type, item_key, *, title, payload=None):
        self.put(item_type, item_key, payload or {})
        return {"write_mode": "upsert"}


@pytest.fixture
def table(monkeypatch):
    import studio_history_cloud as shc
    import suite_account

    t = Table()
    monkeypatch.setattr(shc, "cloud_enabled", lambda: True)
    monkeypatch.setattr(shc, "active_workspace_id", lambda **_k: "daniel")
    for name in ("load_saved_items", "load_saved_item_state", "remember_saved_item"):
        monkeypatch.setattr(suite_account, name, getattr(t, name))
    local = {"cat": {}}
    monkeypatch.setattr(mp, "_resolve_workspace_id", lambda **_k: "daniel")
    monkeypatch.setattr(mp, "_load_local_catalog", lambda **_k: copy.deepcopy(local["cat"]) or mp._empty_catalog(workspace_id="daniel"))
    monkeypatch.setattr(mp, "_save_local_catalog", lambda c, **_k: (local.__setitem__("cat", copy.deepcopy(c)), (True, ""))[1])
    monkeypatch.setattr(mp, "_cloud_authoritative", lambda: True)
    t.local = local
    return t


def _docs(payload):
    return {r["document_id"] for r in (payload or {}).get("song_documents") or [] if not r.get("deleted")}


def _seed_catalog(table, ids):
    cat = mp._empty_catalog(workspace_id="daniel")
    cat["song_documents"] = [{"document_id": i, "source_type": "catalog", "source_id": "s", "title": i,
                              "updated_at": "2026-01-01T00:00:00+00:00", "workspace_id": "daniel"} for i in ids]
    table.put(TYPE, KEY, cat)


def _bury(table, n):
    """n newer rows of the same item type under other keys (not written by today's app, but possible in a table)."""
    for i in range(n):
        table.put(TYPE, f"other_{i:02d}", {"workspace_id": "daniel"})


@pytest.mark.parametrize("newer", [0, 9, 10, 11, 25])
def test_the_catalog_is_found_however_many_newer_rows_there_are(table, newer):
    _seed_catalog(table, ["a", "b", "c"])
    _bury(table, newer)
    payload, err = mp._load_cloud_catalog()
    assert err is None and _docs(payload) == {"a", "b", "c"}


@pytest.mark.parametrize("newer", [10, 11, 25])
def test_a_save_on_a_fresh_disk_keeps_every_cloud_row_however_many_newer_rows_there_are(table, newer):
    _seed_catalog(table, ["a", "b", "c"])
    _bury(table, newer)
    table.local["cat"] = {}
    assert mp.add_song_document(None, {"document_id": "d", "source_type": "catalog", "source_id": "s", "title": "d"})["ok"]
    assert _docs(table.rows[(TYPE, KEY)]["payload"]) == {"a", "b", "c", "d"}
    assert all(table.rows[(TYPE, f"other_{i:02d}")]["payload"] == {"workspace_id": "daniel"} for i in range(newer))


def test_no_catalog_row_at_all_is_an_empty_cloud_and_the_first_save_creates_it(table):
    _bury(table, 12)
    payload, err = mp._load_cloud_catalog()
    assert payload == {} and err is None
    assert mp.add_song_document(None, {"document_id": "first", "source_type": "catalog", "source_id": "s", "title": "x"})["ok"]
    assert _docs(table.rows[(TYPE, KEY)]["payload"]) == {"first"}


@pytest.mark.parametrize("bad", ["outage", "not_a_dict", "other_workspace"])
def test_an_undeterminable_cloud_row_fails_closed(table, bad):
    _seed_catalog(table, ["a", "b", "c"])
    if bad == "outage":
        table.fail_reads = True
    elif bad == "not_a_dict":
        table.rows[(TYPE, KEY)]["payload"] = ["not", "a", "catalog"]
    else:
        table.rows[(TYPE, KEY)]["payload"]["workspace_id"] = "someone-else"
    before = copy.deepcopy(table.rows[(TYPE, KEY)])
    table.local["cat"] = {}
    r = mp.add_song_document(None, {"document_id": "d", "source_type": "catalog", "source_id": "s", "title": "d"})
    assert r["ok"] is False and r["error"]
    assert table.rows[(TYPE, KEY)] == before                       # the cloud row is untouched
    assert "d" in _docs(table.local["cat"])                         # the change is kept on this device


def test_a_deleted_catalog_row_is_not_merged_back_in(table):
    _seed_catalog(table, ["old"])
    table.rows[(TYPE, KEY)]["valid"] = False
    payload, err = mp._load_cloud_catalog()
    assert payload == {} and err is None
