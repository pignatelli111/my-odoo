# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SbuSalSheetLineBulkWizard(models.TransientModel):
    _name = 'sbu.sal.sheet.line.bulk.wizard'
    _description = 'Bulk update customer SAL sheet lines'
    _inherit = ['sbu.bulk.apply.mixin']

    sheet_id = fields.Many2one('sbu.sal.sheet', string='SAL sheet')
    line_ids = fields.Many2many(
        'sbu.sal.sheet.line',
        'sbu_sal_sheet_line_bulk_rel',
        'wizard_id',
        'line_id',
        string='Lines',
    )

    apply_percent_this_sal = fields.Boolean(string='Apply this SAL %')
    percent_this_sal = fields.Float(string='This SAL %', digits=(16, 2))

    apply_retention_on_sheet = fields.Boolean(
        string='Apply retention % on sheet header',
        help='Updates retention on the SAL sheet (all lines on that sheet).',
    )
    retention_percent = fields.Float(string='Retention %', digits=(16, 2))

    def _bulk_line_model(self):
        return 'sbu.sal.sheet.line'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'sbu.sal.sheet' and self.env.context.get('active_ids'):
            sheet = self.env['sbu.sal.sheet'].browse(self.env.context['active_ids'][:1])
            res['sheet_id'] = sheet.id
            res['line_ids'] = [(6, 0, sheet.line_ids.ids)]
        return self._sbu_bulk_default_get(res, fields_list)

    def _bulk_fallback_domain(self):
        if self.sheet_id:
            return [('sheet_id', '=', self.sheet_id.id)]
        return []

    def _bulk_domain_safety_terms(self):
        return ('id', 'sheet_id', 'project_id', 'estimate_id')

    def action_apply(self):
        self.ensure_one()
        self._bulk_require_any_apply([
            self.apply_percent_this_sal,
            self.apply_retention_on_sheet,
        ])
        lines = self._resolve_target_lines()
        updated = 0
        if self.apply_percent_this_sal:
            lines.write({'percent_this_sal': self.percent_this_sal})
            updated = len(lines)
        if self.apply_retention_on_sheet:
            lines.mapped('sheet_id').write({'retention_percent': self.retention_percent})
        return self._bulk_notification(updated)
