# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuSalInstall(TransactionCase):
    """Smoke test so Odoo.sh records sbu_sal in the test suite."""

    def test_models_registered(self):
        self.assertTrue(self.env['sbu.sal.sheet']._name)
        self.assertTrue(self.env['sbu.payment.certificate']._name)
