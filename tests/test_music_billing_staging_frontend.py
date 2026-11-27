"""Offline staging frontend tests: no hosted identities, data or billing operations."""
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

import pytest
import requests

from staging.music_billing import frontend as f

UID = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
EMAIL = 'music-test@example.invalid'
APP = Path(__file__).resolve().parents[1] / 'staging/music_billing/app.py'


def token(data):
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')
    return 'fixture.' + payload + '.not_a_real_signature'


def settings():
    return {'MUSIC_BILLING_ROLLOUT': 'test', 'MUSIC_STRIPE_MODE': 'test',
            'MUSIC_BILLING_SUPABASE_URL': f.ORIGIN,
            'MUSIC_BILLING_SUPABASE_ANON_KEY': token({'ref': f.PROJECT, 'role': 'anon'})}


def access(**changes):
    return token({'sub': UID, 'iss': f.ORIGIN + '/auth/v1', 'role': 'authenticated',
                  'exp': time.time() + 3600} | changes)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Unexpected network call')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)


@pytest.fixture
def isolated_env(monkeypatch):
    for name in list(__import__('os').environ):
        if name.startswith(('SUITE_', 'STRIPE_', 'MUSIC_')):
            monkeypatch.delenv(name)


def test_valid_config_never_enables_billing():
    config = f.load_settings(settings(), {}).billing_config()
    assert config.supabase_url == f.ORIGIN
    assert not config.stripe_secret_key and not config.supabase_service_role_key
    assert not config.public_base_url
    assert not config.client_enabled and not config.checkout_enabled and not config.webhook_enabled


@pytest.mark.parametrize('change', [
    {'MUSIC_BILLING_SUPABASE_URL': 'https://qhprdlwoxjpkiukxhftp.supabase.co'},
    {'MUSIC_BILLING_SUPABASE_ANON_KEY': token({'ref': f.PROJECT, 'role': 'service_role'})},
    {'MUSIC_BILLING_SUPABASE_ANON_KEY': token({'ref': 'production', 'role': 'anon'})},
    {'MUSIC_BILLING_SUPABASE_ANON_KEY': 'opaque-fixture'},
    {'MUSIC_STRIPE_MODE': 'live'}, {'MUSIC_BILLING_ROLLOUT': 'off'},
    {'MUSIC_PUBLIC_BASE_URL': f.BACKEND + '/billing/health'},
    {'suite_activity': {'supabase_url': f.ORIGIN}},
    {'STRIPE_SECRET_KEY': 'sk_test_fixture'},
])
def test_rejects_wrong_or_unapproved_settings(change):
    with pytest.raises(f.StagingError):
        f.load_settings(settings() | change, {})


@pytest.mark.parametrize('environment', [
    {'SUITE_SUPABASE_URL': 'https://qhprdlwoxjpkiukxhftp.supabase.co'},
    {'STRIPE_SECRET_KEY': 'sk_test_fixture'},
    {'MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY': 'fixture'},
    {'MUSIC_BILLING_SERVICE_URL': f.BACKEND},
    {'MUSIC_PUBLIC_BASE_URL': 'https://unverified.example'},
    {'MUSIC_ENTITLEMENT_DEV_CONTROLS': '1'},
    {'SUPABASE_SERVICE_ROLE_KEY': 'fixture'},
    {'MUSIC_STRIPE_SECRET_KEY': 'sk_test_fixture'},
    {'MUSIC_STRIPE_MODE': 'live'},
])
def test_inherited_environment_cannot_bypass_guard(environment):
    with pytest.raises(f.StagingError): f.load_settings(settings(), environment)


