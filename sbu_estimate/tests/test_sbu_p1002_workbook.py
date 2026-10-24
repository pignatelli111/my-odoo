# -*- coding: utf-8 -*-
"""Regression against client workbook ANACO_P1002_25_CON_REV03 (if present on disk)."""
import base64
import io
from pathlib import Path

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

P1002_CANDIDATES = (
    Path(__file__).resolve().parents[2] / 'ANACO_P1002_25_CON_REV03_EIALL+ALL_P1.xlsx',
    Path(__file__).resolve().parents[2].parent / 'ANACO_P1002_25_CON_REV03_EIALL+ALL_P1.xlsx',
    Path(__file__).resolve().parents[2] / 'docs' / 'samples' / 'client'
    / 'ANACO_P1002_25_CON_REV03_EIALL+ALL_P1.xlsx',
)


@tagged('post_install', '-at_install')
class TestSbuP1002Workbook(TransactionCase):
    def _p1002_path(self):
        for path in P1002_CANDIDATES:
            if path.is_file():
                return path
        return None

    def test_p1002_import_row_counts(self):
        if not openpyxl:
            self.skipTest('openpyxl not installed')
        path = self._p1002_path()
        if not path:
            self.skipTest('P1002 workbook not on disk')
        partner = self.env['res.partner'].create({'name': 'P1002 import partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        wizard = self.env['sbu.estimate.anaco.import.wizard'].create({
            'estimate_id': estimate.id,
            'data_file': base64.b64encode(path.read_bytes()),
            'data_filename': path.name,
            'import_anaco': True,
            'import_sal': True,
            'replace_anaco_lines': True,
            'replace_sal_lines': True,
            'auto_detect_first_row': True,
            'auto_detect_sal_first_row': True,
            'auto_detect_sal_columns': True,
        })
        wizard.action_import()
        self.assertGreaterEqual(len(estimate.line_ids), 30)
        self.assertLessEqual(len(estimate.line_ids), 40)
        self.assertGreaterEqual(len(estimate.sal_line_ids), 30)
        self.assertLessEqual(len(estimate.sal_line_ids), 40)
        self.assertFalse(
            estimate.line_ids.filtered(lambda l: 'ANALISI COSTO' in (l.description or '')),
        )
        self.assertFalse(
            estimate.sal_line_ids.filtered(
                lambda l: (l.description or '') == 'SERRAMENTI SERIE F' and not l.item_ref,
            ),
        )
        self.assertEqual(
            len(estimate.sal_line_ids.filtered(lambda l: (l.cumulative_pct or 0) > 0)),
            0,
        )

    def test_p1002_f1_excel_parity_bs_bb_bc(self):
        """Every ANACO row and the BC / BT / BR totals equal the Excel values (to the cent)."""
        if not openpyxl:
            self.skipTest('openpyxl not installed')
        path = self._p1002_path()
        if not path:
            self.skipTest('P1002 workbook not on disk')
        from odoo.addons.sbu_estimate.wizards.sbu_openpyxl_utils import load_openpyxl_workbook

        columns = {  # Excel column (1-based) -> Odoo line field
            54: 'cost_material_worked_cad', 55: 'cost_material_worked_tot', 57: 'cost_trasporto_cad',
            59: 'cost_tech_pm_cad', 61: 'cost_cantiere_cad', 63: 'cost_extra_cad', 66: 'cost_industrial_cad',
            69: 'cost_mol_amount_cad', 70: 'cost_mol_amount_tot', 71: 'price_total_cad', 72: 'price_total_tot',
        }
        wb = load_openpyxl_workbook(path, data_only=True, read_only=True)
        anaco = wb['ANACO']
        rows = {}
        for r in range(12, 157):
            pos = (anaco.cell(r, 2).value or '')
            bb = anaco.cell(r, 54).value
            if pos and isinstance(bb, (int, float)) and bb:
                rows[str(pos).split('\n')[0].strip()] = {c: float(anaco.cell(r, c).value or 0.0) for c in columns}
        totals = {c: float(anaco.cell(157, c).value or 0.0) for c in (55, 70, 72)}
        wb.close()

        partner = self.env['res.partner'].create({'name': 'P1002 F1 parity'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        wizard = self.env['sbu.estimate.anaco.import.wizard'].create({
            'estimate_id': estimate.id,
            'data_file': base64.b64encode(path.read_bytes()),
            'data_filename': path.name,
            'import_anaco': True,
            'import_sal': False,
            'replace_anaco_lines': True,
            'auto_detect_first_row': True,
        })
        wizard.action_import()
        self.assertEqual(estimate.anaco_layout, 'p1002')
        self.assertAlmostEqual(estimate.anaco_pct_mol, 32.0)
        self.assertAlmostEqual(estimate.anaco_posa_rate_sqm, 132.5, msg='AV = $AV$5 × G')
        by_pos = {(line.pos or '').split('\n')[0].strip(): line for line in estimate.line_ids}
        for pos, excel in rows.items():
            line = by_pos[pos]
            for col, fname in columns.items():
                self.assertAlmostEqual(line[fname], excel[col], places=2, msg=f'{pos} col {col} ({fname})')
            self.assertFalse(line.anaco_check_warning, pos)
            self.assertFalse(line.price_anaco_bs_cad, 'BS is a formula in Excel: price stays computed')
        self.assertAlmostEqual(estimate.anaco_material_worked_total, totals[55], places=2)
        self.assertAlmostEqual(estimate.anaco_mol_total, totals[70], places=2)
        self.assertAlmostEqual(estimate.total_price, totals[72], places=2)
        self.assertAlmostEqual(estimate.anaco_installation_total, 133583.01, places=2)
