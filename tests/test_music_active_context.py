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



# ----------------------------------------------------------- semantic-delta hardening

WAVE = "Pop\x1fWave — Antonio Carlos Jobim"
CUSTOM = "custom::My Progression"
COMP = "composition::My Composition"


def seed(store, pick=WAVE, inst="Guitar", page="backing", key="D", device="phone"):
    s = session(pick=pick, inst=inst, page=page, key=key)
    ac.mark_intent(s, "song_selected")
    assert flush(s, store, device) == "published"
    return s


def stale_dell():
    """Dell still shows Blue Bossa / Practice / Saxophone from before the phone moved on."""
    return session(pick=BOSSA, inst="Saxophone", page="practice", key="C")


def content(store):
    r = store.read(ACC, WS)
    return r.resource_id, r.page, r.instrument, r.practice_key, r.revision


def test_stale_instrument_change_does_not_resurrect_song_or_page(store):
    seed(store)
    dell = stale_dell()
    dell["instrument"] = "Flute"
    ac.mark_intent(dell, "instrument_changed")
    assert flush(dell, store, "dell") == "published"
    assert content(store) == (WAVE, "backing", "Flute", "D", 2)


def test_stale_practice_key_intent_against_a_replaced_resource_is_discarded(store):
    seed(store)  # shared: Wave / backing / Guitar / D
    dell = stale_dell()  # Blue Bossa, C minor
    dell["display_key"] = "Ebm"
    ac.mark_intent(dell, "practice_key_changed")
    assert flush(dell, store, "dell") == "discarded"
    assert content(store) == (WAVE, "backing", "Guitar", "D", 1)  # no translation, no guess
    assert "_music_ctx_intent" not in dell


def test_stale_practice_key_intent_on_the_same_resource_merges(store):
    seed(store, pick=BOSSA, key="Cm")
    other = session(pick=BOSSA, inst="Saxophone", page="practice", key="Cm")
    other["display_key"] = "Dm"
    ac.mark_intent(other, "practice_key_changed")
    assert flush(other, store, "dell") == "published"
    assert content(store) == (BOSSA, "backing", "Guitar", "Dm", 2)  # newest page/instrument kept


def test_older_practice_key_intent_is_superseded_by_a_newer_one(store):
    seed(store)
    a, b = session(pick=WAVE), session(pick=WAVE)
    a["display_key"], b["display_key"] = "E", "F"
    ac.mark_intent(a, "practice_key_changed")
    ac.mark_intent(b, "practice_key_changed")
    assert flush(b, store, "b") == "published"
    assert flush(a, store, "a") == "superseded"
    assert content(store)[3] == "F"


def test_song_selected_carries_its_own_practice_key(store):
    seed(store)
    dell = session(pick=BOSSA, inst="Saxophone", page="practice", key="Cm")
    ac.mark_intent(dell, "song_selected")
    assert flush(dell, store, "dell") == "published"
    assert content(store)[0] == BOSSA and content(store)[3] == "Cm"


def test_resume_owns_and_restores_the_practice_key(store):
    seed(store)
    old = session(pick=BOSSA, inst="Saxophone", page="practice", key="Cm")
    ac.mark_intent(old, "resume")
    flush(old, store, "phone")
    assert content(store)[3] == "Cm"
    assert ac.payload_for_adoption(store.read(ACC, WS))["display_key"] == "Cm"


@pytest.mark.parametrize("a_pick,b_pick", [(CUSTOM, WAVE), (COMP, CUSTOM), (WAVE, COMP), (CUSTOM, COMP)])
def test_practice_key_resource_dependency_holds_for_custom_and_composition(store, a_pick, b_pick):
    seed(store, pick=b_pick)
    stale = session(pick=a_pick, page="creative", key="Ebm")
    ac.mark_intent(stale, "practice_key_changed")
    assert flush(stale, store, "dell") == "discarded"
    assert content(store)[3] == "D"
    same = session(pick=b_pick, key="G")
    ac.mark_intent(same, "practice_key_changed")
    assert flush(same, store, "dell") == "published" and content(store)[3] == "G"


def test_standalone_practice_key_change_publishes_and_peer_adopts_canonical_key(store):
    phone = seed(store)
    phone["display_key"] = "F"
    ac.mark_intent(phone, "key")  # legacy alias used by mark_display_key_changed
    assert flush(phone, store, "phone") == "published"
    rec = adoptable(session(pick=SAY), store)
    assert ac.payload_for_adoption(rec)["display_key"] == "F"
    assert ac.payload_for_adoption(rec)["key_kind"] == "concert"


