# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

SBU_JOB_DOMAIN = [('sbu_estimate_id', '!=', False)]


class AccountMove(models.Model):
    _inherit = 'account.move'

    sbu_job_id = fields.Many2one(
        'project.project', string='Job', compute='_compute_sbu_job_id', store=True, readonly=False,
        index='btree_not_null', domain=SBU_JOB_DOMAIN,
        help='SBU job of this invoice or bill. Choosing it puts the job analytic account on the lines, '
             'so the document counts in the job costs / revenue. Filled in by itself from the lines.',
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
            job = Project.search([('account_id', 'in', list(account_ids))] + SBU_JOB_DOMAIN, limit=1) \
                if account_ids else Project
            # A job chosen by hand stays until a line points to another job.
            move.sbu_job_id = job or move.sbu_job_id

    @api.onchange('sbu_job_id')
    def _onchange_sbu_job_id(self):
        self._sbu_apply_job_analytic()

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves.filtered(lambda m: m.sbu_job_id and m.state == 'draft')._sbu_apply_job_analytic()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if vals.get('sbu_job_id'):
            # Also on posted documents: the analytic follows, so old invoices can be put on a job.
            self.filtered(lambda m: m.state != 'cancel')._sbu_apply_job_analytic()
        return res

    def _sbu_apply_job_analytic(self):
        """Job analytic account on the product lines that have none (or another job's)."""
        job_accounts = self.env['project.project'].sudo().with_context(active_test=False).search(
            SBU_JOB_DOMAIN).account_id
        for move in self.filtered(lambda m: m.is_invoice(include_receipts=True)):
            account = move.sbu_job_id.account_id
            if not account:
                continue
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                current = {int(a) for key in (line.analytic_distribution or {}) for a in key.split(',')}
                if account.id in current or (current and not current <= set(job_accounts.ids)):
                    continue  # already on this job, or a distribution chosen on purpose
                line.analytic_distribution = {str(account.id): 100.0}

    def action_sbu_open_job(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job'),
            'res_model': 'project.project',
            'res_id': self.sbu_job_id.id,
            'view_mode': 'form',
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _related_analytic_distribution(self):
        """New lines of an invoice / bill with a job get the job analytic account."""
        distribution = super()._related_analytic_distribution()
        account = self.move_id.sbu_job_id.account_id
        if not distribution and account and self.display_type == 'product':
            return {str(account.id): 100.0}
        return distribution
