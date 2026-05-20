# -*- coding: utf-8 -*-
import base64
import io

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

from odoo.addons.sbu_estimate.wizards.sbu_estimate_anaco_import_wizard import (
    _detect_sal_pct_start_column,
    _filter_model_fields,
    SAL_COL_SAL_START,
)


@tagged('post_install', '-at_install')
class TestSbuAnacoImport(TransactionCase):
    def test_filter_model_fields_drops_unknown_keys(self):
        line_model = self.env['sbu.estimate.line']
        vals = {
            'description': 'Test',
            'qty': 1.0,
            'cost_nolo_cad': 10.0,
        }
        filtered = _filter_model_fields(line_model, vals)
        self.assertNotIn('cost_nolo_cad', filtered)
        self.assertEqual(filtered['description'], 'Test')

    def test_import_smoke_with_minimal_workbook(self):
        if not openpyxl:
            self.skipTest('openpyxl not installed')
        partner = self.env['res.partner'].create({'name': 'Import smoke partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        wb = openpyxl.Workbook()
        default = wb.active
        wb.remove(default)
        sh = wb.create_sheet('ANACO')
        sh.cell(5, 11, 1.0)
        sh.cell(5, 12, 1.0)
        sh.cell(5, 13, 1.0)
        sh.cell(12, 2, 'FT01')
        sh.cell(12, 3, 'Finestra test')
        sh.cell(12, 8, 1)
        sh.cell(12, 71, 100.0)
        buf = io.BytesIO()
        wb.save(buf)
        wizard = self.env['sbu.estimate.anaco.import.wizard'].create({
            'estimate_id': estimate.id,
            'data_file': base64.b64encode(buf.getvalue()),
            'data_filename': 'smoke.xlsx',
            'import_anaco': True,
            'import_sal': False,
            'replace_anaco_lines': True,
        })
        wizard.action_import()
        self.assertEqual(len(estimate.line_ids), 1)
        self.assertEqual(estimate.line_ids[0].pos, 'FT01')

    def test_detect_sal_pct_start_column_non_rev7(self):
        if not openpyxl:
            self.skipTest('openpyxl not installed')
        wb = openpyxl.Workbook()
        default = wb.active
        wb.remove(default)
        sal = wb.create_sheet('Voci Contrattuali_SAL')
        sal.cell(10, 55, 'SAL-1')
        sal.cell(10, 56, 'SAL-2')
        self.assertEqual(_detect_sal_pct_start_column(sal), 55)
        self.assertEqual(_detect_sal_pct_start_column(sal, None, SAL_COL_SAL_START), 55)

    def test_import_sal_pct_from_detected_column(self):
        if not openpyxl:
            self.skipTest('openpyxl not installed')
        partner = self.env['res.partner'].create({'name': 'SAL col partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        wb = openpyxl.Workbook()
        default = wb.active
        wb.remove(default)
        sal = wb.create_sheet('Voci Contrattuali_SAL')
        sal.cell(10, 55, 'SAL-1')
        sal.cell(10, 56, 'SAL-2')
        sal.cell(16, 2, 'SAL-TEST')
        sal.cell(16, 3, 'Voce test SAL %')
        sal.cell(16, 4, 1)
        sal.cell(16, 8, 10000.0)
        sal.cell(16, 55, 20.0)
        sal.cell(16, 56, 30.0)
        buf = io.BytesIO()
        wb.save(buf)
        wizard = self.env['sbu.estimate.anaco.import.wizard'].create({
            'estimate_id': estimate.id,
            'data_file': base64.b64encode(buf.getvalue()),
            'data_filename': 'sal_col.xlsx',
            'import_anaco': False,
            'import_sal': True,
            'replace_sal_lines': True,
            'auto_detect_sal_columns': True,
        })
        wizard.action_import()
        self.assertEqual(len(estimate.sal_line_ids), 1)
        line = estimate.sal_line_ids[0]
        self.assertAlmostEqual(line.sal_1_pct, 20.0)
        self.assertAlmostEqual(line.sal_2_pct, 30.0)
        self.assertAlmostEqual(line.cumulative_pct, 50.0)

    def test_import_requires_file(self):
        partner = self.env['res.partner'].create({'name': 'Import no-file partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        wizard = self.env['sbu.estimate.anaco.import.wizard'].create({
            'estimate_id': estimate.id,
            'import_anaco': True,
            'import_sal': False,
        })
        with self.assertRaises(UserError):
            wizard.action_import()
