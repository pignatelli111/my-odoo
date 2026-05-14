# -*- coding: utf-8 -*-
"""Minimal Revolut Business HTTP client (GET /transactions)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)


class RevolutHttpError(Exception):
    def __init__(self, status, message, body=''):
        super().__init__(message)
        self.status = status
        self.body = body


def revolut_base_url(use_sandbox: bool) -> str:
    if use_sandbox:
        return 'https://sandbox-b2b.revolut.com/api/1.0'
    return 'https://b2b.revolut.com/api/1.0'


def _parse_transactions_payload(payload) -> list:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ('transactions', 'data', 'items'):
            v = payload.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def revolut_list_transactions(
    access_token: str,
    account_id: str,
    use_sandbox: bool,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    count: int = 200,
):
    """
    Return list of transaction dicts from GET /transactions.
    Pagination: pass date_to as the created_at of the last item from the previous page
    to request older movements (Revolut returns newest first).
    """
    if not access_token or not account_id:
        raise RevolutHttpError(0, 'Revolut access token and account id are required.')
    base = revolut_base_url(use_sandbox)
    params = {
        'account': account_id.strip(),
        'count': min(max(count, 1), 1000),
    }
    if date_from:
        params['from'] = date_from.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if date_to:
        params['to'] = date_to.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    qs = urllib.parse.urlencode(params)
    url = f'{base}/transactions?{qs}'
    req = urllib.request.Request(
        url,
        method='GET',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors='replace') if e.fp else ''
        _logger.warning('Revolut HTTP %s: %s', e.code, raw[:2000])
        raise RevolutHttpError(e.code, 'Revolut API request failed.', raw) from e
    return _parse_transactions_payload(payload)
