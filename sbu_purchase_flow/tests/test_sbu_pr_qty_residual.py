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

    def test_demand_loss_shows_103_not_uom(self):
        """1.03 is qty after 3%% loss, not unit of measure."""
        partner = self.env['res.partner'].create({'name': 'Cliente 103'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'description': 'Voce test',
            'product_id': self.product.id,
        })
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': estimate.id,
            'estimate_line_id': eline.id,
            'product_id': self.product.id,
            'uom_id': self.uom.id,
            'qty_theoretical': 1.0,
            'demand_loss_pct': 0.0,
        })
        pr = self.env['sbu.purchase.request'].create({
            'project_id': self.project.id,
            'request_type': 'rda',
            'technical_data_state': 'ready_for_po',
            'demand_loss_pct': 3.0,
            'company_id': self.env.company.id,
        })
        line = self.env['sbu.purchase.request.line'].create({
            'request_id': pr.id,
            'name': 'BOM line',
            'product_id': self.product.id,
            'product_uom': self.uom.id,
            'source_bom_line_id': bom.id,
            'bom_qty_sync': True,
        })
        line.action_refresh_qty_from_bom()
        self.env.flush_all()
        self.assertAlmostEqual(line.product_qty, 1.03, places=2)
        self.assertEqual(line.product_uom, self.uom)
        self.assertAlmostEqual(line._sbu_qty_remaining_to_order(), 1.03, places=2)
        self.assertTrue(line.qty_demand_hint)

    def test_partial_rfq_updates_remaining(self):
        pr, line = self._create_pr_with_line(10.0)
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'company_id': self.env.company.id,
            'sbu_purchase_request_id': pr.id,
        })
        pr._sbu_create_rfq_po_lines(po, line)
        pol = po.order_line.filtered('sbu_pr_line_id')
        self.assertAlmostEqual(pol.product_qty, 10.0, places=2)
        pol.write({'product_qty': 3.0})
        self.env.flush_all()
        self.assertAlmostEqual(line.qty_ordered, 3.0, places=2)
        self.assertAlmostEqual(line._sbu_qty_remaining_to_order(), 7.0, places=2)
        self.assertFalse(line.qty_fully_ordered)

    def test_second_rfq_uses_remaining_only(self):
        pr, line = self._create_pr_with_line(10.0)
        po1 = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'company_id': self.env.company.id,
            'sbu_purchase_request_id': pr.id,
        })
        pr._sbu_create_rfq_po_lines(po1, line)
        po1.order_line.write({'product_qty': 4.0})
        self.env.flush_all()
        self.assertAlmostEqual(line._sbu_qty_remaining_to_order(), 6.0, places=2)
        po2 = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'company_id': self.env.company.id,
            'sbu_purchase_request_id': pr.id,
        })
        pr._sbu_create_rfq_po_lines(po2, line)
        pol2 = po2.order_line.filtered('sbu_pr_line_id')
        self.assertAlmostEqual(pol2.product_qty, 6.0, places=2)
        self.env.flush_all()
        self.assertAlmostEqual(line.qty_ordered, 10.0, places=2)

    def test_create_rfq_reuses_draft_po_and_residual(self):
        pr, line = self._create_pr_with_line(10.03)
        pr.action_create_rfq()
        self.env.flush_all()
        po = pr.purchase_order_ids[:1]
        self.assertTrue(po)
        pol = po.order_line.filtered('sbu_pr_line_id')
        self.assertAlmostEqual(pol.product_qty, 10.03, places=2)
        pol.write({'product_qty': 3.0})
        self.env.flush_all()
        self.assertAlmostEqual(line._sbu_qty_remaining_to_order(), 7.03, places=2)
        pr.action_create_rfq()
        self.env.flush_all()
        self.assertEqual(len(pr.purchase_order_ids), 1)
        self.assertAlmostEqual(pol.product_qty, 7.03, places=2)
