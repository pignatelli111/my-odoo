# -*- coding: utf-8 -*-
import base64
import csv
import io
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.sbu_logikal.services.logikal_client import LogikalHttpError, fetch_positions_json

# Normalised keys → list of accepted header / JSON keys (lower case)
_FIELD_ALIASES = {
    'external_pos': ['position', 'pos', 'posizione', 'codice_pos', 'external_pos', 'code'],
    'profile_code': ['profile_code', 'profile', 'codice_profilo', 'article', 'artikel', 'sku'],
    'description': ['description', 'descr', 'name', 'omschrijving'],
    'qty': ['qty', 'quantity', 'aantal', 'qt'],
    'width_mm': ['width_mm', 'width', 'b', 'breedte_mm'],
    'height_mm': ['height_mm', 'height', 'h', 'hoogte_mm'],
}


def _normalise_row(raw: dict) -> dict:
    """Map assorted keys to our canonical names."""
    lower = {str(k).strip().lower(): v for k, v in raw.items() if k is not None}
    out = {}
    for canonical, aliases in _FIELD_ALIASES.items():
        val = None
        for a in aliases:
            if a in lower and lower[a] not in (None, ''):
                val = lower[a]
                break
        out[canonical] = val
    return out


def _coerce_float(val, default=0.0):
    if val is None or val == '':
        return default
    try:
        return float(str(val).replace(',', '.'))
    except (TypeError, ValueError):
        return default


