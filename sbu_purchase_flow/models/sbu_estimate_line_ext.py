# -*- coding: utf-8 -*-
from odoo import models


class SbuEstimateLine(models.Model):
    _inherit = 'sbu.estimate.line'

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