def test_key_cycling_sounding_key_never_enters_the_record(store):
    s = seed(store)
    s.update(backing_key_cycle_sounding_key="G", key_cycle_current_key="G", backing_sounding_key="G")
    ac.mark_intent(s, "instrument_changed")
    flush(s, store)
    assert store.read(ACC, WS).practice_key == "D"


def test_explicit_stale_song_selection_legitimately_wins(store):
    seed(store)
    dell = stale_dell()
    ac.mark_intent(dell, "song_selected")
    assert flush(dell, store, "dell") == "published"
    assert content(store)[0] == BOSSA and content(store)[2] == "Guitar"  # instrument stays the latest


def test_stale_workflow_change_for_a_replaced_resource_is_discarded(store):
    seed(store)  # shared: Wave / backing
    dell = stale_dell()
    dell["studio_page"] = "creative"
    ac.mark_intent(dell, "workflow_selected")
    assert flush(dell, store, "dell") == "discarded"
    assert content(store) == (WAVE, "backing", "Guitar", "D", 1)
    assert "_music_ctx_intent" not in dell


def test_workflow_change_on_the_current_resource_publishes(store):
    seed(store)
    phone = session(pick=WAVE, inst="Guitar", page="practice", key="D")
    ac.mark_intent(phone, "workflow_selected")
    assert flush(phone, store, "phone") == "published"
    assert content(store) == (WAVE, "practice", "Guitar", "D", 2)


def test_historical_resume_wins_and_becomes_the_new_revision(store):
    seed(store)
    old = session(pick=BOSSA, inst="Saxophone", page="practice", key="C")
    ac.mark_intent(old, "resume")
    assert flush(old, store, "phone") == "published"
    assert content(store) == (BOSSA, "practice", "Saxophone", "C", 2)
    assert store.read(ACC, WS).cause == "resume"


def test_earlier_conflicting_resource_choice_loses_to_later_one(store):
    a, b = session(pick=BOSSA), session(pick=SAY)
    ac.mark_intent(a, "song_selected")
    ac.mark_intent(b, "song_selected")
    assert flush(b, store, "b") == "published"
    assert flush(a, store, "a") == "superseded"
    assert content(store)[0] == SAY and content(store)[4] == 1


def test_independent_compatible_deltas_both_survive_in_either_order(store):
    for order in ((0, 1), (1, 0)):
        st = ac.LocalFileActiveContextStore(store.root / f"o{order[0]}")
        seed(st)
        a = session(pick=WAVE, inst="Guitar", page="backing", key="D")
        b = session(pick=WAVE, inst="Guitar", page="backing", key="D")
        a["instrument"], b["display_key"] = "Flute", "Eb"
        ac.mark_intent(a, "instrument_changed")
        ac.mark_intent(b, "practice_key_changed")
        for i in order:
            assert flush((a, b)[i], st, f"d{i}") == "published"
        assert content(st)[:4] == (WAVE, "backing", "Flute", "Eb")
        assert content(st)[4] == 3


def test_instrument_intent_older_than_a_newer_instrument_change_is_superseded(store):
    seed(store)
    a, b = session(pick=WAVE), session(pick=WAVE)
    a["instrument"], b["instrument"] = "Flute", "Trumpet"
    ac.mark_intent(a, "instrument_changed")
    ac.mark_intent(b, "instrument_changed")
    assert flush(b, store, "b") == "published"
    assert flush(a, store, "a") == "superseded"
    assert content(store)[2] == "Trumpet"


def test_cas_race_reevaluates_against_the_winner(store):
    seed(store)
    dell = stale_dell()
    dell["instrument"] = "Flute"
    ac.mark_intent(dell, "instrument_changed")

    class Racing:
        """Another device wins the first CAS between our read and our write."""
        def __init__(self, inner):
            self.inner, self.raced = inner, False

        def read(self, *a):
            return self.inner.read(*a)

        def compare_and_set(self, expected, record):
            if not self.raced:
                self.raced = True
                phone = session(pick=SAY, inst="Guitar", page="practice", key="G")
                ac.mark_intent(phone, "song_selected")
                assert ac.flush_intent(phone, self.inner, account_id=ACC, workspace_id=WS,
                                       device_id="phone") == "published"
            return self.inner.compare_and_set(expected, record)

    assert flush(dell, Racing(store), "dell") == "published"
    assert content(store) == (SAY, "practice", "Flute", "G", 3)  # winner's song kept, our delta added


