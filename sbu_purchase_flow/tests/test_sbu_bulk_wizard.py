# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuBulkWizard(TransactionCase):
    def test_bulk_apply_delivery_date(self):
        project = self.env['project.project'].create({'name': 'Bulk wiz'})
        pr = self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': 'rda',
        })
        product = self.env['product.product'].create({
            'name': 'Bulk item',
            'type': 'consu',
            'purchase_ok': True,
        })
        lines = self.env['sbu.purchase.request.line'].create([
            {
                'request_id': pr.id,
                'name': 'L1',
                'product_id': product.id,
                'product_qty': 1,
            },
            {
                'request_id': pr.id,
                'name': 'L2',
                'product_id': product.id,
                'product_qty': 2,
            },
        ])
        target = date(2026, 6, 15)
        wiz = self.env['sbu.purchase.request.line.bulk.wizard'].create({
            'line_ids': [(6, 0, lines.ids)],
            'apply_date_required': True,
            'date_required': target,
        })
        wiz.action_apply()
        self.assertEqual(set(lines.mapped('date_required')), {target})
