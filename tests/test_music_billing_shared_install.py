from pathlib import Path

import pytest

from monetization_billing import BillingError, BillingUnavailable, CheckoutService, CustomerRecord, InMemoryBillingStore, VerifiedUser, WebhookProcessor
from monetization_service import STRIPE_API_VERSION, StripeHttpGateway
from monetization_supabase import SupabaseBillingStore
from tests.test_monetization_m2 import FakeStripe, _config, _event, _subscription

INSTALL = Path(__file__).resolve().parents[1] / 'supabase/install/20261112_music_billing_shared_install.sql'
TABLES = {'music_billing_customers', 'music_billing_subscriptions', 'music_billing_webhook_events', 'music_billing_entitlements'}


def test_checkout_replay_keeps_key_and_expiry_and_prevents_interval_race():
    store, stripe = InMemoryBillingStore(), FakeStripe()
    service = CheckoutService(_config(), store, stripe)
    service.create(VerifiedUser('owner'), interval='monthly')
    service.create(VerifiedUser('owner'), interval='monthly')
    assert stripe.checkout_calls[0] == stripe.checkout_calls[1]
    with pytest.raises(BillingUnavailable, match='pending'):
        service.create(VerifiedUser('owner'), interval='annual')
    assert len(stripe.checkout_calls) == 2
    assert stripe.checkout_calls[0]['idempotency_key'].startswith('music-checkout-v1-')


def test_expired_checkout_reservation_generates_new_key(monkeypatch):
    store, stripe = InMemoryBillingStore(), FakeStripe()
    service = CheckoutService(_config(), store, stripe)
    monkeypatch.setattr('monetization_billing.time.time', lambda: 1000)
    service.create(VerifiedUser('owner'), interval='monthly')
    monkeypatch.setattr('monetization_billing.time.time', lambda: 4601)
    service.create(VerifiedUser('owner'), interval='monthly')
    assert stripe.checkout_calls[0]['idempotency_key'] != stripe.checkout_calls[1]['idempotency_key']


@pytest.mark.parametrize('status', ['active', 'trialing', 'past_due', 'incomplete', 'paused'])
def test_existing_stripe_subscription_blocks_new_checkout(status):
    store, stripe = InMemoryBillingStore(), FakeStripe()
    store.upsert_customer(CustomerRecord('user-1', 'cus_1'))
    stripe.subscriptions['sub_1'] = _subscription(status=status)
    with pytest.raises(BillingError, match='subscription management'):
        CheckoutService(_config(), store, stripe).create(VerifiedUser('user-1'), interval='monthly')
    assert not stripe.checkout_calls and not store.checkouts


def test_customer_retry_is_stable_across_email_changes_and_every_request_is_versioned(monkeypatch):
    calls = []
    class Response:
        ok = True
        def json(self): return {'id': 'cus_fixture'}
    monkeypatch.setattr('monetization_service.requests.request', lambda *a, **k: calls.append((a,k)) or Response())
    gateway = StripeHttpGateway('sk_test_fixture')
    gateway.create_customer(app_user_id='private-owner', email='first@example.test')
    gateway.create_customer(app_user_id='private-owner', email='changed@example.test')
    assert calls[0] == calls[1]
    headers = calls[0][1]['headers']
    assert headers['Stripe-Version'] == STRIPE_API_VERSION
    assert headers['Idempotency-Key'].startswith('music-customer-v1-')
    assert 'private-owner' not in headers['Idempotency-Key']
    assert 'email' not in calls[0][1]['data']
    assert calls[0][1]['data']['metadata[app]'] == 'music'


def test_checkout_gateway_sends_same_expiry_key_and_app_metadata(monkeypatch):
    calls = []
    class Response:
        ok = True
        def json(self): return {'id': 'cs_test_fixture'}
    monkeypatch.setattr('monetization_service.requests.request', lambda *a, **k: calls.append((a,k)) or Response())
    gateway = StripeHttpGateway('sk_test_fixture')
    kwargs = dict(customer_id='cus_1', price_id='price_pro', app_user_id='owner',
        success_url='https://music.test/success', cancel_url='https://music.test/cancel',
        idempotency_key='music-checkout-v1-fixture', expires_at=1900000000)
    gateway.create_subscription_checkout(**kwargs)
    gateway.create_subscription_checkout(**kwargs)
    assert calls[0] == calls[1]
    assert calls[0][1]['data']['expires_at'] == kwargs['expires_at']
    assert calls[0][1]['data']['subscription_data[metadata][app]'] == 'music'
    assert calls[0][1]['headers']['Idempotency-Key'] == kwargs['idempotency_key']


@pytest.mark.parametrize('payload', [{'has_more': True, 'data': []}, {}, {'data': [{'customer': 'cus_other'}]}])
def test_subscription_lookup_fails_closed_on_incomplete_or_conflicting_list(monkeypatch, payload):
    class Response:
        ok = True
        def __init__(self, value): self.value = value
        def json(self): return self.value
    monkeypatch.setattr('monetization_service.requests.request', lambda method,url,**k: Response(
        {'id':'cus_1','livemode':False,'metadata':{'app':'music','app_user_id':'owner'}}
        if url.endswith('/customers/cus_1') else payload))
    with pytest.raises(BillingError):
        StripeHttpGateway('sk_test_fixture').has_open_subscription('cus_1')


