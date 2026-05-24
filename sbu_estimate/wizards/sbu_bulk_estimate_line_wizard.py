# -*- coding: utf-8 -*-
from odoo import api, fields, models

from odoo.addons.sbu_estimate.models.sbu_cost_family import SBU_COST_FAMILY_SELECTION


class SbuBulkEstimateLineWizard(models.TransientModel):
    _name = 'sbu.bulk.estimate.line.wizard'
    _description = 'Bulk update ANACO estimate lines'
    _inherit = ['sbu.bulk.apply.mixin']

    line_ids = fields.Many2many(
        'sbu.estimate.line',
        'sbu_bulk_estimate_line_rel',
        'wizard_id',
        'line_id',
        string='Lines',
    )
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Estimate',
        help='Optional limit when opened from an estimate form.',
    )

    apply_cost_family = fields.Boolean(string='Apply cost family')
    cost_family = fields.Selection(
        selection=SBU_COST_FAMILY_SELECTION,
        string='Cost family',
    )

    apply_calc_uom = fields.Boolean(string='Apply calc. UoM')
    calc_uom_type = fields.Selection(
        selection=[
            ('mq', 'MQ (square metres)'),
            ('ml', 'ML (linear metres)'),
            ('nr', 'Nr/Pz (pieces)'),
            ('corpo', 'Lump sum / A corpo'),
        ],
        string='Calc. UoM',
    )

    def _bulk_line_model(self):
        return 'sbu.estimate.line'

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
        return ('id', 'estimate_id')

    def action_apply(self):
        self.ensure_one()
        self._bulk_require_any_apply([
            self.apply_cost_family,
            self.apply_calc_uom,
        ])
        lines = self._resolve_target_lines()
        vals = {}
        if self.apply_cost_family:
            vals['cost_family'] = self.cost_family
        if self.apply_calc_uom:
            vals['calc_uom_type'] = self.calc_uom_type
        lines.write(vals)
        return self._bulk_notification(len(lines))
