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


@tagged('post_install', '-at_install')
class TestSbuAnacoImport(TransactionCase):
    def _make_workbook_bytes(self):
        wb = openpyxl.Workbook()
        default = wb.active
        wb.remove(default)
        sh = wb.create_sheet('ANACO')
        sh.cell(5, 11, 1.0)
        sh.cell(5, 12, 1.0)
        sh.cell(5, 13, 1.0)
        sh.cell(12, 2, 'FT01')
        sh.cell(12, 3, 'Finestra test')
        sh.cell(12, 4, 1200)
        sh.cell(12, 6, 1400)
        sh.cell(12, 8, 2)
        sh.cell(12, 14, 100.0)
        sh.cell(12, 71, 250.0)
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue())

    def test_import_rejects_invalid_field_names(self):
        if not openpyxl:
            self.skipTest('openpyxl not installed')
        estimate = self.env['sbu.estimate'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Import Partner'}).id,
        })
        wizard = self.env['sbu.estimate.anaco.import.wizard'].create({
            'estimate_id': estimate.id,
            'data_file': self._make_workbook_bytes(),
            'data_filename': 'test_anaco.xlsx',
            'import_anaco': True,
            'import_sal': False,
            'replace_anaco_lines': True,
        })
        wizard.action_import()
        self.assertEqual(len(estimate.line_ids), 1)
        line = estimate.line_ids[0]
        self.assertEqual(line.pos, 'FT01')
        self.assertEqual(line.price_anaco_bs_cad, 250.0)

    def test_import_fails_without_file(self):
        estimate = self.env['sbu.estimate'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Import Partner 2'}).id,
        })
        wizard = self.env['sbu.estimate.anaco.import.wizard'].create({
            'estimate_id': estimate.id,
            'import_anaco': True,
            'import_sal': False,
        })
        with self.assertRaises(UserError):
            wizard.action_import()
