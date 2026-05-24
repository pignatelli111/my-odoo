# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuBomImportWizard(TransactionCase):
    def _setup_pr_with_bom(self):
        partner = self.env['res.partner'].create({'name': 'BOM import partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        product = self.env['product.product'].create({
            'name': 'LA sheet item',
            'default_code': 'SBU-LA-TEST',
            'type': 'consu',
            'purchase_ok': True,
        })
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'description': 'Facade LA',
            'pos': 'F1',
            'cost_family': 'aluminum_sheet',
        })
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': estimate.id,
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'unit_cost': 10.0,
            'uom_id': product.uom_id.id,
        })
        project = self.env['project.project'].create({
            'name': 'BOM import job',
            'partner_id': partner.id,
        })
        project.write({'sbu_estimate_id': estimate.id})
        estimate.write({'project_id': project.id})
        pr = self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': 'rda',
            'workflow_route': 'LA',
        })
        self.env.flush_all()
        eline.invalidate_recordset(['workflow_route'])
        return pr, bom, eline

    def test_bom_import_wizard_loads_selected(self):
        pr, bom, _eline = self._setup_pr_with_bom()
        self.assertTrue(pr.estimate_id, 'PR must be linked to source estimate')
        wiz = self.env['sbu.purchase.request.bom.import.wizard'].create({
            'request_id': pr.id,
            'import_scope': 'all',
            'bom_line_ids': [(6, 0, bom.ids)],
        })
        wiz.action_load()
        self.assertEqual(len(pr.line_ids), 1)
        self.assertEqual(pr.line_ids.source_bom_line_id, bom)

    def test_route_scope_finds_la_bom(self):
        pr, bom, eline = self._setup_pr_with_bom()
        self.assertEqual(eline.workflow_route, 'LA')
        candidates = pr._candidate_bom_lines_for_import(scope='route')
        self.assertIn(bom, candidates)

    def test_open_bom_import_wizard_action(self):
        pr, _bom, _eline = self._setup_pr_with_bom()
        action = pr.action_load_lines_from_estimate_bom_append()
        self.assertEqual(action['res_model'], 'sbu.purchase.request.bom.import.wizard')

    def test_pr_line_technical_confirmed_writes_bom(self):
        pr, bom, _eline = self._setup_pr_with_bom()
        bom.needs_technical_confirm = True
        bom.technical_confirmed = False
        pr_line = self.env['sbu.purchase.request.line'].create({
            'request_id': pr.id,
            'source_bom_line_id': bom.id,
            'name': bom.product_id.display_name,
            'product_id': bom.product_id.id,
            'product_uom': bom.uom_id.id,
            'product_qty': 1.0,
        })
        pr_line.write({'technical_confirmed': True})
        bom.invalidate_recordset(['technical_confirmed'])
        self.assertTrue(bom.technical_confirmed)

    def test_wizard_filters_narrow_visible_lines(self):
        pr, bom, eline = self._setup_pr_with_bom()
        other_line = self.env['sbu.estimate.line'].create({
            'estimate_id': eline.estimate_id.id,
            'description': 'Glass row',
            'pos': 'F2',
            'cost_family': 'glass',
        })
        other_product = self.env['product.product'].create({
            'name': 'Glass pane',
            'default_code': 'SBU-GLASS',
            'type': 'consu',
            'purchase_ok': True,
        })
        other_bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': eline.estimate_id.id,
            'estimate_line_id': other_line.id,
            'product_id': other_product.id,
            'unit_cost': 5.0,
            'uom_id': other_product.uom_id.id,
        })
        wiz = self.env['sbu.purchase.request.bom.import.wizard'].create({
            'request_id': pr.id,
            'import_scope': 'all',
            'filter_estimate_line_id': eline.id,
        })
        self.assertIn(bom, wiz.visible_bom_line_ids)
        self.assertNotIn(other_bom, wiz.visible_bom_line_ids)
        wiz.write({
            'filter_estimate_line_id': False,
            'filter_cost_family': 'glass',
        })
        self.assertNotIn(bom, wiz.visible_bom_line_ids)
        self.assertIn(other_bom, wiz.visible_bom_line_ids)