def test_portal_never_uses_account_default_configuration():
    with pytest.raises(BillingUnavailable, match='configuration'):
        StripeHttpGateway('sk_test_fixture').create_portal(customer_id='cus_1', return_url='https://music.test')


def test_explicit_foreign_app_event_ignored_but_unknown_untagged_owner_retries():
    store, stripe = InMemoryBillingStore(), FakeStripe()
    event = _event(_subscription(status='active'), event_id='evt_other', created=100)
    event['data']['object']['metadata']['app'] = 'baseball'
    processor = WebhookProcessor(_config(), store, stripe)
    assert processor.process(event) == 'ignored'
    event['data']['object']['metadata'].pop('app')
    with pytest.raises(BillingError, match='trusted owner'): processor.process(event)
    assert not store.entitlements


def test_adapter_reads_only_music_namespaced_tables_and_reserves_with_rpc():
    calls = []
    class Client:
        def request(self, method, path, **kwargs):
            calls.append((method,path,kwargs))
            if path.endswith('reserve_checkout'): return {'token': 'fixture', 'expires_at': 1900000000}
            return []
    store = SupabaseBillingStore(_config()); store.client = Client()
    store.customer_for_user('owner'); store.customer_by_stripe_id('cus_1'); store.entitlement_for_user('owner')
    store.reserve_checkout('owner', 'price_pro')
    assert all(path.startswith(('music_billing_', 'rpc/music_billing_')) for _,path,_ in calls)
    assert calls[-1][1] == 'rpc/music_billing_reserve_checkout'


def test_install_is_atomic_namespaced_and_never_replaces_existing_objects():
    pglast = pytest.importorskip('pglast')
    from pglast import ast
    from pglast.visitors import Visitor
    parsed = pglast.parse_sql(INSTALL.read_text())
    assert isinstance(parsed[0].stmt, ast.TransactionStmt)
    assert isinstance(parsed[-1].stmt, ast.TransactionStmt)
    created = set()
    class Targets(Visitor):
        def visit_CreateStmt(self, a, n):
            assert n.relation.schemaname == 'public' and n.relation.relname in TABLES
            assert not n.if_not_exists
            created.add(n.relation.relname)
            for c in n.tableElts:
                if isinstance(c, ast.Constraint): assert c.conname.startswith('music_billing_')
        def visit_CreateFunctionStmt(self, a, n):
            assert not n.replace and n.funcname[-1].sval.startswith('music_billing_')
        def visit_AlterTableStmt(self, a, n): assert n.relation.relname in TABLES
        def visit_CreateTrigStmt(self, a, n):
            assert n.trigname.startswith('music_billing_') and n.relation.relname in TABLES
        def visit_IndexStmt(self, a, n): assert n.idxname.startswith('music_billing_') and n.relation.relname in TABLES
        def visit_GrantStmt(self, a, n):
            for o in n.objects:
                if isinstance(o, ast.RangeVar): assert o.relname in TABLES
                elif isinstance(o, ast.ObjectWithArgs): assert o.objname[-1].sval.startswith('music_billing_')
    Targets()(parsed)
    assert created == TABLES
    sql = INSTALL.read_text()
    assert 'create or replace' not in sql.lower()
    assert 'alter default privileges' not in '\n'.join(l for l in sql.lower().splitlines() if not l.lstrip().startswith('--'))
    for protected in ('public.subscriptions','private.baseball_', 'public.suite_'):
        assert protected not in sql
    assert 'auth.users' in sql  # Read-only prerequisites / FK references; no auth trigger.
    assert 'namespace collision' in sql.lower()
    assert len(pglast.parse_plpgsql(sql)) == 9


@pytest.mark.parametrize('role', ['anon', 'authenticated', 'service_role'])
def test_install_has_fail_closed_effective_privilege_postconditions(role):
    sql = INSTALL.read_text()
    assert "array['anon','authenticated','service_role']" in sql
    assert "array['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']" in sql
    assert 'has_any_column_privilege' in sql
    assert "aclexplode(coalesce(c.relacl,acldefault('r',c.relowner)))" in sql
    assert "aclexplode(coalesce(p.proacl,acldefault('f',p.proowner)))" in sql
    assert "set search_path = ''" in sql and 'set search_path = public' not in sql
    assert role in sql
    assert 'grant select on public.music_billing_customers,public.music_billing_entitlements to service_role' in sql
    assert 'grant select on public.music_billing_entitlements to authenticated' in sql
    assert 'using (app_user_id=(select auth.uid()))' in sql


def test_all_embedded_installer_mutations_stay_inside_music_tables():
    pglast = pytest.importorskip('pglast')
    from pglast.visitors import Visitor
    def queries(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'query' and isinstance(item, str): yield item
                else: yield from queries(item)
        elif isinstance(value, list):
            for item in value: yield from queries(item)
    seen = []
    class Mutations(Visitor):
        def check(self, node):
            assert node.relation.schemaname == 'public' and node.relation.relname in TABLES
            seen.append(node.relation.relname)
        def visit_InsertStmt(self, a, n): self.check(n)
        def visit_UpdateStmt(self, a, n): self.check(n)
        def visit_DeleteStmt(self, a, n): self.check(n)
    for query in queries(pglast.parse_plpgsql(INSTALL.read_text())):
        if query.lstrip().lower().startswith(('select ', 'insert ', 'update ', 'delete ')):
            Mutations()(pglast.parse_sql(query))
    assert set(seen) == TABLES
