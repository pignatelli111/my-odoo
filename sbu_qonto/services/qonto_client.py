# -*- coding: utf-8 -*-
"""Qonto third-party HTTP client (transactions, SEPA beneficiaries)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)


class QontoHttpError(Exception):
    def __init__(self, status, message, body=''):
        super().__init__(message)
        self.status = status
        self.body = body


def qonto_base_url(use_sandbox: bool) -> str:
    if use_sandbox:
        return 'https://thirdparty-sandbox.staging.qonto.co'
    return 'https://thirdparty.qonto.com'


def _qonto_request(
    login: str,
    secret_key: str,
    use_sandbox: bool,
    path: str,
    query: dict | None = None,
    staging_token: str | None = None,
):
    if not login or not secret_key:
        raise QontoHttpError(0, 'Qonto login and secret key are required.')
    if use_sandbox and not (staging_token or '').strip():
        raise QontoHttpError(
            0,
            'Qonto sandbox is enabled but «Staging token» is empty. '
            'Copy it from the Qonto Developer Portal (Sandbox) and save on the company.',
        )
    base = qonto_base_url(use_sandbox)
    rel = path if path.startswith('/') else f'/{path}'
    if query:
        rel = f'{rel}?{urllib.parse.urlencode(query)}'
    url = f'{base}{rel}'
    headers = {
        'Authorization': f'{login}:{secret_key}',
        'Accept': 'application/json',
    }
    token = (staging_token or '').strip()
    if use_sandbox and token:
        headers['X-Qonto-Staging-Token'] = token
    req = urllib.request.Request(
        url,
        method='GET',
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors='replace') if e.fp else ''
        _logger.warning('Qonto HTTP %s %s: %s', e.code, path, raw[:2000])
        raise QontoHttpError(e.code, 'Qonto API request failed.', raw) from e


def qonto_get_organization(
    login: str,
    secret_key: str,
    use_sandbox: bool,
    staging_token: str | None = None,
):
    """Smoke test: GET /v2/organization (validates login + secret)."""
    return _qonto_request(
        login,
        secret_key,
        use_sandbox,
        '/v2/organization',
        staging_token=staging_token,
    )


def qonto_list_transactions(
    login: str,
    secret_key: str,
    iban: str,
    use_sandbox: bool,
    page: int = 1,
    per_page: int = 100,
    staging_token: str | None = None,
):
    """Return (transactions_list, meta_dict) from GET /v2/transactions."""
    if not iban:
        raise QontoHttpError(0, 'Qonto IBAN is required.')
    payload = _qonto_request(
        login,
        secret_key,
        use_sandbox,
        '/v2/transactions',
        {'iban': iban.replace(' ', ''), 'current_page': page, 'per_page': per_page},
        staging_token=staging_token,
    )
    return payload.get('transactions') or [], payload.get('meta') or {}


def qonto_list_sepa_beneficiaries(
    login: str,
    secret_key: str,
    use_sandbox: bool,
    max_pages: int = 20,
    per_page: int = 100,
    staging_token: str | None = None,
):
    """Return all SEPA beneficiaries from GET /v2/sepa/beneficiaries."""
    all_rows = []
    page = 1
    while page <= max_pages:
        payload = _qonto_request(
            login,
            secret_key,
            use_sandbox,
            '/v2/sepa/beneficiaries',
            {'current_page': page, 'per_page': per_page},
            staging_token=staging_token,
        )
        rows = payload.get('beneficiaries') or []
        all_rows.extend(rows)
        meta = payload.get('meta') or {}
        next_page = meta.get('next_page')
        if not next_page or not rows:
            break
        try:
            page = int(next_page)
        except (TypeError, ValueError):
            break
    return all_rows


def qonto_list_legacy_beneficiaries(
    login: str,
    secret_key: str,
    use_sandbox: bool,
    max_pages: int = 20,
    per_page: int = 100,
    staging_token: str | None = None,
):
    """Fallback GET /v2/beneficiaries (deprecated API, still used on some stacks)."""
    all_rows = []
    page = 1
    while page <= max_pages:
        try:
            payload = _qonto_request(
                login,
                secret_key,
                use_sandbox,
                '/v2/beneficiaries',
                {'current_page': page, 'per_page': per_page},
                staging_token=staging_token,
            )
        except QontoHttpError:
            break
        rows = payload.get('beneficiaries') or []
        all_rows.extend(rows)
        meta = payload.get('meta') or {}
        next_page = meta.get('next_page')
        if not next_page or not rows:
            break
        try:
            page = int(next_page)
        except (TypeError, ValueError):
            break
    return all_rows
