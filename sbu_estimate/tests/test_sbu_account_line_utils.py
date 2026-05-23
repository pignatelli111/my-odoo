# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.models.sbu_account_line_utils import sbu_is_product_line


@tagged('post_install', '-at_install')
class TestSbuAccountLineUtils(TransactionCase):
    """Odoo 19 uses display_type='product' on invoice/PO lines."""

    def test_sbu_is_product_line_odoo19_product(self):
        line = self.env['account.move.line'].new({'display_type': 'product'})
        self.assertTrue(sbu_is_product_line(line))

    def test_sbu_is_product_line_legacy_false(self):
        line = self.env['account.move.line'].new({'display_type': False})
        self.assertTrue(sbu_is_product_line(line))

    def test_sbu_is_product_line_skips_section(self):
        line = self.env['account.move.line'].new({'display_type': 'line_section'})
        self.assertFalse(sbu_is_product_line(line))
