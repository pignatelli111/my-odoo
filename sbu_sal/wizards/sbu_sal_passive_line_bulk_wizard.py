# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SbuSalPassiveLineBulkWizard(models.TransientModel):
    _name = 'sbu.sal.passive.line.bulk.wizard'
    _description = 'Bulk update passive SAL lines'
    _inherit = ['sbu.bulk.apply.mixin']

    sheet_id = fields.Many2one('sbu.sal.passive.sheet', string='Passive SAL sheet')
    line_ids = fields.Many2many(
        'sbu.sal.passive.line',
        'sbu_sal_passive_line_bulk_rel',
        'wizard_id',
        'line_id',
        string='Lines',
    )

    apply_percent_this_sal = fields.Boolean(string='Apply this SAL %')
    percent_this_sal = fields.Float(string='This SAL %', digits=(16, 2))

    apply_category = fields.Boolean(string='Apply cost type')
    category = fields.Selection(
        [
            ('posa_lin', 'Sheet metal / LIN installation'),
            ('posa_cantiere', 'Site installation'),
            ('subappalto', 'General subcontract'),
            ('servizi', 'Installation services'),
        ],
        string='Cost type',
    )

    def _bulk_line_model(self):
        return 'sbu.sal.passive.line'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'sbu.sal.passive.sheet' and self.env.context.get('active_ids'):
            sheet = self.env['sbu.sal.passive.sheet'].browse(self.env.context['active_ids'][:1])
            res['sheet_id'] = sheet.id
            res['line_ids'] = [(6, 0, sheet.line_ids.ids)]
        return self._sbu_bulk_default_get(res, fields_list)

    def _bulk_fallback_domain(self):
        if self.sheet_id:
            return [('sheet_id', '=', self.sheet_id.id)]
        return []

    def _bulk_domain_safety_terms(self):
        return ('id', 'sheet_id', 'estimate_id')

    def action_apply(self):
        self.ensure_one()
        self._bulk_require_any_apply([
            self.apply_percent_this_sal,
            self.apply_category,
        ])
        lines = self._resolve_target_lines()
        vals = {}
        if self.apply_percent_this_sal:
            vals['percent_this_sal'] = self.percent_this_sal
        if self.apply_category:
            vals['category'] = self.category
        lines.write(vals)
        return self._bulk_notification(len(lines))
