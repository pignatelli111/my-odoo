# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuEstimateInstall(TransactionCase):
    """Minimal smoke tests (no product/estimate creates — safe on Odoo.sh)."""

    def test_models_registered(self):
        self.assertEqual(self.env['sbu.estimate']._name, 'sbu.estimate')
        self.assertEqual(self.env['sbu.estimate.line']._rec_name, 'name')
        self.assertEqual(self.env['sbu.estimate.bom.line']._name, 'sbu.estimate.bom.line')
