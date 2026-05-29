# -*- coding: utf-8 -*-
"""ANACO cost rollup layout (Cosimo feedback — materiale → add-on → subtotale → industriali)."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuAnacoCostRollup(TransactionCase):

    def _line(self, **extra):
        partner = self.env['res.partner'].create({'name': 'Rollup partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        vals = {
            'estimate_id': estimate.id,
            'description': 'Rollup test line',
            'qty': 2.0,
            'cost_coibentazione_cad': 100.0,
            'cost_posa_lamiera_lin_cad': 50.0,
            'cost_trasporto_cad': 10.0,
            'cost_tech_pm_cad': 5.0,
            'cost_cantiere_cad': 3.0,
            'cost_extra_cad': 2.0,
            'cost_industrial_pct': 10.0,
            'cost_mol_pct': 4.0,
            'price_anaco_bs_cad': 500.0,
        }
        vals.update(extra)
        return self.env['sbu.estimate.line'].create(vals)

    def test_cost_rollup_breakdown(self):
        line = self._line()
        self.assertAlmostEqual(line.cost_material_worked_cad, 150.0)
        self.assertAlmostEqual(line.cost_material_worked_tot, 300.0)
        self.assertAlmostEqual(line.cost_trasporto_tot, 20.0)
        self.assertAlmostEqual(line.cost_tech_pm_tot, 10.0)
        self.assertAlmostEqual(line.cost_cantiere_tot, 6.0)
        self.assertAlmostEqual(line.cost_extra_tot, 4.0)
        self.assertAlmostEqual(line.cost_subtotal_cad, 170.0)
        self.assertAlmostEqual(line.cost_subtotal_tot, 340.0)
        self.assertAlmostEqual(line.cost_industrial_cad, 15.0)
        self.assertAlmostEqual(line.cost_industrial_tot, 30.0)
        self.assertAlmostEqual(line.cost_mol_amount_cad, 6.0)
        self.assertAlmostEqual(line.cost_mol_amount_tot, 12.0)
        self.assertAlmostEqual(line.cost_total_cad, 185.0)
        self.assertAlmostEqual(line.cost_total_tot, 370.0)
        self.assertAlmostEqual(line.margin_amount, 630.0)

    def test_estimate_header_anaco_totals(self):
        line = self._line()
        estimate = line.estimate_id
        self.assertAlmostEqual(estimate.anaco_material_worked_total, 300.0)
        self.assertAlmostEqual(estimate.anaco_cost_subtotal, 340.0)
        self.assertAlmostEqual(estimate.anaco_industrial_total, 30.0)
        self.assertAlmostEqual(estimate.anaco_mol_total, 12.0)
        self.assertAlmostEqual(estimate.total_cost, 370.0)
        self.assertAlmostEqual(estimate.total_price, 1000.0)

    def test_bb_bc_certified_totals_unchanged(self):
        line = self._line(
            cost_coibentazione_cad=0.0,
            cost_posa_lamiera_lin_cad=0.0,
            cost_anaco_bb_cad=120.0,
            cost_anaco_bc_tot=250.0,
            cost_trasporto_cad=0.0,
            cost_industrial_pct=0.0,
            cost_mol_pct=0.0,
        )
        self.assertAlmostEqual(line.cost_material_worked_cad, 120.0)
        self.assertAlmostEqual(line.cost_total_cad, 120.0)
        self.assertAlmostEqual(line.cost_total_tot, 250.0)
