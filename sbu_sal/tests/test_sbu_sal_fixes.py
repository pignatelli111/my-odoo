# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestSbuSalFixes(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.write({'group_ids': [(4, cls.env.ref(xmlid).id) for xmlid in (
            'project.group_project_manager', 'sbu_estimate.group_sbu_estimate_user',
        )]})
        cls.customer = cls.env['res.partner'].create({'name': 'SAL fixes customer'})
        cls.estimate = cls.env['sbu.estimate'].create({'partner_id': cls.customer.id})
        cls.project = cls.env['project.project'].create({'name': 'SAL fixes job', 'sbu_estimate_id': cls.estimate.id})

    def _sheet(self, contract, percent):
        sheet = self.env['sbu.sal.sheet'].create({'project_id': self.project.id, 'retention_percent': 0.0})
        self.env['sbu.sal.sheet.line'].create({
            'sheet_id': sheet.id, 'estimate_sal_line_id': contract.id, 'description': contract.description,
            'contract_amount': 10000.0, 'percent_this_sal': percent,
        })
        return sheet

    def test_customer_sal_cannot_exceed_100_percent(self):
        contract = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': self.estimate.id, 'item_ref': 'F1', 'description': 'Facade',
            'uom_type': 'mq', 'qty_contract': 100.0, 'unit_price': 100.0,
        })
        first = self._sheet(contract, 60.0)
        first.action_confirm()
        with self.assertRaises(ValidationError):
            self._sheet(contract, 50.0)
        second = self._sheet(contract, 40.0)  # exactly 100% is allowed
        self.assertEqual(sum((first | second).line_ids.mapped('percent_this_sal')), 100.0)
        second.action_cancel()
        third = self._sheet(contract, 40.0)  # a cancelled sheet no longer counts
        second.state = 'draft'  # reset the cancelled one: confirming it would bill 140%
        with self.assertRaises(ValidationError):
            second.action_confirm()
        self.assertTrue(third)

    def test_subcontractor_bill_uses_one_chosen_tax(self):
        vendor = self.env['res.partner'].create({'name': 'Installer', 'supplier_rank': 1})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': self.estimate.id, 'pos': 'POS01', 'description': 'Installation',
            'cost_family': 'installation', 'cost_posa_lamiera_lin_cad': 100.0, 'qty': 2,
        })
        reverse_charge = self.env['account.tax'].create({
            'name': '22% RC test', 'amount': 22, 'type_tax_use': 'purchase', 'amount_type': 'percent',
        })
        sheet = self.env['sbu.sal.passive.sheet'].create({'project_id': self.project.id, 'vendor_id': vendor.id})
        self.assertEqual(sheet.tax_ids, self.env.company.account_purchase_tax_id, 'company default proposed')
        sheet.tax_ids = reverse_charge
        sheet.action_load_posa_budget_from_estimate()
        self.assertEqual(sheet.line_ids.estimate_line_id, eline)
        sheet.line_ids.write({'percent_this_sal': 50.0})
        sheet.action_confirm()
        bill = self.env['account.move'].browse(sheet.action_create_vendor_bill()['res_id'])
        self.assertTrue(bill.invoice_line_ids)
        for line in bill.invoice_line_ids:
            self.assertEqual(line.tax_ids, reverse_charge, 'exactly the chosen tax, never two taxes')

    def test_invoice_made_in_invoicing_counts_in_job_billing(self):
        invoice = self.init_invoice('out_invoice', partner=self.customer, amounts=[1500.0], taxes=[])
        invoice.sbu_job_id = self.project
        invoice.action_post()
        self.project.invalidate_recordset()
        self.assertAlmostEqual(self.project.sbu_billing_other_invoiced, 1500.0)
        self.assertEqual(self.project.sbu_billing_last_invoice_id, invoice)
        self.assertIn(invoice, self.env['account.move'].search(self.project.action_sbu_customer_invoices()['domain']))
