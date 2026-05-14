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
    invoice_post_override = fields.Selection(
        selection=[
            ('company', 'Use company default'),
            ('draft', 'Always keep invoice in draft'),
            ('posted', 'Always post invoice'),
        ],
        string='Invoice posting',
        default='company',
        help='Overrides the company default for this SAL only (draft vs posted customer invoice).',
    )
    invoice_tax_ids = fields.Many2many(
        'account.tax',
        'sbu_sal_sheet_invoice_tax_rel',
        'sheet_id',
        'tax_id',
        string='Invoice taxes',
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'parent_of', company_id)]",
        help='Optional. If empty, company SAL default sale taxes apply, then fiscal position mapping.',
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

    def _sbu_sal_effective_invoice_post_mode(self):
        self.ensure_one()
        if self.invoice_post_override == 'company':
            return self.company_id.sbu_sal_invoice_post_default or 'draft'
        return self.invoice_post_override

    def _sbu_sal_prepare_invoice_line_vals(self, account, fiscal_position):
        self.ensure_one()
        partner = self.partner_id
        base_taxes = self.invoice_tax_ids or self.company_id.sbu_sal_default_tax_ids
        if fiscal_position:
            account = fiscal_position.map_account(account)
            taxes = fiscal_position.map_tax(base_taxes)
        else:
            taxes = base_taxes

        line_vals = {
            'name': _('SAL %s — progress billing') % self.name,
            'quantity': 1.0,
            'price_unit': self.amount_net,
            'account_id': account.id,
            'tax_ids': [fields.Command.set(taxes.ids)],
        }
        project = self.project_id
        aa = project.account_id if project else False
        if aa and 'analytic_distribution' in self.env['account.move.line']._fields:
            line_vals['analytic_distribution'] = {str(aa.id): 100.0}
        return line_vals

    def action_create_draft_invoice(self):
        """Create a customer invoice from the SAL: taxes, fiscal position, analytic to project; post per policy."""
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

        Fiscal = self.env['account.fiscal.position'].with_company(self.company_id)
        fiscal_position = Fiscal._get_fiscal_position(self.partner_id)
        line_vals = self._sbu_sal_prepare_invoice_line_vals(account, fiscal_position)

        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.name,
            'ref': _('SAL %s') % self.name,
            'fiscal_position_id': fiscal_position.id if fiscal_position else False,
            'invoice_line_ids': [fields.Command.create(line_vals)],
        }
        if 'project_id' in self.env['account.move']._fields:
            move_vals['project_id'] = self.project_id.id

        move = self.env['account.move'].with_company(self.company_id).create(move_vals)
        self.write({'invoice_id': move.id, 'state': 'invoiced'})

        if self._sbu_sal_effective_invoice_post_mode() == 'posted':
            move.action_post()

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
