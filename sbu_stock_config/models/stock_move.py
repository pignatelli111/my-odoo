# -*- coding: utf-8 -*-
from odoo import api, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves.mapped('picking_id')._sbu_sync_project_from_sources()
        return moves

    def write(self, vals):
        res = super().write(vals)
        keys = {'picking_id', 'purchase_line_id', 'production_id', 'raw_material_production_id'}
        if keys.intersection(vals):
            self.mapped('picking_id')._sbu_sync_project_from_sources()
        return res
