# -*- coding: utf-8 -*-
import base64
import io

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

try:
    import openpyxl
except ImportError:
    openpyxl = None


@tagged('post_install', '-at_install')
class TestSbuPrExcelImport(TransactionCase):

    def _request(self):
        partner = self.env['res.partner'].create({'name': 'Excel PR partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        project = self.env['project.project'].create({
            'name': 'Excel PR project',
            'sbu_estimate_id': estimate.id,
        })
        return self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': 'rda',
            'workflow_route': 'LA',
            'topic': 'Test façade',
        })

    def _workbook_b64(self, rows):
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue())

    def test_excel_import_creates_lines(self):
        if not openpyxl:
            self.skipTest('openpyxl not installed')
        pr = self._request()
        data = self._workbook_b64([
            ['POS', 'Descrizione', 'L (mm)', 'H (mm)', 'Qty', 'Utilizzo'],
            ['1', 'Montante verticale', 1200, 3000, 4, 'Montante'],
        ])
        wizard = self.env['sbu.purchase.request.excel.import.wizard'].create({
            'request_id': pr.id,
            'data_file': data,
            'filename': 'rda.xlsx',
            'update_mode': 'merge',
        })
        wizard.action_import()
        self.assertEqual(len(pr.line_ids), 1)
        line = pr.line_ids
        self.assertEqual(line.pos, '1')
        self.assertEqual(line.width_mm, 1200.0)
        self.assertEqual(line.height_mm, 3000.0)
        self.assertEqual(line.utilization, 'Montante')
        self.assertEqual(pr.technical_data_state, 'excel_imported')
