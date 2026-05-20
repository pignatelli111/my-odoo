# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuBomDemand(TransactionCase):
    """ITEM demand qty: loss %, MOQ, pack rounding (Cosimo UAT cases)."""

    def test_apply_demand_qty_rules_loss_pct(self):
        Bom = self.env['sbu.estimate.bom.line']
        qty = Bom._sbu_apply_demand_qty_rules(40.0, loss_pct=10.0)
        self.assertAlmostEqual(qty, 44.0, places=4)

    def test_apply_demand_qty_rules_moq(self):
        Bom = self.env['sbu.estimate.bom.line']
        qty = Bom._sbu_apply_demand_qty_rules(10.0, moq=25.0)
        self.assertAlmostEqual(qty, 25.0, places=4)

    def test_apply_demand_qty_rules_loss_moq_pack(self):
        Bom = self.env['sbu.estimate.bom.line']
        # 10 → +10% = 11 → MOQ 20 → pack 6 → 24
        qty = Bom._sbu_apply_demand_qty_rules(
            10.0, loss_pct=10.0, moq=20.0, pack_size=6.0,
        )
        self.assertAlmostEqual(qty, 24.0, places=4)

    def test_bom_line_stored_qty_ordered_and_total_cost(self):
        """End-to-end on sbu.estimate.bom.line compute fields."""
        partner = self.env['res.partner'].create({'name': 'BOM demand partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'FTF-01',
            'description': 'Test line',
            'qty': 10.0,
        })
        tmpl = self.env.ref(
            'sbu_estimate.product_tmpl_uat_fastener',
            raise_if_not_found=False,
        )
        if not tmpl:
            self.skipTest('UAT product not loaded')
        product = tmpl.product_variant_ids[:1]
        if not product:
            self.skipTest('UAT product has no variant')
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': estimate.id,
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'calc_type': 'per_piece',
            'qty_formula_factor': 4.0,
            'demand_loss_pct': 10.0,
            'pack_size': 0.0,
            'demand_moq': 0.0,
            'uom_id': product.uom_id.id,
            'unit_cost': 0.8,
        })
        self.assertAlmostEqual(bom.qty_theoretical, 40.0, places=4)
        self.assertAlmostEqual(bom.qty_ordered, 44.0, places=4)
        self.assertAlmostEqual(bom.total_cost, 35.2, places=2)
