# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels

SBU_BUDGET_OVER_PCT = 105.0


@tagged('post_install', '-at_install')
class TestSbuProjectBudget(TransactionCase):
    """Cosimo point 11: budget by cost family, traffic lights, admin PO unlock."""

    def _project_with_glass_budget(self, planned_cad=100.0):
        customer = self.env['res.partner'].create({'name': 'Budget test customer'})
        estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'VC01',
            'description': 'Glass package',
            'cost_family': 'glass',
            'cost_posa_lamiera_lin_cad': planned_cad,
            'cost_coibentazione_cad': 0.0,
            'cost_industrial_pct': 0.0,
            'qty': 1,
        })
        self.env.flush_all()
        # ANACO industrial % can inflate planned above raw CAD (yellow band on prod DB).
        self.assertGreaterEqual(
            eline.cost_total_tot,
            planned_cad,
            'estimate line cost_total_tot not computed',
        )
        project = self.env['project.project'].create({
            'name': 'Budget test job',
            'company_id': self.env.company.id,
            'sbu_estimate_id': estimate.id,
        })
        return project, estimate

    def _po_over_glass_budget(self, project):
        """Draft PO linked to glass PR line with offer above ANACO budget."""
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
            'request_id': pr.id,
            'request_line_id': pr_line.id,
            'vendor_id': partner.id,
            'unit_price': 120.0,
        })
        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'project_id': project.id,
            'sbu_purchase_request_id': pr.id,
        })
        pr._sbu_create_rfq_po_lines(po, pr_line)
        return po, pr_line

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

    def test_budget_check_blocks_when_over_budget(self):
        """Direct check on _sbu_check_budget_before_confirm (no PO confirm workflow)."""
        planned = 100.0
        project, _estimate = self._project_with_glass_budget(planned_cad=planned)
        po, _pr_line = self._po_over_glass_budget(project)
        pol = po.order_line.filtered('sbu_pr_line_id')
        self.assertEqual(len(pol), 1)
        # Prod supplier pricelists can lower PO subtotal; force a clearly red amount.
        pol.write({'price_unit': 250.0})
        self.env.flush_all()
        pol.invalidate_recordset(['price_subtotal'])
        self.assertGreater(pol.price_subtotal, planned * 1.1)

        rows = self.env['sbu.project.budget.family'].refresh_project(project)
        glass_row = rows.filtered(lambda r: r.cost_family == 'glass')
        self.assertEqual(len(glass_row), 1)
        self.assertGreater(glass_row.budget_planned, 0.0)
        self.assertGreater(glass_row.amount_engaged, glass_row.budget_planned)
        self.assertGreater(
            glass_row.pct_engaged,
            SBU_BUDGET_OVER_PCT,
            'planned=%s engaged=%s pct=%s light=%s'
            % (
                glass_row.budget_planned,
                glass_row.amount_engaged,
                glass_row.pct_engaged,
                glass_row.traffic_light,
            ),
        )
        self.assertTrue(glass_row.is_over_budget)
        self.assertTrue(
            self.env['sbu.project.budget.family'].project_has_over_budget(project),
        )

        # Dedicated buyer (no system group) — do not reuse prod users from search().
        internal = self.env.ref('base.group_user')
        purchase = self.env.ref('purchase.group_purchase_user')
        partner = self.env['res.partner'].create({
            'name': 'Budget plain buyer',
            'email': 'sbu_budget_plain_buyer@test.invalid',
        })
        plain = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Budget plain buyer',
            'login': 'sbu_budget_plain_%s' % partner.id,
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(6, 0, [internal.id, purchase.id])],
        })
        self.assertFalse(plain.has_group('base.group_system'))

        with self.assertRaises(UserError):
            po.with_user(plain)._sbu_check_budget_before_confirm()

    def test_budget_check_allows_unlock_on_project(self):
        project, _estimate = self._project_with_glass_budget(planned_cad=100.0)
        po, _pr_line = self._po_over_glass_budget(project)
        pol = po.order_line.filtered('sbu_pr_line_id')
        pol.write({'price_unit': 250.0})
        unlock_group = self.env.ref('sbu_purchase_flow.group_sbu_budget_unlock')
        partner = self.env['res.partner'].create({
            'name': 'Budget unlock buyer',
            'email': 'sbu_budget_unlock@test.invalid',
        })
        unlock_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Budget unlock buyer',
            'login': 'sbu_budget_unlock_%s' % partner.id,
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [
                (6, 0, [
                    self.env.ref('base.group_user').id,
                    self.env.ref('purchase.group_purchase_user').id,
                    unlock_group.id,
                ]),
            ],
        })
        project.sbu_budget_po_unlock = True
        po.with_user(unlock_user)._sbu_check_budget_before_confirm()

    def test_budget_flag_alone_not_enough_without_unlock_group(self):
        project, _estimate = self._project_with_glass_budget(planned_cad=100.0)
        po, _pr_line = self._po_over_glass_budget(project)
        pol = po.order_line.filtered('sbu_pr_line_id')
        pol.write({'price_unit': 250.0})
        project.sbu_budget_po_unlock = True
        internal = self.env.ref('base.group_user')
        purchase = self.env.ref('purchase.group_purchase_user')
        partner = self.env['res.partner'].create({
            'name': 'Budget flag only buyer',
            'email': 'sbu_budget_flag_only@test.invalid',
        })
        buyer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Budget flag only buyer',
            'login': 'sbu_budget_flag_%s' % partner.id,
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(6, 0, [internal.id, purchase.id])],
        })
        with self.assertRaises(UserError):
            po.with_user(buyer)._sbu_check_budget_before_confirm()

    def test_budget_check_skipped_for_admin(self):
        project, _estimate = self._project_with_glass_budget(planned_cad=100.0)
        po, _pr_line = self._po_over_glass_budget(project)
        # Default test env user has base.group_system.
        self.assertTrue(self.env.user.has_group('base.group_system'))
        po._sbu_check_budget_before_confirm()

    def test_refresh_includes_actual_and_syncs_estimate_line(self):
        project, estimate = self._project_with_glass_budget(planned_cad=100.0)
        eline = estimate.line_ids[0]
        uom = self.env.ref('uom.product_uom_unit')
        expense = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        product = self.env['product.product'].create({
            'name': 'Glass BOM',
            'default_code': 'GL-BUD-BOM',
            'type': 'consu',
            'purchase_ok': True,
            **({'property_account_expense_id': expense.id} if expense else {}),
        })
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': estimate.id,
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'uom_id': uom.id,
            'unit_cost': 10.0,
            'qty_ordered': 1.0,
        })
        partner = self.env['res.partner'].create({
            'name': 'Actual vendor',
            'supplier_rank': 1,
        })
        pr = self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': 'vt',
            'company_id': self.env.company.id,
        })
        pr_line = self.env['sbu.purchase.request.line'].create({
            'request_id': pr.id,
            'name': 'Glass BOM line',
            'product_id': product.id,
            'product_uom': uom.id,
            'product_qty': 1.0,
            'source_bom_line_id': bom.id,
        })
        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'project_id': project.id,
            'sbu_purchase_request_id': pr.id,
        })
        pr._sbu_create_rfq_po_lines(po, pr_line)
        pol = po.order_line.filtered('sbu_pr_line_id')
        pol.write({'price_unit': 40.0})
        po.button_confirm()

        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            self.skipTest('Purchase journal required for consuntivo test')
        po.action_create_invoice()
        bills = po.invoice_ids.filtered(lambda m: m.state == 'draft')
        if not bills:
            self.skipTest('PO did not create a vendor bill draft')
        bills.with_context(sbu_skip_budget_refresh=True).action_post()

        rows = self.env['sbu.project.budget.family'].with_context(
            sbu_skip_budget_refresh=True,
        ).refresh_project(project)
        glass = rows.filtered(lambda r: r.cost_family == 'glass')
        self.assertGreater(glass.amount_po_confirmed, 0.0)
        self.assertGreater(glass.amount_actual, 0.0)
        eline.invalidate_recordset()
        self.assertGreater(eline.budget_orders_issued, 0.0)
        self.assertGreater(eline.budget_costs_incurred, 0.0)
