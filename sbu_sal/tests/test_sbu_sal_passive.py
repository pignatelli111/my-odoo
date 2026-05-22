# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuSalPassive(TransactionCase):

    def _estimate_with_posa(self):
        customer = self.env['res.partner'].create({'name': 'Passive SAL customer'})
        vendor = self.env['res.partner'].create({
            'name': 'Installer subcontractor',
            'supplier_rank': 1,
        })
        estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        eline = self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'POS01',
            'description': 'Installation package',
            'cost_family': 'installation',
            'cost_posa_lamiera_lin_cad': 100.0,
            'qty': 2,
            'discount_sc1': 10.0,
        })
        project = self.env['project.project'].create({
            'name': 'Passive SAL project',
            'company_id': self.env.company.id,
            'sbu_estimate_id': estimate.id,
        })
        return estimate, eline, project, vendor

    def test_models_registered(self):
        self.assertTrue(self.env['sbu.sal.passive.sheet']._name)
        self.assertTrue(self.env['sbu.sal.passive.line']._name)

    def test_passive_model_labels_distinct(self):
        """Regression: duplicate labels on SBU fields (not mail.thread Followers)."""
        for model in (
            'sbu.sal.passive.sheet',
            'sbu.sal.passive.line',
            'sbu.sal.sheet',
            'sbu.payment.certificate',
            'account.move',
        ):
            dups = duplicate_custom_field_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')

    def test_load_posa_budget_from_estimate(self):
        estimate, eline, project, vendor = self._estimate_with_posa()
        sheet = self.env['sbu.sal.passive.sheet'].create({
            'project_id': project.id,
            'vendor_id': vendor.id,
            'subcontract_scope': 'posa',
        })
        sheet.action_load_posa_budget_from_estimate()
        self.assertEqual(len(sheet.line_ids), 1)
        line = sheet.line_ids[0]
        self.assertEqual(line.estimate_line_id, eline)
        self.assertEqual(line.category, 'posa_lin')
        self.assertGreater(line.budget_amount, 0.0)

    def test_passive_sal_vendor_bill(self):
        estimate, eline, project, vendor = self._estimate_with_posa()
        sheet = self.env['sbu.sal.passive.sheet'].create({
            'project_id': project.id,
            'vendor_id': vendor.id,
        })
        sheet.action_load_posa_budget_from_estimate()
        sheet.line_ids.write({'percent_this_sal': 50.0})
        sheet.action_confirm()
        self.assertGreater(sheet.amount_net, 0.0)

        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal or not journal.default_account_id:
            self.skipTest('Purchase journal with default account required for vendor bill test')

        action = sheet.action_create_vendor_bill()
        self.assertEqual(action['res_model'], 'account.move')
        move = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(move.move_type, 'in_invoice')
        self.assertEqual(move.partner_id, vendor)
        self.assertEqual(sheet.state, 'invoiced')
        self.assertEqual(sheet.vendor_bill_id, move)

    def test_reload_budget_blocked_with_lines(self):
        _, _, project, vendor = self._estimate_with_posa()
        sheet = self.env['sbu.sal.passive.sheet'].create({
            'project_id': project.id,
            'vendor_id': vendor.id,
        })
        sheet.action_load_posa_budget_from_estimate()
        with self.assertRaises(UserError):
            sheet.action_load_posa_budget_from_estimate()

    def test_prior_sal_percent_cumulative(self):
        estimate, eline, project, vendor = self._estimate_with_posa()
        first = self.env['sbu.sal.passive.sheet'].create({
            'project_id': project.id,
            'vendor_id': vendor.id,
        })
        first.action_load_posa_budget_from_estimate()
        first.line_ids.write({'percent_this_sal': 30.0})
        first.action_confirm()

        second = self.env['sbu.sal.passive.sheet'].create({
            'project_id': project.id,
            'vendor_id': vendor.id,
        })
        second.action_load_posa_budget_from_estimate()
        self.env.flush_all()
        prior = second.line_ids.mapped('percent_prior_sal')
        self.assertEqual(len(prior), 1)
        self.assertAlmostEqual(prior[0], 30.0)
