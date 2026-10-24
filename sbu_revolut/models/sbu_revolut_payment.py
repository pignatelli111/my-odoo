# -*- coding: utf-8 -*-
import logging
import uuid

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools import float_compare

from odoo.addons.base.models.res_bank import sanitize_account_number
from odoo.addons.sbu_revolut.services.revolut_client import RevolutHttpError

_logger = logging.getLogger(__name__)

APPROVER_GROUP = 'sbu_revolut.group_sbu_revolut_payment_approver'
_ACTIVE_STATES = ('draft', 'waiting_second', 'approved', 'sent')
_LOCKED_FIELDS = {
    'move_id', 'partner_bank_id', 'amount', 'currency_id', 'account_id', 'reference', 'company_id',
}
_FAILED_REVOLUT_STATES = ('declined', 'failed', 'reverted')
_REFERENCE_MAX = 100


class SbuRevolutPayment(models.Model):
    _name = 'sbu.revolut.payment'
    _description = 'SBU Revolut payment order (vendor bill)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'execution_date desc, id desc'

    name = fields.Char(string='Reference', default='/', readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company,
    )
    move_id = fields.Many2one(
        'account.move', string='Vendor bill', required=True, index=True, tracking=True,
        domain="[('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), ('company_id', '=', company_id)]",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Supplier', related='move_id.commercial_partner_id', store=True,
    )
    partner_bank_id = fields.Many2one(
        'res.partner.bank', string='Supplier bank account', required=True, tracking=True,
        domain="[('partner_id', 'child_of', partner_id)]",
        help='Must be a trusted account ("Send Money" enabled by an authorized person).',
    )
    iban = fields.Char(string='IBAN at approval', readonly=True, copy=False)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    reference = fields.Char(string='Payment reference', required=True, tracking=True)
    account_id = fields.Many2one(
        'sbu.revolut.account', string='Pay from (Revolut)', required=True, tracking=True,
        domain="[('company_id', '=', company_id), ('currency_id', '=', currency_id)]",
    )
    execution_date = fields.Date(
        string='Pay on', required=True, tracking=True,
        default=fields.Date.context_today,
        help='Approved payments are sent automatically on this date.',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('waiting_second', 'Waiting second approval'),
            ('approved', 'Approved'),
            ('sent', 'Sent to Revolut'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status', default='draft', required=True, tracking=True, copy=False,
    )
    requires_second_approval = fields.Boolean(compute='_compute_requires_second_approval')
    approved_by_id = fields.Many2one('res.users', string='Approved by', readonly=True, copy=False)
    approved_on = fields.Datetime(string='Approved on', readonly=True, copy=False)
    second_approved_by_id = fields.Many2one('res.users', string='Second approval by', readonly=True, copy=False)
    second_approved_on = fields.Datetime(string='Second approval on', readonly=True, copy=False)
    sent_on = fields.Datetime(string='Sent on', readonly=True, copy=False)
    request_id = fields.Char(string='Revolut request id', readonly=True, copy=False, index=True)
    revolut_transaction_id = fields.Char(string='Revolut transaction id', readonly=True, copy=False, index=True)
    revolut_state = fields.Char(string='Revolut state', readonly=True, copy=False, tracking=True)
    error_message = fields.Text(string='Last error', readonly=True, copy=False)
    payment_id = fields.Many2one('account.payment', string='Odoo payment', readonly=True, copy=False)

    _sbu_revolut_payment_request_uniq = models.Constraint(
        'unique(request_id)',
        'A Revolut request id must be unique.',
    )

    @api.depends('amount', 'company_id.sbu_revolut_second_approval_amount')
    def _compute_requires_second_approval(self):
        for order in self:
            limit = order.company_id.sbu_revolut_second_approval_amount
            order.requires_second_approval = bool(limit) and float_compare(
                order.amount, limit, precision_rounding=order.currency_id.rounding or 0.01,
            ) >= 0

    # ── ORM ───────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.revolut.payment') or '/'
            vals['request_id'] = str(uuid.uuid4())
        orders = super().create(vals_list)
        orders._sbu_check_amount_available()
        return orders

    def write(self, vals):
        if _LOCKED_FIELDS & set(vals) and any(o.state not in ('draft', 'failed', 'cancelled') for o in self):
            raise UserError(_('Reset the payment to draft before changing amount, bank account or reference.'))
        res = super().write(vals)
        if {'amount', 'move_id'} & set(vals):
            self._sbu_check_amount_available()
        return res

    def unlink(self):
        if any(o.state not in ('draft', 'cancelled') for o in self):
            raise UserError(_('Only draft or cancelled Revolut payments can be deleted.'))
        return super().unlink()

    # ── Defaults from a bill ──────────────────────────────────────────────────
    @api.model
    def _sbu_vals_from_bill(self, bill):
        company = bill.company_id
        others = self.search([('move_id', '=', bill.id), ('state', 'in', _ACTIVE_STATES)])
        remaining = bill.amount_residual - sum(others.mapped('amount'))
        partner = bill.commercial_partner_id
        bank = bill.partner_bank_id or partner.bank_ids.filtered('allow_out_payment')[:1] or partner.bank_ids[:1]
        account = company.sbu_revolut_payment_account_id
        if account.currency_id != bill.currency_id:
            account = self.env['sbu.revolut.account'].search([
                ('company_id', '=', company.id), ('currency_id', '=', bill.currency_id.id),
            ], limit=1)
        due = bill.invoice_date_due or fields.Date.context_today(self)
        return {
            'company_id': company.id,
            'move_id': bill.id,
            'partner_bank_id': bank.id,
            'amount': remaining,
            'currency_id': bill.currency_id.id,
            'reference': (bill.ref or bill.payment_reference or bill.name or '')[:_REFERENCE_MAX],
            'account_id': account.id,
            'execution_date': max(due, fields.Date.context_today(self)),
        }

    # ── Checks ────────────────────────────────────────────────────────────────
    def _sbu_check_amount_available(self):
        for order in self.filtered(lambda o: o.state in _ACTIVE_STATES):
            bill = order.move_id
            if bill.move_type != 'in_invoice':
                raise UserError(_('Revolut payments can only pay vendor bills.'))
            if float_compare(order.amount, 0.0, precision_rounding=order.currency_id.rounding) <= 0:
                raise UserError(_('The payment amount must be positive.'))
            others = self.search([
                ('move_id', '=', bill.id), ('state', 'in', _ACTIVE_STATES), ('id', '!=', order.id),
            ])
            available = bill.amount_residual - sum(others.mapped('amount'))
            if float_compare(order.amount, available, precision_rounding=order.currency_id.rounding) > 0:
                raise UserError(_(
                    '%(bill)s: only %(available).2f %(cur)s is left to pay (other Revolut payments included).',
                    bill=bill.name, available=available, cur=order.currency_id.name,
                ))

    def _sbu_check_payable(self, at_send=False):
        self.ensure_one()
        bill = self.move_id
        if bill.state != 'posted':
            raise UserError(_('%s must be posted.', bill.display_name))
        if bill.company_id != self.company_id:
            raise UserError(_('The bill belongs to another company.'))
        if bill.currency_id != self.currency_id:
            raise UserError(_('The payment currency must be the bill currency.'))
        self._sbu_check_amount_available()
        bank = self.partner_bank_id
        if bank.partner_id.commercial_partner_id != bill.commercial_partner_id:
            raise UserError(_('The bank account does not belong to %s.', bill.commercial_partner_id.display_name))
        if not bank.allow_out_payment:
            raise UserError(_(
                'The bank account %s is not trusted. An authorized person must enable "Send Money" '
                'on it before it can be paid.', bank.display_name,
            ))
        iban = sanitize_account_number(bank.acc_number)
        if len(iban) < 15 or not iban[:2].isalpha():
            raise UserError(_('%s is not an IBAN.', bank.acc_number))
        if at_send and iban != self.iban:
            raise UserError(_('The IBAN changed after approval. Reset to draft and approve again.'))
        account = self.account_id
        if not account.active or account.currency_id != self.currency_id:
            raise UserError(_('Choose an active Revolut account in %s.', self.currency_id.name))
        if account.company_id != self.company_id:
            raise UserError(_('The Revolut account belongs to another company.'))

    # ── Approval ──────────────────────────────────────────────────────────────
    def action_approve(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_('Only Revolut payment approvers can approve payments.'))
        now = fields.Datetime.now()
        for order in self:
            if order.state == 'draft':
                order._sbu_check_payable()
                order.write({
                    'approved_by_id': self.env.uid,
                    'approved_on': now,
                    'iban': sanitize_account_number(order.partner_bank_id.acc_number),
                    'state': 'waiting_second' if order.requires_second_approval else 'approved',
                    'error_message': False,
                })
            elif order.state == 'waiting_second':
                if order.approved_by_id == self.env.user:
                    raise UserError(_('%s needs the approval of a second, different person.', order.name))
                order._sbu_check_payable(at_send=True)
                order.write({
                    'second_approved_by_id': self.env.uid,
                    'second_approved_on': now,
                    'state': 'approved',
                })
            else:
                raise UserError(_('%s cannot be approved in its current status.', order.name))
        return True

    def action_cancel(self):
        for order in self:
            if order.state in ('sent', 'paid'):
                raise UserError(_('%s was already sent to Revolut and cannot be cancelled here.', order.name))
        self.write({'state': 'cancelled'})
        return True

    def action_reset_to_draft(self):
        for order in self:
            if order.state not in ('waiting_second', 'approved', 'failed', 'cancelled'):
                raise UserError(_('%s cannot be reset to draft.', order.name))
            # A new request id: Revolut must treat the retry as a new payment.
            new_request = str(uuid.uuid4()) if order.state in ('failed', 'cancelled') else order.request_id
            super(SbuRevolutPayment, order).write({
                'state': 'draft',
                'request_id': new_request,
                'approved_by_id': False,
                'approved_on': False,
                'second_approved_by_id': False,
                'second_approved_on': False,
                'iban': False,
                'revolut_transaction_id': False if order.state in ('failed', 'cancelled') else order.revolut_transaction_id,
                'revolut_state': False if order.state in ('failed', 'cancelled') else order.revolut_state,
            })
        return True

    # ── Sending ───────────────────────────────────────────────────────────────
    def action_send_now(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_('Only Revolut payment approvers can send payments.'))
        for order in self:
            if order.state != 'approved':
                raise UserError(_('%s must be approved before it is sent.', order.name))
            order._sbu_send(raise_on_error=True)
        return True

    def _sbu_send(self, raise_on_error=False):
        """Send one approved order to Revolut (idempotent thanks to request_id).

        Returns True when Revolut accepted the payment.
        """
        self.ensure_one()
        order = self.sudo()
        try:
            order._sbu_check_payable(at_send=True)
            balance = order.account_id._sbu_refresh_balance()
            if float_compare(balance, order.amount, precision_rounding=order.currency_id.rounding) < 0:
                raise UserError(_(
                    'Insufficient balance on %(account)s: %(balance).2f %(cur)s available.',
                    account=order.account_id.name, balance=balance, cur=order.currency_id.name,
                ))
            company = order.company_id
            cp_id, cp_account_id = order.partner_id._sbu_revolut_ensure_counterparty(
                company, order.partner_bank_id, order.currency_id,
            )
            result = company._sbu_revolut_client().pay({
                'request_id': order.request_id,
                'account_id': order.account_id.revolut_account_id,
                'receiver': {'counterparty_id': cp_id, 'account_id': cp_account_id},
                'amount': round(order.amount, 2),
                'currency': order.currency_id.name,
                'reference': order.reference[:_REFERENCE_MAX],
            })
        except (UserError, RevolutHttpError) as err:
            if raise_on_error:
                raise UserError(_('%(name)s not sent: %(err)s', name=order.name, err=err)) from err
            order.error_message = str(err)
            order.message_post(body=_('Revolut payment not sent: %s', err))
            return False
        order.write({
            'state': 'sent',
            'sent_on': fields.Datetime.now(),
            'revolut_transaction_id': result.get('id'),
            'revolut_state': result.get('state'),
            'error_message': False,
        })
        # Money has left Revolut: keep "sent" even if the Odoo-side registration fails below.
        if not tools.config['test_enable']:
            self.env.cr.commit()
        try:
            with self.env.cr.savepoint():
                order._sbu_apply_revolut_state(result.get('state'), result.get('completed_at'))
        except UserError as err:
            order.error_message = _('Paid in Revolut, but the Odoo payment could not be registered: %s', err)
            order.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Register the Revolut payment'),
                note=order.error_message,
                user_id=order.approved_by_id.id or self.env.uid,
            )
        return True

    def _sbu_apply_revolut_state(self, revolut_state, completed_at=None, reason=None):
        self.ensure_one()
        if revolut_state:
            self.revolut_state = revolut_state
        if revolut_state == 'completed' and self.state == 'sent':
            self._sbu_register_odoo_payment(completed_at)
        elif revolut_state in _FAILED_REVOLUT_STATES:
            if self.state == 'paid':
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Revolut payment %s', revolut_state),
                    note=_('Revolut reports this paid transfer as %s: check the bill and the Odoo payment.', revolut_state),
                    user_id=self.approved_by_id.id or self.env.uid,
                )
            else:
                self.write({
                    'state': 'failed',
                    'error_message': reason or _('Revolut status: %s', revolut_state),
                })

    def _sbu_register_odoo_payment(self, completed_at=None):
        self.ensure_one()
        bill = self.move_id
        pay_date = fields.Date.to_date(str(completed_at)[:10]) if completed_at else fields.Date.context_today(self)
        vals = {
            'amount': min(self.amount, bill.amount_residual),
            'payment_date': pay_date,
            'communication': self.reference,
            'partner_bank_id': self.partner_bank_id.id,
        }
        journal = self.account_id._sbu_journal()
        if journal:
            vals['journal_id'] = journal.id
        wizard = self.env['account.payment.register'].sudo().with_context(
            active_model='account.move', active_ids=bill.ids, active_id=bill.id,
        ).create(vals)
        payment = wizard._create_payments()[:1]
        self.write({'payment_id': payment.id, 'state': 'paid'})
        movements = self.env['sbu.revolut.transaction'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('revolut_remote_id', '=', self.revolut_transaction_id),
        ])
        movements.write({
            'revolut_payment_id': self.id,
            'match_vendor_bill_id': bill.id,
            'match_payment_id': payment.id,
            'sbu_match_confidence': 'high',
            'sbu_match_hint': _('Paid from Odoo (%s).', self.name),
            'state': 'matched',
        })

    @api.model
    def _sbu_update_from_transaction(self, company, tx):
        """Apply a Revolut transaction status (webhook / polling) to its payment order."""
        if not isinstance(tx, dict) or not tx.get('id'):
            return
        domain = [('company_id', '=', company.id), ('state', 'in', ('sent', 'paid', 'approved'))]
        if tx.get('request_id'):
            domain += ['|', ('revolut_transaction_id', '=', tx['id']), ('request_id', '=', tx['request_id'])]
        else:
            domain += [('revolut_transaction_id', '=', tx['id'])]
        for order in self.search(domain):
            if order.state == 'approved' and order.request_id == tx.get('request_id'):
                order.write({'state': 'sent', 'revolut_transaction_id': tx['id'], 'sent_on': fields.Datetime.now()})
            order._sbu_apply_revolut_state(tx.get('state'), tx.get('completed_at'), tx.get('reason_code'))

    # ── Cron ──────────────────────────────────────────────────────────────────
    @api.model
    def cron_sbu_revolut_payments(self):
        """Send approved payments that are due, then refresh the status of sent ones."""
        today = fields.Date.context_today(self)
        for order in self.sudo().search([('state', '=', 'approved'), ('execution_date', '<=', today)]):
            if not order._sbu_send():
                _logger.warning('Revolut payment %s not sent: %s', order.name, order.error_message)
        for order in self.sudo().search([('state', '=', 'sent')]):
            try:
                tx = order.company_id._sbu_revolut_client().transaction(order.revolut_transaction_id)
                with self.env.cr.savepoint():
                    order._sbu_apply_revolut_state(tx.get('state'), tx.get('completed_at'), tx.get('reason_code'))
            except (UserError, RevolutHttpError) as err:
                _logger.warning('Revolut payment %s status not refreshed: %s', order.name, err)
