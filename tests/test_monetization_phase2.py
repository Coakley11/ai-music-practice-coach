from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from monetization_billing import (
    AuthenticationRequired, BillingError, BillingUnavailable, CheckoutService,
    CustomerRecord, InMemoryBillingStore, WebhookBusy, WebhookProcessor,
    VerifiedUser, derive_entitlement,
)
from monetization_entitlements import Feature, Plan, SubscriptionStatus, access_decision
from monetization_service import StripeHttpGateway, app
from monetization_supabase import SupabaseBillingStore, _derived
from tests.test_monetization_m2 import FakeStripe, _config, _event, _subscription


@pytest.fixture
def runtime(monkeypatch):
    class Clock(datetime):
        instant = datetime(2026, 11, 11, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.instant if tz else cls.instant.replace(tzinfo=None)

    for module in ('monetization_billing', 'monetization_entitlements', 'monetization_supabase'):
        monkeypatch.setattr(f'{module}.datetime', Clock)
    store = InMemoryBillingStore()
    store.upsert_customer(CustomerRecord('user-1', 'cus_1'))
    stripe = FakeStripe()
    stripe.portal_calls = []

    def create_portal(**kwargs):
        stripe.portal_calls.append(kwargs)
        return {'url': 'https://billing.stripe.com/p/session_test'}

    stripe.create_portal = create_portal
    stripe.subscriptions['sub_1'] = _subscription(status='active')
    return store, stripe, WebhookProcessor(_config(), store, stripe), Clock


def deliver(runtime, event_id='evt_1', kind='customer.subscription.updated', created=100, payload=None):
    store, stripe, processor, _ = runtime
    event = _event(payload or stripe.subscriptions['sub_1'], event_id=event_id, created=created)
    event['type'] = kind
    return processor.process(event)


def test_free_to_pro_and_renewal_with_current_item_period(runtime):
    store, stripe, _, clock = runtime
    assert store.entitlement_for_user('user-1') is None
    sub = stripe.subscriptions['sub_1']
    del sub['current_period_end']
    end = clock.instant + timedelta(days=30)
    sub['items']['data'].insert(0, {'price': {'id': 'price_unrelated'}})
    sub['items']['data'][1]['current_period_end'] = int(end.timestamp())
    deliver(runtime, kind='customer.subscription.created')
    assert store.entitlement_for_user('user-1').plan is Plan.PRO
    assert store.entitlement_for_user('user-1').current_period_end == end
    sub['items']['data'][1]['current_period_end'] += 30 * 86400
    invoice = {'customer': 'cus_1', 'parent': {'subscription_details': {'subscription': {'id': 'sub_1'}}}}
    deliver(runtime, 'evt_renew', 'invoice.paid', payload=invoice)
    assert store.entitlement_for_user('user-1').current_period_end == end + timedelta(days=30)


def test_scheduled_cancellation_expires_without_final_webhook(runtime):
    store, stripe, _, clock = runtime
    sub = stripe.subscriptions['sub_1']
    sub['cancel_at_period_end'] = True
    end = clock.instant + timedelta(days=1)
    sub['current_period_end'] = int(end.timestamp())
    deliver(runtime)
    entitlement = store.entitlement_for_user('user-1')
    assert entitlement.status is SubscriptionStatus.CANCELED_PERIOD_END
    assert entitlement.as_product_entitlement().grants_pro
    clock.instant = end
    assert not entitlement.as_product_entitlement().grants_pro  # cached object also expires
    assert store.entitlement_for_user('user-1').plan is Plan.FREE
    assert not access_decision(Feature.COMPOSITION_STUDIO,
        entitlement=entitlement.as_product_entitlement(), environ={'MUSIC_BILLING_ROLLOUT': 'test'}).allowed


@pytest.mark.parametrize('kind', ['customer.subscription.updated', 'customer.subscription.deleted'])
def test_immediate_termination(runtime, kind):
    store, stripe, _, _ = runtime
    deliver(runtime)
    stripe.subscriptions['sub_1']['status'] = 'canceled'
    deliver(runtime, 'evt_end', kind)
    assert store.entitlement_for_user('user-1').plan is Plan.FREE


@pytest.mark.parametrize('status,paid', [('active', True), ('past_due', False), ('unpaid', False), ('incomplete', False)])
def test_failed_invoice_respects_actual_status_then_recovers(runtime, status, paid):
    store, stripe, _, _ = runtime
    deliver(runtime)
    stripe.subscriptions['sub_1']['status'] = status
    invoice = {'customer': 'cus_1', 'subscription': 'sub_1'}
    deliver(runtime, 'evt_fail', 'invoice.payment_failed', payload=invoice)
    assert store.entitlement_for_user('user-1').as_product_entitlement().grants_pro is paid
    stripe.subscriptions['sub_1']['status'] = 'active'
    deliver(runtime, 'evt_recover', 'invoice.paid', payload=invoice)
    assert store.entitlement_for_user('user-1').plan is Plan.PRO


def test_duplicate_does_not_fetch_again_and_collision_fails(runtime, monkeypatch):
    _, stripe, processor, _ = runtime
    event = _event(stripe.subscriptions['sub_1'], event_id='evt_same', created=100)
    processor.process(event)
    monkeypatch.setattr(stripe, 'retrieve_subscription', lambda _: pytest.fail('duplicate fetched provider'))
    assert processor.process(event) == 'duplicate'
    changed = deepcopy(event)
    changed['created'] = 101
    with pytest.raises(BillingError, match='identity conflict'):
        processor.process(changed)


@pytest.mark.parametrize('created,event_id', [(1, 'evt_a'), (100, 'evt_a'), (200, 'evt_z')])
def test_old_or_equal_time_event_always_fetches_current_status(runtime, created, event_id):
    store, stripe, _, _ = runtime
    deliver(runtime, 'evt_m', created=100)
    old_payload = deepcopy(stripe.subscriptions['sub_1'])
    stripe.subscriptions['sub_1']['status'] = 'past_due'
    deliver(runtime, event_id, created=created, payload=old_payload)
    assert store.entitlement_for_user('user-1').plan is Plan.FREE


def test_busy_customer_returns_retry_and_serializes_different_events(runtime, monkeypatch):
    store, stripe, _, _ = runtime
    original = stripe.retrieve_subscription

    def retrieve(sub_id):
        with pytest.raises(WebhookBusy):
            deliver(runtime, 'evt_concurrent')
        return original(sub_id)

    monkeypatch.setattr(stripe, 'retrieve_subscription', retrieve)
    deliver(runtime)
    assert 'evt_concurrent' not in store.events
    monkeypatch.setattr(stripe, 'retrieve_subscription', original)
    assert deliver(runtime, 'evt_concurrent') == 'processed'


def test_failed_atomic_commit_retries_without_partial_subscription(runtime, monkeypatch):
    store, _, _, _ = runtime
    original = store.complete_delivery

    def unavailable(*args):
        raise BillingError('database unavailable')

    monkeypatch.setattr(store, 'complete_delivery', unavailable)
    with pytest.raises(BillingError):
        deliver(runtime)
    assert not store.subscriptions and not store.entitlements
    assert store.events['evt_1']['state'] == 'failed'
    monkeypatch.setattr(store, 'complete_delivery', original)
    assert deliver(runtime) == 'processed'
    assert store.entitlement_for_user('user-1').plan is Plan.PRO


def test_response_lost_after_atomic_commit_is_safe_to_replay(runtime, monkeypatch):
    store, _, _, _ = runtime
    original = store.complete_delivery

    def committed_then_disconnected(*args):
        original(*args)
        raise OSError('response lost')

    monkeypatch.setattr(store, 'complete_delivery', committed_then_disconnected)
    with pytest.raises(OSError):
        deliver(runtime)
    assert store.events['evt_1']['state'] == 'processed'
    assert store.entitlement_for_user('user-1').plan is Plan.PRO
    assert deliver(runtime) == 'duplicate'


def test_expired_lease_worker_cannot_commit_or_fail_new_worker(runtime, monkeypatch):
    store, stripe, processor, _ = runtime
    event = _event(stripe.subscriptions['sub_1'], event_id='evt_lease', created=100)
    old = store.claim_delivery(event, 'cus_1')
    store.events['evt_lease']['expires'] = 0
    new = store.claim_delivery(event, 'cus_1')
    record = processor._record(stripe.subscriptions['sub_1'], event_id='evt_lease', created=100)
    entitlement = derive_entitlement(record, known_price_ids=_config().known_price_ids)
    with pytest.raises(WebhookBusy):
        store.complete_delivery('evt_lease', old, record, entitlement)
    store.fail_delivery('evt_lease', old)
    assert store.events['evt_lease']['token'] == new
    store.complete_delivery('evt_lease', new, record, entitlement)


def test_old_subscription_deletion_does_not_revoke_new_subscription(runtime):
    store, stripe, _, _ = runtime
    deliver(runtime)
    sub2 = deepcopy(stripe.subscriptions['sub_1'])
    sub2['id'] = 'sub_2'
    stripe.subscriptions['sub_2'] = sub2
    deliver(runtime, 'evt_other', payload=sub2)
    stripe.subscriptions['sub_1']['status'] = 'canceled'
    deliver(runtime, 'evt_delete', 'customer.subscription.deleted')
    assert store.entitlement_for_user('user-1').plan is Plan.PRO
    assert store.entitlement_for_user('user-1').source_subscription_id == 'sub_2'


@pytest.mark.parametrize('mutation', ['live_event', 'live_subscription', 'unknown_owner', 'wrong_customer', 'wrong_metadata'])
def test_untrusted_webhooks_never_grant_access(runtime, mutation):
    store, stripe, processor, _ = runtime
    event = _event(stripe.subscriptions['sub_1'], event_id='evt_bad', created=100)
    if mutation == 'live_event': event['livemode'] = True
    if mutation == 'live_subscription': stripe.subscriptions['sub_1']['livemode'] = True
    if mutation == 'unknown_owner': store.customers_by_stripe.clear()
    if mutation == 'wrong_customer': stripe.subscriptions['sub_1']['customer'] = 'cus_other'
    if mutation == 'wrong_metadata': stripe.subscriptions['sub_1']['metadata']['app_user_id'] = 'attacker'
    with pytest.raises(BillingError): processor.process(event)
    assert not store.entitlements


@pytest.mark.parametrize('user_id', ['', 'unknown'])
def test_portal_requires_authenticated_mapped_owner(runtime, user_id):
    store, stripe, _, _ = runtime
    with pytest.raises(BillingError):
        CheckoutService(_config(), store, stripe).portal(VerifiedUser(user_id))
    assert not stripe.portal_calls


def test_portal_rejects_conflicting_reverse_ownership(runtime):
    store, stripe, _, _ = runtime
    store.customers_by_stripe['cus_1'] = CustomerRecord('attacker', 'cus_1')
    with pytest.raises(BillingError, match='ownership conflict'):
        CheckoutService(_config(), store, stripe).portal(VerifiedUser('user-1'))
    assert not stripe.portal_calls


def test_portal_route_ignores_forged_body_and_does_not_cache(runtime, monkeypatch):
    store, stripe, _, _ = runtime
    monkeypatch.setattr('monetization_service._dependencies', lambda: (_config(), store, stripe))
    def verify(config, token):
        if token != 'verified-jwt': raise AuthenticationRequired('Invalid session')
        return VerifiedUser('user-1')
    monkeypatch.setattr('monetization_service.verify_supabase_user', verify)
    with TestClient(app) as client:
        assert client.post('/billing/portal').status_code == 401
        assert client.get('/billing/portal').status_code == 405
        response = client.post('/billing/portal', headers={'Authorization': 'Bearer verified-jwt'},
            json={'customer_id': 'cus_attacker', 'user_id': 'attacker', 'return_url': 'https://evil.test'})
    assert response.status_code == 201
    assert response.headers['cache-control'] == 'no-store'
    assert stripe.portal_calls == [{'customer_id': 'cus_1', 'return_url': _config().public_base_url}]
    assert set(response.json()) == {'url'}


def test_gateway_creates_portal_with_server_credentials_only(monkeypatch):
    calls = []
    class Response:
        ok = True
        def __init__(self, method): self.method = method
        def json(self): return ({'id':'cus_1','livemode':False,'metadata':{'app':'music','app_user_id':'owner'}}
                               if self.method=='GET' else {'url': 'https://billing.stripe.com/p/test'})
    monkeypatch.setattr('monetization_service.requests.request', lambda *a, **k: calls.append((a,k)) or Response(a[0]))
    StripeHttpGateway('sk_test_fixture', 'bpc_music_test').create_portal(customer_id='cus_1', return_url='https://music.test')
    assert calls[0][0] == ('GET', 'https://api.stripe.com/v1/customers/cus_1')
    assert calls[1][0] == ('POST', 'https://api.stripe.com/v1/billing_portal/sessions')
    assert calls[1][1]['data'] == {'customer': 'cus_1', 'return_url': 'https://music.test', 'configuration': 'bpc_music_test'}
    with pytest.raises(BillingUnavailable): StripeHttpGateway('sk_live_fixture')


def test_supabase_atomic_boundary_is_one_rpc(runtime):
    _, stripe, processor, _ = runtime
    record = processor._record(stripe.subscriptions['sub_1'], event_id='evt_1', created=100)
    entitlement = derive_entitlement(record, known_price_ids=_config().known_price_ids)
    calls = []
    class Client:
        def request(self, *args, **kwargs): calls.append((args, kwargs))
    store = SupabaseBillingStore(_config())
    store.client = Client()
    store.complete_delivery('evt_1', 'lease-token', record, entitlement)
    assert len(calls) == 1
    assert calls[0][0] == ('POST', 'rpc/music_billing_complete_delivery')
    assert calls[0][1]['json_body']['p_record']['stripe_customer_id'] == 'cus_1'


def test_database_read_normalizes_expired_pro_to_free(runtime):
    _, _, _, clock = runtime
    value = _derived({'app_user_id': 'user-1', 'plan': 'pro', 'status': 'canceled_period_end',
        'current_period_end': clock.instant.isoformat()})
    assert value.plan is Plan.FREE and value.status is SubscriptionStatus.EXPIRED


def test_public_ui_readiness_never_requires_server_secrets():
    config = replace(_config(), stripe_secret_key='', stripe_webhook_secret='', supabase_service_role_key='')
    assert config.client_enabled
    assert not config.checkout_enabled

@pytest.mark.parametrize('value,expected', [
    ('busy', WebhookBusy), ('collision', BillingError), (None, BillingError),
    ('not-a-token', BillingError),
])
def test_supabase_claim_never_acknowledges_invalid_or_busy_response(value, expected):
    class Client:
        def request(self, *args, **kwargs): return value
    store = SupabaseBillingStore(_config())
    store.client = Client()
    with pytest.raises(expected):
        store.claim_delivery(_event(_subscription(status='active'), event_id='evt_1', created=100), 'cus_1')


def test_portal_ui_uses_only_jwt_and_does_not_store_session_url(monkeypatch):
    from monetization_config import BillingConfig
    from monetization_ui import request_portal
    from suite_auth import AUTH_TOKENS_KEY
    config = replace(_config(), stripe_secret_key='', supabase_service_role_key='')
    monkeypatch.setattr(BillingConfig, 'from_environ', classmethod(lambda cls: config))
    calls = []
    class Response:
        ok = True
        def json(self): return {'url': 'https://billing.stripe.com/p/test'}
    monkeypatch.setattr('monetization_ui.requests.post', lambda *a, **k: calls.append((a,k)) or Response())
    session = {AUTH_TOKENS_KEY: {'access_token': 'verified-jwt'}, 'customer_id': 'cus_attacker'}
    before = deepcopy(session)
    assert request_portal(session) == 'https://billing.stripe.com/p/test'
    assert session == before
    assert calls[0][1] == {'headers': {'Authorization': 'Bearer verified-jwt'}, 'timeout': 15}
    with pytest.raises(RuntimeError): request_portal({})


def test_portal_rejects_non_stripe_url_and_disabled_rollout(runtime):
    store, stripe, _, _ = runtime
    stripe.create_portal = lambda **kwargs: {'url': 'https://evil.test/portal'}
    with pytest.raises(BillingError, match='Invalid portal'):
        CheckoutService(_config(), store, stripe).portal(VerifiedUser('user-1'))
    with pytest.raises(BillingUnavailable):
        CheckoutService(replace(_config(), stripe_mode='live'), store, stripe).portal(VerifiedUser('user-1'))


def test_missing_period_cannot_grant_access(runtime):
    store, stripe, _, _ = runtime
    stripe.subscriptions['sub_1'].pop('current_period_end')
    deliver(runtime)
    assert store.entitlement_for_user('user-1').plan is Plan.FREE


def test_signed_webhook_route_retries_busy_customer(runtime, monkeypatch):
    import hashlib
    import hmac
    import json
    import time
    store, stripe, _, _ = runtime
    monkeypatch.setattr('monetization_service._dependencies', lambda: (_config(), store, stripe))
    event = _event(stripe.subscriptions['sub_1'], event_id='evt_route', created=100)
    raw = json.dumps(event).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(_config().stripe_webhook_secret.encode(), stamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
    token = store.claim_delivery(event, 'cus_1')
    with TestClient(app) as client:
        response = client.post('/billing/webhooks/stripe', content=raw,
            headers={'stripe-signature': f't={stamp},v1={signature}'})
        assert response.status_code == 503
        assert not store.entitlements
        store.fail_delivery('evt_route', token)
        response = client.post('/billing/webhooks/stripe', content=raw,
            headers={'stripe-signature': f't={stamp},v1={signature}'})
        assert response.status_code == 200
        assert response.json()['result'] == 'processed'
        response = client.post('/billing/webhooks/stripe', content=raw,
            headers={'stripe-signature': f't={stamp},v1={signature}'})
        assert response.json()['result'] == 'duplicate'


def test_delivery_bookkeeping_change_does_not_cause_event_collision(runtime):
    _, stripe, processor, _ = runtime
    event = _event(stripe.subscriptions['sub_1'], event_id='evt_bookkeeping', created=100)
    event['pending_webhooks'] = 2
    assert processor.process(event) == 'processed'
    event['pending_webhooks'] = 1
    assert processor.process(event) == 'duplicate'
