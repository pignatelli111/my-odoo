# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuEstimateInstall(TransactionCase):
    """Smoke tests for Odoo.sh (avoid overriding Model.display_name)."""

    def test_estimate_line_uses_name_not_custom_display_name(self):
        line_model = self.env['sbu.estimate.line']
        self.assertIn('name', line_model._fields)
        self.assertEqual(line_model._rec_name, 'name')
        # Must not replace the framework display_name field with a stored custom one.
        disp = line_model._fields['display_name']
        self.assertTrue(disp.compute)

    def test_bom_line_sets_estimate_from_anaco_row(self):
        partner = self.env['res.partner'].create({'name': 'UAT Partner'})
        est = self.env['sbu.estimate'].create({
            'partner_id': partner.id,
            'line_ids': [(0, 0, {
                'description': 'UAT BOM smoke line',
                'pos': 'FT01',
                'qty': 1.0,
            })],
        })
        eline = est.line_ids[0]
        product = self.env['product.product'].create({
            'name': 'UAT smoke product',
            'type': 'consu',
            'purchase_ok': True,
        })
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'calc_type': 'per_piece',
            'uom_id': product.uom_id.id,
        })
        self.assertEqual(bom.estimate_id, est)
