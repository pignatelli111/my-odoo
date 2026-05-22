# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuProjectBudget(TransactionCase):
    """Cosimo point 11: budget by cost family, traffic lights, admin PO unlock."""

    def _project_with_glass_budget(self, planned_cad=100.0):
        customer = self.env['res.partner'].create({'name': 'Budget test customer'})
        estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'VC01',
            'description': 'Glass package',
            'cost_family': 'glass',
            'cost_posa_lamiera_lin_cad': planned_cad,
            'qty': 1,
        })
        project = self.env['project.project'].create({
            'name': 'Budget test job',
            'company_id': self.env.company.id,
            'sbu_estimate_id': estimate.id,
        })
        return project, estimate

    def test_budget_family_model_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.project.budget.family')
        self.assertEqual(dups, {}, dups)

    def test_refresh_creates_family_row(self):
        project, _estimate = self._project_with_glass_budget()
        rows = self.env['sbu.project.budget.family'].refresh_project(project)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.cost_family, 'glass')
        self.assertGreater(row.budget_planned, 0.0)
        self.assertEqual(row.traffic_light, 'ok')

    def test_po_confirm_blocked_over_budget_admin_unlock(self):
        project, _estimate = self._project_with_glass_budget(planned_cad=100.0)
        partner = self.env['res.partner'].create({
            'name': 'Budget vendor',
            'supplier_rank': 1,
        })
        uom = self.env.ref('uom.product_uom_unit')
        product = self.env['product.product'].create({
            'name': 'Glass panel',
            'default_code': 'GL-BUD',
            'type': 'consu',
            'purchase_ok': True,
        })
        pr = self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': 'vt',
            'company_id': self.env.company.id,
        })
        pr_line = self.env['sbu.purchase.request.line'].create({
            'request_id': pr.id,
            'name': 'Glass line',
            'product_id': product.id,
            'product_uom': uom.id,
            'product_qty': 1.0,
        })
        self.env['sbu.purchase.request.offer'].create({
            'request_line_id': pr_line.id,
            'partner_id': partner.id,
            'unit_price': 120.0,
        })
        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'project_id': project.id,
            'sbu_purchase_request_id': pr.id,
        })
        pr._sbu_create_rfq_po_lines(po, pr_line)
        self.env.flush_all()

        rows = self.env['sbu.project.budget.family'].refresh_project(project)
        self.assertTrue(rows.is_over_budget)

        purchase_user = self.env.ref('base.group_user')
        buyer_group = self.env.ref('purchase.group_purchase_user')
        buyer = self.env['res.users'].create({
            'name': 'Purchase buyer budget test',
            'login': 'sbu_budget_buyer_test',
            'groups_id': [(6, 0, [purchase_user.id, buyer_group.id])],
        })
        with self.assertRaises(UserError):
            po.with_user(buyer).button_confirm()

        project.sudo().write({'sbu_budget_po_unlock': True})
        po.with_user(buyer).button_confirm()
        self.assertIn(po.state, ('purchase', 'done'))
