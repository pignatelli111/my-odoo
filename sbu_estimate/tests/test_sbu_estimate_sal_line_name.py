# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuEstimateSalLineName(TransactionCase):
    def test_sal_line_display_name_for_many2one(self):
        partner = self.env['res.partner'].create({'name': 'Name test partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        sal = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': estimate.id,
            'item_ref': 'F1',
            'description': 'Serramento in legno doppia anta battente',
            'qty_contract': 10,
            'unit_price': 4443.06,
        })
        self.assertIn('F1', sal.name)
        self.assertIn('Serramento', sal.name)
        self.assertIn('44', sal.name)

        found = self.env['sbu.estimate.sal.line'].name_search(
            'F1',
            args=[('estimate_id', '=', estimate.id)],
        )
        self.assertTrue(found)
        self.assertEqual(found[0][0], sal.id)
        self.assertIn('F1', found[0][1])
