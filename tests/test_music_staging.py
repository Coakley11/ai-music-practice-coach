"""Focused staging startup and cross-application customer isolation checks."""
import base64
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from monetization_billing import BillingError
from monetization_service import StripeHttpGateway, app
from monetization_staging_config import ISOLATED_SUPABASE_URL, validate_staging_environment


def key(role, project='smpyutzfktjgpdibdbqb'):
    data = base64.urlsafe_b64encode(json.dumps({'ref':project,'role':role}).encode()).decode().rstrip('=')
    return 'fixture.'+data+'.fixture'


def env():
    return {'MUSIC_BILLING_ROLLOUT':'test','MUSIC_STRIPE_MODE':'test',
            'MUSIC_BILLING_SUPABASE_URL':ISOLATED_SUPABASE_URL,
            'MUSIC_BILLING_SUPABASE_ANON_KEY':key('anon'),
            'MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY':key('service_role')}


@pytest.mark.parametrize('changes',[
    {'MUSIC_BILLING_SUPABASE_URL':'https://qhprdlwoxjpkiukxhftp.supabase.co'},
    {'MUSIC_BILLING_SUPABASE_URL':''}, {'MUSIC_BILLING_ROLLOUT':'off'},
    {'MUSIC_STRIPE_MODE':'live'}, {'STRIPE_SECRET_KEY':'sk_live_fixture'},
    {'SUITE_SUPABASE_URL':ISOLATED_SUPABASE_URL},
    {'MUSIC_BILLING_SUPABASE_ANON_KEY':key('anon','qhprdlwoxjpkiukxhftp')},
    {'MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY':key('anon')},
    {'MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY':'sb_secret_fixture'},
])
def test_staging_rejects_wrong_target_mode_keys_and_suite_fallback(changes):
    with pytest.raises(RuntimeError): validate_staging_environment(env()|changes)


def test_health_only_bootstrap_is_safe_and_reports_disabled_stripe(monkeypatch):
    validate_staging_environment(env())
    for name in ('STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','STRIPE_PRO_MONTHLY_PRICE_ID','STRIPE_PRO_ANNUAL_PRICE_ID'):
        monkeypatch.delenv(name,raising=False)
    for name,value in env().items(): monkeypatch.setenv(name,value)
    with TestClient(app) as client:
        result=client.get('/billing/health')
        assert result.status_code==200
        assert result.json()['checkout_enabled'] is False
        assert result.json()['webhook_enabled'] is False


@pytest.mark.parametrize('customer',[
    {'id':'cus_fixture','livemode':False,'metadata':{'app':'baseball','app_user_id':'owner'}},
    {'id':'cus_fixture','livemode':False,'metadata':{}},
    {'id':'cus_fixture','livemode':True,'metadata':{'app':'music','app_user_id':'owner'}},
    {'id':'cus_other','livemode':False,'metadata':{'app':'music','app_user_id':'owner'}},
    {'id':'cus_fixture','livemode':False,'deleted':True,'metadata':{'app':'music','app_user_id':'owner'}},
])
@pytest.mark.parametrize('operation',['portal','checkout_lookup'])
def test_foreign_or_untagged_customers_cannot_reach_portal_or_checkout(monkeypatch,customer,operation):
    calls=[]
    gateway=StripeHttpGateway('sk_test_fixture','bpc_music')
    def request(method,path,**kwargs):
        calls.append((method,path));return customer
    monkeypatch.setattr(gateway,'_request',request)
    with pytest.raises(BillingError):
        if operation=='portal': gateway.create_portal(customer_id='cus_fixture',return_url='https://music.test')
        else: gateway.has_open_subscription('cus_fixture')
    assert calls==[('GET','customers/cus_fixture')]


def test_music_customer_can_open_explicit_music_portal(monkeypatch):
    gateway=StripeHttpGateway('sk_test_fixture','bpc_music');calls=[]
    def request(method,path,**kwargs):
        calls.append((method,path,kwargs))
        return ({'id':'cus_fixture','livemode':False,'metadata':{'app':'music','app_user_id':'owner'}}
                if method=='GET' else {'url':'https://billing.stripe.com/fixture'})
    monkeypatch.setattr(gateway,'_request',request)
    gateway.create_portal(customer_id='cus_fixture',return_url='https://music.test')
    assert calls[-1][2]['data']['configuration']=='bpc_music'


def test_staging_wrapper_exports_existing_app(monkeypatch):
    import importlib.util
    root=Path(__file__).resolve().parents[1]
    for name in list(__import__('os').environ):
        if name.startswith('SUITE_'): monkeypatch.delenv(name)
    for name,value in env().items(): monkeypatch.setenv(name,value)
    monkeypatch.delenv('STRIPE_SECRET_KEY',raising=False)
    spec=importlib.util.spec_from_file_location('staging_fixture',root/'monetization_staging.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.app is app