def mock_api(monkeypatch, *, rows=None, user=None):
    calls = []
    def call(self, method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.startswith('/auth/v1/token'):
            return {'access_token': access(), 'refresh_token': 'must_not_be_stored'}
        if path == '/auth/v1/user':
            return user or {'id': UID, 'email': EMAIL}
        if path == '/rest/v1/music_billing_entitlements':
            return [] if rows is None else rows
        pytest.fail('Unexpected endpoint')
    monkeypatch.setattr(f.Client, 'call', call)
    return calls


def client(): return f.Client(f.load_settings(settings(), {}))


def test_password_login_uses_existing_auth_only_and_retains_no_password(monkeypatch):
    calls = mock_api(monkeypatch)
    auth = client().sign_in(EMAIL, 'fixture_password')
    assert set(auth) == {'id', 'email', 'access_token'}
    assert auth['id'] == UID
    assert calls[0] == ('POST', '/auth/v1/token?grant_type=password',
                        {'body': {'email': EMAIL, 'password': 'fixture_password'}})
    assert calls[1][1] == '/auth/v1/user'
    assert 'fixture_password' not in repr(auth)
    assert 'refresh_token' not in auth


@pytest.mark.parametrize('email,password', [('real@example.com','fixture'), (EMAIL,'')])
def test_non_synthetic_or_empty_password_never_contacts_auth(monkeypatch,email,password):
    calls = mock_api(monkeypatch)
    with pytest.raises(f.StagingError): client().sign_in(email,password)
    assert calls == []


@pytest.mark.parametrize('changes', [
    {'iss': 'https://qhprdlwoxjpkiukxhftp.supabase.co/auth/v1'},
    {'exp': 1}, {'role': 'service_role'}, {'sub': 'invalid'},
])
def test_wrong_or_expired_jwt_never_reaches_provider(monkeypatch, changes):
    calls = mock_api(monkeypatch)
    with pytest.raises(f.StagingError): client().identity(access(**changes))
    assert calls == []


def test_supabase_identity_must_match_local_token_guard(monkeypatch):
    mock_api(monkeypatch, user={'id': OTHER, 'email': EMAIL})
    with pytest.raises(f.StagingError): client().identity(access())


@pytest.mark.parametrize('plan,status,days,expected', [
    ('pro','active',1,True), ('pro','canceled_period_end',1,True),
    ('pro','active',-1,False), ('pro','past_due',1,False), ('free','expired',1,False),
])
def test_reuses_music_expiry_and_status_rules(monkeypatch,plan,status,days,expected):
    row = {'app_user_id': UID, 'plan': plan, 'status': status,
           'current_period_end': (datetime.now(timezone.utc)+timedelta(days=days)).isoformat()}
    calls = mock_api(monkeypatch, rows=[row])
    entitlement = client().entitlement({'id': UID,'access_token': access()})
    assert entitlement.grants_pro is expected
    assert calls[-1][2]['params']['app_user_id'] == 'eq.' + UID
    assert calls[-1][2]['token']


def test_empty_entitlement_is_free(monkeypatch):
    mock_api(monkeypatch)
    assert not client().entitlement({'id': UID,'access_token': access()}).grants_pro


def test_cross_user_entitlement_is_rejected(monkeypatch):
    mock_api(monkeypatch, rows=[{'app_user_id': OTHER,'plan':'pro','status':'active'}])
    with pytest.raises(f.StagingError, match='ownership'):
        client().entitlement({'id': UID,'access_token': access()})


def test_transport_is_pinned_anon_only_no_redirects_or_proxy(monkeypatch):
    seen = []
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def request(self,method,url,**kwargs):
            seen.append((method,url,kwargs,self.trust_env))
            class Response:
                status_code = 200
                def json(self): return {'id':UID}
            return Response()
    monkeypatch.setattr(requests,'Session',Session)
    client().call('GET','/auth/v1/user',token=access())
    assert seen[0][1] == f.ORIGIN + '/auth/v1/user'
    assert seen[0][2]['allow_redirects'] is False and seen[0][3] is False
    assert seen[0][2]['headers']['apikey'] == settings()['MUSIC_BILLING_SUPABASE_ANON_KEY']
    for method,path in [('POST','/auth/v1/signup'),('POST','/rest/v1/rpc/music_billing_attach_customer'),
                        ('GET','https://production.example'),('POST','/billing/checkout')]:
        with pytest.raises(f.StagingError): client().call(method,path)
    assert len(seen) == 1


def test_errors_never_expose_provider_messages_or_credentials(monkeypatch):
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def request(self,*args,**kwargs): raise requests.ConnectionError('secret fixture details')
    monkeypatch.setattr(requests,'Session',Session)
    with pytest.raises(f.StagingError) as error: client().call('GET','/auth/v1/user')
    assert 'secret' not in str(error.value)


def test_signout_clears_all_frontend_auth_and_form_state():
    state = {f.SESSION: {'access_token':'fixture'}, '_music_billing_staging_password':'fixture',
             '_music_billing_staging_email':EMAIL,'unrelated':'keep'}
    f.sign_out(state)
    assert state == {'unrelated':'keep'}


def test_return_values_never_restore_auth_or_grant_entitlement():
    query = {'billing':'success','session_id':'sensitive_fixture','plan':'pro',
             'suite_sid':'copied_fixture','access_token':'fixture','next':'https://production.example'}
    state = {}
    assert f.consume_return(query)
    assert query == {} and state == {}
    assert not f.consume_return(query)


def app_test():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP), default_timeout=15)
    at.secrets.update(settings())
    return at


