# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuSalLineImportWizard(TransactionCase):
    def _setup_sheet(self):
        customer = self.env['res.partner'].create({'name': 'SAL import customer'})
        estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        sal_a = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': estimate.id,
            'item_ref': 'F1',
            'description': 'Facade package',
            'uom_type': 'mq',
            'qty_contract': 100.0,
            'unit_price': 100.0,
        })
        sal_b = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': estimate.id,
            'item_ref': 'F2',
            'description': 'Glass option',
            'uom_type': 'corpo',
            'qty_contract': 1.0,
            'unit_price': 5000.0,
        })
        project = self.env['project.project'].create({
            'name': 'SAL import project',
            'sbu_estimate_id': estimate.id,
        })
        sheet = self.env['sbu.sal.sheet'].create({'project_id': project.id})
        return sheet, sal_a, sal_b

    def test_import_wizard_adds_selected_lines(self):
        sheet, sal_a, _sal_b = self._setup_sheet()
        wiz = self.env['sbu.sal.sheet.line.import.wizard'].create({
            'sheet_id': sheet.id,
            'import_scope': 'all',
        })
        wiz.line_ids.write({'selected': False})
        wiz.line_ids.filtered(
            lambda ln: ln.contract_line_id == sal_a
        ).write({'selected': True})
        wiz.action_load()
        self.assertEqual(len(sheet.line_ids), 1)
        self.assertEqual(sheet.line_ids.estimate_sal_line_id, sal_a)

    def test_apply_filters_narrows_list(self):
        sheet, sal_a, sal_b = self._setup_sheet()
        wiz = self.env['sbu.sal.sheet.line.import.wizard'].create({
            'sheet_id': sheet.id,
            'import_scope': 'all',
        })
        self.assertEqual(wiz.filtered_count, 2)
        wiz.write({'filter_item_ref': 'F1'})
        wiz.action_apply_filters()
        self.assertEqual(wiz.filtered_count, 1)
        self.assertEqual(wiz.line_ids.contract_line_id, sal_a)

    def test_missing_scope_excludes_lines_on_sheet(self):
        sheet, sal_a, sal_b = self._setup_sheet()
        self.env['sbu.sal.sheet.line'].create({
            'sheet_id': sheet.id,
            'estimate_sal_line_id': sal_a.id,
            'description': sal_a.description,
            'contract_amount': sal_a.total_contract,
        })
        wiz = self.env['sbu.sal.sheet.line.import.wizard'].create({
            'sheet_id': sheet.id,
            'import_scope': 'missing',
        })
        self.assertEqual(wiz.filtered_count, 1)
        self.assertEqual(wiz.line_ids.contract_line_id, sal_b)
