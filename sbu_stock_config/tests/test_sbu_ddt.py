# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuDdt(TransactionCase):
    def test_ddt_sequence_on_validate(self):
        partner = self.env['res.partner'].create({'name': 'DDT UAT Vendor'})
        product = self.env['product.product'].create({
            'name': 'DDT UAT Product',
            'type': 'consu',
            'purchase_ok': True,
        })
        project = self.env['project.project'].create({'name': 'DDT UAT Job'})
        wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        picking_type = wh.in_type_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'partner_id': partner.id,
            'project_id': project.id,
            'move_ids': [(0, 0, {
                'name': product.display_name,
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': 1.0,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.quantity = 1.0
        picking._sbu_assign_ddt_number_if_missing()
        self.assertTrue(picking.sbu_ddt_number)
        self.assertTrue(picking.sbu_ddt_number.startswith('DDT/'))
