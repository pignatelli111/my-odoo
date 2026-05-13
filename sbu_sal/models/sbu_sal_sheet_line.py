from odoo import models, fields, api


class SbuSalSheetLine(models.Model):
    _name = 'sbu.sal.sheet.line'
    _description = 'SBU SAL line'
    _order = 'sequence, id'

    sheet_id = fields.Many2one(
        'sbu.sal.sheet',
        string='SAL sheet',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    description = fields.Char(string='Description', required=True)
    contract_amount = fields.Monetary(
        string='Contract amount',
        currency_field='currency_id',
    )
    percent_this_sal = fields.Float(string='This SAL %', digits=(16, 2))
    amount_this_sal = fields.Monetary(
        string='Amount this SAL',
        compute='_compute_amount_this_sal',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='sheet_id.currency_id',
        store=True,
        readonly=True,
    )

    @api.depends('contract_amount', 'percent_this_sal')
    def _compute_amount_this_sal(self):
        for line in self:
            line.amount_this_sal = (line.contract_amount or 0.0) * (line.percent_this_sal or 0.0) / 100.0
