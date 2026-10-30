# -*- coding: utf-8 -*-
from odoo.exceptions import RedirectWarning
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_sal.tests.test_sbu_invoice_sal_report import TestSbuInvoiceSalReport


@tagged('post_install', '-at_install')
class TestSbuSetupChecklist(TransactionCase):

    def _checks(self):
        settings = self.env['res.config.settings'].create({})
        return settings, {check['label']: check for check in settings._sbu_setup_checks()}

    def test_checklist_rows(self):
        company = self.env.company
        company.write({'sbu_sal_retention_account_id': False, 'sbu_sal_default_retention_percent': 5.0})
        settings, checks = self._checks()
        self.assertEqual(checks['SAL retention account']['status'], 'missing')
        self.assertEqual(checks['Revolut connection']['status'], 'optional')
        numbering = checks['Numbering: Estimates']
        self.assertEqual(numbering['status'], 'ok')
        self.assertIn('PRV/', numbering['detail'])
        for label in ('Numbering: SAL sheets', 'Numbering: Payment certificates (CDP)',
                      'Numbering: Purchase requests (RDA)'):
            self.assertIn(label, checks)
        html = str(settings.sbu_setup_checklist_html)
        self.assertIn('setting(s) missing before go-live', html)
        self.assertIn('SAL retention account', html)

        account = self.env['account.account'].search([('company_ids', 'in', company.id)], limit=1)
        company.sbu_sal_retention_account_id = account
        _settings, checks = self._checks()
        self.assertEqual(checks['SAL retention account']['status'], 'ok')

    def test_sal_invoice_without_retention_account_offers_settings(self):
        self.env.company.sbu_sal_retention_account_id = False
        sheet, _contract = TestSbuInvoiceSalReport._customer_sal_sheet(self)
        sheet.action_confirm()
        with self.assertRaises(RedirectWarning) as err:
            sheet.action_create_draft_invoice()
        _message, action, button = err.exception.args[:3]
        self.assertEqual(action['res_model'], 'res.company')
        self.assertEqual(action['res_id'], self.env.company.id)
        self.assertEqual(button, 'Open company settings')
