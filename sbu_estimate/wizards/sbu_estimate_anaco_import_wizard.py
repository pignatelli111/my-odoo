# -*- coding: utf-8 -*-
"""Import ANACO / Voci Contrattuali_SAL from ANACO_REV7-style .xlsx (openpyxl, data_only)."""
import base64
import io
import math
from odoo import fields, models, _
from odoo.exceptions import UserError

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

from ..models.sbu_cost_family import (
    infer_cost_family_from_pos,
    infer_cost_family_from_price_cost_vals,
)


# Column indices (1-based) validated against ANACO_REV7_111122.xlsx layout.
ANACO_ROW_PARAMS = 5  # sheet-level Sc multipliers K5:M5, cost % BM/BP, …
ANACO_ROW_FIRST_DATA_DEFAULT = 12

ANACO_COL_POS = 2  # B
ANACO_COL_DESC = 3  # C
ANACO_COL_B_MM = 4  # D
ANACO_COL_H_MM = 6  # F
ANACO_COL_QTY = 8  # H
ANACO_COL_SC_MULT = (11, 12, 13)  # K, L, M — row 5 multipliers, not row data discounts
ANACO_COL_PRICE = {
    'price_serramento_cad': 14,
    'price_oscuramento_cad': 28,
    'price_accessori_cad': 22,
    'price_kit_avvolgimento_cad': 32,
    'price_cassonetto_cad': 34,
    'price_automatismo_cad': 36,
    'price_zanzariera_cad': 38,
    'price_vetro_cad': 40,
    'price_pannello_cad': 42,
    'price_controtelaio_cad': 44,
    'price_trasformazione_cad': 46,
    'price_smontaggio_cad': 48,
    'price_nolo_cad': 52,
}
ANACO_COL_COST_COIB = 30
ANACO_COL_COST_POSA_LIN = 50
ANACO_COL_COST_NOLO = 52
ANACO_COL_COST_TRASPORTO = 57
ANACO_COL_COST_TECH_PM = 59
ANACO_COL_COST_CANTIERE = 61
ANACO_COL_COST_EXTRA = 63
ANACO_COL_COST_IND_PCT = 65  # BM
ANACO_COL_COST_MOL_PCT = 68  # BP
ANACO_COL_BS_UNIT = 71
ANACO_COL_NOTE = 74

SAL_ROW_FIRST_DATA_DEFAULT = 16
SAL_COL_ITEM = 2
SAL_COL_DESC = 3
SAL_COL_QTY = 4
SAL_COL_TOT_ML = 5
SAL_COL_MQ = 6
SAL_COL_TOT_MQ = 7
SAL_COL_UNIT_PRICE = 8
SAL_COL_FLOOR_BLOCKS = (
    (12, 15),  # PT: L–O
    (16, 19),
    (20, 23),
    (24, 27),
    (28, 31),
    (32, 35),
    (36, 39),
    (40, 43),
    (44, 47),
)
SAL_FLOOR_FIELDS = (
    'floor_pt', 'floor_p1', 'floor_p2', 'floor_p3', 'floor_p4',
    'floor_p5', 'floor_p6', 'floor_p7', 'floor_p8',
)
SAL_COL_SAL_START = 98  # SAL-1 … SAL-10


def _sheet_by_aliases(wb, aliases):
    lower = {n.lower(): n for n in wb.sheetnames}
    for a in aliases:
        if a.lower() in lower:
            return wb[lower[a.lower()]]
    return None


def _cell_num(sh, row, col):
    v = sh.cell(row, col).value
    if v is None or v == '':
        return None
    if isinstance(v, str):
        vs = v.replace(',', '.').strip()
        if not vs or vs == '-' or vs.upper().startswith('#'):
            return None
        v = vs
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def _norm_pct(val):
    """Excel may store 5 as 5% or 0.05 as 5%."""
    if val is None:
        return 0.0
    try:
        v = float(val)
    except (TypeError, ValueError):
        return 0.0
    if 0 < v <= 1.0:
        return v * 100.0
    return v


def _mult_to_discount_pct(mult):
    """K5/L5/M5 style multiplier 1 = 0% discount, 0.85 = 15%."""
    if mult is None:
        return 0.0
    try:
        m = float(mult)
    except (TypeError, ValueError):
        return 0.0
    if m >= 1.0 or m <= 0.0:
        return 0.0
    return max(0.0, min(100.0, (1.0 - m) * 100.0))