class SbuLogikalImportBatch(models.Model):
    _name = 'sbu.logikal.import.batch'
    _description = 'Logikal / ReynaPro import batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, default='New')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        index=True,
        tracking=True,
    )
    source = fields.Selection(
        [
            ('file', 'File (CSV / JSON)'),
            ('api', 'API bridge'),
        ],
        string='Source',
        default='file',
        required=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('parsed', 'Parsed'),
            ('applied', 'Applied'),
            ('error', 'Error'),
        ],
        string='State',
        default='draft',
        tracking=True,
    )

    export_file = fields.Binary(
        string='Export file',
        help='CSV or JSON from Logikal / ReynaPro (comma, semicolon, or tab-separated CSV).',
    )
    export_filename = fields.Char(string='Export filename')
    remote_project_ref = fields.Char(
        string='External project ref',
        tracking=True,
        help='Project code or id passed to the API bridge (query parameter «project»).',
    )

    apply_mode = fields.Selection(
        [
            ('estimate_bom', 'SBU estimate BOM (preventivo line)'),
            ('mrp_bom', 'MRP BOM (finished product)'),
        ],
        string='Apply to',
        default='estimate_bom',
        required=True,
    )
    target_estimate_line_id = fields.Many2one(
        'sbu.estimate.line',
        string='Target estimate line',
        domain=lambda self: (
            [('estimate_id.project_id', '=', self.project_id.id)]
            if self.project_id
            else [('id', '=', False)]
        ),
        help='BOM lines are created under this preventivo row.',
    )
    mrp_finished_product_id = fields.Many2one(
        'product.product',
        string='Finished product (MRP)',
        domain="[('type', '=', 'product')]",
        help='Manufactured article whose BOM will receive imported components.',
    )

    line_ids = fields.One2many(
        'sbu.logikal.import.line',
        'batch_id',
        string='Import lines',
    )
    line_count = fields.Integer(compute='_compute_line_stats', string='Line count')
    unmapped_count = fields.Integer(compute='_compute_line_stats', string='Unmapped lines')

    last_message = fields.Text(string='Last run log', readonly=True)

    @api.depends('line_ids', 'line_ids.map_state')
    def _compute_line_stats(self):
        for batch in self:
            batch.line_count = len(batch.line_ids)
            batch.unmapped_count = len(batch.line_ids.filtered(lambda l: l.map_state == 'unmapped'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.logikal.import') or 'IMP'
        return super().create(vals_list)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.project_id.sbu_estimate_id:
            est = self.project_id.sbu_estimate_id
            lines = est.line_ids
            self.target_estimate_line_id = lines[0] if len(lines) == 1 else False

    def action_reset_lines(self):
        for batch in self:
            if batch.state == 'applied':
                raise UserError(_('Applied batches cannot be reset. Create a new import instead.'))
            batch.line_ids.unlink()
            batch.write({'state': 'draft', 'last_message': False})
        return True

    def _parse_rows(self, rows: list) -> list:
        """rows: list of dicts (already JSON objects or CSV rows)."""
        parsed = []
        seq = 0
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            norm = _normalise_row(raw)
            seq += 10
            parsed.append({
                'sequence': seq,
                'external_pos': norm.get('external_pos') and str(norm['external_pos']).strip() or False,
                'profile_code': norm.get('profile_code') and str(norm['profile_code']).strip() or False,
                'description': norm.get('description') and str(norm['description']).strip() or False,
                'qty': _coerce_float(norm.get('qty'), 1.0) or 1.0,
                'width_mm': _coerce_float(norm.get('width_mm'), 0.0),
                'height_mm': _coerce_float(norm.get('height_mm'), 0.0),
                'raw_payload': json.dumps(raw, ensure_ascii=False),
            })
        return parsed

    def action_parse_file(self):
        for batch in self:
            if batch.source != 'file':
                raise UserError(_('Switch source to «File» to parse an attachment.'))
            if not batch.export_file:
                raise UserError(_('Upload an export file first.'))
            data = base64.b64decode(batch.export_file)
            if not data:
                raise UserError(_('The file is empty.'))
            name = (batch.export_filename or 'export.csv').lower()
            rows = []
            if name.endswith('.json'):
                payload = json.loads(data.decode('utf-8-sig'))
                if isinstance(payload, dict):
                    for key in ('data', 'positions', 'items', 'rows'):
                        inner = payload.get(key)
                        if isinstance(inner, list):
                            payload = inner
                            break
                if not isinstance(payload, list):
                    raise UserError(_('JSON file must contain an array or an object with a list field.'))
                rows = [r for r in payload if isinstance(r, dict)]
            else:
                text = data.decode('utf-8-sig', errors='replace')
                sample = text[:2048]
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=';,\t')
                except csv.Error:
                    dialect = csv.excel
                reader = csv.DictReader(io.StringIO(text), dialect=dialect)
                rows = list(reader)

            batch.action_reset_lines()
            vals_lines = batch._parse_rows(rows)
            if not vals_lines:
                raise UserError(_('No rows could be parsed from the file.'))
            batch.env['sbu.logikal.import.line'].create([
                dict(line, batch_id=batch.id) for line in vals_lines
            ])
            batch.write({'state': 'parsed', 'last_message': _('Parsed %s lines from file.') % len(vals_lines)})
        return True

    def action_fetch_api(self):
        ICP = self.env['ir.config_parameter'].sudo()
        base = ICP.get_param('sbu.logikal_base_url', '').strip()
        bearer = ICP.get_param('sbu.logikal_api_bearer', '').strip()
        path = ICP.get_param('sbu.logikal_api_path', '/positions').strip() or '/positions'
        for batch in self:
            if batch.source != 'api':
                raise UserError(_('Switch source to «API bridge» to fetch from the middleware.'))
            if not batch.remote_project_ref:
                raise UserError(_('Set «External project ref» for the API call.'))
            if not base:
                raise UserError(_('Configure «Logikal API base URL» in Settings → SBU first.'))
            try:
                payload = fetch_positions_json(base, bearer, batch.remote_project_ref.strip(), path=path)
            except LogikalHttpError as e:
                raise UserError(_('API error: %s') % e.args[0]) from e
            batch.action_reset_lines()
            vals_lines = batch._parse_rows(payload)
            if not vals_lines:
                raise UserError(_('API returned no usable rows.'))
            self.env['sbu.logikal.import.line'].create([
                dict(line, batch_id=batch.id) for line in vals_lines
            ])
            batch.write({'state': 'parsed', 'last_message': _('Fetched %s lines from API.') % len(vals_lines)})
        return True

    def action_match_products(self):
        Map = self.env['sbu.logikal.product.map']
        for batch in self:
            company = batch.company_id
            for line in batch.line_ids:
                code = (line.profile_code or '').strip()
                if not code:
                    line.write({'product_id': False, 'map_state': 'unmapped'})
                    continue
                pmap = Map.search([
                    ('company_id', '=', company.id),
                    ('active', '=', True),
                    ('profile_code', '=', code),
                ], limit=1)
                if pmap:
                    line.write({'product_id': pmap.product_id.id, 'map_state': 'mapped'})
                else:
                    line.write({'product_id': False, 'map_state': 'unmapped'})
            batch.last_message = _('Product matching done: %s mapped, %s unmapped.') % (
                len(batch.line_ids.filtered(lambda l: l.map_state == 'mapped')),
                len(batch.line_ids.filtered(lambda l: l.map_state == 'unmapped')),
            )
        return True

    def _ensure_apply_ready(self):
        self.ensure_one()
        if self.state != 'parsed':
            raise UserError(_('Parse or fetch lines first (state must be «Parsed»).'))
        if self.line_ids.filtered(lambda l: l.sbu_estimate_bom_line_id or l.mrp_bom_line_id):
            raise UserError(_('This batch was already applied. Use «Reset lines» to start over.'))
        bad = self.line_ids.filtered(lambda l: l.map_state != 'mapped' or not l.product_id)
        if bad:
            raise UserError(
                _('All lines must be mapped to a product before apply. Unmapped: %s.')
                % len(bad)
            )
        if self.apply_mode == 'estimate_bom':
            if not self.target_estimate_line_id:
                raise UserError(_('Choose a target estimate line.'))
            if self.target_estimate_line_id.estimate_id.project_id != self.project_id:
                raise UserError(_('Target estimate line must belong to this project\'s estimate.'))
        else:
            if not self.mrp_finished_product_id:
                raise UserError(_('Choose a finished product for MRP BOM apply.'))

    def _get_or_create_mrp_bom(self):
        self.ensure_one()
        product = self.mrp_finished_product_id
        company = self.company_id
        Bom = self.env['mrp.bom']
        bom = Bom.search([
            '|', ('company_id', '=', False), ('company_id', '=', company.id),
            ('product_id', '=', product.id),
            ('active', '=', True),
        ], limit=1)
        if not bom:
            bom = Bom.search([
                '|', ('company_id', '=', False), ('company_id', '=', company.id),
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ('product_id', '=', False),
                ('active', '=', True),
            ], limit=1)
        if bom:
            return bom
        return Bom.create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_id': product.id,
            'product_qty': 1.0,
            'type': 'normal',
            'company_id': company.id,
        })

    def action_apply(self):
        BomLine = self.env['sbu.estimate.bom.line']
        MrpLine = self.env['mrp.bom.line']
        for batch in self:
            batch._ensure_apply_ready()
            if batch.apply_mode == 'estimate_bom':
                target = batch.target_estimate_line_id
                seq_base = max(target.bom_line_ids.mapped('sequence') or [0])
                seq = seq_base
                for line in batch.line_ids.sorted(lambda l: (l.sequence, l.id)):
                    seq += 1
                    bl = BomLine.create({
                        'estimate_line_id': target.id,
                        'product_id': line.product_id.id,
                        'sequence': seq,
                        'calc_type': 'per_piece',
                        'dimension_source': 'manual',
                        'qty_formula_factor': line.qty or 1.0,
                        'uom_id': line.product_id.uom_id.id,
                        'unit_cost': 0.0,
                        'note': _('Logikal/ReynaPro %s') % (line.external_pos or line.profile_code or ''),
                    })
                    line.write({'sbu_estimate_bom_line_id': bl.id})
            else:
                bom = batch._get_or_create_mrp_bom()
                seq = max(bom.bom_line_ids.mapped('sequence') or [0])
                for line in batch.line_ids.sorted(lambda l: (l.sequence, l.id)):
                    seq += 1
                    ml = MrpLine.create({
                        'bom_id': bom.id,
                        'product_id': line.product_id.id,
                        'product_qty': line.qty or 1.0,
                        'product_uom_id': line.product_id.uom_id.id,
                        'sequence': seq,
                    })
                    line.write({'mrp_bom_line_id': ml.id})
            batch.write({'state': 'applied', 'last_message': _('Applied %s lines.') % len(batch.line_ids)})
        return True

    def action_open_estimate_line(self):
        self.ensure_one()
        if not self.target_estimate_line_id:
            raise UserError(_('No estimate line set.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.estimate.line',
            'res_id': self.target_estimate_line_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_mrp_bom(self):
        self.ensure_one()
        if not self.mrp_finished_product_id:
            raise UserError(_('No finished product set.'))
        bom = self._get_or_create_mrp_bom()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom',
            'res_id': bom.id,
            'view_mode': 'form',
            'target': 'current',
        }
