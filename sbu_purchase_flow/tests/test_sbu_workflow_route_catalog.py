# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuWorkflowRouteCatalog(TransactionCase):

    def test_catalog_has_la_route(self):
        la = self.env['sbu.workflow.route'].search([('code', '=', 'LA')], limit=1)
        self.assertTrue(la)
        self.assertEqual(la.request_type, 'rda')
        self.assertTrue(la.require_topic)

    def test_admin_can_add_custom_route(self):
        custom = self.env['sbu.workflow.route'].create({
            'code': 'TST',
            'name': 'Test route',
            'request_type': 'rda',
            'wizard_enabled': True,
        })
        sel = self.env['sbu.purchase.request']._sbu_workflow_route_selection()
        codes = [c for c, _label in sel]
        self.assertIn('TST', codes)
        custom.unlink()

    def test_by_workflow_skips_duplicate_open_pr(self):
        partner = self.env['res.partner'].create({'name': 'WF project customer'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id, 'state': 'won'})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'LA01',
            'description': 'Aluminium',
            'workflow_route': 'LA',
            'cost_family': 'aluminum_sheet',
            'qty': 1,
        })
        project = self.env['project.project'].create({
            'name': 'WF duplicate test',
            'company_id': self.env.company.id,
            'sbu_estimate_id': estimate.id,
        })
        project.action_sbu_create_purchase_requests_by_workflow()
        count1 = self.env['sbu.purchase.request'].search_count([
            ('project_id', '=', project.id),
            ('workflow_route', '=', 'LA'),
        ])
        self.assertEqual(count1, 1)
        project.action_sbu_create_purchase_requests_by_workflow()
        count2 = self.env['sbu.purchase.request'].search_count([
            ('project_id', '=', project.id),
            ('workflow_route', '=', 'LA'),
        ])
        self.assertEqual(count2, 1)
