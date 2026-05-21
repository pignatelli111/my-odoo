# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuBomDimensionRules(TransactionCase):
    """Cosimo point 1: glass 90% mq, zanzariere +300 mm height on distinta."""

    def _ensure_product(self, code, name):
        product = self.env['product.product'].search(
            [('default_code', '=', code)], limit=1,
        )
        if product:
            return product
        self.env['product.template'].create({
            'name': name,
            'default_code': code,
            'type': 'consu',
            'purchase_ok': True,
        })
        return self.env['product.product'].search(
            [('default_code', '=', code)], limit=1,
        )

    def _line_with_dims(self, w_mm, h_mm, qty=10.0, **extra_line_vals):
        partner = self.env['res.partner'].create({'name': 'Dim rules partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        vals = {
            'estimate_id': estimate.id,
            'pos': 'F1',
            'description': 'Posizione test',
            'qty': qty,
            'width_mm': w_mm,
            'height_mm': h_mm,
        }
        vals.update(extra_line_vals)
        eline = self.env['sbu.estimate.line'].create(vals)
        return eline

    def _bom_for_code(self, eline, code):
        product = self._ensure_product(
            code,
            {'SBU-VETRO': 'Vetro', 'SBU-ZANZ': 'Zanzariera', 'SBU-OSC': 'Oscuramento'}.get(code, code),
        )
        cov = 0.9 if code == 'SBU-VETRO' else 1.0
        h_adj = 300.0 if code in ('SBU-ZANZ', 'SBU-OSC') else 0.0
        return self.env['sbu.estimate.bom.line'].create({
            'estimate_id': eline.estimate_id.id,
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'calc_type': 'surface',
            'dimension_source': 'surface',
            'sqm_coverage_factor': cov,
            'height_adjust_mm': h_adj,
            'qty_formula_factor': cov,
            'needs_technical_confirm': True,
            'uom_id': product.uom_id.id,
        })

    def test_glass_90pct_sqm(self):
        eline = self._line_with_dims(2000, 2500, qty=10.0)
        bom = self._bom_for_code(eline, 'SBU-VETRO')
        self.assertAlmostEqual(bom.sqm_per_piece_effective, 4.5, places=3)
        self.assertAlmostEqual(bom.qty_theoretical, 45.0, places=3)
        self.assertIn('2000', bom.dimension_display)
        self.assertTrue(bom.needs_technical_confirm)

    def test_zanzariere_height_plus_300(self):
        eline = self._line_with_dims(1500, 2000, qty=5.0)
        bom = self._bom_for_code(eline, 'SBU-ZANZ')
        self.assertEqual(bom.height_mm_effective, 2300.0)
        self.assertAlmostEqual(bom.sqm_per_piece_effective, 3.45, places=3)
        self.assertAlmostEqual(bom.qty_theoretical, 17.25, places=3)

    def test_anaco_bom_generation_applies_vetro_rule(self):
        self._ensure_product('SBU-VETRO', 'Vetro')
        eline = self._line_with_dims(1000, 1000, qty=1.0, price_vetro_cad=500.0)
        estimate = eline.estimate_id
        n = estimate._sbu_create_bom_from_anaco_lines()
        self.assertGreater(n, 0)
        vetro = estimate.item_bom_line_ids.filtered(
            lambda b: b.product_id.default_code == 'SBU-VETRO',
        )
        self.assertEqual(len(vetro), 1)
        self.assertAlmostEqual(vetro.sqm_coverage_factor, 0.9, places=4)
        self.assertEqual(vetro.calc_type, 'surface')
        self.assertTrue(vetro.needs_technical_confirm)
