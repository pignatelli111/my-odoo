# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.sbu_revolut.services import revolut_client as rc
from odoo.addons.sbu_revolut.tests.common import RevolutTestCommon


@tagged('post_install', '-at_install')
class TestSbuRevolutSync(RevolutTestCommon):

    def test_access_token_refreshed_automatically(self):
        self.company.sudo().sbu_revolut_token_expiry = fields.Datetime.now() - timedelta(minutes=1)
        with self.fake_revolut() as fake:
            fake.on('POST', '/1.0/auth/token', {
                'access_token': 'token-new', 'expires_in': 2399, 'refresh_token': 'refresh-2',
            })
            fake.on('GET', '/1.0/accounts', [])
            self.env['sbu.revolut.account']._sbu_sync_company_accounts(self.company)
        token_call = fake.called('POST', '/1.0/auth/token')[0]['form']
        self.assertEqual(token_call['grant_type'], 'refresh_token')
        self.assertEqual(token_call['refresh_token'], 'refresh-1')
        self.assertEqual(token_call['client_assertion_type'], rc.CLIENT_ASSERTION_TYPE)
        self.assertEqual(token_call['client_assertion'].count('.'), 2)
        self.assertEqual(fake.called('GET', '/1.0/accounts')[0]['headers']['Authorization'], 'Bearer token-new')
        company = self.company.sudo()
        self.assertEqual(company.sbu_revolut_access_token, 'token-new')
        self.assertEqual(company.sbu_revolut_refresh_token, 'refresh-2')
        self.assertGreater(company.sbu_revolut_token_expiry, fields.Datetime.now() + timedelta(minutes=30))

    def test_refresh_rejected_marks_connection_error(self):
        self.company.sudo().sbu_revolut_token_expiry = fields.Datetime.now() - timedelta(minutes=1)
        with self.fake_revolut() as fake:
            fake.on('POST', '/1.0/auth/token', rc.RevolutHttpError(400, 'Revolut API request failed', '{"error":"invalid_grant"}'))
            # Not assertRaises: it rolls back the error status written before the exception.
            try:
                self.company._sbu_revolut_client()
                self.fail('RevolutHttpError expected')
            except rc.RevolutHttpError:
                pass
        self.assertEqual(self.company.sbu_revolut_connection_state, 'error')
        self.assertIn('invalid_grant', self.company.sbu_revolut_last_error)

    def test_sync_accounts_with_iban(self):
        with self.fake_revolut() as fake:
            fake.on('GET', '/1.0/accounts', [
                {'id': 'acc-eur', 'name': 'Main', 'balance': 1234.5, 'currency': self.eur.name, 'state': 'active'},
                {'id': 'acc-usd', 'name': 'Second', 'balance': 10, 'currency': 'GBP', 'state': 'active'},
            ])
            fake.on('GET', '/1.0/accounts/acc-eur/bank-details', [{'iban': 'LT12 3250 0000 0000 0001', 'bic': 'REVOLT21'}])
            fake.on('GET', '/1.0/accounts/acc-usd/bank-details', [])
            n = self.env['sbu.revolut.account']._sbu_sync_company_accounts(self.company)
        self.assertEqual(n, 2)
        accounts = self.env['sbu.revolut.account'].search([('company_id', '=', self.company.id)])
        self.assertEqual(sorted(accounts.mapped('revolut_account_id')), ['acc-eur', 'acc-usd'])
        self.assertEqual(self.rev_eur.balance, 1234.5)
        self.assertEqual(self.rev_eur.iban, 'LT123250000000000001')
        usd = accounts.filtered(lambda a: a.revolut_account_id == 'acc-usd')
        self.assertEqual(usd.currency_id.name, 'GBP')

    def _import(self, fake, txs):
        fake.on('GET', '/1.0/transactions', txs)
        return self.env['sbu.revolut.transaction'].import_transactions_for_company(self.company)

    def test_import_matches_invoice_by_reference(self):
        invoice = self.make_invoice(1220.0)
        with self.fake_revolut() as fake:
            n = self._import(fake, [self.tx('t-in-1', 1220.0, reference=f'Saldo fattura {invoice.name}')])
            self.assertEqual(n, 1)
            self._import(fake, [self.tx('t-in-1', 1220.0, reference=f'Saldo fattura {invoice.name}')])
        movement = self.env['sbu.revolut.transaction'].search([('revolut_remote_id', '=', 't-in-1')])
        self.assertEqual(len(movement), 1, 'a second import must not duplicate')
        self.assertEqual(movement.account_id, self.rev_eur)
        self.assertEqual(movement.amount_signed, 1220.0)
        self.assertEqual(str(movement.transfer_date), '2026-10-01')
        self.assertEqual(movement.sbu_match_confidence, 'high')
        self.assertEqual(movement.match_invoice_id, invoice, 'high confidence is linked automatically')
        self.assertFalse(movement.match_payment_id, 'no accounting entry without auto-register')
        movement.action_register_payment()
        self.assertEqual(movement.state, 'matched')
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        self.assertEqual(movement.match_payment_id.journal_id, self.bank_journal)

    def test_auto_register_inbound(self):
        self.company.sbu_revolut_auto_register_inbound = True
        invoice = self.make_invoice(500.0)
        with self.fake_revolut() as fake:
            self._import(fake, [self.tx('t-in-2', 500.0, reference=invoice.name)])
        movement = self.env['sbu.revolut.transaction'].search([('revolut_remote_id', '=', 't-in-2')])
        self.assertEqual(movement.state, 'matched')
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))

    def test_amount_only_is_low_and_not_linked(self):
        self.make_invoice(777.0)
        with self.fake_revolut() as fake:
            self._import(fake, [self.tx('t-in-3', 777.0, reference='bonifico')])
        movement = self.env['sbu.revolut.transaction'].search([('revolut_remote_id', '=', 't-in-3')])
        self.assertEqual(movement.sbu_match_confidence, 'low')
        self.assertTrue(movement.suggested_invoice_id)
        self.assertFalse(movement.match_invoice_id)

    def test_counterparty_partner_match(self):
        self.supplier.sbu_revolut_counterparty_id = 'cp-1'
        bill = self.make_bill(300.0, ref='XYZ')
        with self.fake_revolut() as fake:
            self._import(fake, [self.tx('t-out-1', -300.0, reference='pagamento', counterparty={'id': 'cp-1'})])
        movement = self.env['sbu.revolut.transaction'].search([('revolut_remote_id', '=', 't-out-1')])
        self.assertEqual(movement.partner_id, self.supplier)
        self.assertEqual(movement.amount_signed, -300.0)
        self.assertEqual(movement.sbu_match_confidence, 'high')
        self.assertEqual(movement.match_vendor_bill_id, bill)

    def test_internal_transfer_creates_one_record_per_leg(self):
        usd = self.env['sbu.revolut.account'].create({
            'company_id': self.company.id, 'revolut_account_id': 'acc-2', 'name': 'Savings',
            'currency_id': self.eur.id, 'import_enabled': False,
        })
        tx = self.tx('t-int', -100.0)
        tx['legs'].append({'leg_id': 't-int-leg2', 'account_id': 'acc-2', 'amount': 100.0, 'currency': self.eur.name})
        Movement = self.env['sbu.revolut.transaction']
        Movement.revolut_upsert_from_dict(self.company, tx, 'webhook')
        records = Movement.search([('revolut_remote_id', '=', 't-int')])
        self.assertEqual(len(records), 2)
        self.assertEqual(records.filtered(lambda r: r.account_id == usd).amount_signed, 100.0)

    def test_sync_counterparties_links_partner_by_iban(self):
        with self.fake_revolut() as fake:
            fake.on('GET', '/1.0/counterparties', [{
                'id': 'cp-9', 'name': 'Fornitore', 'accounts': [{'id': 'cpa-9', 'iban': 'IT60 X054 2811 1010 0000 0123 456'}],
            }])
            n = self.env['res.partner']._sbu_revolut_sync_counterparties(self.company)
        self.assertEqual(n, 1)
        self.assertEqual(self.supplier.sbu_revolut_counterparty_id, 'cp-9')
        self.assertEqual(self.supplier.sbu_revolut_counterparty_account_id, 'cpa-9')

    def test_csv_export_neutralises_formulas(self):
        Movement = self.env['sbu.revolut.transaction']
        Movement.revolut_upsert_from_dict(self.company, self.tx('t-csv', 10.0, reference='=HYPERLINK("x")'), 'api')
        self.assertEqual(Movement._csv_safe('=HYPERLINK("x")'), '\'=HYPERLINK("x")')
        self.assertEqual(Movement._csv_safe(-5.0), "'-5.0")
        action = Movement.search([('revolut_remote_id', '=', 't-csv')]).action_export_csv()
        self.assertIn('/web/content/', action['url'])

    def test_only_admin_configures_connection(self):
        with self.assertRaises(UserError):
            self.company.with_user(self.billing_user).action_sbu_revolut_generate_certificate()
