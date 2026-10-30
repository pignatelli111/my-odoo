# -*- coding: utf-8 -*-
"""Minimal Microsoft Graph client (client credentials). Used by SBU Documents sync."""
from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)

GRAPH_ROOT = 'https://graph.microsoft.com/v1.0'
SIMPLE_UPLOAD_MAX = 4 * 1024 * 1024
UPLOAD_CHUNK = 320 * 1024 * 16  # 5 MiB, a multiple of 320 KiB as Graph requires
_FORBIDDEN_NAME_CHARS = '"*:<>?/\\|'


def safe_drive_name(name, max_len=200):
    """OneDrive-safe file / folder name."""
    cleaned = ''.join('_' if c in _FORBIDDEN_NAME_CHARS or ord(c) < 32 else c for c in (name or '')).strip(' .')
    return (cleaned or 'document')[:max_len]


def encode_sharing_url(url):
    """Graph /shares id for a sharing link: 'u!' + base64url without padding."""
    return 'u!' + base64.urlsafe_b64encode(url.strip().encode()).decode().rstrip('=')


class GraphHttpError(Exception):
    def __init__(self, status, message, body=''):
        super().__init__(message)
        self.status = status
        self.body = body

    def __str__(self):
        base = super().__str__()
        return f'{base} (HTTP {self.status})' if self.status else base


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

    # ── Write access (OneDrive sync and backups) ───────────────────────────────
    def _http(self, method, url, token=None, data=None, headers=None, retries=4):
        """Raw request with retry on throttling; returns parsed JSON (or None)."""
        headers = dict(headers or {})
        if token:
            headers['Authorization'] = f'Bearer {token}'
        for attempt in range(retries):
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    raw = resp.read()
                return json.loads(raw.decode()) if raw.strip() else None
            except urllib.error.HTTPError as e:
                raw = e.read().decode(errors='replace') if e.fp else ''
                if e.code in (429, 502, 503, 504) and attempt < retries - 1:
                    time.sleep(int(e.headers.get('Retry-After') or 2 ** attempt))
                    continue
                _logger.warning('Graph %s %s HTTP %s: %s', method, url.split('?')[0], e.code, raw[:1000])
                raise GraphHttpError(e.code, f'Graph request failed ({e.code}).', raw) from e
            except urllib.error.URLError as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise GraphHttpError(0, f'Cannot reach Microsoft Graph: {e.reason}') from e
        return None

    def _json(self, method, url, token, body):
        return self._http(method, url, token, json.dumps(body).encode(), {'Content-Type': 'application/json'})

    @staticmethod
    def _item_url(drive_id, item_id):
        return f'{GRAPH_ROOT}/drives/{urllib.parse.quote(drive_id)}/items/{urllib.parse.quote(item_id)}'

    def resolve_sharing_link(self, url, token):
        """driveItem (with parentReference.driveId) behind a OneDrive / SharePoint sharing link."""
        return self._http('GET', f'{GRAPH_ROOT}/shares/{encode_sharing_url(url)}/driveItem', token)

    def get_child(self, drive_id, parent_id, name, token):
        """Child item by name, or None."""
        url = f'{self._item_url(drive_id, parent_id)}:/{urllib.parse.quote(safe_drive_name(name))}'
        try:
            return self._http('GET', url, token)
        except GraphHttpError as err:
            if err.status == 404:
                return None
            raise

    def ensure_folder(self, drive_id, parent_id, name, token):
        """Existing or new child folder; returns its driveItem."""
        existing = self.get_child(drive_id, parent_id, name, token)
        if existing:
            return existing
        try:
            return self._json('POST', f'{self._item_url(drive_id, parent_id)}/children', token, {
                'name': safe_drive_name(name), 'folder': {}, '@microsoft.graph.conflictBehavior': 'fail',
            })
        except GraphHttpError as err:
            if err.status == 409:  # created meanwhile
                return self.get_child(drive_id, parent_id, name, token)
            raise

    def upload_bytes(self, drive_id, parent_id, filename, data, token):
        """Upload (replace) a file; large files go through an upload session. Returns the driveItem."""
        name = urllib.parse.quote(safe_drive_name(filename))
        base = f'{self._item_url(drive_id, parent_id)}:/{name}:'
        if len(data) <= SIMPLE_UPLOAD_MAX:
            return self._http('PUT', f'{base}/content?@microsoft.graph.conflictBehavior=replace', token, data,
                              {'Content-Type': 'application/octet-stream'})
        session = self._json('POST', f'{base}/createUploadSession', token,
                             {'item': {'@microsoft.graph.conflictBehavior': 'replace'}})
        return self._upload_chunks(session['uploadUrl'], len(data), lambda start, end: data[start:end])

    def upload_file(self, drive_id, parent_id, filename, path, token):
        """Upload a (large) local file in chunks. Returns the driveItem."""
        size = os.path.getsize(path)
        name = urllib.parse.quote(safe_drive_name(filename))
        session = self._json('POST', f'{self._item_url(drive_id, parent_id)}:/{name}:/createUploadSession', token,
                             {'item': {'@microsoft.graph.conflictBehavior': 'replace'}})
        with open(path, 'rb') as fh:
            def read(start, end):
                fh.seek(start)
                return fh.read(end - start)
            return self._upload_chunks(session['uploadUrl'], size, read)

    def _upload_chunks(self, upload_url, size, read):
        result = None
        for start in range(0, size, UPLOAD_CHUNK):
            end = min(start + UPLOAD_CHUNK, size)
            result = self._http('PUT', upload_url, None, read(start, end), {
                'Content-Length': str(end - start),
                'Content-Range': f'bytes {start}-{end - 1}/{size}',
            })
        return result

    def list_children(self, drive_id, item_id, token):
        return list(self.iter_drive_item_children(drive_id, item_id, token))

    def delete_item(self, drive_id, item_id, token):
        self._http('DELETE', self._item_url(drive_id, item_id), token)
