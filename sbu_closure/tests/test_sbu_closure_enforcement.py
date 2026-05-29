# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuClosureEnforcement(TransactionCase):
    def test_cannot_close_job_with_open_checklist(self):
        partner = self.env['res.partner'].create({'name': 'Closure UAT Partner'})
        est = self.env['sbu.estimate'].create({
            'partner_id': partner.id,
            'line_ids': [(0, 0, {'description': 'Line', 'qty': 1.0})],
        })
        est.state = 'won'
        project = self.env['project.project'].create({
            'name': 'UAT Closure Job',
            'partner_id': partner.id,
            'sbu_estimate_id': est.id,
            'sbu_project_code': 'P0099',
        })
        doc_type = self.env['sbu.closure.document.type'].create({
            'name': 'UAT DOP',
            'code': 'UAT_DOP',
            'init_on_project': True,
            'default_required': True,
        })
        project._sbu_closure_init_missing_lines()
        self.assertTrue(project.sbu_closure_requirement_ids)
        with self.assertRaises(UserError):
            project.write({'sbu_state': 'closed'})
