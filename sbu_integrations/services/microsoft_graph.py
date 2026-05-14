# -*- coding: utf-8 -*-
"""Minimal Microsoft Graph client (client credentials). Used by SBU Documents sync."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)

GRAPH_ROOT = 'https://graph.microsoft.com/v1.0'


class GraphHttpError(Exception):
    def __init__(self, status, message, body=''):
        super().__init__(message)
        self.status = status
        self.body = body


class SbuMicrosoftGraphClient:
    """Application-only Graph access (tenant app registration + secret)."""

    def __init__(self, env):
        icp = env['ir.config_parameter'].sudo()
        self.env = env
        self.tenant_id = (icp.get_param('sbu.graph_tenant_id') or '').strip()
        self.client_id = (icp.get_param('sbu.graph_client_id') or '').strip()
        self.client_secret = icp.get_param('sbu.graph_client_secret') or ''
        self.enabled = icp.get_param('sbu.graph_sync_enabled') == 'True'

    def is_configured(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.client_secret)

    def get_app_access_token(self) -> str:
        if not self.is_configured():
            raise GraphHttpError(0, 'Microsoft Graph is not configured (tenant, client id, client secret).')
        url = f'https://login.microsoftonline.com/{urllib.parse.quote(self.tenant_id)}/oauth2/v2.0/token'
        body = urllib.parse.urlencode(
            {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'https://graph.microsoft.com/.default',
                'grant_type': 'client_credentials',
            }
        ).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method='POST',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors='replace') if e.fp else ''
            _logger.warning('Graph token HTTP %s: %s', e.code, raw[:2000])
            raise GraphHttpError(e.code, 'Failed to obtain Microsoft Graph token.', raw) from e
        token = payload.get('access_token')
        if not token:
            raise GraphHttpError(0, 'Token response did not contain access_token.', json.dumps(payload)[:2000])
        return token

    def _request_json(self, method: str, url: str, token: str) -> dict:
        req = urllib.request.Request(url, method=method, headers={'Authorization': f'Bearer {token}'})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors='replace') if e.fp else ''
            _logger.warning('Graph %s %s HTTP %s: %s', method, url, e.code, raw[:2000])
            raise GraphHttpError(e.code, f'Graph request failed ({e.code}).', raw) from e

    def get_drive_item(self, drive_id: str, item_id: str, token: str) -> dict:
        url = f'{GRAPH_ROOT}/drives/{urllib.parse.quote(drive_id)}/items/{urllib.parse.quote(item_id)}'
        return self._request_json('GET', url, token)

    def iter_drive_item_children(self, drive_id: str, item_id: str, token: str, max_pages: int = 25):
        """Yield raw Graph driveItem dicts (immediate children only)."""
        next_url = (
            f'{GRAPH_ROOT}/drives/{urllib.parse.quote(drive_id)}/items/'
            f'{urllib.parse.quote(item_id)}/children?$top=200'
        )
        pages = 0
        while next_url and pages < max_pages:
            data = self._request_json('GET', next_url, token)
            for it in data.get('value') or []:
                yield it
            next_url = data.get('@odata.nextLink') or ''
            pages += 1

    def get_item_content(self, drive_id: str, item_id: str, token: str, max_bytes: int) -> bytes:
        url = f'{GRAPH_ROOT}/drives/{urllib.parse.quote(drive_id)}/items/{urllib.parse.quote(item_id)}/content'
        req = urllib.request.Request(url, method='GET', headers={'Authorization': f'Bearer {token}'})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                chunk = resp.read(max_bytes + 1)
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors='replace') if e.fp else ''
            raise GraphHttpError(e.code, 'Failed to download file content from Graph.', raw) from e
        if len(chunk) > max_bytes:
            raise GraphHttpError(0, f'File exceeds maximum download size ({max_bytes} bytes).')
        return chunk
