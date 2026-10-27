# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuEstimateNewRevision(TransactionCase):

    def test_new_revision_copies_the_whole_estimate(self):
        Partner = self.env['res.partner']
        estimate = self.env['sbu.estimate'].create({
            'partner_id': Partner.create({'name': 'Revision customer'}).id,
            'anaco_pct_mol': 30.0, 'anaco_staffame_rate_ml': 9.0,
        })
        lines = self.env['sbu.estimate.line'].create([{
            'estimate_id': estimate.id, 'description': f'Window {w}', 'width_mm': w, 'height_mm': 1500, 'qty': 2,
            'price_serramento_cad': 300.0, 'price_vetro_cad': 80.0,
        } for w in (1000, 1200)])
        estimate._sbu_create_bom_from_anaco_lines()
        glass = Partner.create({'name': 'Vetreria', 'supplier_rank': 1})
        estimate.column_supplier_ids.filtered(lambda r: r.column_field == 'price_vetro_cad').partner_id = glass
        self.env['sbu.estimate.sal.line'].create({
            'estimate_id': estimate.id, 'item_ref': 'F1', 'description': 'Windows',
            'uom_type': 'mq', 'qty_contract': 10.0, 'unit_price': 100.0,
            'estimate_line_ids': [(6, 0, lines.ids)],
        })

        action = estimate.action_new_revision()
        new = self.env['sbu.estimate'].browse(action['res_id'])
        self.assertEqual(new.revision, 'REV01')
        self.assertEqual(len(new.line_ids), 2)
        self.assertEqual(len(new.item_bom_line_ids), len(estimate.item_bom_line_ids))
        self.assertEqual(len(new.sal_line_ids), 1)
        self.assertAlmostEqual(new.total_price, estimate.total_price, places=2)
        self.assertAlmostEqual(new.anaco_material_worked_total, estimate.anaco_material_worked_total, places=2)
        self.assertEqual(new.anaco_pct_mol, 30.0)
        self.assertFalse(new.item_bom_line_ids.estimate_line_id & estimate.line_ids, 'BOM points to the new lines')
        self.assertEqual(new.item_bom_line_ids.estimate_line_id, new.line_ids)
        self.assertEqual(new.sal_line_ids.estimate_line_ids, new.line_ids, 'SAL items point to the new lines')
        new_glass = new.column_supplier_ids.filtered(lambda r: r.column_field == 'price_vetro_cad')
        self.assertEqual(new_glass.partner_id, glass, 'supplier per column kept')
        self.assertEqual(len(estimate.line_ids), 2, 'the previous revision is untouched')
        self.assertFalse(estimate.sbu_is_latest_revision)
        self.assertTrue(new.sbu_is_latest_revision)
