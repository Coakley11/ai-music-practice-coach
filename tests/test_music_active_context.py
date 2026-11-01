"""Active-context state machine against the local/mock store (no cloud claimed)."""
import threading

import pytest

import music_active_context as ac

ACC, WS = "acct-1", "daniel"
BOSSA = "Jazz\x1fBlue Bossa — Kenny Dorham"
SAY = "Pop\x1fSay — John Mayer"


def session(pick=BOSSA, inst="Tenor Sax", page="backing", key="Cm"):
    return {"_suite_active_workspace_id": WS, "studio_page": page, "active_catalog_pick_key": pick,
            "song": pick.split("\x1f")[-1].split(" —")[0], "instrument": inst, "display_key": key}


def flush(s, store, device="dev"):
    return ac.flush_intent(s, store, account_id=ACC, workspace_id=WS, device_id=device)


def adoptable(s, store, resume=False):
    return ac.pending_adoption(s, store, account_id=ACC, workspace_id=WS, explicit_resume_present=resume)


@pytest.fixture
def store(tmp_path):
    return ac.LocalFileActiveContextStore(tmp_path)


def test_publish_only_on_explicit_intent_never_on_hydration_or_rerun(store):
    phone = session()
    assert flush(phone, store) == "no_intent"  # hydration / rerun / render
    assert store.read(ACC, WS) is None
    ac.mark_intent(phone, "select")
    assert flush(phone, store, "phone") == "published"
    rec = store.read(ACC, WS)
    assert (rec.revision, rec.source_type, rec.instrument, rec.practice_key, rec.page, rec.device_id) == \
        (1, "catalog", "Tenor Sax", "Cm", "backing", "phone")
    for _ in range(3):  # reruns create nothing
        assert flush(phone, store) == "no_intent"
    assert store.read(ACC, WS).revision == 1


def test_same_context_does_not_burn_a_revision(store):
    s = session()
    ac.mark_intent(s)
    flush(s, store)
    ac.mark_intent(s)
    assert flush(s, store) == "unchanged"
    assert store.read(ACC, WS).revision == 1


def test_dell_adopts_phone_context_and_adoption_never_publishes(store):
    phone = session()
    ac.mark_intent(phone)
    flush(phone, store, "phone")
    dell = session(pick=SAY, inst="Guitar", page="practice", key="G")  # older hydrated state
    rec = adoptable(dell, store)
    assert rec is not None and rec.resource_id == BOSSA

    def apply(payload):
        ac.mark_intent(dell, "resume")  # apply_music_resume_payload does this for real
        dell.update(active_catalog_pick_key=payload["pick_key"], instrument=payload["instrument"],
                    display_key=payload["display_key"], studio_page=payload["studio_page"])
        return True

    assert ac.adopt(dell, rec, apply)
    assert flush(dell, store, "dell") == "no_intent"  # hydration created no revision
    assert store.read(ACC, WS).revision == 1 and ac.accepted_revision(dell) == 1
    assert adoptable(dell, store) is None  # cold start only


def test_explicit_resume_url_skips_adoption(store):
    phone = session()
    ac.mark_intent(phone)
    flush(phone, store)
    assert adoptable(session(pick=SAY), store, resume=True) is None


def test_dell_selection_then_phone_adopts_newer_revision(store):
    phone = session()
    ac.mark_intent(phone)
    flush(phone, store, "phone")
    dell = session(pick=SAY, inst="Guitar", page="practice", key="G")
    ac.mark_intent(dell)
    assert flush(dell, store, "dell") == "published"
    assert store.read(ACC, WS).revision == 2
    rec = adoptable(session(), store)  # phone reloads later (cold)
    assert rec.revision == 2 and rec.resource_id == SAY


