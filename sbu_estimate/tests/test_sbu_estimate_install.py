# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuEstimateInstall(TransactionCase):
    """Minimal smoke tests (no product/estimate creates — safe on Odoo.sh)."""

    def test_models_registered(self):
        self.assertEqual(self.env['sbu.estimate']._name, 'sbu.estimate')
        self.assertEqual(self.env['sbu.estimate.line']._rec_name, 'name')
        self.assertEqual(self.env['sbu.estimate.sal.line']._rec_name, 'name')
        self.assertEqual(self.env['sbu.estimate.bom.line']._name, 'sbu.estimate.bom.line')

    def test_security_groups_load_in_order(self):
        """Regression: approver must not reference UAT cleanup before it exists in XML."""
        user = self.env.ref('sbu_estimate.group_sbu_estimate_user', raise_if_not_found=False)
        uat = self.env.ref('sbu_estimate.group_sbu_estimate_uat_cleanup', raise_if_not_found=False)
        approver = self.env.ref('sbu_estimate.group_sbu_estimate_approver', raise_if_not_found=False)
        self.assertTrue(user and uat and approver)
        self.assertIn(user, approver.implied_ids)
        self.assertIn(uat, approver.implied_ids)