def test_ui_banner_disabled_buttons_and_neutral_return(isolated_env):
    at = app_test()
    at.query_params.update({'billing':'success','session_id':'sensitive_fixture','plan':'pro'})
    at.run()
    assert not at.exception
    assert at.title[0].value == f.TITLE
    assert 'does not confirm a payment' in at.info[0].value
    assert at.query_params == {}
    assert all(b.disabled for b in at.button if b.label in f.BILLING_ACTIONS)
    assert not at.metric
    assert 'sensitive_fixture' not in str(at)


def test_ui_login_entitlement_and_signout(isolated_env,monkeypatch):
    calls = mock_api(monkeypatch)
    at = app_test().run()
    at.text_input(key='_music_billing_staging_email').input(EMAIL)
    at.text_input(key='_music_billing_staging_password').input('fixture_password')
    next(b for b in at.button if b.label == 'Sign in').click().run()
    assert not at.exception
    assert at.metric[0].value == 'Free'
    assert at.session_state[f.SESSION]['id'] == UID
    assert all(b.disabled for b in at.button if b.label in f.BILLING_ACTIONS)
    assert not any('/billing/' in path for _,path,_ in calls)
    at.button(key='_music_billing_staging_signout').click().run()
    assert not at.exception
    assert f.SESSION not in at.session_state
    assert not at.metric
    assert at.text_input(key='_music_billing_staging_password').value == ''


def test_ui_bad_configuration_is_safe(isolated_env):
    at = app_test()
    at.secrets['MUSIC_BILLING_SUPABASE_URL'] = 'https://qhprdlwoxjpkiukxhftp.supabase.co'
    at.run()
    assert not at.exception and at.error
    assert not at.text_input and not at.metric


def test_ui_failed_entitlement_shows_login_without_cached_pro(isolated_env,monkeypatch):
    mock_api(monkeypatch, rows=[{'app_user_id': OTHER,'plan':'pro','status':'active'}])
    at = app_test()
    at.session_state[f.SESSION] = {'id':UID,'email':EMAIL,'access_token':access()}
    at.run()
    assert not at.exception and at.error
    assert f.SESSION not in at.session_state
    assert not at.metric
    assert at.text_input(key='_music_billing_staging_password').value == ''


def test_frontend_import_does_not_load_suite_or_full_music_app():
    import subprocess,sys
    code = ('import sys; import staging.music_billing.frontend; '
            'assert not any(n.startswith("suite_") for n in sys.modules); '
            'assert "streamlit_music_practice_app" not in sys.modules; '
            'print("minimal import passed")')
    result = subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'minimal import passed'

@pytest.mark.parametrize('status', [302,401,503])
def test_http_failures_do_not_parse_or_expose_provider_body(monkeypatch,status):
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def request(self,*args,**kwargs):
            class Response:
                status_code = status
                def json(self): pytest.fail('Failure response body must not be read')
            return Response()
    monkeypatch.setattr(requests,'Session',Session)
    with pytest.raises(f.StagingError) as error:
        client().call('GET','/auth/v1/user',token='fixture')
    assert str(error.value) == 'Staging sign-in or subscription lookup is unavailable.'