class SbuEstimateAnacoImportWizard(models.TransientModel):
    _name = 'sbu.estimate.anaco.import.wizard'
    _description = 'Import ANACO / SAL from Excel'

    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo',
        required=True,
        ondelete='cascade',
    )
    data_file = fields.Binary(string='File .xlsx', required=True)
    data_filename = fields.Char(string='Nome file')

    import_anaco = fields.Boolean(string='Importa righe ANACO', default=True)
    import_sal = fields.Boolean(string='Importa Voci Contrattuali SAL', default=True)
    replace_anaco_lines = fields.Boolean(
        string='Sostituisci righe preventivo esistenti',
        default=True,
        help='Se attivo, elimina le righe ANACO (sbu.estimate.line) prima dell\'import.',
    )
    replace_sal_lines = fields.Boolean(
        string='Sostituisci righe SAL esistenti',
        default=True,
    )
    anaco_first_row = fields.Integer(
        string='Prima riga dati ANACO (1-based)',
        default=ANACO_ROW_FIRST_DATA_DEFAULT,
        required=True,
    )
    sal_first_row = fields.Integer(
        string='Prima riga dati SAL (1-based)',
        default=SAL_ROW_FIRST_DATA_DEFAULT,
        required=True,
    )
    default_commission_pct = fields.Float(
        string='Comm. % default (righe ANACO)',
        default=0.0,
        digits=(16, 2),
        help='La colonna «Comm.» in testata ANACO non è mappata per-riga in REV7; '
             'impostare qui la commissione da applicare a tutte le righe importate, se serve.',
    )

    def action_import(self):
        if not openpyxl:
            raise UserError(_('Installare la libreria Python openpyxl sul server Odoo.'))
        self.ensure_one()
        if not self.import_anaco and not self.import_sal:
            raise UserError(_('Selezionare almeno un tipo di import (ANACO e/o SAL).'))
        if not self.data_file:
            raise UserError(_('Selezionare un file .xlsx.'))

        raw = base64.b64decode(self.data_file)
        try:
            wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=False)
        except Exception as err:  # pylint: disable=broad-except
            raise UserError(_('Impossibile leggere il file Excel: %s') % (err,)) from err

        anaco_sh = _sheet_by_aliases(wb, ('ANACO',))
        sal_sh = _sheet_by_aliases(wb, ('Voci Contrattuali_SAL',))

        n_anaco = 0
        n_sal = 0
        estimate = self.estimate_id

        if self.import_anaco:
            if not anaco_sh:
                raise UserError(_('Foglio «ANACO» non trovato nel file.'))
            sc1 = _mult_to_discount_pct(_cell_num(anaco_sh, ANACO_ROW_PARAMS, ANACO_COL_SC_MULT[0]))
            sc2 = _mult_to_discount_pct(_cell_num(anaco_sh, ANACO_ROW_PARAMS, ANACO_COL_SC_MULT[1]))
            sc3 = _mult_to_discount_pct(_cell_num(anaco_sh, ANACO_ROW_PARAMS, ANACO_COL_SC_MULT[2]))
            ind_pct = _norm_pct(_cell_num(anaco_sh, ANACO_ROW_PARAMS, ANACO_COL_COST_IND_PCT))
            mol_pct = _norm_pct(_cell_num(anaco_sh, ANACO_ROW_PARAMS, ANACO_COL_COST_MOL_PCT))

            if self.replace_anaco_lines:
                estimate.line_ids.unlink()

            seq = 10
            empty_run = 0
            max_row = anaco_sh.max_row or self.anaco_first_row
            for r in range(self.anaco_first_row, max_row + 1):
                pos = (anaco_sh.cell(r, ANACO_COL_POS).value or '')
                if isinstance(pos, (int, float)):
                    pos = str(pos)
                pos = str(pos).strip()
                desc_cell = anaco_sh.cell(r, ANACO_COL_DESC).value
                desc = str(desc_cell).strip() if desc_cell is not None else ''
                if not pos and not desc:
                    empty_run += 1
                    if empty_run >= 5:
                        break
                    continue
                empty_run = 0
                if not desc:
                    desc = pos or _('Riga importata')

                b_mm = _cell_num(anaco_sh, r, ANACO_COL_B_MM) or 0.0
                h_mm = _cell_num(anaco_sh, r, ANACO_COL_H_MM) or 0.0
                if b_mm and h_mm:
                    calc_uom = 'mq'
                else:
                    calc_uom = 'nr'

                line_vals = {
                    'estimate_id': estimate.id,
                    'sequence': seq,
                    'pos': pos or False,
                    'item_code': pos or False,
                    'description': desc,
                    'calc_uom_type': calc_uom,
                    'qty': _cell_num(anaco_sh, r, ANACO_COL_QTY) or 1.0,
                    'width_mm': b_mm,
                    'height_mm': h_mm,
                    'discount_sc1': sc1,
                    'discount_sc2': sc2,
                    'discount_sc3': sc3,
                    'commission_pct': self.default_commission_pct or 0.0,
                    'cost_industrial_pct': ind_pct,
                    'cost_mol_pct': mol_pct,
                }
                note_parts = []
                for fname, col in ANACO_COL_PRICE.items():
                    v = _cell_num(anaco_sh, r, col)
                    if v is not None:
                        line_vals[fname] = v
                for fname, col in (
                    ('cost_coibentazione_cad', ANACO_COL_COST_COIB),
                    ('cost_posa_lamiera_lin_cad', ANACO_COL_COST_POSA_LIN),
                    ('cost_nolo_cad', ANACO_COL_COST_NOLO),
                    ('cost_trasporto_cad', ANACO_COL_COST_TRASPORTO),
                    ('cost_tech_pm_cad', ANACO_COL_COST_TECH_PM),
                    ('cost_cantiere_cad', ANACO_COL_COST_CANTIERE),
                    ('cost_extra_cad', ANACO_COL_COST_EXTRA),
                ):
                    v = _cell_num(anaco_sh, r, col)
                    if v is not None:
                        line_vals[fname] = v

                bs = _cell_num(anaco_sh, r, ANACO_COL_BS_UNIT)
                if bs is not None:
                    line_vals['price_anaco_bs_cad'] = bs

                ntxt = anaco_sh.cell(r, ANACO_COL_NOTE).value
                if ntxt:
                    note_parts.append(str(ntxt).strip())
                if note_parts:
                    line_vals['note'] = '\n'.join(note_parts)

                cost_family = infer_cost_family_from_pos(pos) or infer_cost_family_from_price_cost_vals(line_vals)
                if cost_family:
                    line_vals['cost_family'] = cost_family

                self.env['sbu.estimate.line'].create(line_vals)
                n_anaco += 1
                seq += 10

        if self.import_sal:
            if not sal_sh:
                raise UserError(_('Foglio «Voci Contrattuali_SAL» non trovato nel file.'))
            if self.replace_sal_lines:
                estimate.sal_line_ids.unlink()

            seq = 10
            empty_run = 0
            max_row = sal_sh.max_row or self.sal_first_row
            for r in range(self.sal_first_row, max_row + 1):
                item = sal_sh.cell(r, SAL_COL_ITEM).value
                item = str(item).strip() if item is not None else ''
                desc_cell = sal_sh.cell(r, SAL_COL_DESC).value
                desc = str(desc_cell).strip() if desc_cell is not None else ''
                if not item and not desc:
                    empty_run += 1
                    if empty_run >= 5:
                        break
                    continue
                empty_run = 0
                if not desc:
                    desc = item or _('Voce SAL importata')

                qty = _cell_num(sal_sh, r, SAL_COL_QTY)
                unit = _cell_num(sal_sh, r, SAL_COL_UNIT_PRICE)
                tot_ml = _cell_num(sal_sh, r, SAL_COL_TOT_ML) or 0.0
                mq = _cell_num(sal_sh, r, SAL_COL_MQ) or 0.0
                tot_mq = _cell_num(sal_sh, r, SAL_COL_TOT_MQ) or 0.0

                if tot_ml and tot_ml > 0 and not (mq or tot_mq):
                    uom = 'ml'
                elif mq or tot_mq:
                    uom = 'mq'
                else:
                    uom = 'nr'

                sal_vals = {
                    'estimate_id': estimate.id,
                    'sequence': seq,
                    'item_ref': item or False,
                    'description': desc,
                    'uom_type': uom,
                    'qty_contract': qty or 0.0,
                    'unit_price': unit or 0.0,
                    'retention_percent': self.env['sbu.estimate.sal.line']._sbu_default_retention_percent(),
                }
                for (c0, c1), fname in zip(SAL_COL_FLOOR_BLOCKS, SAL_FLOOR_FIELDS):
                    block_sum = 0.0
                    for c in range(c0, c1 + 1):
                        v = _cell_num(sal_sh, r, c)
                        if v is not None:
                            block_sum += v
                    if block_sum:
                        sal_vals[fname] = block_sum

                for i in range(10):
                    v = _cell_num(sal_sh, r, SAL_COL_SAL_START + i)
                    if v is not None:
                        sal_vals[f'sal_{i + 1}_pct'] = _norm_pct(v)

                self.env['sbu.estimate.sal.line'].create(sal_vals)
                n_sal += 1
                seq += 10

        wb.close()

        body = _(
            'Import Excel completato: %(anaco)d righe ANACO, %(sal)d righe SAL.'
        ) % {'anaco': n_anaco, 'sal': n_sal}
        estimate.message_post(body=body)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.estimate',
            'res_id': estimate.id,
            'view_mode': 'form',
            'target': 'current',
        }
