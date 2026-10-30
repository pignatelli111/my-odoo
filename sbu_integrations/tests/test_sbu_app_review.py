# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestSbuAppReview(TransactionCase):

    def test_review_lines(self):
        wizard = self.env['sbu.app.review.wizard'].create({})
        lines = {line.technical_name: line for line in wizard.line_ids}
        self.assertTrue(lines, 'installed apps are listed')
        self.assertTrue(all(self.env['ir.module.module'].search([('name', '=', name)]).application for name in lines))
        project = lines.get('project')
        if project:
            self.assertEqual(project.recommendation, 'required')
            self.assertTrue(project.needed_by)
        for name, line in lines.items():
            if name.startswith('sbu_'):
                self.assertEqual(line.recommendation, 'sbu')

    def test_user_records_ignore_odoo_data(self):
        Wizard = self.env['sbu.app.review.wizard']
        before = Wizard._sbu_user_records('project')
        user = new_test_user(self.env, 'app_review_user', groups='project.group_project_manager')
        self.env['project.project'].with_user(user).create({'name': 'Entered by a person'})
        after = Wizard._sbu_user_records('project')
        self.assertGreater(after, before, 'data entered by people is counted')
        self.env['project.project'].create({'name': 'Created by Odoo (superuser)'})
        self.assertEqual(Wizard._sbu_user_records('project'), after, 'records created by Odoo itself are not')
