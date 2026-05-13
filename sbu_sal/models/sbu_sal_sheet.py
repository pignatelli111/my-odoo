from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SbuSalSheet(models.Model):
    """Progress billing sheet (SAL) linked to a project."""
    _name = 'sbu.sal.sheet'
    _description = 'SBU SAL / Progress billing sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project / Job',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Source estimate',
        related='project_id.sbu_estimate_id',
        store=True,
        readonly=True,
    )
    date = fields.Date(string='SAL date', default=fields.Date.today, tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('invoiced', 'Invoiced'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    retention_percent = fields.Float(
        string='Retention %',
        digits=(16, 2),
        default=5.0,
        help='Withholding / retention on gross amount (e.g. garanzia).',
    )
    line_ids = fields.One2many(
        'sbu.sal.sheet.line',
        'sheet_id',
        string='Lines',
    )
    certificate_ids = fields.One2many(
        'sbu.payment.certificate',
        'sal_sheet_id',
        string='Payment certificates',
    )
    amount_gross = fields.Monetary(
        string='Gross amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_retention = fields.Monetary(
        string='Retention',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_net = fields.Monetary(
        string='Net payable',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.sal.sheet') or _('New')
        return super().create(vals_list)

    @api.depends('line_ids.amount_this_sal', 'retention_percent')
    def _compute_amounts(self):
        for rec in self:
            gross = sum(rec.line_ids.mapped('amount_this_sal'))
            rec.amount_gross = gross
            rec.amount_retention = gross * (rec.retention_percent or 0.0) / 100.0
            rec.amount_net = gross - rec.amount_retention

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_create_certificate(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Confirm the SAL before creating a payment certificate.'))
        cert = self.env['sbu.payment.certificate'].create({
            'sal_sheet_id': self.id,
            'project_id': self.project_id.id,
            'currency_id': self.currency_id.id,
            'amount_gross': self.amount_gross,
            'retention_percent': self.retention_percent,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.payment.certificate',
            'res_id': cert.id,
            'view_mode': 'form',
        }
