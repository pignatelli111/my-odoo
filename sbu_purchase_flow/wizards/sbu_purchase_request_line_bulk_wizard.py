# -*- coding: utf-8 -*-
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
        string='Lines to update',
        help='Filled from list selection (use filters, then select all matching).',
    )
    line_count = fields.Integer(compute='_compute_line_count')

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
        string='Priority',
        default='0',
    )

    apply_need_by_header = fields.Boolean(
        string='Apply need-by on request header',
        help='Updates the RDA/ACP header «Need by» date (all lines document).',
    )
    need_by_date = fields.Date(string='Header need-by date')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for wiz in self:
            wiz.line_count = len(wiz.line_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        if active_model == 'sbu.purchase.request.line' and active_ids:
            res['line_ids'] = [(6, 0, active_ids)]
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
        return res

    def _target_lines(self):
        self.ensure_one()
        lines = self.line_ids
        if not lines and self.request_id:
            lines = self.request_id.line_ids
        if not lines:
            raise UserError(
                _('Select at least one line in the list (filter → tick rows or «Select all»), '
                  'then run «Apply to selected lines» again.'),
            )
        return lines

    def action_apply(self):
        self.ensure_one()
        lines = self._target_lines()
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

        return True