def test_historical_resume_becomes_newest_and_stale_dell_rerun_cannot_overwrite(store):
    phone, dell = session(), session(pick=SAY, page="practice")
    for s, d in ((phone, "phone"), (dell, "dell")):
        ac.mark_intent(s)
        flush(s, store, d)
    assert store.read(ACC, WS).device_id == "dell"
    ac.mark_intent(phone, "resume")  # phone deliberately clicks an OLD Continue card
    assert flush(phone, store, "phone") == "published"
    rec = store.read(ACC, WS)
    assert rec.revision == 3 and rec.resource_id == BOSSA
    for _ in range(3):  # stale Dell keeps rerunning / hydrating
        assert flush(dell, store, "dell") == "no_intent"
    assert store.read(ACC, WS).revision == 3 and store.read(ACC, WS).device_id == "phone"


def test_conflict_older_intent_is_superseded_later_intent_wins(store):
    a, b = session(), session(pick=SAY)
    ac.mark_intent(a)  # a acts first...
    ac.mark_intent(b)  # ...b acts later
    assert flush(b, store, "b") == "published"
    assert flush(a, store, "a") == "superseded"  # a's earlier intent loses
    assert store.read(ACC, WS).device_id == "b" and store.read(ACC, WS).revision == 1
    ac.mark_intent(a, "select")  # a later intent from the stale session wins on top
    assert flush(a, store, "a") == "published"
    assert store.read(ACC, WS).revision == 2 and store.read(ACC, WS).device_id == "a"


class Boom:
    def read(self, *a):
        raise OSError("down")

    def compare_and_set(self, *a):
        raise OSError("down")


def test_failed_write_keeps_intent_and_never_touches_durable_state(store):
    s = session()
    before = dict(s)
    ac.mark_intent(s)
    assert flush(s, Boom()) == "store_error"
    assert s["_music_ctx_intent"]  # kept for a later retry
    assert {k: s[k] for k in before} == before  # durable Music state untouched
    assert flush(s, store) == "published"  # store recovered -> retried


def test_rejected_adoption_does_not_publish_or_retry(store):
    phone = session()
    ac.mark_intent(phone)
    flush(phone, store)
    dell = session(pick=SAY)
    rec = adoptable(dell, store)
    assert not ac.adopt(dell, rec, lambda p: False)  # e.g. resource missing on this device
    assert flush(dell, store) == "no_intent" and store.read(ACC, WS).revision == 1
    assert ac.accepted_revision(dell) == 0


def test_no_active_song_publishes_nothing(store):
    s = session(pick="")
    ac.mark_intent(s)
    assert flush(s, store) == "no_context" and store.read(ACC, WS) is None


def test_simultaneous_writers_get_unique_consecutive_revisions(store):
    results = []

    def writer(i):
        s = session(pick=f"Pop\x1fSong {i} — X")
        ac.mark_intent(s)
        results.append(flush(s, store, f"d{i}"))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    final = store.read(ACC, WS)
    assert final.revision == results.count("published") >= 1  # no duplicate or skipped revision
    assert set(results) <= {"published", "superseded", "conflict"}


def test_cas_rejects_wrong_expected_revision(store):
    s = session()
    ac.mark_intent(s)
    flush(s, store)
    stale = ac.ActiveContext(**{**store.read(ACC, WS).to_dict(), "revision": 2})
    assert not store.compare_and_set(0, stale).ok and not store.compare_and_set(5, stale).ok
    assert store.read(ACC, WS).revision == 1


def test_feature_is_dark_by_default(monkeypatch):
    monkeypatch.delenv(ac.ENV_MODE, raising=False)
    assert ac.get_store() is None
    monkeypatch.setenv(ac.ENV_MODE, "local")
    assert isinstance(ac.get_store(), ac.LocalFileActiveContextStore)


def test_songs_page_queued_pick_records_intent_but_hydration_apply_does_not():
    from types import SimpleNamespace

    from songs.state import queue_pending_catalog_pick

    st = SimpleNamespace(session_state={})
    queue_pending_catalog_pick(st, SAY)
    assert st.session_state["_music_ctx_intent"]["cause"] == "select"
    quiet = SimpleNamespace(session_state={})
    queue_pending_catalog_pick(quiet, "")  # nothing queued -> no intent
    assert "_music_ctx_intent" not in quiet.session_state
