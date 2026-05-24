# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SbuBulkEstimateSalLineWizard(models.TransientModel):
    _name = 'sbu.bulk.estimate.sal.line.wizard'
    _description = 'Bulk update contractual SAL lines on estimate'
    _inherit = ['sbu.bulk.apply.mixin']

    line_ids = fields.Many2many(
        'sbu.estimate.sal.line',
        'sbu_bulk_estimate_sal_line_rel',
        'wizard_id',
        'line_id',
        string='Lines',
    )
    estimate_id = fields.Many2one('sbu.estimate', string='Estimate')

    apply_retention_percent = fields.Boolean(string='Apply retention %')
    retention_percent = fields.Float(string='Retention %', digits=(16, 2))

    apply_sal_status = fields.Boolean(string='Apply SAL status')
    sal_status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('prepared', 'Prepared'),
            ('planning', 'Planned (SAL % only)'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('invoiced', 'Invoiced'),
            ('paid', 'Paid'),
        ],
        string='SAL status',
    )

    def _bulk_line_model(self):
        return 'sbu.estimate.sal.line'

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
            self.apply_retention_percent,
            self.apply_sal_status,
        ])
        lines = self._resolve_target_lines()
        vals = {}
        if self.apply_retention_percent:
            vals['retention_percent'] = self.retention_percent
        if self.apply_sal_status:
            vals['sal_status'] = self.sal_status
        lines.write(vals)
        return self._bulk_notification(len(lines))
