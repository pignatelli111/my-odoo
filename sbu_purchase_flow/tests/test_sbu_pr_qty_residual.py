# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuPrQtyResidual(TransactionCase):
    """Cosimo point 15: RDA qty remaining after partial RFQ qty."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom = cls.env.ref('uom.product_uom_unit')
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Residual vendor',
            'supplier_rank': 1,
        })
        cls.project = cls.env['project.project'].create({'name': 'P015 residual'})
        cls.product = cls.env['product.product'].create({
            'name': 'Residual item',
            'default_code': 'RES-01',
            'type': 'consu',
            'purchase_ok': True,
        })

    def _create_pr_with_line(self, product_qty=10.0):
        pr = self.env['sbu.purchase.request'].create({
            'project_id': self.project.id,
            'request_type': 'rda',
            'technical_data_state': 'ready_for_po',
            'vendor_id': self.vendor.id,
            'company_id': self.env.company.id,
        })
        line = self.env['sbu.purchase.request.line'].create({
            'request_id': pr.id,
            'name': 'Test residual',
            'product_id': self.product.id,
            'product_uom': self.uom.id,
            'product_qty': product_qty,
            'bom_qty_sync': False,
        })
        self.env.flush_all()
        return pr, line

    def test_demand_loss_three_percent_is_qty_not_uom(self):
        """1.03 = 1.00 × (1 + 3%% loss) — quantity column, not UoM."""
        BomLine = self.env['sbu.estimate.bom.line']
        qty = BomLine._sbu_apply_demand_qty_rules(1.0, loss_pct=3.0)
        self.assertAlmostEqual(qty, 1.03, places=2)

    def test_partial_rfq_updates_remaining(self):
        pr, line = self._create_pr_with_line(10.0)
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'company_id': self.env.company.id,
            'sbu_purchase_request_id': pr.id,
        })
        pr._sbu_create_rfq_po_lines(po, line)
        pol = po.order_line.filtered('sbu_pr_line_id')
        self.assertEqual(len(pol), 1)
        self.assertAlmostEqual(pol.product_qty, 10.0, places=2)
        pol.write({'product_qty': 3.0})
        self.env.flush_all()
        self.assertAlmostEqual(line.qty_ordered, 3.0, places=2)
        self.assertAlmostEqual(line._sbu_qty_remaining_to_order(), 7.0, places=2)

    def test_create_rfq_reuses_draft_po_and_residual(self):
        pr, line = self._create_pr_with_line(10.03)
        pr.action_create_rfq()
        self.env.flush_all()
        po = pr.purchase_order_ids[:1]
        self.assertTrue(po, 'RFQ should link via sbu_purchase_request_id')
        pol = po.order_line.filtered('sbu_pr_line_id')
        self.assertAlmostEqual(pol.product_qty, 10.03, places=2)
        pol.write({'product_qty': 3.0})
        self.env.flush_all()
        self.assertAlmostEqual(line._sbu_qty_remaining_to_order(), 7.03, places=2)
        pr.action_create_rfq()
        self.env.flush_all()
        self.assertEqual(len(pr.purchase_order_ids), 1)
        self.assertAlmostEqual(pol.product_qty, 10.03, places=2, msg='re-run brings the draft back to the full need')
        self.assertAlmostEqual(line._sbu_qty_remaining_to_order(), 0.0, places=2)

    def test_rfq_to_several_suppliers_are_alternatives(self):
        second = self.env['res.partner'].create({'name': 'Second quote', 'supplier_rank': 1})
        pr, line = self._create_pr_with_line(10.0)
        pr.vendor_ids = [(6, 0, (self.vendor | second).ids)]
        pr.action_create_rfq()
        self.env.flush_all()
        self.assertEqual(len(pr.purchase_order_ids), 2)
        for po in pr.purchase_order_ids:
            self.assertAlmostEqual(po.order_line.filtered('sbu_pr_line_id').product_qty, 10.0, places=2,
                                   msg=f'{po.partner_id.name} gets the full quantity to quote')
        self.assertAlmostEqual(line.qty_ordered, 10.0, places=2, msg='alternative quotes are not added up')

    def test_confirmed_partial_order_then_rfq_for_the_rest(self):
        pr, line = self._create_pr_with_line(10.03)
        pr.action_create_rfq()
        po = pr.purchase_order_ids
        po.order_line.filtered('sbu_pr_line_id').product_qty = 4.0
        po.button_confirm()
        self.env.flush_all()
        self.assertAlmostEqual(line._sbu_qty_remaining_to_order(), 6.03, places=2)
        pr.action_create_rfq()
        new_po = pr.purchase_order_ids - po
        self.assertEqual(len(new_po), 1)
        self.assertAlmostEqual(new_po.order_line.filtered('sbu_pr_line_id').product_qty, 6.03, places=2)
