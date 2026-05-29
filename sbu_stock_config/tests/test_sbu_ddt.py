# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuDdt(TransactionCase):
    def test_ddt_sequence_and_picking_fields(self):
        seq = self.env.ref('sbu_stock_config.seq_sbu_ddt_number', raise_if_not_found=False)
        self.assertTrue(seq)
        self.assertEqual(seq.code, 'sbu.stock.ddt')
        picking = self.env['stock.picking']
        for fname in ('sbu_ddt_number', 'sbu_carrier_name', 'project_id'):
            self.assertIn(fname, picking._fields)

    def test_assign_ddt_number_on_picking(self):
        wh = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1
        )
        if not wh:
            self.skipTest('No warehouse on company')
        picking_type = wh.in_type_id
        partner = self.env['res.partner'].create({'name': 'DDT smoke vendor'})
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'partner_id': partner.id,
        })
        picking._sbu_assign_ddt_number_if_missing()
        self.assertTrue(picking.sbu_ddt_number)
        self.assertTrue(str(picking.sbu_ddt_number).startswith('DDT/'))
