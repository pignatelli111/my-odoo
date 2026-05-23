# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuPoLineDimensions(TransactionCase):
    """Cosimo point 2: L/H/P + mq on RFQ lines from RDA."""

    def test_format_dimensions_string(self):
        from odoo.addons.sbu_estimate.models.sbu_dimension_format import format_sbu_dimensions
        text = format_sbu_dimensions(
            width_mm=2000,
            height_mm=2500,
            depth_mm=40,
            sqm_per_piece=4.5,
            sqm_total=45.0,
        )
        self.assertIn('L 2000', text)
        self.assertIn('H 2500', text)
        self.assertIn('P 40', text)
        self.assertIn('mq/cad', text)
        self.assertIn('mq tot', text)

    def test_pr_line_po_line_dimension_copy(self):
        uom = self.env.ref('uom.product_uom_unit')
        partner = self.env['res.partner'].create({
            'name': 'PO dim vendor',
            'supplier_rank': 1,
        })
        project = self.env['project.project'].create({'name': 'P0099 dim test'})
        pr = self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': 'rda',
            'technical_data_state': 'ready_for_po',
            'company_id': self.env.company.id,
        })
        product = self.env['product.product'].create({
            'name': 'Test profile',
            'default_code': 'TEST-DIM',
            'type': 'consu',
            'purchase_ok': True,
        })
        pr_line = self.env['sbu.purchase.request.line'].create({
            'request_id': pr.id,
            'name': 'Profilo test',
            'product_id': product.id,
            'product_uom': uom.id,
            'product_qty': 10.3,
            'width_mm': 1500,
            'height_mm': 2300,
            'depth_mm': 50,
            'sqm_per_piece': 3.45,
            'sqm_total': 34.5,
            'utilization': 'Montante',
        })
        self.env.flush_all()
        pr_line.invalidate_recordset(['dimension_mm'])
        self.assertIn('L 1500', pr_line.dimension_mm or '')
        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'sbu_purchase_request_id': pr.id,
        })
        pr._sbu_create_rfq_po_lines(po, pr_line)
        self.env.flush_all()
        pol = po.order_line.filtered(lambda l: l.sbu_pr_line_id.id == pr_line.id)
        self.assertEqual(len(pol), 1, po.order_line.mapped('name'))
        self.assertEqual(pol.sbu_width_mm, 1500)
        self.assertEqual(pol.sbu_height_mm, 2300)
        self.assertEqual(pol.sbu_depth_mm, 50)
        self.assertAlmostEqual(pol.sbu_sqm_per_piece, 3.45, places=3)
        self.assertAlmostEqual(pol.sbu_sqm_total, 34.5, places=3)
        self.assertIn('mq/cad', pol.sbu_dimension_summary or '')
        self.assertEqual(pol.sbu_utilization, 'Montante')
        pr_line.write({'utilization': 'Traverso'})
        pol.invalidate_recordset()
        self.assertEqual(pol.sbu_utilization, 'Traverso')
