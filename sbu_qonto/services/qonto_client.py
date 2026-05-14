# -*- coding: utf-8 -*-
"""Minimal Qonto third-party HTTP client (list transactions)."""
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


def qonto_list_transactions(login: str, secret_key: str, iban: str, use_sandbox: bool, page: int = 1, per_page: int = 100):
    """Return (transactions_list, meta_dict) from GET /v2/transactions."""
    if not login or not secret_key or not iban:
        raise QontoHttpError(0, 'Qonto login, secret key and IBAN are required.')
    base = qonto_base_url(use_sandbox)
    qs = urllib.parse.urlencode({'iban': iban, 'current_page': page, 'per_page': per_page})
    url = f'{base}/v2/transactions?{qs}'
    req = urllib.request.Request(
        url,
        method='GET',
        headers={
            'Authorization': f'{login}:{secret_key}',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors='replace') if e.fp else ''
        _logger.warning('Qonto HTTP %s: %s', e.code, raw[:2000])
        raise QontoHttpError(e.code, 'Qonto API request failed.', raw) from e
    transactions = payload.get('transactions') or []
    meta = payload.get('meta') or {}
    return transactions, meta
