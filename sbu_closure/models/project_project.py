# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sbu_closure_requirement_ids = fields.One2many(
        'sbu.closure.requirement',
        'project_id',
        string='Closure checklist',
    )
    sbu_closure_ready = fields.Boolean(
        string='Closure checklist OK',
        compute='_compute_sbu_closure_metrics',
        compute_sudo=True,
        help='True when every required line is Done, Waived, or N/A.',
    )
    sbu_closure_required_open = fields.Integer(
        string='Required items still open',
        compute='_compute_sbu_closure_metrics',
        compute_sudo=True,
    )

    @api.depends(
        'sbu_closure_requirement_ids.state',
        'sbu_closure_requirement_ids.required',
    )
    def _compute_sbu_closure_metrics(self):
        for project in self:
            reqs = project.sbu_closure_requirement_ids.filtered(lambda r: r.required)
            open_pending = reqs.filtered(lambda r: r.state == 'pending')
            project.sbu_closure_required_open = len(open_pending)
            project.sbu_closure_ready = not open_pending

    def _sbu_closure_init_missing_lines(self):
        """Create checklist lines from types marked «Add on init» (no UI notification)."""
        Type = self.env['sbu.closure.document.type'].sudo()
        Requirement = self.env['sbu.closure.requirement']
        created_total = 0
        for project in self:
            types = Type.search([('active', '=', True), ('init_on_project', '=', True)])
            existing_type_ids = set(project.sbu_closure_requirement_ids.mapped('document_type_id').ids)
            for doc_type in types:
                if doc_type.id in existing_type_ids:
                    continue
                Requirement.create(
                    {
                        'project_id': project.id,
                        'document_type_id': doc_type.id,
                        'name': doc_type.name,
                        'required': doc_type.default_required,
                        'sequence': doc_type.sequence,
                    }
                )
                created_total += 1
        return created_total

    def write(self, vals):
        if 'sbu_state' in vals:
            target = vals['sbu_state']
            if target == 'closing':
                pre = self.filtered(lambda p: p.sbu_estimate_id)
                if pre:
                    pre._sbu_closure_init_missing_lines()
            if target in ('closed', 'archived'):
                for project in self.filtered(lambda p: p.sbu_estimate_id):
                    if not project.sbu_closure_requirement_ids:
                        project._sbu_closure_init_missing_lines()
                    project.invalidate_recordset(['sbu_closure_ready', 'sbu_closure_required_open'])
                    if not project.sbu_closure_ready:
                        raise UserError(
                            _(
                                'Cannot set job «%(state)s» until the closure checklist is complete '
                                '(%(n)s required item(s) still pending). Open tab «Chiusura / DOP» on %(job)s.'
                            )
                            % {
                                'state': dict(project._fields['sbu_state'].selection).get(target, target),
                                'n': project.sbu_closure_required_open,
                                'job': project.display_name,
                            }
                        )
        return super().write(vals)

    def action_sbu_closure_init_checklist(self):
        """Create missing checklist lines from active document types."""
        total = self._sbu_closure_init_missing_lines()
        if not total:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Closure checklist'),
                    'message': _('No new lines to add (types already present or none marked “Add on init”).'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Closure checklist'),
                'message': _('Added %(n)s checklist line(s) across selected jobs.', n=total),
                'type': 'success',
                'sticky': False,
            },
        }

