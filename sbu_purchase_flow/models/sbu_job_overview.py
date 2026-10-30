# -*- coding: utf-8 -*-
"""Jobs overview: one row per SBU job with budget, purchases, costs, invoicing and collections.

Read-only SQL view built only from standard Odoo documents (purchase orders, invoices, bills,
analytic items), so it counts what is made in SBU and what is made directly in the standard apps.
"""
from odoo import _, fields, models, tools

INCOME_TYPES = ('income', 'income_other')
EXPENSE_TYPES = ('expense', 'expense_direct_cost', 'expense_depreciation')


class SbuJobOverview(models.Model):
    _name = 'sbu.job.overview'
    _description = 'SBU jobs overview'
    _auto = False
    _order = 'project_id desc'
    _rec_name = 'project_id'

    project_id = fields.Many2one('project.project', string='Job', readonly=True)
    project_code = fields.Char(string='Job code', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    estimate_id = fields.Many2one('sbu.estimate', string='Estimate', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    active = fields.Boolean(readonly=True)
    contract_value = fields.Monetary(string='Contract value', readonly=True,
                                     help='Customer price of the estimate.')
    budget_cost = fields.Monetary(string='Cost budget', readonly=True, help='Total cost of the estimate.')
    planned_margin = fields.Monetary(string='Planned margin', readonly=True)
    ordered = fields.Monetary(string='Ordered', readonly=True,
                              help='Confirmed purchase orders of the job, untaxed (from SBU or from Purchase).')
    received = fields.Monetary(string='Received', readonly=True,
                               help='Value of the quantities received on those orders.')
    costs = fields.Monetary(string='Costs billed', readonly=True,
                            help='Posted vendor bills of the job, untaxed (job analytic account).')
    paid = fields.Monetary(string='Paid to suppliers', readonly=True)
    to_pay = fields.Monetary(string='To pay', readonly=True)
    invoiced = fields.Monetary(string='Invoiced', readonly=True,
                               help='Posted customer invoices minus credit notes, untaxed (job analytic account).')
    collected = fields.Monetary(string='Collected', readonly=True)
    to_collect = fields.Monetary(string='To collect', readonly=True)
    margin = fields.Monetary(string='Margin to date', readonly=True, help='Invoiced − costs billed.')
    budget_used_pct = fields.Float(string='Budget used %', readonly=True, digits=(16, 1), aggregator=False,
                                   help='Highest of ordered and costs billed, against the cost budget.')
    invoiced_pct = fields.Float(string='Invoiced %', readonly=True, digits=(16, 1), aggregator=False)
    over_budget = fields.Boolean(string='Over budget', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
            WITH po AS (
                SELECT po.project_id,
                       SUM(pol.price_subtotal / COALESCE(NULLIF(po.currency_rate, 0), 1)) AS ordered,
                       SUM(CASE WHEN pol.product_qty > 0
                                THEN pol.price_subtotal * LEAST(pol.qty_received / pol.product_qty, 1)
                                ELSE 0 END / COALESCE(NULLIF(po.currency_rate, 0), 1)) AS received
                  FROM purchase_order_line pol
                  JOIN purchase_order po ON po.id = pol.order_id
                 WHERE po.state IN ('purchase', 'done') AND po.project_id IS NOT NULL
                   AND pol.display_type IS NULL
              GROUP BY po.project_id
            ), an AS (
                SELECT p.id AS project_id,
                       SUM(CASE WHEN acc.account_type IN %(income)s THEN aal.amount ELSE 0 END) AS invoiced,
                       -SUM(CASE WHEN acc.account_type IN %(expense)s THEN aal.amount ELSE 0 END) AS costs
                  FROM project_project p
                  JOIN account_analytic_line aal ON aal.account_id = p.account_id
                  JOIN account_account acc ON acc.id = aal.general_account_id
                 WHERE p.sbu_estimate_id IS NOT NULL
              GROUP BY p.id
            ), mv AS (
                SELECT sbu_job_id AS project_id,
                       SUM(CASE WHEN move_type IN ('out_invoice', 'out_refund')
                                THEN amount_total_signed - amount_residual_signed ELSE 0 END) AS collected,
                       SUM(CASE WHEN move_type IN ('out_invoice', 'out_refund')
                                THEN amount_residual_signed ELSE 0 END) AS to_collect,
                       -SUM(CASE WHEN move_type IN ('in_invoice', 'in_refund')
                                 THEN amount_total_signed - amount_residual_signed ELSE 0 END) AS paid,
                       -SUM(CASE WHEN move_type IN ('in_invoice', 'in_refund')
                                 THEN amount_residual_signed ELSE 0 END) AS to_pay
                  FROM account_move
                 WHERE state = 'posted' AND sbu_job_id IS NOT NULL
              GROUP BY sbu_job_id
            ), base AS (
                SELECT p.id AS project_id, p.sbu_project_code AS project_code, p.partner_id,
                       p.sbu_estimate_id AS estimate_id, COALESCE(p.company_id, e.company_id) AS company_id,
                       COALESCE(e.currency_id, c.currency_id) AS currency_id, p.active,
                       COALESCE(e.total_price, 0) AS contract_value, COALESCE(e.total_cost, 0) AS budget_cost,
                       COALESCE(po.ordered, 0) AS ordered, COALESCE(po.received, 0) AS received,
                       COALESCE(an.costs, 0) AS costs, COALESCE(an.invoiced, 0) AS invoiced,
                       COALESCE(mv.collected, 0) AS collected, COALESCE(mv.to_collect, 0) AS to_collect,
                       COALESCE(mv.paid, 0) AS paid, COALESCE(mv.to_pay, 0) AS to_pay
                  FROM project_project p
                  JOIN sbu_estimate e ON e.id = p.sbu_estimate_id
                  JOIN res_company c ON c.id = COALESCE(p.company_id, e.company_id)
             LEFT JOIN po ON po.project_id = p.id
             LEFT JOIN an ON an.project_id = p.id
             LEFT JOIN mv ON mv.project_id = p.id
            )
            SELECT project_id AS id, *,
                   contract_value - budget_cost AS planned_margin,
                   invoiced - costs AS margin,
                   CASE WHEN budget_cost > 0 THEN GREATEST(ordered, costs) / budget_cost * 100 ELSE 0 END
                       AS budget_used_pct,
                   CASE WHEN contract_value > 0 THEN invoiced / contract_value * 100 ELSE 0 END AS invoiced_pct,
                   budget_cost > 0 AND GREATEST(ordered, costs) > budget_cost AS over_budget
              FROM base
            )
        """, {'income': INCOME_TYPES, 'expense': EXPENSE_TYPES})

    # ── Drill-down to the standard documents ──────────────────────────────────
    def _sbu_open(self, name, model, domain, context=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': f'{name} — {self.project_id.display_name}',
            'res_model': model, 'view_mode': 'list,form', 'domain': domain, 'context': context or {},
        }

    def action_open_job(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'project.project', 'res_id': self.project_id.id,
                'view_mode': 'form'}

    def action_open_purchase_orders(self):
        return self._sbu_open(_('Purchase orders'), 'purchase.order', [('project_id', '=', self.project_id.id)],
                              {'default_project_id': self.project_id.id})

    def action_open_vendor_bills(self):
        return self._sbu_open(_('Vendor bills'), 'account.move', [
            ('sbu_job_id', '=', self.project_id.id), ('move_type', 'in', ('in_invoice', 'in_refund'))],
            {'default_move_type': 'in_invoice', 'default_sbu_job_id': self.project_id.id})

    def action_open_customer_invoices(self):
        return self._sbu_open(_('Customer invoices'), 'account.move', [
            ('sbu_job_id', '=', self.project_id.id), ('move_type', 'in', ('out_invoice', 'out_refund'))],
            {'default_move_type': 'out_invoice', 'default_sbu_job_id': self.project_id.id})
