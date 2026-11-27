"""Isolated, read-only client surface for Music billing staging."""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Mapping

import requests

from monetization_config import BillingConfig
from monetization_entitlements import EntitlementSubject
from monetization_supabase import SupabaseEntitlementProvider
from monetization_ui import request_checkout, request_portal

PROJECT = 'smpyutzfktjgpdibdbqb'
ORIGIN = f'https://{PROJECT}.supabase.co'
BACKEND = 'https://music-billing-staging.onrender.com'
TITLE = 'Music Practice Coach \u2013 Billing Staging'
SESSION = '_music_billing_staging_auth'
SETTING_NAMES = frozenset({
    'MUSIC_BILLING_ROLLOUT', 'MUSIC_STRIPE_MODE',
    'MUSIC_BILLING_SUPABASE_URL', 'MUSIC_BILLING_SUPABASE_ANON_KEY',
})
# Reuse the existing client entry points; this build never invokes them.
BILLING_ACTIONS = {'Checkout': request_checkout, 'Customer Portal': request_portal}


class StagingError(RuntimeError):
    """Only fixed, sanitized messages reach the UI."""


def claims(token):
    try:
        return json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
    except Exception:
        raise StagingError('Invalid isolated-project credential.') from None


@dataclass(frozen=True, repr=False)
class Settings:
    anon_key: str

    def billing_config(self):
        # Explicit mapping prevents all Suite/environment fallback paths.
        return BillingConfig.from_environ({
            'MUSIC_BILLING_ROLLOUT': 'test', 'MUSIC_STRIPE_MODE': 'test',
            'MUSIC_BILLING_SUPABASE_URL': ORIGIN,
            'MUSIC_BILLING_SUPABASE_ANON_KEY': self.anon_key,
        })


def load_settings(secrets: Mapping, environment: Mapping | None = None):
    env = os.environ if environment is None else environment
    if set(secrets) - SETTING_NAMES:
        raise StagingError('Use only the four approved staging frontend settings.')
    for name, value in env.items():
        if value and (name.startswith(('SUITE_', 'STRIPE_', 'SUPABASE_'))
                      or (name.startswith('MUSIC_') and name not in SETTING_NAMES)):
            raise StagingError('Server credentials or billing activation settings are not allowed here.')
    values = {}
    for name in SETTING_NAMES:
        secret, inherited = str(secrets.get(name, '')).strip(), str(env.get(name, '')).strip()
        if secret and inherited and secret != inherited:
            raise StagingError('Conflicting staging settings.')
        values[name] = secret or inherited
    if (values['MUSIC_BILLING_ROLLOUT'] != 'test'
            or values['MUSIC_STRIPE_MODE'] != 'test'
            or values['MUSIC_BILLING_SUPABASE_URL'] != ORIGIN):
        raise StagingError('Only the isolated Music test project and test mode are allowed.')
    key = values['MUSIC_BILLING_SUPABASE_ANON_KEY']
    identity = claims(key)
    if not isinstance(identity, dict) or identity.get('ref') != PROJECT or identity.get('role') != 'anon':
        raise StagingError('Only the isolated Music public anon key is allowed.')
    return Settings(key)


