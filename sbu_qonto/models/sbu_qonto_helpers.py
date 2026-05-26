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
            'Check: API sign-in (not email), secret key, and that «Qonto sandbox» matches '
            'your keys (off = production keys, on = sandbox keys + staging token).'
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
