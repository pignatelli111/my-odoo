# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    sbu_job_id = fields.Many2one(
        'project.project', string='Job', compute='_compute_sbu_job_id', store=True, index='btree_not_null',
        help='SBU job of this invoice or bill, from the analytic account of its lines.',
    )

    @api.depends('invoice_line_ids.analytic_distribution')
    def _compute_sbu_job_id(self):
        Project = self.env['project.project'].sudo().with_context(active_test=False)
        for move in self:
            account_ids = {
                int(account_id)
                for line in move.invoice_line_ids
                for key in (line.analytic_distribution or {})
                for account_id in key.split(',')
            }
            move.sbu_job_id = Project.search([
                ('account_id', 'in', list(account_ids)), ('sbu_estimate_id', '!=', False),
            ], limit=1) if account_ids else False

    def action_sbu_open_job(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job'),
            'res_model': 'project.project',
            'res_id': self.sbu_job_id.id,
            'view_mode': 'form',
        }
