# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuEstimateBomLineName(TransactionCase):

    def test_bom_line_display_name_for_many2one(self):
        partner = self.env['res.partner'].create({'name': 'BOM name partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'F1',
            'description': 'Facciata nord',
            'qty': 2.0,
            'width_mm': 1100,
            'height_mm': 1970,
        })
        product = self.env['product.product'].create({
            'name': 'Kit avvolgimento',
            'default_code': 'SBU-COIB',
            'type': 'consu',
        })
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': estimate.id,
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'calc_type': 'surface',
            'dimension_source': 'surface',
            'uom_id': product.uom_id.id,
        })
        self.env.flush_all()
        bom.invalidate_recordset(['name', 'dimension_display'])
        self.assertIn('F1', bom.name)
        self.assertIn('SBU-COIB', bom.name)
        self.assertIn('Kit avvolgimento', bom.name)
        self.assertNotIn('sbu.estimate.bom.line', bom.name)

        found = self.env['sbu.estimate.bom.line'].name_search(
            'SBU-COIB',
            domain=[('estimate_id', '=', estimate.id)],
        )
        self.assertTrue(found)
        self.assertEqual(found[0][0], bom.id)
        self.assertIn('SBU-COIB', found[0][1])
