# -*- coding: utf-8 -*-
"""Revolut Business API client (OAuth with JWT client assertion, accounts,
transactions, counterparties, payments, webhooks v2).

Reference: https://developer.revolut.com/docs/business/business-api
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

_logger = logging.getLogger(__name__)

JWT_AUDIENCE = 'https://revolut.com'
CLIENT_ASSERTION_TYPE = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
WEBHOOK_EVENTS = ('TransactionCreated', 'TransactionStateChanged')
WEBHOOK_MAX_AGE_SECONDS = 300


class RevolutHttpError(Exception):
    def __init__(self, status, message, body=''):
        super().__init__(message)
        self.status = status
        self.body = body

    def __str__(self):
        detail = ''
        if self.body:
            try:
                data = json.loads(self.body)
                detail = data.get('message') or data.get('error_description') or data.get('error') or ''
            except (ValueError, AttributeError):
                detail = self.body[:300]
        base = super().__str__()
        return f'{base} (HTTP {self.status}: {detail})' if detail else f'{base} (HTTP {self.status})'


def api_base_url(use_sandbox: bool) -> str:
    return 'https://sandbox-b2b.revolut.com/api' if use_sandbox else 'https://b2b.revolut.com/api'


def consent_url(use_sandbox: bool, client_id: str, redirect_uri: str, state: str = '') -> str:
    host = 'https://sandbox-business.revolut.com' if use_sandbox else 'https://business.revolut.com'
    params = {'client_id': client_id, 'redirect_uri': redirect_uri, 'response_type': 'code'}
    if state:
        params['state'] = state
    return f'{host}/app-confirm?{urllib.parse.urlencode(params)}'


# ── Keys, certificate, JWT ────────────────────────────────────────────────────

def generate_private_key_and_certificate(common_name: str, days: int = 1825):
    """Return (private_key_pem, certificate_pem) — the certificate is uploaded to Revolut."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, (common_name or 'Odoo')[:64])])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    return key_pem, cert_pem


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def build_client_assertion(private_key_pem: str, client_id: str, issuer: str, ttl: int = 300) -> str:
    """RS256 JWT: iss = redirect URI domain, sub = client id, aud = https://revolut.com."""
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    header = {'alg': 'RS256', 'typ': 'JWT'}
    payload = {'iss': issuer, 'sub': client_id, 'aud': JWT_AUDIENCE, 'exp': int(time.time()) + ttl}
    signing_input = (
        _b64url(json.dumps(header, separators=(',', ':')).encode())
        + '.'
        + _b64url(json.dumps(payload, separators=(',', ':')).encode())
    )
    signature = key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f'{signing_input}.{_b64url(signature)}'


def issuer_from_redirect_uri(redirect_uri: str) -> str:
    return urllib.parse.urlparse(redirect_uri).netloc


# ── Webhook signature ─────────────────────────────────────────────────────────

def verify_webhook_signature(signing_secret, timestamp, raw_body, signature_header, now_ms=None):
    """Revolut-Signature: 'v1=<hex>[,v1=<hex>]' over 'v1.{timestamp}.{raw body}' (HMAC-SHA256)."""
    if not (signing_secret and timestamp and signature_header):
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    if abs(now_ms - ts) > WEBHOOK_MAX_AGE_SECONDS * 1000:
        return False
    if isinstance(raw_body, bytes):
        raw_body = raw_body.decode('utf-8')
    expected = 'v1=' + hmac.new(
        signing_secret.encode(), f'v1.{timestamp}.{raw_body}'.encode(), hashlib.sha256,
    ).hexdigest()
    return any(
        hmac.compare_digest(expected, candidate.strip())
        for candidate in signature_header.split(',')
    )


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _http(method, url, *, headers=None, json_body=None, form_body=None, timeout=60):
    """Low-level request; patched in tests. Returns parsed JSON (or None for empty body)."""
    data = None
    headers = dict(headers or {}, Accept='application/json')
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers['Content-Type'] = 'application/json'
    elif form_body is not None:
        data = urllib.parse.urlencode(form_body).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors='replace') if e.fp else ''
        _logger.warning('Revolut HTTP %s %s: %s', e.code, url.split('?')[0], raw[:1000])
        raise RevolutHttpError(e.code, 'Revolut API request failed', raw) from e
    except urllib.error.URLError as e:
        raise RevolutHttpError(0, f'Cannot reach Revolut: {e.reason}') from e
    return json.loads(raw) if raw.strip() else None


def request_token(use_sandbox, form):
    """POST /1.0/auth/token — returns dict with access_token, expires_in, refresh_token?"""
    return _http('POST', f'{api_base_url(use_sandbox)}/1.0/auth/token', form_body=form)


class RevolutClient:
    """Authenticated calls with a valid access token."""

    def __init__(self, access_token, use_sandbox=False):
        if not access_token:
            raise RevolutHttpError(0, 'Revolut is not connected (no access token).')
        self.token = access_token
        self.base = api_base_url(use_sandbox)

    def _call(self, method, path, *, params=None, json_body=None, version='1.0'):
        url = f'{self.base}/{version}{path}'
        if params:
            url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return _http(method, url, headers={'Authorization': f'Bearer {self.token}'}, json_body=json_body)

    # Accounts
    def accounts(self):
        return self._call('GET', '/accounts') or []

    def account(self, account_id):
        return self._call('GET', f'/accounts/{account_id}') or {}

    def account_bank_details(self, account_id):
        return self._call('GET', f'/accounts/{account_id}/bank-details') or []

    # Transactions
    def transactions(self, *, account_id=None, date_from=None, date_to=None, count=1000):
        params = {
            'account': account_id,
            'from': _iso(date_from),
            'to': _iso(date_to),
            'count': min(max(int(count), 1), 1000),
        }
        return self._call('GET', '/transactions', params=params) or []

    def transaction(self, transaction_id):
        return self._call('GET', f'/transaction/{transaction_id}') or {}

    # Counterparties
    def counterparties(self):
        return self._call('GET', '/counterparties') or []

    def create_counterparty(self, payload):
        return self._call('POST', '/counterparty', json_body=payload) or {}

    # Payments
    def pay(self, payload):
        return self._call('POST', '/pay', json_body=payload) or {}

    # Webhooks (API v2)
    def webhooks(self):
        return self._call('GET', '/webhooks', version='2.0') or []

    def create_webhook(self, url, events=WEBHOOK_EVENTS):
        return self._call('POST', '/webhooks', json_body={'url': url, 'events': list(events)}, version='2.0') or {}

    def delete_webhook(self, webhook_id):
        return self._call('DELETE', f'/webhooks/{webhook_id}', version='2.0')


def _iso(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
