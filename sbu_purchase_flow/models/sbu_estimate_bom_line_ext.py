# -*- coding: utf-8 -*-
from odoo import models


class SbuEstimateBomLine(models.Model):
    _inherit = 'sbu.estimate.bom.line'

    purchase_request_line_ids = fields.One2many(
        'sbu.purchase.request.line',
        'source_bom_line_id',
        string='Purchase request lines',
        help='Righe richiesta acquisto collegate a questa riga distinta (unica fonte quantità/costo).',
    )

    def write(self, vals):
        res = super().write(vals)
        self._sbu_propagate_qty_to_purchase_lines()
        return res

    def _sbu_propagate_qty_to_purchase_lines(self):
        for bom in self:
            for pr_line in bom.purchase_request_line_ids:
                if pr_line.bom_qty_sync and pr_line.source_bom_line_id == bom:
                    pr_line.product_qty = bom.qty_ordered
