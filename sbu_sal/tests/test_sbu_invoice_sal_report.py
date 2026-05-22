# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuInvoiceSalReport(TransactionCase):

    def _customer_sal_sheet(self):
        customer = self.env['res.partner'].create({'name': 'SAL detail customer'})
        estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        sal_contract = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': estimate.id,
            'item_ref': 'F1',
            'description': 'Curtain wall package',
            'uom_type': 'mq',
            'qty_contract': 100.0,
            'unit_price': 250.0,
        })
        project = self.env['project.project'].create({
            'name': 'SAL detail project',
            'company_id': self.env.company.id,
            'sbu_estimate_id': estimate.id,
        })
        sheet = self.env['sbu.sal.sheet'].create({
            'project_id': project.id,
            'retention_percent': 5.0,
        })
        self.env['sbu.sal.sheet.line'].create({
            'sheet_id': sheet.id,
            'estimate_sal_line_id': sal_contract.id,
            'description': sal_contract.description,
            'contract_amount': 25000.0,
            'percent_this_sal': 10.0,
        })
        return sheet, sal_contract

    def test_sal_sheet_line_labels_distinct(self):
        """Regression: duplicate labels on sbu.sal.sheet.line trigger Odoo.sh WARNING."""
        dups = duplicate_custom_field_labels(self.env, 'sbu.sal.sheet.line')
        self.assertEqual(dups, {}, dups)

    def test_report_action_registered(self):
        report = self.env.ref('sbu_sal.action_report_sbu_invoice_sal_detail', raise_if_not_found=False)
        self.assertTrue(report)
        self.assertEqual(report.model, 'account.move')

    def test_sheet_line_contract_meta(self):
        sheet, sal_contract = self._customer_sal_sheet()
        line = sheet.line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.item_ref, 'F1')
        self.assertEqual(line.qty_display, 100.0)
        self.assertEqual(line.unit_price_display, 250.0)
        self.assertTrue(line.uom_label)

    def test_invoice_links_sal_sheet(self):
        sheet, _sal = self._customer_sal_sheet()
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal or not journal.default_account_id:
            self.skipTest('Sales journal with default account required')
        if sheet.amount_retention > 0 and not self.env.company.sbu_sal_retention_account_id:
            self.env.company.sbu_sal_retention_account_id = journal.default_account_id

        sheet.action_confirm()
        sheet.action_create_draft_invoice()
        self.env.flush_all()
        move = sheet.invoice_id
        self.assertEqual(move.sbu_sal_sheet_id, sheet)
        self.assertFalse(move.sbu_sal_cdp_name)

        sheet.action_create_certificate()
        self.env.flush_all()
        self.assertTrue(sheet.certificate_ids, 'CDP should be created on the SAL sheet')
        move.invalidate_recordset(['sbu_sal_cdp_name'])
        cdp_name = move.sbu_sal_cdp_name
        self.assertTrue(cdp_name, 'CDP name should appear on the invoice after certificate create')

        action = sheet.action_print_invoice_sal_detail()
        self.assertEqual(action.get('type'), 'ir.actions.report')
        self.assertEqual(
            action.get('report_name'),
            'sbu_sal.report_sbu_invoice_sal_detail_document',
        )
        active_ids = action.get('context', {}).get('active_ids') or []
        self.assertIn(move.id, active_ids)
