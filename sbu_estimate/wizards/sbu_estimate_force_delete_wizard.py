# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models, _


class SbuEstimateForceDeleteWizard(models.TransientModel):
    _name = 'sbu.estimate.force.delete.wizard'
    _description = 'UAT: force-delete preventivo and linked test data'

    estimate_ids = fields.Many2many(
        'sbu.estimate',
        string='Preventivi',
        required=True,
        readonly=True,
    )
    summary = fields.Html(string='Summary', compute='_compute_summary', sanitize=False)
    confirm = fields.Boolean(
        string='I understand this permanently removes the preventivo and linked test documents',
        default=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        if active_ids and 'estimate_ids' in fields_list and not res.get('estimate_ids'):
            res['estimate_ids'] = [Command.set(active_ids)]
        return res

    @api.depends('estimate_ids')
    def _compute_summary(self):
        for wiz in self:
            if not wiz.estimate_ids:
                wiz.summary = '<p class="text-muted">No estimates selected.</p>'
                continue
            parts = [
                '<p><strong>This will permanently delete:</strong></p><ul>',
            ]
            for est in wiz.estimate_ids:
                parts.append(f'<li><b>{est.display_name}</b> ({est.state})')
                if est.project_id:
                    project = est.project_id
                    parts.append(
                        f' — commessa <b>{project.display_name}</b>'
                    )
                    if 'sbu.sal.sheet' in self.env:
                        n_sal = self.env['sbu.sal.sheet'].search_count(
                            [('project_id', '=', project.id)]
                        )
                        if n_sal:
                            parts.append(f', {n_sal} SAL sheet(s)')
                    if 'sbu.purchase.request' in self.env:
                        n_pr = self.env['sbu.purchase.request'].search_count(
                            [('project_id', '=', project.id)]
                        )
                        if n_pr:
                            parts.append(f', {n_pr} purchase request(s)')
                    if 'purchase.order' in self.env:
                        n_po = self.env['purchase.order'].search_count(
                            [('project_id', '=', project.id)]
                        )
                        if n_po:
                            parts.append(f', {n_po} PO(s)')
                parts.append('</li>')
            parts.append(
                '</ul><p class="text-danger">'
                'Use only for <b>test/UAT</b> data. Production jobs should not be removed this way.'
                '</p>'
            )
            wiz.summary = ''.join(parts)

    def action_force_delete(self):
        self.ensure_one()
        if not self.confirm:
            from odoo.exceptions import UserError
            raise UserError(_('Tick the confirmation box to proceed.'))
        n = self.estimate_ids._sbu_force_delete_with_cleanup()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Test cleanup'),
                'message': _('Removed %(n)s preventivo(s).', n=n),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Preventivi'),
                    'res_model': 'sbu.estimate',
                    'view_mode': 'list,form',
                    'target': 'current',
                },
            },
        }
