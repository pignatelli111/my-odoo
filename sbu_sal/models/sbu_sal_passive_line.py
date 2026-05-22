from odoo import api, fields, models


class SbuSalPassiveLine(models.Model):
    _name = 'sbu.sal.passive.line'
    _description = 'SBU passive SAL line (subcontract / installation)'
    _order = 'sequence, id'

    sheet_id = fields.Many2one(
        'sbu.sal.passive.sheet',
        string='Passive SAL sheet',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    estimate_line_id = fields.Many2one(
        'sbu.estimate.line',
        string='ANACO estimate line',
        ondelete='set null',
        index=True,
        domain="[('estimate_id', '=', parent.estimate_id)]",
    )
    category = fields.Selection(
        [
            ('posa_lin', 'Sheet metal / LIN installation'),
            ('posa_cantiere', 'Site installation'),
            ('subappalto', 'General subcontract'),
            ('servizi', 'Installation services'),
        ],
        string='Cost type',
        required=True,
        default='posa_lin',
    )
    description = fields.Char(string='Description', required=True)
    budget_amount = fields.Monetary(
        string='Budget (ANACO)',
        currency_field='currency_id',
        help='Installation/subcontract budget from the estimate (POS / site costs).',
    )
    percent_prior_sal = fields.Float(
        string='Prior SAL %',
        compute='_compute_percent_prior_sal',
        digits=(16, 2),
        help='Sum of progress % on previous confirmed passive SALs for this budget line.',
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

    @api.depends(
        'estimate_line_id',
        'sheet_id.project_id',
        'sheet_id.state',
    )
    def _compute_percent_prior_sal(self):
        Sheet = self.env['sbu.sal.passive.sheet']
        for line in self:
            if not line.sheet_id.project_id or not line.estimate_line_id:
                line.percent_prior_sal = 0.0
                continue
            prior_lines = self.search([
                ('id', '!=', line.id),
                ('estimate_line_id', '=', line.estimate_line_id.id),
                ('sheet_id.project_id', '=', line.sheet_id.project_id.id),
                ('sheet_id.state', 'in', ('confirmed', 'invoiced')),
                ('sheet_id', '!=', line.sheet_id.id),
            ])
            line.percent_prior_sal = sum(prior_lines.mapped('percent_this_sal'))

    @api.depends('budget_amount', 'percent_this_sal')
    def _compute_amount_this_sal(self):
        for line in self:
            line.amount_this_sal = (line.budget_amount or 0.0) * (line.percent_this_sal or 0.0) / 100.0

    @api.onchange('estimate_line_id')
    def _onchange_estimate_line_id(self):
        if not self.estimate_line_id:
            return
        eline = self.estimate_line_id
        self.description = eline.name or eline.description or self.description
        self.budget_amount = self.sheet_id._sbu_posa_budget_amount(eline)
        self.category = self.sheet_id._sbu_passive_category_for_line(eline)
