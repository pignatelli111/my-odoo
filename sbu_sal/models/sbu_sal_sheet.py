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
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='estimate_id.partner_id',
        store=True,
        readonly=True,
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Customer invoice',
        copy=False,
        readonly=True,
        tracking=True,
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

    def action_create_draft_invoice(self):
        """Create a draft customer invoice for the net SAL amount (accounting link)."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Confirm the SAL before creating an invoice.'))
        if not self.partner_id:
            raise UserError(_('The linked estimate has no customer; set a client on the estimate first.'))
        if self.invoice_id:
            raise UserError(_('An invoice is already linked to this SAL.'))
        if not self.amount_net or self.amount_net <= 0:
            raise UserError(_('Net payable must be greater than zero.'))
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            raise UserError(_('Configure a sales journal for this company.'))
        account = journal.default_account_id
        if not account:
            raise UserError(_('Set a default income account on the sales journal %s.') % journal.display_name)
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.name,
            'ref': _('SAL %s') % self.name,
            'invoice_line_ids': [(0, 0, {
                'name': _('SAL %s — progress billing') % self.name,
                'quantity': 1.0,
                'price_unit': self.amount_net,
                'account_id': account.id,
                'tax_ids': [(6, 0, [])],
            })],
        })
        self.write({'invoice_id': move.id, 'state': 'invoiced'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }
