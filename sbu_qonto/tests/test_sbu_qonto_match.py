# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


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
        ):
            self.assertIn(fname, tx._fields)

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
