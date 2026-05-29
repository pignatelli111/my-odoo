# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .sbu_budget_helpers import sbu_traffic_light_from_pct


class SbuEstimateLine(models.Model):
    _inherit = 'sbu.estimate.line'

    budget_traffic_light = fields.Selection(
        [
            ('ok', 'Green'),
            ('warning', 'Yellow'),
            ('over', 'Red'),
        ],
        string='Budget traffic light',
        compute='_compute_sbu_budget_traffic_light',
        store=True,
    )

    @api.depends(
        'cost_total_tot',
        'budget_orders_issued',
        'budget_costs_incurred',
    )
    def _compute_sbu_budget_traffic_light(self):
        for line in self:
            planned = line.cost_total_tot or 0.0
            if not planned:
                line.budget_traffic_light = 'ok'
                continue
            pct_orders = (line.budget_orders_issued / planned) * 100.0
            pct_actual = (line.budget_costs_incurred / planned) * 100.0
            pct_watch = max(pct_orders, pct_actual)
            line.budget_traffic_light = sbu_traffic_light_from_pct(pct_watch, planned)

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('width_mm', 'height_mm', 'qty')):
            bom_lines = self.mapped('bom_line_ids')
            if bom_lines:
                # Invalidate stored computes so qty_ordered / total_cost refresh on read
                # (do not call _compute_* directly — breaks in some ORM flush states).
                bom_lines.invalidate_recordset(
                    ['qty_theoretical', 'qty_ordered', 'total_cost'],
                )
                bom_lines._sbu_propagate_qty_to_purchase_lines()
        return res
