# -*- coding: utf-8 -*-
from unittest.mock import patch

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

    def test_uat_cleanup_group_xml_id(self):
        group = self.env.ref('sbu_estimate.group_sbu_estimate_uat_cleanup', raise_if_not_found=False)
        self.assertTrue(group, 'SBU UAT cleanup group must be loaded')

    def test_normal_unlink_blocks_won(self):
        est = self._create_estimate(state='won')
        reason = est._sbu_unlink_blocked_reason()
        self.assertTrue(reason)
        with self.assertRaises(UserError):
            est.unlink()

    def test_force_delete_draft_as_admin(self):
        est = self._create_estimate(state='draft')
        self.assertFalse(est._sbu_unlink_blocked_reason())
        est._sbu_force_delete_with_cleanup()
        self.assertFalse(self.env['sbu.estimate'].browse(est.id).exists())

    def test_force_delete_won_without_project_as_admin(self):
        est = self._create_estimate(state='won')
        self.assertTrue(est._sbu_unlink_blocked_reason())
        est._sbu_force_delete_with_cleanup()
        self.assertFalse(self.env['sbu.estimate'].browse(est.id).exists())

    def test_force_delete_access_check_message(self):
        est = self._create_estimate(state='won')
        with patch.object(
            type(self.env.user),
            'has_group',
            lambda self, group_ext_id=None: False,
        ):
            with self.assertRaises(UserError) as cm:
                est._sbu_check_uat_force_delete_access()
        self.assertIn('UAT cleanup', str(cm.exception))
