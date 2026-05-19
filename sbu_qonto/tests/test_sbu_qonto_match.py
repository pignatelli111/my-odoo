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
        Company = self.env['res.company'].sudo()
        previous = {
            c.id: c.sbu_qonto_import_enabled
            for c in Company.search([])
        }
        try:
            Company.search([]).write({'sbu_qonto_import_enabled': False})
            self.env.company.sbu_qonto_import_enabled = True
            Company._sbu_sync_qonto_cron_active()
            self.assertTrue(cron.active)
            self.env.company.sbu_qonto_import_enabled = False
            Company._sbu_sync_qonto_cron_active()
            self.assertFalse(cron.active)
        finally:
            for cid, enabled in previous.items():
                Company.browse(cid).sbu_qonto_import_enabled = enabled
            Company._sbu_sync_qonto_cron_active()
