# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    project_id = fields.Many2one(
        'project.project',
        string='Job / project',
        index=True,
        ondelete='set null',
        tracking=True,
        help='SBU job this transfer belongs to (incoming from PO, internal, or deliveries).',
    )

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._sbu_sync_project_from_sources()
        return pickings

    def write(self, vals):
        res = super().write(vals)
        if 'move_ids' in vals or 'move_line_ids' in vals:
            self._sbu_sync_project_from_sources()
        return res

    def _sbu_sync_project_from_sources(self):
        """Fill project_id on pickings when missing (service/subcontract/MRP paths)."""
        for picking in self.filtered(lambda p: not p.project_id):
            project = picking._sbu_project_from_moves()
            if project:
                picking.project_id = project

    def _sbu_project_from_moves(self):
        self.ensure_one()
        for move in self.move_ids:
            pol = move.purchase_line_id
            if pol and pol.order_id.project_id:
                return pol.order_id.project_id
        for move in self.move_ids:
            mo = False
            if 'raw_material_production_id' in move._fields and move.raw_material_production_id:
                mo = move.raw_material_production_id
            elif 'production_id' in move._fields and move.production_id:
                mo = move.production_id
            if mo and 'project_id' in mo._fields and mo.project_id:
                return mo.project_id
        return False

