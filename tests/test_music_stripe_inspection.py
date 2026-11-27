"""Offline regression tests for the read-only Stripe inspection boundary."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stripe_inspection', ROOT/'scripts/inspect_music_stripe_sandbox.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Fake:
    def __init__(self):
        self.price = {'id':m.PRICE_ID,'livemode':False,'active':True,'type':'recurring',
            'recurring':{'interval':'month','interval_count':1},
            'product':{'id':'prod_fixture','name':'Music Pro','active':True,'livemode':False,'metadata':{'app':'music'}}}
        self.portals = [{'id':'bpc_music','active':True,'livemode':False,'is_default':False,'metadata':{'app':'music'}}]
    def get(self,path,params=None):
        if path=='account': return {'id':'acct_fixture','email':'never-print@example.invalid'}
        if path.startswith('prices/'): return self.price
        return {'data':self.portals,'has_more':False}


def test_output_excludes_account_identity_and_selects_explicit_music_config():
    result=m.inspect(Fake())
    assert result['unique_music_portal_id']=='bpc_music'
    assert 'email' not in result
    assert 'never-print' not in str(result)


@pytest.mark.parametrize('change',[{'livemode':True},{'active':False},
    {'recurring':{'interval':'year','interval_count':1}},
    {'product':{'id':'prod_fixture','active':True,'livemode':False,'metadata':{'app':'baseball'}}}])
def test_wrong_price_mode_or_product_stops_inspection(change):
    fake=Fake();fake.price.update(change)
    with pytest.raises(RuntimeError):m.inspect(fake)


@pytest.mark.parametrize('mutation',['default','untagged','duplicate','none'])
def test_portal_selection_never_guesses_an_ambiguous_or_default_config(mutation):
    fake=Fake()
    if mutation=='default':fake.portals[0]['is_default']=True
    if mutation=='untagged':fake.portals[0]['metadata']={}
    if mutation=='duplicate':fake.portals.append(copy.deepcopy(fake.portals[0])|{'id':'bpc_other'})
    if mutation=='none':fake.portals=[]
    assert m.inspect(fake)['unique_music_portal_id'] is None


def test_transport_only_uses_pinned_gets_and_disables_redirects(monkeypatch):
    calls=[]
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,**kwargs):
            calls.append((url,kwargs,self.trust_env))
            return type('Response',(),{'status_code':200,'json':lambda self:{'id':'acct_fixture'}})()
    monkeypatch.setattr(m.requests,'Session',Session)
    m.StripeReadOnly('sk_test_fixture').get('account')
    assert calls[0][0]=='https://api.stripe.com/v1/account'
    assert calls[0][1]['allow_redirects'] is False
    assert calls[0][1]['headers']['Stripe-Version']==m.API_VERSION
    assert calls[0][2] is False
    with pytest.raises(ValueError):m.StripeReadOnly('sk_test_fixture').get('https://other.test')
    with pytest.raises(ValueError):m.StripeReadOnly('sk_live_fixture')


def test_inspection_pin_matches_billing_backend():
    from monetization_service import STRIPE_API_VERSION
    assert m.API_VERSION==STRIPE_API_VERSION
