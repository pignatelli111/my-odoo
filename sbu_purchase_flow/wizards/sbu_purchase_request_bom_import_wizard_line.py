# -*- coding: utf-8 -*-
from odoo import fields, models


class SbuPurchaseRequestBomImportWizardLine(models.TransientModel):
    _name = 'sbu.purchase.request.bom.import.wizard.line'
    _description = 'BOM row in purchase request import wizard'
    _order = 'estimate_line_id, bom_line_id'

    wizard_id = fields.Many2one(
        'sbu.purchase.request.bom.import.wizard',
        required=True,
        ondelete='cascade',
    )
    bom_line_id = fields.Many2one(
        'sbu.estimate.bom.line',
        string='BOM line',
        required=True,
        ondelete='cascade',
    )
    selected = fields.Boolean(string='Load', default=False)
    estimate_line_id = fields.Many2one(
        related='bom_line_id.estimate_line_id',
        string='ANACO position',
    )
    name = fields.Char(related='bom_line_id.name', string='Component')
    product_id = fields.Many2one(related='bom_line_id.product_id')
    product_category_id = fields.Many2one(
        related='bom_line_id.product_category_id',
        string='Category',
    )
    calc_type = fields.Selection(related='bom_line_id.calc_type', string='Calculation')
    data_phase = fields.Selection(related='bom_line_id.data_phase')
    dimension_display = fields.Char(
        related='bom_line_id.dimension_display',
        string='Dimensions',
    )
    qty_theoretical = fields.Float(
        related='bom_line_id.qty_theoretical',
        string='Qty theoretical',
    )
