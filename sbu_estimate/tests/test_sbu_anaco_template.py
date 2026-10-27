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

from odoo.addons.sbu_estimate.models.sbu_anaco_template import TEMPLATE_ID, TEMPLATE_SHEET, TEMPLATE_VERSION

ROW_PARAMS = {
    'anaco_pct_transport': 4.0, 'anaco_pct_tech_pm': 10.0, 'anaco_pct_extra': 1.0, 'anaco_pct_mol': 55.0,
    'anaco_staffame_rate_ml': 9.0, 'anaco_posa_rate_sqm': 60.0, 'anaco_posa_min_sqm': 1.8,
}


@tagged('post_install', '-at_install')
class TestSbuAnacoTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        if not openpyxl:
            self.skipTest('openpyxl not installed')
        partner = self.env['res.partner'].create({'name': 'Template customer'})
        self.estimate = self.env['sbu.estimate'].create(dict(ROW_PARAMS, partner_id=partner.id))

    def _template_workbook(self):
        action = self.estimate.action_download_anaco_template()
        attachment = self.env['ir.attachment'].browse(int(action['url'].split('/')[3].split('?')[0]))
        return openpyxl.load_workbook(io.BytesIO(base64.b64decode(attachment.datas)))

    def _import(self, wb, **options):
        buf = io.BytesIO()
        wb.save(buf)
        target = self.env['sbu.estimate'].create({'partner_id': self.estimate.partner_id.id})
        self.env['sbu.estimate.anaco.import.wizard'].create(dict({
            'estimate_id': target.id,
            'data_file': base64.b64encode(buf.getvalue()),
            'data_filename': 'filled.xlsx',
            'import_sal': False,
            'import_distinta_bom': False,
        }, **options)).action_import()
        return target

    def test_download_template(self):
        wb = self._template_workbook()
        marker = wb[TEMPLATE_SHEET]
        self.assertEqual((marker['A1'].value, marker['B1'].value), (TEMPLATE_ID, TEMPLATE_VERSION))
        self.assertEqual(marker.sheet_state, 'veryHidden')
        sheet = wb['ANACO']
        self.assertTrue(sheet.protection.sheet)
        self.assertEqual(sheet['P5'].value, 9.0)
        self.assertEqual(sheet['AV5'].value, 60.0)
        self.assertAlmostEqual(sheet['BP5'].value, 0.55)
        self.assertEqual(sheet['AV12'].value, '=MAX(G12,$AW$5)*$AV$5')
        self.assertFalse(sheet['J12'].protection.locked, 'inputs are editable')
        self.assertTrue(sheet['BB12'].protection.locked, 'formulas are protected')
        self.assertIn('Voci Contrattuali_SAL', wb.sheetnames)

    def test_filled_template_imports_like_excel(self):
        wb = self._template_workbook()
        sheet = wb['ANACO']
        for row, (width, height, qty, price) in ((12, (350, 1500, 1, 108.72)), (13, (500, 800, 6, 134.59))):
            sheet[f'B{row}'], sheet[f'C{row}'] = 'ser', f'Serramento {width}x{height}'
            sheet[f'D{row}'], sheet[f'F{row}'], sheet[f'H{row}'] = width, height, qty
            sheet[f'J{row}'], sheet[f'AD{row}'] = price, 15
        estimate = self._import(wb, allow_legacy_files=False)
        self.assertAlmostEqual(estimate.anaco_staffame_rate_ml, 9.0)
        self.assertEqual((estimate.anaco_posa_min_sqm, estimate.anaco_posa_rate_sqm), (1.8, 60.0))
        first, second = estimate.line_ids.sorted('sequence')
        self.assertAlmostEqual(first.cost_material_worked_cad, 265.02)  # Excel row 12
        self.assertAlmostEqual(first.price_total_cad, 450.534)
        self.assertAlmostEqual(second.cost_material_worked_cad, 280.99)  # Excel row 13
        self.assertAlmostEqual(second.price_total_cad, 477.683)
        self.assertFalse(second.price_anaco_bs_cad, 'BS is a formula: price stays computed')
        self.assertTrue(any('modello SBU' in m.body for m in estimate.message_ids))

    def test_modified_template_is_refused(self):
        wb = self._template_workbook()
        wb['ANACO']['AV4'] = 'Posa a corpo'
        with self.assertRaises(UserError) as err:
            self._import(wb)
        self.assertIn('column AV', str(err.exception))

    def test_foreign_or_newer_template_is_refused(self):
        wb = self._template_workbook()
        wb[TEMPLATE_SHEET]['B1'] = TEMPLATE_VERSION + 1
        with self.assertRaises(UserError):
            self._import(wb)
        wb[TEMPLATE_SHEET]['B1'] = TEMPLATE_VERSION
        wb[TEMPLATE_SHEET]['A1'] = 'SBU-RDA'
        with self.assertRaises(UserError):
            self._import(wb)

    def test_legacy_files_option(self):
        wb = self._template_workbook()
        del wb[TEMPLATE_SHEET]
        sheet = wb['ANACO']
        sheet['B12'], sheet['C12'], sheet['D12'], sheet['F12'], sheet['H12'], sheet['AD12'] = 'ser', 'Legacy', 600, 900, 1, 10
        with self.assertRaises(UserError):
            self._import(wb, allow_legacy_files=False)
        estimate = self._import(wb, allow_legacy_files=True)
        self.assertEqual(len(estimate.line_ids), 1)
        self.assertTrue(any('non da modello SBU' in m.body for m in estimate.message_ids))
