# -*- coding: utf-8 -*-
"""Import / update RDA lines from Excel template (Cosimo punto 1 — dati tecnici)."""
import base64
import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import openpyxl
except ImportError:
    openpyxl = None

_HEADER_ALIASES = {
    'pos': ('pos', 'pos.', 'posizione', 'position'),
    'article_code': (
        'cod. articolo', 'cod articolo', 'codice articolo', 'article', 'cod.articolo',
        'cod articolo', 'sku',
    ),
    'name': ('descrizione', 'description', 'desc', 'nome'),
    'width_mm': ('l (mm)', 'l', 'larghezza', 'width', 'width mm', 'l mm'),
    'height_mm': ('h (mm)', 'h', 'altezza', 'height', 'height mm', 'h mm'),
    'depth_mm': ('p (mm)', 'p', 'profondità', 'profondita', 'depth', 'depth mm', 'p mm'),
    'sqm_per_piece': ('mq/cad', 'mq cad', 'mq per pezzo', 'sqm/cad'),
    'sqm_total': ('mq tot', 'mq tot.', 'mq totali', 'mq totale', 'sqm total'),
    'product_qty': ('qty', 'quantità', 'quantita', 'q.tà', 'qta', 'quantity'),
    'utilization': ('utilizzo', 'utilization', 'uso'),
}


def _norm_header(cell):
    if cell is None:
        return ''
    return re.sub(r'\s+', ' ', str(cell).strip().lower())


def _map_headers(row_cells):
    """Return {field_name: column_index} from first row."""
    mapping = {}
    for idx, cell in enumerate(row_cells):
        h = _norm_header(cell)
        if not h:
            continue
        for field_name, aliases in _HEADER_ALIASES.items():
            if h in aliases or h.replace('.', '') in aliases:
                mapping.setdefault(field_name, idx)
                break
    return mapping


def _cell_float(row, idx):
    if idx is None or idx >= len(row):
        return 0.0
    val = row[idx]
    if val is None or val == '':
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _cell_str(row, idx):
    if idx is None or idx >= len(row):
        return ''
    val = row[idx]
    if val is None:
        return ''
    return str(val).strip()


class SbuPurchaseRequestExcelImportWizard(models.TransientModel):
    _name = 'sbu.purchase.request.excel.import.wizard'
    _description = 'Import RDA lines from Excel'

    request_id = fields.Many2one(
        'sbu.purchase.request',
        string='Purchase request',
        required=True,
        ondelete='cascade',
    )
    data_file = fields.Binary(string='Excel file', required=True)
    filename = fields.Char(string='Filename')
    sheet_name = fields.Char(
        string='Sheet name',
        help='Leave empty to use the first worksheet.',
    )
    update_mode = fields.Selection(
        [
            ('merge', 'Update matching lines / add new'),
            ('replace', 'Replace all lines from file'),
        ],
        string='Mode',
        default='merge',
        required=True,
    )
    line_count = fields.Integer(string='Lines processed', readonly=True)

    def _parse_workbook_rows(self):
        self.ensure_one()
        if not openpyxl:
            raise UserError(_('Install the openpyxl Python library on the Odoo server.'))
        raw = base64.b64decode(self.data_file)
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        if self.sheet_name:
            if self.sheet_name not in wb.sheetnames:
                raise UserError(_('Sheet «%s» not found in workbook.') % self.sheet_name)
            ws = wb[self.sheet_name]
        else:
            ws = wb[wb.sheetnames[0]]
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if not rows:
            raise UserError(_('The worksheet is empty.'))
        header_row = None
        header_idx = 0
        for i, row in enumerate(rows[:30]):
            mapping = _map_headers(row)
            if 'name' in mapping or ('pos' in mapping and 'article_code' in mapping):
                header_row = mapping
                header_idx = i
                break
        if not header_row:
            raise UserError(
                _('Could not find a header row. Expected columns such as POS, Descrizione, L, H, Qty.')
            )
        data_rows = []
        for row in rows[header_idx + 1:]:
            if not any(c is not None and str(c).strip() for c in row):
                continue
            name = _cell_str(row, header_row.get('name'))
            pos = _cell_str(row, header_row.get('pos'))
            article = _cell_str(row, header_row.get('article_code'))
            if not name and not article and not pos:
                continue
            data_rows.append({
                'pos': pos,
                'article_code': article,
                'name': name or article or _('Imported line'),
                'width_mm': _cell_float(row, header_row.get('width_mm')),
                'height_mm': _cell_float(row, header_row.get('height_mm')),
                'depth_mm': _cell_float(row, header_row.get('depth_mm')),
                'sqm_per_piece': _cell_float(row, header_row.get('sqm_per_piece')),
                'sqm_total': _cell_float(row, header_row.get('sqm_total')),
                'product_qty': _cell_float(row, header_row.get('product_qty')) or 1.0,
                'utilization': _cell_str(row, header_row.get('utilization')),
            })
        return data_rows

    def _match_line(self, Line, row):
        domain = [('request_id', '=', self.request_id.id)]
        if row.get('pos'):
            domain.append(('pos', '=', row['pos']))
        if row.get('article_code'):
            domain.append(('article_code', '=', row['article_code']))
        return Line.search(domain, limit=1)

    def action_import(self):
        self.ensure_one()
        if self.request_id.state == 'cancelled':
            raise UserError(_('Cannot import lines on a cancelled request.'))
        rows = self._parse_workbook_rows()
        if not rows:
            raise UserError(_('No data rows found below the header.'))
        Line = self.env['sbu.purchase.request.line']
        Product = self.env['product.product']
        if self.update_mode == 'replace':
            self.request_id.line_ids.unlink()
        created = updated = 0
        for row in rows:
            product = False
            if row.get('article_code'):
                product = Product.search(
                    [('default_code', '=', row['article_code'])],
                    limit=1,
                )
            vals = {
                'pos': row.get('pos') or False,
                'article_code': row.get('article_code') or False,
                'name': row['name'],
                'width_mm': row['width_mm'],
                'height_mm': row['height_mm'],
                'depth_mm': row['depth_mm'],
                'sqm_per_piece': row['sqm_per_piece'],
                'sqm_total': row['sqm_total'],
                'product_qty': row['product_qty'],
                'utilization': row.get('utilization') or False,
                'procurement_mode': 'purchase',
                'line_priority': self.request_id.priority,
            }
            if product:
                vals['product_id'] = product.id
                vals['product_uom'] = product.uom_id.id
            existing = self._match_line(Line, row) if self.update_mode == 'merge' else Line
            if existing:
                existing.write(vals)
                updated += 1
            else:
                vals['request_id'] = self.request_id.id
                Line.create(vals)
                created += 1
        self.request_id.write({'technical_data_state': 'excel_imported'})
        self.request_id.message_post(
            body=_(
                'Excel import: %(c)s created, %(u)s updated (%(n)s rows).',
                c=created,
                u=updated,
                n=len(rows),
            ),
        )
        self.line_count = created + updated
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.purchase.request',
            'res_id': self.request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
