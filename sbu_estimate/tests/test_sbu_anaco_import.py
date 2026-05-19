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
    _filter_model_fields,
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
