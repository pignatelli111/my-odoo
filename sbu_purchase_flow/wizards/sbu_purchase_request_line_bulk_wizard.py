# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SbuPurchaseRequestLineBulkWizard(models.TransientModel):
    _name = 'sbu.purchase.request.line.bulk.wizard'
    _description = 'Bulk update purchase request lines (filtered selection)'
    _inherit = ['sbu.bulk.apply.mixin']

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

    apply_date_required = fields.Boolean(string='Apply delivery date')
    date_required = fields.Date(string='Delivery date')

    apply_destination = fields.Boolean(string='Apply destination')
    destination = fields.Char(string='Destination')

    apply_procurement_mode = fields.Boolean(string='Apply procurement mode')
    procurement_mode = fields.Selection(
        [('purchase', 'Purchase'), ('warehouse', 'Warehouse')],
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
        string='Line priority',
        default='0',
    )

    apply_need_by_header = fields.Boolean(
        string='Apply need-by on request header',
        help='Updates the RDA/ACP header «Need by» date (all lines document).',
    )
    need_by_date = fields.Date(string='Header need-by date')

    def _bulk_line_model(self):
        return 'sbu.purchase.request.line'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        if active_model == 'sbu.purchase.request' and active_ids:
            req = self.env['sbu.purchase.request'].browse(active_ids[:1])
            res['request_id'] = req.id
            res['line_ids'] = [(6, 0, req.line_ids.ids)]
        elif self.env.context.get('default_request_id'):
            req = self.env['sbu.purchase.request'].browse(
                self.env.context['default_request_id'],
            )
            res['request_id'] = req.id
            res['line_ids'] = [(6, 0, req.line_ids.ids)]
        return self._sbu_bulk_default_get(res, fields_list)

    def _bulk_fallback_domain(self):
        if self.request_id:
            return [('request_id', '=', self.request_id.id)]
        return []

    def _bulk_domain_safety_terms(self):
        return ('id', 'request_id', 'request_id.project_id', 'project_id')

    def action_apply(self):
        self.ensure_one()
        self._bulk_require_any_apply([
            self.apply_date_required,
            self.apply_destination,
            self.apply_procurement_mode,
            self.apply_line_priority,
            self.apply_need_by_header,
        ])
        lines = self._resolve_target_lines()
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
        return self._bulk_notification(updated)
