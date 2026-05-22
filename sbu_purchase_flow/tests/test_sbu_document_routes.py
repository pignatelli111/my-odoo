# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_purchase_flow.models.sbu_workflow_routing import (
    collect_workflow_routes_from_estimate,
    workflow_route_to_request_type,
)


@tagged('post_install', '-at_install')
class TestSbuDocumentRoutes(TransactionCase):

    def test_route_maps_to_request_type(self):
        self.assertEqual(workflow_route_to_request_type('LA'), 'rda')
        self.assertEqual(workflow_route_to_request_type('LZ'), 'fe')
        self.assertEqual(workflow_route_to_request_type('OSC'), 'vt')
        self.assertEqual(workflow_route_to_request_type('ST'), 'st')

    def _project(self, name):
        return self.env['project.project'].create({
            'name': name,
            'company_id': self.env.company.id,
        })

    def test_create_wizard_la_requires_topic(self):
        project = self._project('Route wizard')
        wiz = self.env['sbu.purchase.request.create.wizard'].create({
            'project_id': project.id,
            'workflow_route': 'LA',
            'load_from_estimate': False,
            'need_by_date': date(2026, 8, 1),
        })
        with self.assertRaises(UserError):
            wiz.action_create()

    def test_create_wizard_la_success(self):
        project = self._project('Route LA')
        wiz = self.env['sbu.purchase.request.create.wizard'].create({
            'project_id': project.id,
            'workflow_route': 'LA',
            'load_from_estimate': False,
            'need_by_date': date(2026, 8, 1),
            'topic': 'Facciata sud',
        })
        action = wiz.action_create()
        pr = self.env['sbu.purchase.request'].browse(action['res_id'])
        self.assertEqual(pr.workflow_route, 'LA')
        self.assertEqual(pr.request_type, 'rda')
        self.assertEqual(pr.topic, 'Facciata sud')

    def test_collect_routes_splits_osc_from_glass(self):
        partner = self.env['res.partner'].create({'name': 'Route C'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        estimate.write({'state': 'won'})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'P01',
            'cost_family': 'glass',
            'qty': 1,
        })
        osc = self.env['product.product'].search(
            [('default_code', '=', 'SBU-OSC')], limit=1,
        )
        if not osc:
            self.env['product.template'].create({
                'name': 'Oscurante test',
                'default_code': 'SBU-OSC',
                'type': 'consu',
            })
            osc = self.env['product.product'].search(
                [('default_code', '=', 'SBU-OSC')], limit=1,
            )
        self.env['sbu.estimate.bom.line'].create({
            'estimate_id': estimate.id,
            'estimate_line_id': eline.id,
            'product_id': osc.id,
            'calc_type': 'surface',
            'qty_theoretical': 1,
            'uom_id': osc.uom_id.id,
        })
        routes = collect_workflow_routes_from_estimate(estimate)
        self.assertIn('OSC', routes)
