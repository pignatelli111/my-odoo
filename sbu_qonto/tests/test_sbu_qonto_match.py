# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_qonto.models.sbu_qonto_helpers import (
    sbu_beneficiary_display_name,
    sbu_beneficiary_iban,
    sbu_beneficiary_remote_id,
    sbu_normalize_iban,
)


@tagged('post_install', '-at_install')
class TestSbuQontoMatch(TransactionCase):
    def test_cron_and_match_fields_registered(self):
        cron = self.env.ref('sbu_qonto.ir_cron_qonto_import')
        self.assertEqual(cron.model_id.model, 'sbu.qonto.transaction')
        tx = self.env['sbu.qonto.transaction']
        for fname in (
            'sbu_match_confidence',
            'sbu_match_hint',
            'suggested_payment_id',
            'suggested_invoice_id',
            'suggested_vendor_bill_id',
            'match_vendor_bill_id',
            'counterparty_iban',
            'partner_id',
        ):
            self.assertIn(fname, tx._fields)
        company = self.env.company
        for fname in (
            'sbu_qonto_sync_partners_on_import',
            'sbu_qonto_auto_match_high',
            'sbu_qonto_auto_register_inbound',
            'sbu_qonto_auto_register_outbound',
        ):
            self.assertIn(fname, company._fields)

    def test_company_qonto_automation_defaults(self):
        company = self.env.company
        self.assertTrue(company.sbu_qonto_sync_partners_on_import)
        self.assertTrue(company.sbu_qonto_auto_match_high)
        self.assertTrue(company.sbu_qonto_auto_register_inbound)
        self.assertFalse(company.sbu_qonto_auto_register_outbound)

    def test_cron_active_follows_company_import_flag(self):
        cron = self.env.ref('sbu_qonto.ir_cron_qonto_import')
        company = self.env.company
        previous = company.sbu_qonto_import_enabled
        try:
            company.sbu_qonto_import_enabled = True
            self.env['res.company']._sbu_sync_qonto_cron_active()
            self.assertTrue(cron.active)
            company.sbu_qonto_import_enabled = False
            self.env['res.company']._sbu_sync_qonto_cron_active()
            if not self.env['res.company'].search_count([('sbu_qonto_import_enabled', '=', True)]):
                self.assertFalse(cron.active)
        finally:
            company.sbu_qonto_import_enabled = previous
            self.env['res.company']._sbu_sync_qonto_cron_active()

    def test_helpers_normalize_and_beneficiary_extract(self):
        self.assertEqual(sbu_normalize_iban(' it60 x0542 '), 'IT60X0542')
        ben = {
            'id': 'uuid-1',
            'name': 'Fornitore Test',
            'iban': 'IT60X0542811101000000123456',
        }
        self.assertEqual(sbu_beneficiary_remote_id(ben), 'uuid-1')
        self.assertEqual(sbu_beneficiary_display_name(ben), 'Fornitore Test')
        self.assertEqual(sbu_beneficiary_iban(ben), 'IT60X0542811101000000123456')

    def test_partner_fields_on_res_partner(self):
        partner = self.env['res.partner'].create({
            'name': 'Qonto sync test',
            'sbu_qonto_beneficiary_id': 'ben-test-1',
            'sbu_qonto_iban': 'IT60X0542811101000000123456',
            'sbu_qonto_partner_synced': True,
        })
        self.assertEqual(partner.sbu_qonto_beneficiary_id, 'ben-test-1')

    def test_transaction_links_partner_by_iban(self):
        partner = self.env['res.partner'].create({
            'name': 'Cliente IBAN',
            'sbu_qonto_iban': 'IT11X0000000000000000000001',
        })
        company = self.env.company
        vals = self.env['sbu.qonto.transaction']._vals_from_qonto_dict(
            company,
            {
                'id': 'tx-partner-1',
                'side': 'credit',
                'amount': 100.0,
                'currency': company.currency_id.name,
                'counterparty_account_number': 'IT11X0000000000000000000001',
            },
            'api',
        )
        self.assertEqual(vals['partner_id'], partner.id)

    def test_outbound_skips_customer_invoice_match(self):
        company = self.env.company
        tx = self.env['sbu.qonto.transaction'].create({
            'company_id': company.id,
            'qonto_remote_id': 'tx-out-1',
            'amount': 500.0,
            'amount_signed': -500.0,
            'currency_id': company.currency_id.id,
        })
        inv, conf, _hint = tx._sbu_find_invoice_match()
        self.assertEqual(conf, 'none')
        self.assertFalse(inv)

    @patch('odoo.addons.sbu_qonto.models.res_company.qonto_list_sepa_beneficiaries')
    @patch('odoo.addons.sbu_qonto.models.res_company.qonto_list_legacy_beneficiaries')
    def test_sync_qonto_partners_creates_supplier(
        self, mock_legacy, mock_sepa,
    ):
        mock_sepa.return_value = [{
            'id': 'ben-uuid-99',
            'name': 'Fornitore Qonto SRL',
            'iban': 'IT60X0542811101000000123456',
        }]
        mock_legacy.return_value = []
        company = self.env.company
        company.write({
            'sbu_qonto_login': 'login',
            'sbu_qonto_secret_key': 'secret',
            'sbu_qonto_iban': 'IT00X0000000000000000000000',
        })
        stats = company._sbu_sync_qonto_partners()
        partner = self.env['res.partner'].search([
            ('sbu_qonto_beneficiary_id', '=', 'ben-uuid-99'),
        ], limit=1)
        self.assertTrue(partner)
        self.assertGreaterEqual(partner.supplier_rank, 1)
        self.assertTrue(partner.sbu_qonto_partner_synced)
        self.assertEqual(stats['created'], 1)
        self.assertEqual(stats['total'], 1)

    def test_vendor_bill_match_by_invoice_number_in_label(self):
        if 'account.move' not in self.env:
            self.skipTest('account module required')
        company = self.env.company
        vendor = self.env['res.partner'].create({
            'name': 'Vendor match test',
            'supplier_rank': 1,
        })
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not journal:
            self.skipTest('Purchase journal required')
        bill = self.env['account.move'].with_context(default_move_type='in_invoice').create({
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'journal_id': journal.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test line',
                'quantity': 1,
                'price_unit': 500.0,
            })],
        })
        try:
            bill.action_post()
        except Exception as exc:
            self.skipTest('Vendor bill post not available: %s' % exc)
        inv_name = bill.name
        tx = self.env['sbu.qonto.transaction'].create({
            'company_id': company.id,
            'qonto_remote_id': 'tx-vbill-1',
            'amount': 500.0,
            'amount_signed': -500.0,
            'currency_id': company.currency_id.id,
            'label': 'Payment %s' % inv_name,
            'partner_id': vendor.id,
        })
        matched_bill, conf, _hint = tx._sbu_find_vendor_bill_match()
        self.assertEqual(conf, 'high')
        self.assertEqual(matched_bill, bill)
