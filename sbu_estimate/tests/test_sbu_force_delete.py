# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuForceDelete(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'UAT Force Delete Client'})
        cls.uat_user = cls.env['res.users'].create({
            'name': 'UAT Cleanup User',
            'login': 'uat_cleanup_test',
            'email': 'uat_cleanup_test@example.com',
            'groups_id': [
                Command.link(cls.env.ref('sbu_estimate.group_sbu_estimate_uat_cleanup').id),
                Command.link(cls.env.ref('base.group_user').id),
            ],
        })

    def _create_estimate(self, state='draft'):
        return self.env['sbu.estimate'].create({
            'partner_id': self.partner.id,
            'state': state,
        })

    def test_normal_unlink_blocks_won(self):
        est = self._create_estimate(state='won')
        with self.assertRaises(UserError):
            est.unlink()

    def test_force_delete_draft(self):
        est = self._create_estimate(state='draft')
        est.with_user(self.uat_user)._sbu_force_delete_with_cleanup()
        self.assertFalse(self.env['sbu.estimate'].browse(est.id).exists())

    def test_force_delete_won_without_project(self):
        est = self._create_estimate(state='won')
        est.with_user(self.uat_user)._sbu_force_delete_with_cleanup()
        self.assertFalse(self.env['sbu.estimate'].browse(est.id).exists())

    def test_force_delete_requires_group(self):
        est = self._create_estimate(state='won')
        plain = self.env['res.users'].create({
            'name': 'Plain',
            'login': 'plain_uat_test',
            'email': 'plain@example.com',
            'groups_id': [Command.link(self.env.ref('base.group_user').id)],
        })
        with self.assertRaises(UserError):
            est.with_user(plain)._sbu_force_delete_with_cleanup()
