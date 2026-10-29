"""The published currentUrl is the WAV of the CURRENT cycling key, never the Play-time WAV.

The browser treats a command whose sounding key matches the buffer it is playing but whose
currentUrl does not match that buffer as "a new arrangement file for this key" and reloads it.
After a key change the Play-time URL belongs to a different key, so publishing it put the old
key's audio under the new key's label.
"""
from __future__ import annotations

import backing_key_cycle as kc
from tests.test_backing_key_cycle_ui_contract import _session

SIG = ("song", "C", "lvl", "feel", 100, "4/4", 2, ("Verse",), 0, False, "p", 10, 4, 0, "arr_v2")


def _make(monkeypatch, *, current_key: str, cur_url: str, entries: dict) -> dict:
    monkeypatch.setattr(kc, "_kc_static_url_on_disk", lambda _u: True)
    session = _session()
    kc.start_key_cycle(session, start_key="C")
    owner = kc.resolve_cycle_owner(session)
    data = dict(kc.get_owner_cycle_session(session))
    data["current_playback_key"] = current_key
    kc._put_owner_cycle_session(session, owner, data)
    session["_last_backing_signature"] = SIG
    from backing_take_identity import capture_take_request

    request = capture_take_request(session, prefetch=True)
    session[kc.BACKING_KEY_CYCLE_PREPARED_KEY] = {
        k: {"take_request": request, "signature": SIG, "path": f"/tmp/{k}.wav", "static_url": url} for k, url in entries.items()
    }
    session["_kc_current_static_url"] = cur_url
    for flag in ("_kc_force_arrangement_replace", "_kc_arrangement_reload", "_kc_arrangement_url"):
        session.pop(flag, None)
    return session


def test_stale_play_url_is_replaced_by_current_keys_prepared_url(monkeypatch) -> None:
    s = _make(monkeypatch, current_key="Db", cur_url="/kc/C.wav", entries={"C": "/kc/C.wav", "Db": "/kc/Db.wav"})
    assert kc.authoritative_cycle_current_url(s, "/kc/C.wav") == "/kc/Db.wav"


def test_url_of_another_key_is_not_published_when_current_keys_file_is_missing(monkeypatch) -> None:
    s = _make(monkeypatch, current_key="Db", cur_url="/kc/C.wav", entries={"C": "/kc/C.wav"})
    assert kc.authoritative_cycle_current_url(s, "/kc/C.wav") == ""


def test_explicit_play_replace_keeps_its_own_url(monkeypatch) -> None:
    s = _make(monkeypatch, current_key="Db", cur_url="/kc/NEW.wav", entries={"C": "/kc/C.wav", "Db": "/kc/Db_old.wav"})
    s["_kc_force_arrangement_replace"] = True
    assert kc.authoritative_cycle_current_url(s, "/kc/NEW.wav") == "/kc/NEW.wav"


def test_prepared_entry_from_another_arrangement_is_not_used(monkeypatch) -> None:
    s = _make(monkeypatch, current_key="Db", cur_url="/kc/NEW.wav", entries={"Db": "/kc/Db_old.wav"})
    s["_last_backing_signature"] = ("song", "C", "lvl", "feel", 120, "4/4", 2, ("Verse",), 0, False, "p", 10, 4, 0, "arr_v2")
    assert kc.authoritative_cycle_current_url(s, "/kc/NEW.wav") == "/kc/NEW.wav"


def test_matching_current_url_is_untouched(monkeypatch) -> None:
    s = _make(monkeypatch, current_key="C", cur_url="/kc/C.wav", entries={"C": "/kc/C.wav", "Db": "/kc/Db.wav"})
    assert kc.authoritative_cycle_current_url(s, "/kc/C.wav") == "/kc/C.wav"
