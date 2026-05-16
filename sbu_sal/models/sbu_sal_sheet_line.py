from odoo import api, fields, models


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
    estimate_sal_line_id = fields.Many2one(
        'sbu.estimate.sal.line',
        string='Contractual SAL item',
        ondelete='set null',
        index=True,
        domain="[('estimate_id', '=', parent.estimate_id)]",
    )
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

    @api.onchange('estimate_sal_line_id')
    def _onchange_estimate_sal_line_id(self):
        if not self.estimate_sal_line_id:
            return
        sal = self.estimate_sal_line_id
        self.description = sal.description or sal.item_ref or self.description
        self.contract_amount = sal.total_contract
        if sal.retention_percent and self.sheet_id:
            self.sheet_id.retention_percent = sal.retention_percent

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sbu_touch_contractual_billing()
        return lines

    def write(self, vals):
        before = self.mapped('estimate_sal_line_id')
        res = super().write(vals)
        touch = before | self.mapped('estimate_sal_line_id')
        if touch:
            touch._sbu_recompute_billing_from_sheet_lines()
        return res

    def unlink(self):
        before = self.mapped('estimate_sal_line_id')
        res = super().unlink()
        if before:
            before._sbu_recompute_billing_from_sheet_lines()
        return res

    def _sbu_touch_contractual_billing(self):
        sal_lines = self.mapped('estimate_sal_line_id')
        if sal_lines:
            sal_lines._sbu_recompute_billing_from_sheet_lines()
