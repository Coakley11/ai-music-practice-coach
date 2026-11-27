import pytest

from monetization_billing import BillingError, CheckoutService, CustomerRecord, InMemoryBillingStore, VerifiedUser
from monetization_supabase import SupabaseBillingStore
from tests.test_monetization_m2 import FakeStripe, _config


def test_customer_cannot_be_shared_or_rebound():
    store = InMemoryBillingStore()
    store.upsert_customer(CustomerRecord("owner", "cus_owner"))
    for row in (CustomerRecord("other", "cus_owner"), CustomerRecord("owner", "cus_other")):
        with pytest.raises(BillingError):
            store.upsert_customer(row)
    assert store.customer_for_user("owner").stripe_customer_id == "cus_owner"
    assert store.customer_for_user("other") is None


def test_repeated_checkout_reuses_persisted_owner():
    store = InMemoryBillingStore()
    stripe = FakeStripe()
    service = CheckoutService(_config(), store, stripe)
    service.create(VerifiedUser("owner"), interval="monthly")
    service.create(VerifiedUser("owner"), interval="monthly")
    assert len(store.customers_by_user) == 1
    assert {call["customer_id"] for call in stripe.checkout_calls} == {"cus_owner"}
    assert store.entitlement_for_user("owner") is None


def test_empty_stripe_customer_never_starts_checkout():
    stripe = FakeStripe()
    stripe.create_customer = lambda **kwargs: ""
    store = InMemoryBillingStore()
    with pytest.raises(BillingError):
        CheckoutService(_config(), store, stripe).create(VerifiedUser("owner"), interval="monthly")
    assert not stripe.checkout_calls
    assert not store.customers_by_user


@pytest.mark.parametrize("persisted", ["cus_requested", "cus_concurrent"])
def test_durable_customer_insert_never_overwrites_and_checks_winner(persisted):
    calls = []

    class Client:
        def request(self, method, path, **kwargs):
            calls.append((method, path, kwargs))
            if method == "GET":
                return [{"app_user_id": "owner", "stripe_customer_id": persisted}]

    store = SupabaseBillingStore(_config())
    store.client = Client()
    row = CustomerRecord("owner", "cus_requested")
    if persisted != row.stripe_customer_id:
        with pytest.raises(BillingError, match="ownership conflict"):
            store.upsert_customer(row)
    else:
        store.upsert_customer(row)
    assert calls[0][1] == "rpc/music_billing_attach_customer"
    assert calls[0][2]["json_body"] == {"p_user_id": "owner", "p_customer_id": "cus_requested"}


def test_wrong_owner_returned_by_store_cannot_start_checkout():
    store = InMemoryBillingStore()
    store.customers_by_user["owner"] = CustomerRecord("other", "cus_other")
    stripe = FakeStripe()
    with pytest.raises(BillingError, match="ownership"):
        CheckoutService(_config(), store, stripe).create(VerifiedUser("owner"), interval="monthly")
    assert not stripe.checkout_calls
