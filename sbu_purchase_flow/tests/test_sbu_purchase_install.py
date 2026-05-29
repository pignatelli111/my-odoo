# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuPurchaseInstall(TransactionCase):
    """Smoke tests so Odoo.sh runs sbu_purchase_flow after install."""

    def test_models_registered(self):
        self.assertEqual(self.env['sbu.purchase.request']._name, 'sbu.purchase.request')
        self.assertEqual(
            self.env['sbu.purchase.request.line.bulk.wizard']._name,
            'sbu.purchase.request.line.bulk.wizard',
        )
        self.assertEqual(
            self.env['sbu.purchase.request.create.wizard']._name,
            'sbu.purchase.request.create.wizard',
        )
        self.assertEqual(
            self.env['sbu.purchase.request.bom.import.wizard']._name,
            'sbu.purchase.request.bom.import.wizard',
        )
        pr = self.env['sbu.purchase.request']
        self.assertEqual(pr._fields['workflow_route'].type, 'selection')
        line = self.env['sbu.purchase.request.line']
        self.assertEqual(line._fields['workflow_route'].type, 'selection')
        po_line = self.env['purchase.order.line']
        for fname in (
            'sbu_pr_line_id',
            'sbu_width_mm',
            'sbu_height_mm',
            'sbu_depth_mm',
            'sbu_sqm_per_piece',
            'sbu_dimension_summary',
        ):
            self.assertIn(fname, po_line._fields, fname)
        pr_line = self.env['sbu.purchase.request.line']
        for fname in ('qty_ordered', 'qty_remaining', 'qty_fully_ordered'):
            self.assertIn(fname, pr_line._fields, fname)
        self.assertEqual(
            self.env['sbu.purchase.request']._fields['purchase_order_ids'].type,
            'many2many',
        )
