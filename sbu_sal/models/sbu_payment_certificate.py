# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.sbu_estimate.models.sbu_account_line_utils import sbu_is_product_line


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
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='sal_sheet_id.company_id',
        store=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
    )
    sbu_revision_label = fields.Char(
        string='Job REV label',
        related='project_id.sbu_revision_label',
        store=True,
        readonly=True,
    )
    sbu_display_label = fields.Char(
        string='Display label',
        compute='_compute_sbu_display_label',
        store=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='sal_sheet_id.partner_id',
        store=True,
        readonly=True,
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Customer invoice',
        related='sal_sheet_id.invoice_id',
        store=True,
        readonly=True,
    )
    invoice_payment_state = fields.Selection(
        string='Invoice payment',
        related='invoice_id.payment_state',
        readonly=True,
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Customer payment',
        copy=False,
        tracking=True,
        domain="[('payment_type', '=', 'inbound'), ('partner_id', 'child_of', partner_id)]",
        help='Optional link to the bank/customer payment that cleared this certificate (after invoice is paid).',
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
        [
            ('draft', 'Draft'),
            ('issued', 'Issued'),
            ('paid', 'Paid'),
        ],
        default='draft',
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                company = self.env.company
                if vals.get('company_id'):
                    company = self.env['res.company'].browse(vals['company_id'])
                elif vals.get('sal_sheet_id'):
                    company = self.env['sbu.sal.sheet'].browse(vals['sal_sheet_id']).company_id
                vals['name'] = (
                    self.env['ir.sequence'].with_company(company.id).next_by_code('sbu.payment.certificate')
                    or _('New')
                )
        certs = super().create(vals_list)
        certs._sbu_touch_linked_contractual_lines()
        return certs

    @api.depends('name', 'sbu_revision_label')
    def _compute_sbu_display_label(self):
        from odoo.addons.sbu_estimate.models.sbu_revision_display import sbu_doc_name_with_revision
        for cert in self:
            cert.sbu_display_label = sbu_doc_name_with_revision(
                cert.name,
                cert.sbu_revision_label,
            ) or cert.name

    def name_get(self):
        if self.env.context.get('sbu_use_document_name_only'):
            return super().name_get()
        return [(rec.id, rec.sbu_display_label or rec.name) for rec in self]

    def write(self, vals):
        res = super().write(vals)
        self._sbu_touch_linked_contractual_lines()
        return res

    def unlink(self):
        if not self.env.context.get('sbu_force_certificate_unlink'):
            blocked = self.filtered(lambda c: c.state != 'draft')
            if blocked and not self.env.user.has_group('base.group_system'):
                raise UserError(
                    _(
                        'Only draft payment certificates can be deleted. '
                        'Use "Remove duplicate CDPs" on the SAL sheet or ask an administrator.'
                    )
                )
        sal_lines = self.env['sbu.estimate.sal.line']
        if 'sbu.estimate.sal.line' in self.env:
            sal_lines = self.mapped('sal_sheet_id.line_ids.estimate_sal_line_id')
        res = super().unlink()
        if sal_lines:
            sal_lines._sbu_recompute_billing_from_sheet_lines()
        return res

    def _sbu_touch_linked_contractual_lines(self):
        if 'sbu.estimate.sal.line' not in self.env:
            return
        for cert in self:
            sal_lines = cert.sal_sheet_id.line_ids.mapped('estimate_sal_line_id')
            if sal_lines:
                sal_lines._sbu_recompute_billing_from_sheet_lines()

    @api.depends('amount_gross', 'retention_percent')
    def _compute_retention(self):
        for rec in self:
            rec.amount_retention = (rec.amount_gross or 0.0) * (rec.retention_percent or 0.0) / 100.0
            rec.amount_net = (rec.amount_gross or 0.0) - rec.amount_retention

    def action_issue(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft certificates can be issued.'))
            inv = rec.invoice_id
            vals = {'state': 'issued'}
            if inv and inv.state == 'posted' and inv.payment_state == 'paid':
                vals['state'] = 'paid'
            rec.write(vals)
            rec._sbu_link_payment_from_invoice()

    def action_mark_paid(self):
        for rec in self:
            if rec.state != 'issued':
                raise UserError(_('Only issued certificates can be marked paid.'))
        self.write({'state': 'paid'})

    def action_sync_payment_from_invoice(self):
        """Try to link customer payment(s) from invoice reconciliation; set paid when invoice is fully paid."""
        for rec in self:
            rec._sbu_link_payment_from_invoice()
        return True

    def _sbu_link_payment_from_invoice(self):
        """Discover account.payment from receivable reconciliation; set state paid if invoice is paid."""
        for rec in self:
            inv = rec.invoice_id
            if not inv or inv.state != 'posted':
                continue
            payments = rec._sbu_find_payments_reconciled_with_invoice(inv)
            vals = {}
            if payments and not rec.payment_id:
                vals['payment_id'] = payments[0].id
            if inv.payment_state == 'paid' and rec.state == 'issued':
                vals['state'] = 'paid'
            if vals:
                rec.write(vals)

    def _sbu_find_payments_reconciled_with_invoice(self, invoice):
        """Return account.payment records linked to moves reconciled with this invoice's receivable lines."""
        self.ensure_one()
        payments = self.env['account.payment']
        receivable_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and sbu_is_product_line(l)
        )
        for line in receivable_lines:
            partials = line.matched_debit_ids | line.matched_credit_ids
            for partial in partials:
                other = partial.debit_move_id if partial.credit_move_id == line else partial.credit_move_id
                move = other.move_id
                pay = move.origin_payment_id
                if pay:
                    payments |= pay
        return payments
