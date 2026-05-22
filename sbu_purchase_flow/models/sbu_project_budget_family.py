# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

from .sbu_budget_helpers import (
    sbu_collect_project_budget,
    sbu_cost_family_label,
    sbu_traffic_light_from_pct,
)
from odoo.addons.sbu_estimate.models.sbu_cost_family import SBU_COST_FAMILY_SELECTION


class SbuProjectBudgetFamily(models.Model):
    """Budget vs actual by ANACO cost family (ITEM sheet style)."""
    _name = 'sbu.project.budget.family'
    _description = 'SBU project budget by cost family'
    _order = 'project_id, cost_family'

    project_id = fields.Many2one(
        'project.project',
        string='Project / Job',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='project_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    cost_family = fields.Selection(
        selection=SBU_COST_FAMILY_SELECTION,
        string='Cost family',
        required=True,
        index=True,
    )
    cost_family_label = fields.Char(
        string='Family label',
        compute='_compute_cost_family_label',
    )
    budget_planned = fields.Monetary(
        string='Budget (estimate)',
        currency_field='currency_id',
        help='Sum of ANACO line costs (cost_total_tot) for this family on the linked estimate.',
    )
    amount_open_pr = fields.Monetary(
        string='Open PR',
        currency_field='currency_id',
        help='Purchase request lines not yet on a PO (quoted or standard price).',
    )
    amount_po_draft = fields.Monetary(
        string='PO draft',
        currency_field='currency_id',
        help='RFQ/PO in draft, sent, or waiting approval.',
    )
    amount_po_confirmed = fields.Monetary(
        string='PO confirmed',
        currency_field='currency_id',
        help='Confirmed purchase orders (purchase/done).',
    )
    amount_engaged = fields.Monetary(
        string='Total engaged',
        compute='_compute_derived_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_residual = fields.Monetary(
        string='Residual budget',
        compute='_compute_derived_amounts',
        store=True,
        currency_field='currency_id',
    )
    pct_engaged = fields.Float(
        string='Engaged %',
        compute='_compute_derived_amounts',
        store=True,
        digits=(16, 2),
    )
    pct_residual = fields.Float(
        string='Residual %',
        compute='_compute_derived_amounts',
        store=True,
        digits=(16, 2),
    )
    traffic_light = fields.Selection(
        [
            ('ok', 'Green'),
            ('warning', 'Yellow'),
            ('over', 'Red'),
        ],
        string='Traffic light',
        compute='_compute_derived_amounts',
        store=True,
    )
    is_over_budget = fields.Boolean(
        string='Over budget',
        compute='_compute_derived_amounts',
        store=True,
    )

    _project_family_unique = models.Constraint(
        'unique(project_id, cost_family)',
        'Only one budget row per project and cost family.',
    )

    @api.depends('cost_family')
    def _compute_cost_family_label(self):
        for row in self:
            row.cost_family_label = sbu_cost_family_label(self.env, row.cost_family)

    @api.depends(
        'budget_planned',
        'amount_open_pr',
        'amount_po_draft',
        'amount_po_confirmed',
    )
    def _compute_derived_amounts(self):
        for row in self:
            engaged = (
                (row.amount_open_pr or 0.0)
                + (row.amount_po_draft or 0.0)
                + (row.amount_po_confirmed or 0.0)
            )
            row.amount_engaged = engaged
            planned = row.budget_planned or 0.0
            row.amount_residual = planned - engaged
            if planned > 0:
                row.pct_engaged = engaged / planned * 100.0
                row.pct_residual = row.amount_residual / planned * 100.0
            else:
                row.pct_engaged = 0.0
                row.pct_residual = 0.0
            row.traffic_light = sbu_traffic_light_from_pct(row.pct_engaged, planned)
            row.is_over_budget = row.traffic_light == 'over'

    @api.model
    def refresh_project(self, project):
        """Rebuild budget rows from estimate + PR/PO (call from project button)."""
        project.ensure_one()
        self.search([('project_id', '=', project.id)]).unlink()
        totals = sbu_collect_project_budget(project, self.env)
        if not totals:
            return self.browse()
        currency = project.company_id.currency_id or self.env.company.currency_id
        vals_list = []
        for fam, amounts in sorted(totals.items(), key=lambda x: sbu_cost_family_label(self.env, x[0])):
            planned = amounts['planned']
            engaged = amounts['open_pr'] + amounts['po_draft'] + amounts['po_confirmed']
            if planned <= 0 and engaged <= 0:
                continue
            vals_list.append({
                'project_id': project.id,
                'currency_id': currency.id,
                'cost_family': fam,
                'budget_planned': planned,
                'amount_open_pr': amounts['open_pr'],
                'amount_po_draft': amounts['po_draft'],
                'amount_po_confirmed': amounts['po_confirmed'],
            })
        return self.create(vals_list)

    @api.model
    def project_has_over_budget(self, project):
        rows = self.search([('project_id', '=', project.id)])
        if not rows:
            rows = self.refresh_project(project)
        return any(rows.mapped('is_over_budget'))
