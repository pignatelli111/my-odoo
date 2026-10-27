# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestSbuJobAnalytic(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.write({'group_ids': [(4, cls.env.ref(xmlid).id) for xmlid in (
            'project.group_project_manager', 'sbu_estimate.group_sbu_estimate_user', 'purchase.group_purchase_manager',
        )]})

    def _job(self):
        customer = self.env['res.partner'].create({'name': 'Analytic customer'})
        estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        return self.env['project.project'].create({'name': 'Analytic job', 'sbu_estimate_id': estimate.id})

    def test_job_gets_analytic_account(self):
        job = self._job()
        self.assertTrue(job.account_id, 'SBU jobs get their analytic account')
        plain = self.env['project.project'].create({'name': 'Internal project'})
        self.assertFalse(plain.account_id, 'plain Odoo projects are left alone')

    def test_purchase_and_vendor_bill_follow_the_job(self):
        job = self._job()
        order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'project_id': job.id,
            'order_line': [(0, 0, {'product_id': self.product_a.id, 'product_qty': 2, 'price_unit': 100.0})],
        })
        self.assertEqual(order.order_line.analytic_distribution, {str(job.account_id.id): 100.0})
        order.button_confirm()
        order.order_line.qty_received = 2
        order.action_create_invoice()
        bill = order.invoice_ids
        self.assertEqual(bill.invoice_line_ids.analytic_distribution, {str(job.account_id.id): 100.0})
        self.assertEqual(bill.sbu_job_id, job)
        self.assertEqual(bill.action_sbu_open_job()['res_id'], job.id)
