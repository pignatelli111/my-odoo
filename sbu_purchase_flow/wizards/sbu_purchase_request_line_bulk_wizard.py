# -*- coding: utf-8 -*-
import ast

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SbuPurchaseRequestLineBulkWizard(models.TransientModel):
    _name = 'sbu.purchase.request.line.bulk.wizard'
    _description = 'Bulk update purchase request lines (filtered selection)'

    request_id = fields.Many2one(
        'sbu.purchase.request',
        string='Purchase request',
        help='Optional: limit to lines of this RDA/ACO/ACP document.',
    )
    line_ids = fields.Many2many(
        'sbu.purchase.request.line',
        'sbu_pr_line_bulk_wiz_rel',
        'wizard_id',
        'line_id',
        string='Lines to update',
        help='Filled when scope is «Selected lines only».',
    )
    apply_scope = fields.Selection(
        [
            ('selection', 'Selected lines only'),
            ('filtered', 'All lines matching list filters'),
        ],
        string='Apply to',
        required=True,
        default='selection',
        help='Use «All lines matching list filters» after setting filters in the list '
             '(no need to tick every row — same idea as Purchase area bulk edit).',
    )
    target_count = fields.Integer(
        string='Lines affected',
        compute='_compute_target_count',
    )

    apply_date_required = fields.Boolean(string='Apply delivery date')
    date_required = fields.Date(string='Delivery date')

    apply_destination = fields.Boolean(string='Apply destination')
    destination = fields.Char(string='Destination')

    apply_procurement_mode = fields.Boolean(string='Apply procurement mode')
    procurement_mode = fields.Selection(
        [('purchase', 'Acquisto'), ('warehouse', 'Magazzino')],
        string='Procurement',
    )

    apply_line_priority = fields.Boolean(string='Apply line priority')
    line_priority = fields.Selection(
        [
            ('0', 'Normal'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Critical'),
        ],
        string='Priorità riga',
        default='0',
    )

    apply_need_by_header = fields.Boolean(
        string='Apply need-by on request header',
        help='Updates the RDA/ACP header «Need by» date (all lines document).',
    )
    need_by_date = fields.Date(string='Header need-by date')

    @api.depends('apply_scope', 'line_ids', 'request_id')
    def _compute_target_count(self):
        for wiz in self:
            try:
                wiz.target_count = len(wiz._resolve_target_lines(raise_if_empty=False))
            except Exception:
                wiz.target_count = 0

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        active_domain = self.env.context.get('active_domain')

        if active_model == 'sbu.purchase.request.line' and active_ids:
            res['line_ids'] = [(6, 0, active_ids)]
            if active_domain and len(active_ids) > 20:
                res['apply_scope'] = 'filtered'
        elif active_model == 'sbu.purchase.request' and active_ids:
            req = self.env['sbu.purchase.request'].browse(active_ids[:1])
            res['request_id'] = req.id
            res['line_ids'] = [(6, 0, req.line_ids.ids)]
        elif self.env.context.get('default_request_id'):
            req = self.env['sbu.purchase.request'].browse(
                self.env.context['default_request_id'],
            )
            res['request_id'] = req.id
            res['line_ids'] = [(6, 0, req.line_ids.ids)]

        if active_domain and res.get('apply_scope') != 'selection':
            res.setdefault('apply_scope', 'filtered')
        return res

    def _domain_from_context(self):
        """Domain of the list view when the wizard was opened (filtered rows)."""
        raw = self.env.context.get('active_domain')
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return list(raw)
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                return []
            return list(parsed) if isinstance(parsed, (list, tuple)) else []
        return []

    def _resolve_target_lines(self, raise_if_empty=True):
        self.ensure_one()
        Line = self.env['sbu.purchase.request.line']
        if self.apply_scope == 'filtered':
            domain = self._domain_from_context()
            if not domain and self.request_id:
                domain = [('request_id', '=', self.request_id.id)]
            if not domain:
                if raise_if_empty:
                    raise UserError(
                        _('Open this wizard from the request lines list with at least one '
                          'filter active, or choose «Selected lines only» and tick rows.'),
                    )
                return Line.browse()
            return Line.search(domain)

        lines = self.line_ids
        if not lines and self.request_id:
            lines = self.request_id.line_ids
        if not lines and raise_if_empty:
            raise UserError(
                _('Select at least one line in the list (or use filters + '
                  '«All lines matching list filters»).'),
            )
        return lines

    def action_apply(self):
        self.ensure_one()
        lines = self._resolve_target_lines()
        if not any([
            self.apply_date_required,
            self.apply_destination,
            self.apply_procurement_mode,
            self.apply_line_priority,
            self.apply_need_by_header,
        ]):
            raise UserError(_('Enable at least one field to apply (checkbox on the left).'))

        line_vals = {}
        if self.apply_date_required:
            line_vals['date_required'] = self.date_required
        if self.apply_destination:
            line_vals['destination'] = self.destination
        if self.apply_procurement_mode:
            line_vals['procurement_mode'] = self.procurement_mode
        if self.apply_line_priority:
            line_vals['line_priority'] = self.line_priority

        updated = 0
        if line_vals:
            lines.write(line_vals)
            updated = len(lines)

        if self.apply_need_by_header:
            lines.mapped('request_id').write({'need_by_date': self.need_by_date})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk update'),
                'message': _('Updated %(n)s line(s).', n=updated),
                'type': 'success',
                'sticky': False,
            },
        }
