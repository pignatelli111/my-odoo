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
        self.assertEqual(action.get('res_model'), 'sbu.purchase.request')
        pr = self.env['sbu.purchase.request'].browse(action['res_id'])
        self.assertTrue(pr.exists())
        self.assertEqual(pr.workflow_route, 'LA')
        self.assertEqual(pr.request_type, 'rda')
        self.assertEqual(pr.topic, 'Facciata sud')
        self.assertEqual(pr.company_id, self.env.company)
        self.assertFalse(pr.line_ids)

    def test_create_wizard_default_does_not_load_bom(self):
        wiz = self.env['sbu.purchase.request.create.wizard'].new({
            'project_id': self._project('Empty RDA').id,
            'workflow_route': 'LA',
        })
        self.assertFalse(wiz.load_from_estimate)

    def test_remove_bom_lines_keeps_manual_lines(self):
        partner = self.env['res.partner'].create({'name': 'Clear BOM partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        product = self.env['product.product'].create({
            'name': 'BOM item',
            'default_code': 'SBU-CLEAR',
            'type': 'consu',
            'purchase_ok': True,
        })
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'description': 'Line',
            'pos': 'F1',
            'cost_family': 'aluminum_sheet',
        })
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': estimate.id,
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'unit_cost': 1.0,
            'uom_id': product.uom_id.id,
        })
        project = self.env['project.project'].create({
            'name': 'Clear BOM job',
            'partner_id': partner.id,
            'sbu_estimate_id': estimate.id,
        })
        pr = self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': 'rda',
            'workflow_route': 'LA',
        })
        self.env['sbu.purchase.request.line'].create({
            'request_id': pr.id,
            'source_bom_line_id': bom.id,
            'name': 'From BOM',
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_qty': 1.0,
        })
        manual = self.env['sbu.purchase.request.line'].create({
            'request_id': pr.id,
            'name': 'Manual extra',
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_qty': 2.0,
        })
        pr.action_remove_lines_from_estimate_bom()
        self.assertEqual(pr.line_ids, manual)

    def test_collect_routes_splits_osc_from_glass(self):
        partner = self.env['res.partner'].create({'name': 'Route C'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'P01',
            'description': 'Glass position with oscurante',
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
