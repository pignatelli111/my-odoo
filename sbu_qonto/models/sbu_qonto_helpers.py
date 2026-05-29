# -*- coding: utf-8 -*-
"""Shared helpers for Qonto import and partner sync."""
from odoo.exceptions import UserError
from odoo.tools.translate import _


def sbu_qonto_user_error(http_error):
    """Turn QontoHttpError into a readable Odoo dialog."""
    status = getattr(http_error, 'status', 0) or 0
    body = (getattr(http_error, 'body', '') or '').strip()
    if len(body) > 600:
        body = body[:600] + '…'
    if status == 401:
        hint = _(
            'Invalid credentials. In Qonto: Integrations → API key — copy the «Sign-in» '
            '(slug, e.g. suburban-1234) and the «Secret key» (long hex string). '
            'Do not use your email. Click Save in Odoo Settings, then Test again. '
            '«Qonto sandbox» must be off for production keys.'
        )
    elif status == 403 and (
        'error_code":1010' in body
        or 'error_code": 1010' in body
        or 'browser_signature_banned' in body
        or 'cloudflare' in body.lower()
    ):
        hint = _(
            'Cloudflare blocked Odoo.sh (error 1010). Upgrade sbu_qonto to 19.0.1.0.9+, '
            'then retry. If it persists, send the Ray ID below to Qonto support and ask them '
            'to allow API traffic from Odoo.sh / your integration User-Agent.'
        )
    elif status == 0:
        hint = ''
    else:
        hint = _('Verify IBAN belongs to this Qonto organization.')
    detail = '\n'.join(x for x in (str(http_error), body, hint) if x)
    return UserError(
        _('Qonto API error (HTTP %(status)s):\n%(detail)s')
        % {'status': status or '—', 'detail': detail}
    )


def sbu_normalize_iban(iban):
    if not iban:
        return ''
    return ''.join(str(iban).upper().split())


def sbu_beneficiary_display_name(ben: dict) -> str:
    for key in ('name', 'company_name', 'label', 'beneficiary_name'):
        val = (ben.get(key) or '').strip()
        if val:
            return val
    return ''


def sbu_beneficiary_iban(ben: dict) -> str:
    for key in ('iban', 'account_number', 'counterparty_account_number'):
        val = ben.get(key)
        if val:
            return sbu_normalize_iban(val)
    return ''


def sbu_beneficiary_remote_id(ben: dict) -> str:
    return str(ben.get('id') or ben.get('beneficiary_id') or '').strip()
