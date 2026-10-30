# -*- coding: utf-8 -*-
from markupsafe import Markup

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
                wiz.summary = Markup('<p class="text-muted">%s</p>') % _('No estimates selected.')
                continue
            items = []
            for est in wiz.estimate_ids:
                parts = [Markup('<b>%s</b> (%s)') % (est.display_name, est.state)]
                project = est.project_id
                if project:
                    parts.append(Markup(' — commessa <b>%s</b>') % project.display_name)
                    for model, label in (('sbu.sal.sheet', _('SAL sheet(s)')),
                                         ('sbu.purchase.request', _('purchase request(s)')),
                                         ('purchase.order', _('PO(s)'))):
                        if model in self.env:
                            count = self.env[model].search_count([('project_id', '=', project.id)])
                            if count:
                                parts.append(Markup(', %s %s') % (count, label))
                    protected = project._sbu_protected_moves()
                    if protected:
                        parts.append(Markup(' <span class="text-danger">— %s</span>') % _(
                            'blocked: posted invoices %s', ', '.join(protected.mapped('display_name'))))
                items.append(Markup('<li>%s</li>') % Markup('').join(parts))
            wiz.summary = Markup(
                '<p><strong>%s</strong></p><ul>%s</ul><p class="text-danger">%s</p>'
            ) % (
                _('This will permanently delete:'), Markup('').join(items),
                _('Use only for test/UAT data. To stop a real job use "Cancel job" on the job.'),
            )

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
