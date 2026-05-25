# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuProjectBillingDashboard(TransactionCase):

    def _project_with_sal_billing(self):
        customer = self.env['res.partner'].create({'name': 'Dashboard billing customer'})
        estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        sal_contract = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': estimate.id,
            'item_ref': 'D1',
            'description': 'Facade scope',
            'uom_type': 'mq',
            'qty_contract': 50.0,
            'unit_price': 400.0,
        })
        project = self.env['project.project'].create({
            'name': 'Billing dashboard project',
            'company_id': self.env.company.id,
            'sbu_estimate_id': estimate.id,
        })
        sheet = self.env['sbu.sal.sheet'].create({
            'project_id': project.id,
            'retention_percent': 0.0,
        })
        self.env['sbu.sal.sheet.line'].create({
            'sheet_id': sheet.id,
            'estimate_sal_line_id': sal_contract.id,
            'description': sal_contract.description,
            'contract_amount': 20000.0,
            'percent_this_sal': 25.0,
        })
        return project, sheet, sal_contract

    def test_project_sbu_billing_field_labels_distinct(self):
        """Regression: duplicate sbu_* labels on project.project fail Odoo.sh builds."""
        dups = duplicate_custom_field_labels(
            self.env, 'project.project', field_prefix='sbu_',
        )
        self.assertEqual(dups, {}, dups)

    def test_billing_dashboard_kpis_from_contract_lines(self):
        project, sheet, sal_contract = self._project_with_sal_billing()
        project.invalidate_recordset()
        project._compute_sbu_billing_dashboard()
        self.assertEqual(project.sbu_billing_contract_total, 20000.0)
        self.assertEqual(project.sbu_billing_billed, 0.0)
        self.assertEqual(project.sbu_billing_remaining, 20000.0)
        self.assertEqual(project.sbu_billing_open_sal_count, 1)

        sheet.action_confirm()
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal or not journal.default_account_id:
            self.skipTest('Sales journal with default account required')
        sheet.action_create_draft_invoice()
        sal_contract._sbu_recompute_billing_from_sheet_lines()
        project.invalidate_recordset()
        project._compute_sbu_billing_dashboard()
        self.assertGreater(project.sbu_billing_billed, 0.0)
        self.assertLess(project.sbu_billing_remaining, project.sbu_billing_contract_total)
        self.assertTrue(project.sbu_billing_last_invoice_id)

    def test_customer_invoice_domain_never_uses_missing_move_project_id(self):
        """Odoo.sh: account.move has no project_id — domain must use SAL sheet link only."""
        project, _sheet, _sal = self._project_with_sal_billing()
        domain = self.env['project.project']._sbu_customer_invoice_domain(project)
        field_names = {term[0] for term in domain if isinstance(term, (list, tuple)) and len(term) >= 3}
        self.assertNotIn('project_id', field_names)
        self.assertIn('sbu_sal_sheet_id.project_id', field_names)
        # Must not raise during search (regression: Invalid field account.move.project_id)
        self.env['account.move'].search(domain, limit=1)

    def test_billing_dashboard_actions(self):
        project, _sheet, _sal = self._project_with_sal_billing()
        action = project.action_sbu_contractual_billing_overview()
        self.assertEqual(action['res_model'], 'sbu.estimate.sal.line')
        inv_action = project.action_sbu_customer_invoices()
        self.assertEqual(inv_action['res_model'], 'account.move')

    def test_invoice_ref_includes_sal_and_job(self):
        project, sheet, _sal = self._project_with_sal_billing()
        sheet.action_confirm()
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal or not journal.default_account_id:
            self.skipTest('Sales journal with default account required')
        sheet.action_create_draft_invoice()
        move = sheet.invoice_id
        self.assertIn(sheet.name, move.ref)
        self.assertIn('SAL', move.ref)
        if project.sbu_revision_label:
            self.assertIn(project.sbu_revision_label, move.ref)
        sheet.action_create_certificate()
        move.invalidate_recordset(['ref', 'sbu_sal_cdp_name'])
        self.assertTrue(move.sbu_sal_cdp_name)
        self.assertIn('CDP', move.ref)
