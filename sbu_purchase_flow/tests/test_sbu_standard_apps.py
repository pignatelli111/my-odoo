# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestSbuStandardApps(AccountTestInvoicingCommon):
    """Documents made directly in Purchase / Invoicing with a job count in that job."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.write({'group_ids': [(4, cls.env.ref(xmlid).id) for xmlid in (
            'project.group_project_manager', 'sbu_estimate.group_sbu_estimate_user',
            'purchase.group_purchase_manager', 'analytic.group_analytic_accounting',
        )]})
        customer = cls.env['res.partner'].create({'name': 'Standard apps customer'})
        cls.estimate = cls.env['sbu.estimate'].create({'partner_id': customer.id})
        cls.env['sbu.estimate.line'].create({
            'estimate_id': cls.estimate.id, 'description': 'Window', 'width_mm': 1000, 'height_mm': 1000,
            'qty': 1, 'price_serramento_cad': 5000.0,
        })
        cls.job = cls.env['project.project'].create({'name': 'Standard apps job', 'sbu_estimate_id': cls.estimate.id})
        cls.job_analytic = {str(cls.job.account_id.id): 100.0}
        cls.service = cls.env['product.product'].create({
            'name': 'Site crane', 'type': 'service', 'purchase_method': 'purchase', 'standard_price': 10.0,
        })

    def _overview(self):
        self.env.flush_all()
        return self.env['sbu.job.overview'].search([('project_id', '=', self.job.id)])

    def _pay(self, move):
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids,
        ).create({'payment_date': move.invoice_date})._create_payments()

    def test_vendor_bill_made_in_invoicing(self):
        bill = self.init_invoice('in_invoice', partner=self.partner_a, amounts=[400.0], taxes=[])
        bill.sbu_job_id = self.job
        self.assertEqual(bill.invoice_line_ids.analytic_distribution, self.job_analytic,
                         'choosing the job puts its analytic account on the lines')
        bill.write({'invoice_line_ids': [(0, 0, {'name': 'Extra', 'price_unit': 100.0, 'quantity': 1})]})
        self.assertTrue(all(l.analytic_distribution == self.job_analytic for l in bill.invoice_line_ids),
                        'lines added later follow the job')
        bill.action_post()
        budget = self.env['sbu.project.budget.family'].search([('project_id', '=', self.job.id)])
        self.assertAlmostEqual(sum(budget.mapped('amount_actual')), 500.0, msg='bill without PO counts as cost')
        self.assertAlmostEqual(self._overview().costs, 500.0)
        self.assertAlmostEqual(self._overview().to_pay, 500.0)

    def test_purchase_order_made_in_purchase(self):
        order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id, 'project_id': self.job.id,
            'order_line': [(0, 0, {'product_id': self.service.id, 'product_qty': 4, 'price_unit': 250.0})],
        })
        self.assertEqual(order.order_line.analytic_distribution, self.job_analytic)
        order.button_confirm()
        order.order_line.qty_received = 1
        overview = self._overview()
        self.assertAlmostEqual(overview.ordered, 1000.0)
        self.assertAlmostEqual(overview.received, 250.0)
        order.action_create_invoice()
        bill = order.invoice_ids
        bill.invoice_date = fields.Date.today()
        bill.action_post()
        self.assertEqual(bill.sbu_job_id, self.job)
        overview = self._overview()
        self.assertAlmostEqual(overview.costs, 1000.0)
        self.assertAlmostEqual(overview.budget_cost, self.estimate.total_cost)
        self.assertEqual(overview.over_budget, 1000.0 > self.estimate.total_cost)

    def test_customer_invoice_made_in_invoicing(self):
        invoice = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[3000.0], taxes=[])
        invoice.sbu_job_id = self.job
        invoice.action_post()
        self.assertEqual(invoice.sbu_job_id, self.job)
        self._pay(invoice)
        overview = self._overview()
        self.assertAlmostEqual(overview.invoiced, 3000.0)
        self.assertAlmostEqual(overview.collected, 3000.0)
        self.assertAlmostEqual(overview.to_collect, 0.0)
        self.assertAlmostEqual(overview.margin, 3000.0)
        action = overview.action_open_customer_invoices()
        self.assertEqual(self.env['account.move'].search(action['domain']), invoice)

    def test_posted_invoice_can_be_put_on_a_job(self):
        invoice = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[800.0], taxes=[], post=True)
        self.assertFalse(invoice.sbu_job_id)
        invoice.sbu_job_id = self.job
        self.assertEqual(invoice.invoice_line_ids.analytic_distribution, self.job_analytic)
        self.assertAlmostEqual(self._overview().invoiced, 800.0)
