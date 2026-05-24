# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SbuBulkEstimateBomLineWizard(models.TransientModel):
    _name = 'sbu.bulk.estimate.bom.line.wizard'
    _description = 'Bulk update estimate BOM (ITEM) lines'
    _inherit = ['sbu.bulk.apply.mixin']

    line_ids = fields.Many2many(
        'sbu.estimate.bom.line',
        'sbu_bulk_estimate_bom_line_rel',
        'wizard_id',
        'line_id',
        string='Lines',
    )
    estimate_id = fields.Many2one('sbu.estimate', string='Estimate')

    apply_technical_confirmed = fields.Boolean(string='Apply confirmed for PO')
    technical_confirmed = fields.Boolean(string='Confirmed for PO')

    apply_data_phase = fields.Boolean(string='Apply data phase')
    data_phase = fields.Selection(
        [
            ('estimate', 'Stima ANACO'),
            ('logikal', 'Bozza Logikal'),
            ('technical', 'Documento tecnico'),
        ],
        string='Data phase',
    )

    def _bulk_line_model(self):
        return 'sbu.estimate.bom.line'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'sbu.estimate' and self.env.context.get('active_ids'):
            res['estimate_id'] = self.env.context['active_ids'][0]
        return self._sbu_bulk_default_get(res, fields_list)

    def _bulk_fallback_domain(self):
        if self.estimate_id:
            return [('estimate_id', '=', self.estimate_id.id)]
        return []

    def _bulk_domain_safety_terms(self):
        return ('id', 'estimate_id', 'estimate_line_id')

    def action_apply(self):
        self.ensure_one()
        self._bulk_require_any_apply([
            self.apply_technical_confirmed,
            self.apply_data_phase,
        ])
        lines = self._resolve_target_lines()
        vals = {}
        if self.apply_technical_confirmed:
            vals['technical_confirmed'] = self.technical_confirmed
        if self.apply_data_phase:
            vals['data_phase'] = self.data_phase
        lines.write(vals)
        return self._bulk_notification(len(lines))
