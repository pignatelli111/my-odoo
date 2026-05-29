# -*- coding: utf-8 -*-
"""Optional HTTP bridge for Logikal/ReynaPro middleware (JSON over GET).

Real vendor APIs vary by installation; this client calls a configurable path
and expects a JSON array of position objects (see sbu.logikal.import.batch).
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)


class LogikalHttpError(Exception):
    def __init__(self, status: int, message: str, body: str = ''):
        super().__init__(message)
        self.status = status
        self.body = body


def fetch_positions_json(
    base_url: str,
    bearer_token: str,
    project_ref: str,
    path: str = '/positions',
    timeout: int = 120,
) -> list:
    """GET JSON list of position dicts from a middleware URL.

    Final URL: ``{base_url}{path}?project={project_ref}`` (path should start with /).

    Response body: JSON array, e.g.
    ``[{"position":"LA01","profile_code":"RA16","description":"...","qty":2,"width_mm":1200,"height_mm":1400}]``
    """
    if not base_url or not project_ref:
        raise LogikalHttpError(0, 'Base URL and project reference are required for API fetch.')
    base = base_url.rstrip('/')
    rel = path if path.startswith('/') else f'/{path}'
    qs = urllib.parse.urlencode({'project': project_ref})
    url = f'{base}{rel}?{qs}'
    headers = {'Accept': 'application/json'}
    if bearer_token:
        headers['Authorization'] = f'Bearer {bearer_token}'
    req = urllib.request.Request(url, method='GET', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors='replace') if e.fp else ''
        _logger.warning('Logikal bridge HTTP %s: %s', e.code, raw[:2000])
        raise LogikalHttpError(e.code, 'Logikal/ReynaPro bridge request failed.', raw) from e
    if isinstance(payload, dict):
        # Common envelope shapes
        for key in ('data', 'positions', 'items', 'rows'):
            inner = payload.get(key)
            if isinstance(inner, list):
                return inner
        raise LogikalHttpError(0, 'JSON response is an object without a list field (data/positions/items/rows).')
    if not isinstance(payload, list):
        raise LogikalHttpError(0, 'JSON response must be a list or an object wrapping a list.')
    return payload
