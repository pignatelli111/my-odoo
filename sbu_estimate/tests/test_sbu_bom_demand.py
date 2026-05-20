# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuBomDemand(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'BOM demand test partner'})
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.product = cls.env['product.product'].create({
            'name': 'BOM demand test product',
            'uom_id': cls.uom_unit.id,
            'uom_po_id': cls.uom_unit.id,
        })

    def _create_bom_line(self, estimate_line, **bom_vals):
        estimate = estimate_line.estimate_id
        defaults = {
            'estimate_id': estimate.id,
            'estimate_line_id': estimate_line.id,
            'product_id': self.product.id,
            'calc_type': 'per_piece',
            'qty_formula_factor': 1.0,
            'uom_id': self.uom_unit.id,
            'unit_cost': 1.0,
        }
        defaults.update(bom_vals)
        return self.env['sbu.estimate.bom.line'].create(defaults)

    def test_demand_loss_increases_qty_ordered_and_total_cost(self):
        estimate = self.env['sbu.estimate'].create({'partner_id': self.partner.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'FTF-01',
            'description': 'Test line',
            'qty': 10.0,
        })
        bom = self._create_bom_line(
            eline,
            qty_formula_factor=4.0,
            demand_loss_pct=10.0,
            demand_moq=0.0,
            pack_size=0.0,
            unit_cost=0.8,
        )
        self.assertAlmostEqual(bom.qty_theoretical, 40.0)
        self.assertAlmostEqual(bom.qty_ordered, 44.0)
        self.assertAlmostEqual(bom.total_cost, 35.2)

    def test_demand_moq_raises_qty_ordered_and_total_cost(self):
        estimate = self.env['sbu.estimate'].create({'partner_id': self.partner.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'FTF-01',
            'description': 'Test line',
            'qty': 10.0,
        })
        bom = self._create_bom_line(
            eline,
            qty_formula_factor=1.0,
            demand_loss_pct=0.0,
            demand_moq=25.0,
            pack_size=0.0,
            unit_cost=2.0,
        )
        self.assertAlmostEqual(bom.qty_theoretical, 10.0)
        self.assertAlmostEqual(bom.qty_ordered, 25.0)
        self.assertAlmostEqual(bom.total_cost, 50.0)

    def test_loss_then_moq_then_pack_rounding(self):
        estimate = self.env['sbu.estimate'].create({'partner_id': self.partner.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'FTF-02',
            'description': 'Pack rounding',
            'qty': 10.0,
        })
        bom = self._create_bom_line(
            eline,
            qty_formula_factor=1.0,
            demand_loss_pct=10.0,
            demand_moq=20.0,
            pack_size=6.0,
            unit_cost=1.0,
        )
        # theoretical 10 → +10% = 11 → MOQ 20 → pack 6 → ceil(20/6)*6 = 24
        self.assertAlmostEqual(bom.qty_theoretical, 10.0)
        self.assertAlmostEqual(bom.qty_ordered, 24.0)
        self.assertAlmostEqual(bom.total_cost, 24.0)
