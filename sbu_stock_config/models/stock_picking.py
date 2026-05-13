# -*- coding: utf-8 -*-
from odoo import fields, models


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
