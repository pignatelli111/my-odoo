# -*- coding: utf-8 -*-
from odoo import fields, models


class SbuLogikalImportLine(models.Model):
    _name = 'sbu.logikal.import.line'
    _description = 'Logikal / ReynaPro import line'
    _order = 'sequence, id'

    batch_id = fields.Many2one(
        'sbu.logikal.import.batch',
        string='Import',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    external_pos = fields.Char(string='Position', index=True)
    profile_code = fields.Char(string='Profile code', index=True)
    description = fields.Char(string='Description')
    qty = fields.Float(string='Qty (per unit)', default=1.0, digits=(16, 3))
    width_mm = fields.Float(string='Width mm', digits=(16, 1))
    height_mm = fields.Float(string='Height mm', digits=(16, 1))
    raw_payload = fields.Text(string='Raw row (JSON)', help='Original row for audit.')

    product_id = fields.Many2one(
        'product.product',
        string='Mapped product',
    )
    map_state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('mapped', 'Mapped'),
            ('unmapped', 'Unmapped'),
        ],
        string='Mapping',
        default='pending',
    )

    sbu_estimate_bom_line_id = fields.Many2one(
        'sbu.estimate.bom.line',
        string='Estimate BOM line',
        readonly=True,
        copy=False,
    )
    mrp_bom_line_id = fields.Many2one(
        'mrp.bom.line',
        string='MRP BOM line',
        readonly=True,
        copy=False,
    )
