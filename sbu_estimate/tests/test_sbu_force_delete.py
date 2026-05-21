# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuForceDelete(TransactionCase):
    """Smoke tests for UAT force-delete (no res.users.create — safe on Odoo.sh)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'UAT Force Delete Client'})

    def _create_estimate(self, state='draft'):
        return self.env['sbu.estimate'].create({
            'partner_id': self.partner.id,
            'state': state,
        })

    def test_uat_cleanup_group_and_action_load(self):
        self.assertTrue(
            self.env.ref('sbu_estimate.group_sbu_estimate_uat_cleanup', raise_if_not_found=False)
        )
        action = self.env.ref(
            'sbu_estimate.action_sbu_estimate_force_delete_wizard',
            raise_if_not_found=False,
        )
        self.assertTrue(action)
        self.assertIn(
            self.env.ref('sbu_estimate.group_sbu_estimate_uat_cleanup'),
            action.group_ids,
        )

    def test_normal_unlink_blocks_won(self):
        est = self._create_estimate(state='won')
        self.assertTrue(est._sbu_unlink_blocked_reason())
        with self.assertRaises(UserError):
            est.unlink()

    def test_force_delete_won_without_project_as_admin(self):
        est = self._create_estimate(state='won')
        est._sbu_force_delete_with_cleanup()
        self.assertFalse(self.env['sbu.estimate'].browse(est.id).exists())
