from odoo import models, fields, api, _


class SbuPaymentCertificate(models.Model):
    _name = 'sbu.payment.certificate'
    _description = 'SBU Payment certificate (CDP)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    sal_sheet_id = fields.Many2one(
        'sbu.sal.sheet',
        string='SAL sheet',
        required=True,
        ondelete='cascade',
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
    )
    date = fields.Date(string='Date', default=fields.Date.today)
    currency_id = fields.Many2one(
        'res.currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    amount_gross = fields.Monetary(string='Gross amount', currency_field='currency_id')
    retention_percent = fields.Float(string='Retention %', digits=(16, 2))
    amount_retention = fields.Monetary(
        string='Retention amount',
        compute='_compute_retention',
        store=True,
        currency_field='currency_id',
    )
    amount_net = fields.Monetary(
        string='Net payable',
        compute='_compute_retention',
        store=True,
        currency_field='currency_id',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('issued', 'Issued'), ('paid', 'Paid')],
        default='draft',
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.payment.certificate') or _('New')
        return super().create(vals_list)

    @api.depends('amount_gross', 'retention_percent')
    def _compute_retention(self):
        for rec in self:
            rec.amount_retention = (rec.amount_gross or 0.0) * (rec.retention_percent or 0.0) / 100.0
            rec.amount_net = (rec.amount_gross or 0.0) - rec.amount_retention
