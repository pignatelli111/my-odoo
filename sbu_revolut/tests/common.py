# -*- coding: utf-8 -*-
import json
import re
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import new_test_user

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.sbu_revolut.services import revolut_client as rc

_KEY_PEM, _CERT_PEM = rc.generate_private_key_and_certificate('SBU test')


class FakeRevolut:
    """In-memory Revolut API: register responses per (method, path regex)."""

    def __init__(self):
        self.calls = []
        self.routes = []

    def on(self, method, path_regex, response):
        self.routes.insert(0, (method, re.compile(path_regex), response))

    def __call__(self, method, url, headers=None, json_body=None, form_body=None, timeout=60):
        path = url.split('/api', 1)[1].split('?')[0]
        self.calls.append({
            'method': method, 'path': path, 'url': url, 'json': json_body, 'form': form_body,
            'headers': dict(headers or {}),
        })
        for route_method, regex, response in self.routes:
            if route_method == method and regex.fullmatch(path):
                result = response(json_body or form_body, url) if callable(response) else response
                if isinstance(result, rc.RevolutHttpError):
                    raise result
                return json.loads(json.dumps(result))
        raise AssertionError(f'Unexpected Revolut call {method} {path}')

    def called(self, method, path):
        return [c for c in self.calls if c['method'] == method and c['path'] == path]


class RevolutTestCommon(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls.company.sudo().write({
            'sbu_revolut_client_id': 'client-test',
            'sbu_revolut_private_key': _KEY_PEM,
            'sbu_revolut_certificate': _CERT_PEM,
            'sbu_revolut_access_token': 'token-valid',
            'sbu_revolut_refresh_token': 'refresh-1',
            'sbu_revolut_token_expiry': fields.Datetime.now() + timedelta(minutes=30),
            'sbu_revolut_connection_state': 'connected',
            'sbu_revolut_journal_id': cls.bank_journal.id,
        })
        cls.eur = cls.company.currency_id  # company currency of the accounting test company
        cls.rev_eur = cls.env['sbu.revolut.account'].create({
            'company_id': cls.company.id,
            'revolut_account_id': 'acc-eur',
            'name': 'Main EUR',
            'currency_id': cls.eur.id,
            'balance': 50000.0,
        })
        cls.company.sbu_revolut_payment_account_id = cls.rev_eur
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente Spa', 'is_company': True})
        cls.supplier = cls.env['res.partner'].create({
            'name': 'Fornitore Srl', 'is_company': True, 'street': 'Via Roma 1', 'city': 'Milano',
            'zip': '20100', 'country_id': cls.env.ref('base.it').id,
        })
        cls.supplier_bank = cls.env['res.partner.bank'].create({
            'partner_id': cls.supplier.id,
            'acc_number': 'IT60X0542811101000000123456',
            'allow_out_payment': True,
        })
        cls.approver = new_test_user(
            cls.env, 'rev_approver', groups='account.group_account_manager,sbu_revolut.group_sbu_revolut_payment_approver',
            company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)],
        )
        cls.approver2 = new_test_user(
            cls.env, 'rev_approver2', groups='account.group_account_manager,sbu_revolut.group_sbu_revolut_payment_approver',
            company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)],
        )
        cls.billing_user = new_test_user(
            cls.env, 'rev_billing', groups='account.group_account_invoice',
            company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)],
        )

    @contextmanager
    def fake_revolut(self):
        fake = FakeRevolut()
        with patch.object(rc, '_http', fake):
            yield fake

    def make_bill(self, amount=1000.0, ref='FT-2026-77'):
        bill = self.init_invoice('in_invoice', partner=self.supplier, amounts=[amount], taxes=[])
        bill.ref = ref
        bill.partner_bank_id = self.supplier_bank
        bill.action_post()
        return bill

    def make_invoice(self, amount=1220.0):
        return self.init_invoice('out_invoice', partner=self.customer, amounts=[amount], taxes=[], post=True)

    def tx(self, tx_id, amount, account='acc-eur', reference=None, state='completed', counterparty=None, **extra):
        currency = self.eur.name
        leg = {'leg_id': f'{tx_id}-leg', 'account_id': account, 'amount': amount, 'currency': currency,
               'description': extra.pop('description', 'Payment')}
        if counterparty:
            leg['counterparty'] = counterparty
        data = {
            'id': tx_id, 'type': 'transfer', 'state': state, 'reference': reference,
            'created_at': '2026-10-01T10:00:00.000Z', 'completed_at': '2026-10-01T10:05:00.000Z',
            'legs': [leg],
        }
        data.update(extra)
        return data