class Client:
    def __init__(self, settings):
        self.settings = settings

    def call(self, method, path, *, token=None, body=None, params=None):
        allowed = {('POST', '/auth/v1/token?grant_type=password'),
                   ('GET', '/auth/v1/user'), ('GET', '/rest/v1/music_billing_entitlements')}
        if (method, path) not in allowed:
            raise StagingError('Request outside the staging client allowlist.')
        try:
            with requests.Session() as session:
                session.trust_env = False
                response = session.request(
                    method, ORIGIN + path,
                    headers={'apikey': self.settings.anon_key,
                             'Authorization': 'Bearer ' + (token or self.settings.anon_key)},
                    json=body, params=params, timeout=12, allow_redirects=False)
            if response.status_code != 200:
                raise StagingError('Staging sign-in or subscription lookup is unavailable.')
            return response.json()
        except (requests.RequestException, ValueError):
            raise StagingError('Staging connection unavailable. Please try again.') from None

    def identity(self, token):
        data = claims(token)
        try:
            uid = str(uuid.UUID(data['sub']))
            valid = (data['iss'] == ORIGIN + '/auth/v1' and data['role'] == 'authenticated'
                     and float(data['exp']) > time.time())
        except (KeyError, TypeError, ValueError):
            raise StagingError('Sign in again to continue.') from None
        if not valid:
            raise StagingError('Sign in again to continue.')
        # Local decoding is only a guard; Supabase verifies token authenticity.
        user = self.call('GET', '/auth/v1/user', token=token)
        if (not isinstance(user, dict) or user.get('id') != uid
                or not str(user.get('email', '')).lower().endswith('@example.invalid')):
            raise StagingError('Use a pre-created synthetic test account.')
        return {'id': uid, 'email': user['email'], 'access_token': token}

    def sign_in(self, email, password):
        email = email.strip().lower()
        if not email.endswith('@example.invalid') or not password:
            raise StagingError('Use a pre-created synthetic example.invalid account.')
        response = self.call('POST', '/auth/v1/token?grant_type=password',
                             body={'email': email, 'password': password})
        if not isinstance(response, dict) or not isinstance(response.get('access_token'), str):
            raise StagingError('Staging sign-in was not accepted.')
        auth = self.identity(response['access_token'])
        if auth['email'].lower() != email:
            raise StagingError('Staging identity did not match the sign-in account.')
        return auth

    def entitlement(self, auth):
        identity = self.identity(auth['access_token'])
        if identity['id'] != auth['id']:
            raise StagingError('Sign in again to continue.')
        client = self
        class ReadOnlyTransport:
            def request(self, method, path, *, params):
                if (method != 'GET' or path != 'music_billing_entitlements'
                        or params.get('app_user_id') != 'eq.' + identity['id']):
                    raise StagingError('Subscription ownership check failed.')
                rows = client.call('GET', '/rest/v1/music_billing_entitlements',
                                   token=identity['access_token'], params=params)
                if (not isinstance(rows, list) or len(rows) > 1
                        or any(not isinstance(row, dict) or row.get('app_user_id') != identity['id']
                               for row in rows)):
                    raise StagingError('Subscription ownership check failed.')
                return rows
        # Reuse current Music entitlement parsing/expiry rules, with a pinned transport.
        provider = SupabaseEntitlementProvider(self.settings.billing_config(), identity['access_token'])
        provider.client = ReadOnlyTransport()
        return provider.entitlement_for(EntitlementSubject(identity['id'], True))


def sign_out(state):
    for key in list(state):
        if str(key).startswith('_music_billing_staging_'):
            del state[key]


def consume_return(query):
    present = bool(query)
    # Never read, render or trust session IDs, tokens, plans or return destinations.
    if present:
        query.clear()
    return present


def render(st, *, environment=None):
    st.set_page_config(page_title=TITLE, page_icon='\U0001f3b5', layout='centered')
    st.title(TITLE)
    st.warning('TEST ENVIRONMENT — pre-created synthetic accounts only. Payments are disabled.')
    if consume_return(st.query_params):
        st.info('You have returned to billing staging. Sign in to check your current subscription. '
                'Returning here does not confirm a payment or grant Pro access.')
    try:
        settings = load_settings(st.secrets, environment)
    except Exception:
        sign_out(st.session_state)
        st.error('Staging configuration is not ready. Contact the staging owner.')
        return
    client = Client(settings)
    auth = st.session_state.get(SESSION)
    if auth:
        if st.button('Sign out', key='_music_billing_staging_signout'):
            sign_out(st.session_state)
            st.rerun()
            return
        try:
            entitlement = client.entitlement(auth)
            st.write('Signed in as ' + auth['email'])
            st.metric('Subscription', 'Pro' if entitlement.grants_pro else 'Free')
            st.caption('Subscription access is read from your isolated test account.')
        except Exception:
            sign_out(st.session_state)
            st.error('Your session or subscription could not be verified. Sign in again.')
            auth = None
    if not auth:
        with st.form('_music_billing_staging_login', clear_on_submit=True):
            email = st.text_input('Synthetic test email', key='_music_billing_staging_email')
            password = st.text_input('Password', type='password', key='_music_billing_staging_password')
            submitted = st.form_submit_button('Sign in')
        if submitted:
            try:
                auth = client.sign_in(email, password)
            except Exception:
                sign_out(st.session_state)
                st.error('Sign-in failed. Use your pre-created synthetic test account.')
            else:
                st.session_state[SESSION] = auth
                st.rerun()
                return
    for label in BILLING_ACTIONS:
        st.button(label, disabled=True, key='_music_billing_staging_' + label.replace(' ', '_'))
    st.caption('Checkout and Customer Portal access are disabled in this staging build.')
