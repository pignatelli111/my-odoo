# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_id = fields.Many2one(
        'project.project',
        string='Job / project',
        index=True,
        ondelete='set null',
        tracking=True,
        help='Links vendor orders to the SBU job; receptions inherit this project.',
    )

    def _prepare_picking(self):
        res = super()._prepare_picking()
        if self.project_id:
            res['project_id'] = self.project_id.id
        return res
