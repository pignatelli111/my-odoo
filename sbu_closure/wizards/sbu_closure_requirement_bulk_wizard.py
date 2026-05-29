# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SbuClosureRequirementBulkWizard(models.TransientModel):
    _name = 'sbu.closure.requirement.bulk.wizard'
    _description = 'Bulk update project closure checklist lines'
    _inherit = ['sbu.bulk.apply.mixin']

    project_id = fields.Many2one('project.project', string='Project / Job')
    line_ids = fields.Many2many(
        'sbu.closure.requirement',
        'sbu_closure_req_bulk_rel',
        'wizard_id',
        'line_id',
        string='Lines',
    )

    apply_state = fields.Boolean(string='Apply status')
    state = fields.Selection(
        [
            ('pending', 'To do'),
            ('done', 'Done'),
            ('waived', 'Waived'),
            ('na', 'N/A'),
        ],
        string='Status',
    )

    apply_required = fields.Boolean(string='Apply required flag')
    required = fields.Boolean(string='Required')

    apply_due_date = fields.Boolean(string='Apply due date')
    due_date = fields.Date(string='Due date')

    apply_user_id = fields.Boolean(string='Apply responsible')
    user_id = fields.Many2one('res.users', string='Responsible')

    def _bulk_line_model(self):
        return 'sbu.closure.requirement'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'project.project' and self.env.context.get('active_ids'):
            res['project_id'] = self.env.context['active_ids'][0]
        return self._sbu_bulk_default_get(res, fields_list)

    def _bulk_fallback_domain(self):
        if self.project_id:
            return [('project_id', '=', self.project_id.id)]
        return []

    def _bulk_domain_safety_terms(self):
        return ('id', 'project_id', 'document_type_id')

    def action_apply(self):
        self.ensure_one()
        self._bulk_require_any_apply([
            self.apply_state,
            self.apply_required,
            self.apply_due_date,
            self.apply_user_id,
        ])
        lines = self._resolve_target_lines()
        vals = {}
        if self.apply_state:
            vals['state'] = self.state
        if self.apply_required:
            vals['required'] = self.required
        if self.apply_due_date:
            vals['due_date'] = self.due_date
        if self.apply_user_id:
            vals['user_id'] = self.user_id.id
        lines.write(vals)
        return self._bulk_notification(len(lines))
