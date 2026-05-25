# -*- coding: utf-8 -*-
from odoo import fields, models


class SbuSalSheetLineImportWizardLine(models.TransientModel):
    _name = 'sbu.sal.sheet.line.import.wizard.line'
    _description = 'Contractual SAL row in customer SAL import wizard'
    _order = 'sequence, contract_line_id'

    wizard_id = fields.Many2one(
        'sbu.sal.sheet.line.import.wizard',
        required=True,
        ondelete='cascade',
    )
    contract_line_id = fields.Many2one(
        'sbu.estimate.sal.line',
        string='Contractual item',
        required=True,
        ondelete='cascade',
    )
    selected = fields.Boolean(string='Add', default=False)
    sequence = fields.Integer(related='contract_line_id.sequence', readonly=True)
    name = fields.Char(related='contract_line_id.name', string='Voce')
    item_ref = fields.Char(related='contract_line_id.item_ref', string='Item')
    description = fields.Text(related='contract_line_id.description')
    uom_type = fields.Selection(related='contract_line_id.uom_type', string='U.M.')
    total_contract = fields.Monetary(
        related='contract_line_id.total_contract',
        string='Contract €',
        currency_field='currency_id',
    )
    cumulative_pct = fields.Float(related='contract_line_id.cumulative_pct', string='Cum. %')
    sal_status = fields.Selection(related='contract_line_id.sal_status', string='Status')
    currency_id = fields.Many2one(related='contract_line_id.currency_id')
