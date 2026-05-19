# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuEstimateInstall(TransactionCase):
    """Smoke tests for Odoo.sh."""

    def test_estimate_line_rec_name(self):
        line_model = self.env['sbu.estimate.line']
        self.assertEqual(line_model._rec_name, 'name')
        self.assertIn('name', line_model._fields)

    def test_bom_line_sets_estimate_from_anaco_row(self):
        partner = self.env['res.partner'].create({'name': 'UAT Partner'})
        est = self.env['sbu.estimate'].with_company(self.env.company).create({
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'line_ids': [(0, 0, {
                'description': 'UAT BOM smoke line',
                'pos': 'FT01',
                'qty': 1.0,
            })],
        })
        eline = est.line_ids[0]
        tmpl = self.env['product.template'].create({
            'name': 'UAT smoke product',
            'type': 'consu',
            'purchase_ok': True,
        })
        product = tmpl.product_variant_ids[0]
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'calc_type': 'per_piece',
            'uom_id': product.uom_id.id,
        })
        self.assertEqual(bom.estimate_id, est)
