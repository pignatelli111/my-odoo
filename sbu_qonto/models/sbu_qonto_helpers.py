# -*- coding: utf-8 -*-
"""Shared helpers for Qonto import and partner sync."""


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