def test_passive_initialisation_publishes_nothing_and_first_intent_creates_revision_1(store):
    fresh = session(pick=SAY, page="practice")  # default Songs init, no intent
    assert flush(fresh, store) == "no_intent" and store.read(ACC, WS) is None
    ac.mark_intent(fresh, "bogus")  # unknown causes are never inferred into intent
    assert flush(fresh, store) == "no_intent" and store.read(ACC, WS) is None
    for cause in ("workflow_selected", "instrument_changed", "practice_key_changed"):
        ac.mark_intent(fresh, cause)  # Songs nav / instrument change on a default song
    assert flush(fresh, store) == "discarded" and store.read(ACC, WS) is None
    ac.mark_intent(fresh, "song_selected")  # first deliberate resource choice
    assert flush(fresh, store) == "published" and store.read(ACC, WS).revision == 1


def test_adopting_never_marks_intent(store):
    seed(store)
    dell = stale_dell()
    rec = adoptable(dell, store)

    def apply(payload):
        for cause in ("song_selected", "workflow_selected", "instrument_changed", "practice_key_changed"):
            ac.mark_intent(dell, cause)
        return True

    assert ac.adopt(dell, rec, apply)
    assert flush(dell, store) == "no_intent" and store.read(ACC, WS).revision == 1


def test_newer_context_available_is_non_mutating_and_does_not_redirect(store):
    kw = dict(account_id=ACC, workspace_id=WS)
    dell = stale_dell()
    assert ac.newer_context_available(dell, store, **kw) is None  # nothing shared yet
    seed(store)
    before = dict(dell)
    rec = ac.newer_context_available(dell, store, **kw)
    assert rec is not None and rec.resource_id == WAVE
    assert dict(dell) == before and store.read(ACC, WS).revision == 1  # read-only
    assert ac.newer_context_available(dell, None, **kw) is None
    in_sync = session(pick=WAVE, inst="Guitar", page="backing", key="D")
    assert ac.newer_context_available(in_sync, store, **kw) is None


def test_stale_merge_publish_leaves_the_tab_reporting_a_newer_shared_context(store):
    seed(store)
    dell = stale_dell()
    dell["instrument"] = "Flute"
    ac.mark_intent(dell, "instrument_changed")
    flush(dell, store, "dell")
    rec = ac.newer_context_available(dell, store, account_id=ACC, workspace_id=WS)
    assert rec is not None and rec.resource_id == WAVE  # Dell still shows Blue Bossa


def test_custom_and_composition_identities_round_trip(store):
    for pick, kind in ((CUSTOM, "custom"), (COMP, "composition"), (BOSSA, "catalog")):
        s = session(pick=pick, page="creative" if kind != "catalog" else "practice")
        ac.mark_intent(s, "song_selected")
        flush(s, store, "p")
        rec = store.read(ACC, WS)
        assert (rec.source_type, rec.resource_id) == (kind, pick)
        payload = ac.payload_for_adoption(rec)
        assert payload["source_type"] == kind and payload["pick_key"] == pick


def test_failed_publish_does_not_rewrite_unrelated_context(store):
    seed(store)
    dell = stale_dell()
    dell["instrument"] = "Flute"
    ac.mark_intent(dell, "instrument_changed")
    assert flush(dell, Boom()) == "store_error"
    assert content(store) == (WAVE, "backing", "Guitar", "D", 1)
    assert flush(dell, store) == "published"  # retry merges, still without stale song
    assert content(store) == (WAVE, "backing", "Flute", "D", 2)


def test_records_are_scoped_by_account_and_workspace_and_never_cross(store):
    """6c898773 can change WHICH workspace a restarted device resolves; the record stays keyed by
    (account, resolved workspace), so a different workspace or account never sees or adopts it."""
    seed(store)
    assert store.read(ACC, "ariel") is None and store.read("acct-2", WS) is None
    other_ws = session(pick=SAY)
    other_ws["_suite_active_workspace_id"] = "ariel"
    assert ac.pending_adoption(other_ws, store, account_id=ACC, workspace_id="ariel",
                               explicit_resume_present=False) is None
    ac.mark_intent(other_ws, "song_selected")
    assert ac.flush_intent(other_ws, store, account_id=ACC, workspace_id="ariel", device_id="d") == "published"
    assert store.read(ACC, WS).resource_id == WAVE and store.read(ACC, "ariel").resource_id == SAY
