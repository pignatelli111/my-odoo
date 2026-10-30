# -*- coding: utf-8 -*-
from odoo import models

from .sbu_budget_helpers import sbu_projects_for_budget_refresh, sbu_refresh_projects_budget


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _sbu_refresh_budget_after_vendor_move(self):
        projects = sbu_projects_for_budget_refresh(self, self.env)
        if projects:
            sbu_refresh_projects_budget(projects, self.env)

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        vendor_moves = self.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund'))
        if vendor_moves and not self.env.context.get('sbu_skip_budget_refresh'):
            vendor_moves._sbu_refresh_budget_after_vendor_move()
        return res

    def write(self, vals):
        if 'sbu_job_id' not in vals:
            return super().write(vals)
        # A posted bill moved to another job: both jobs' budgets change.
        bills = self.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund') and m.state == 'posted')
        before = bills.mapped('sbu_job_id')
        res = super().write(vals)
        projects = (before | bills.mapped('sbu_job_id')).filtered('sbu_estimate_id')
        if projects:
            sbu_refresh_projects_budget(projects, self.env)
        return res

    def button_cancel(self):
        res = super().button_cancel()
        vendor_moves = self.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund'))
        if vendor_moves:
            vendor_moves._sbu_refresh_budget_after_vendor_move()
        return res

    def button_draft(self):
        res = super().button_draft()
        vendor_moves = self.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund'))
        if vendor_moves:
            vendor_moves._sbu_refresh_budget_after_vendor_move()
        return res
