# -*- coding: utf-8 -*-
"""Bank movements (Qonto, Revolut…) as Accounting bank statement lines, reconciled with their payments.

Odoo Community has no reconciliation screen, but its payments always get an "outstanding receipts /
payments" journal item. A statement line is reconciled by moving its suspense item to that outstanding
account and reconciling the two items — what the Enterprise reconciliation widget does.
"""
import logging
from collections import defaultdict
from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    sbu_opening_balance = fields.Boolean(
        string='SBU opening balance', readonly=True, copy=False,
        help='Balance of the bank account before the "bank statements from" date, computed from the '
             'imported movements. Its counterpart stays on the suspense account for the accountant.',
    )


class ResCompany(models.Model):
    _inherit = 'res.company'

    sbu_bank_statement_start_date = fields.Date(
        string='Bank statements from',
        help='Bank movements (Qonto, Revolut…) from this date are created as bank statement lines in '
             'Accounting; earlier movements become one opening balance line. Empty = not synchronised.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_bank_statement_start_date = fields.Date(
        related='company_id.sbu_bank_statement_start_date', readonly=False,
    )

    def _sbu_setup_checks(self):
        checks = super()._sbu_setup_checks()
        start = self.company_id.sbu_bank_statement_start_date
        checks.append({
            'label': _('Bank statements in Accounting'),
            'status': 'ok' if start else 'missing',
            'detail': _('From %s', fields.Date.to_string(start)) if start
            else _('Set "Bank statements from" (usually the go-live date).'),
            'url': False,
        })
        return checks


class SbuBankStatementSyncMixin(models.AbstractModel):
    _name = 'sbu.bank.statement.sync.mixin'
    _description = 'SBU bank movement synchronised to Accounting'

    statement_line_id = fields.Many2one(
        'account.bank.statement.line', string='Bank statement line', copy=False, readonly=True,
        index='btree_not_null', ondelete='set null',
    )
    statement_status = fields.Selection(
        [('none', 'Not in Accounting'), ('to_reconcile', 'To reconcile'), ('reconciled', 'Reconciled')],
        string='Accounting', compute='_compute_statement_status',
    )

    @api.depends('statement_line_id.is_reconciled')
    def _compute_statement_status(self):
        for rec in self:
            if not rec.statement_line_id:
                rec.statement_status = 'none'
            else:
                rec.statement_status = 'reconciled' if rec.statement_line_id.is_reconciled else 'to_reconcile'

    # ── To implement in the movement model ─────────────────────────────────────
    def _sbu_stmt_journal(self):
        """Bank journal of the movement (empty recordset if none configured)."""
        raise NotImplementedError

    def _sbu_stmt_is_final(self):
        """True when the bank has settled the movement (completed)."""
        raise NotImplementedError

    def _sbu_stmt_date(self):
        raise NotImplementedError

    def _sbu_stmt_amount(self):
        """Signed amount in the journal currency (money in > 0)."""
        raise NotImplementedError

    def _sbu_stmt_label(self):
        raise NotImplementedError

    def _sbu_stmt_payment(self):
        """Odoo payment registered for this movement, if any."""
        raise NotImplementedError

    # ── Synchronisation ───────────────────────────────────────────────────────
    def _sbu_stmt_line_vals(self, journal):
        self.ensure_one()
        partner = self['partner_id'] if 'partner_id' in self._fields else self.env['res.partner']
        return {
            'journal_id': journal.id,
            'date': self._sbu_stmt_date(),
            'amount': self._sbu_stmt_amount(),
            'payment_ref': self._sbu_stmt_label() or '/',
            'partner_id': partner.id or False,
        }

    def _sbu_sync_statement_lines(self):
        """Create the missing statement lines (and opening balances), then reconcile. Returns (created, reconciled)."""
        StatementLine = self.env['account.bank.statement.line'].sudo()
        to_create = defaultdict(lambda: self.browse())
        for rec in self.filtered(lambda r: not r.statement_line_id):
            start = rec.company_id.sbu_bank_statement_start_date
            date = rec._sbu_stmt_date()
            if not start or not date or date < start or not rec._sbu_stmt_is_final():
                continue
            journal = rec._sbu_stmt_journal()
            if journal:
                to_create[journal] |= rec
        created = 0
        for journal, recs in to_create.items():
            self._sbu_ensure_opening_balance(journal)
            lines = StatementLine.create([rec._sbu_stmt_line_vals(journal) for rec in recs])
            for rec, line in zip(recs, lines):
                rec.statement_line_id = line
            created += len(lines)
        reconciled = sum(
            1 for rec in self.filtered(lambda r: r.statement_line_id and not r.statement_line_id.is_reconciled)
            if rec._sbu_reconcile_statement_line()
        )
        return created, reconciled

    @api.model
    def _sbu_ensure_opening_balance(self, journal):
        """One opening line per journal: sum of the settled movements before the start date."""
        company = journal.company_id
        start = company.sbu_bank_statement_start_date
        StatementLine = self.env['account.bank.statement.line'].sudo()
        if not start or StatementLine.search_count([('journal_id', '=', journal.id), ('sbu_opening_balance', '=', True)]):
            return StatementLine
        earlier = self.sudo().search([('company_id', '=', company.id)]).filtered(
            lambda r: (r._sbu_stmt_date() or start) < start and r._sbu_stmt_is_final() and r._sbu_stmt_journal() == journal
        )
        amount = sum(r._sbu_stmt_amount() for r in earlier)
        if float_is_zero(amount, precision_rounding=journal.currency_id.rounding or company.currency_id.rounding):
            return StatementLine
        return StatementLine.create({
            'journal_id': journal.id,
            'date': start - timedelta(days=1),
            'amount': amount,
            'payment_ref': _('Opening balance (%s movements before %s)', len(earlier), fields.Date.to_string(start)),
            'sbu_opening_balance': True,
        })

    def _sbu_reconcile_statement_line(self):
        """Reconcile the statement line with the payment's outstanding item when the amounts match."""
        self.ensure_one()
        st_line = self.statement_line_id.sudo()
        payment = self._sbu_stmt_payment().sudo()
        if not st_line or st_line.is_reconciled or not payment or payment.move_id.state != 'posted':
            return False
        outstanding = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == payment.outstanding_account_id and not l.reconciled
        )
        _liquidity, suspense, _other = st_line._seek_for_lines()
        if len(suspense) != 1 or len(outstanding) != 1 or not outstanding.account_id.reconcile:
            return False
        rounding = st_line.company_id.currency_id.rounding
        if float_compare(suspense.balance, -outstanding.balance, precision_rounding=rounding):
            _logger.info('Statement line %s not reconciled: amount differs from payment %s', st_line.id, payment.name)
            return False
        st_line.move_id.with_context(skip_readonly_check=True).write({'line_ids': [
            Command.update(suspense.id, {
                'account_id': outstanding.account_id.id,
                'partner_id': payment.partner_id.id or suspense.partner_id.id,
            }),
        ]})
        (suspense | outstanding).reconcile()
        return st_line.is_reconciled

    def action_sbu_sync_statement_lines(self):
        records = self or self.search([('company_id', '=', self.env.company.id)])
        created, reconciled = records._sbu_sync_statement_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bank statements'),
                'message': _('%(created)s statement line(s) created, %(reconciled)s reconciled.',
                             created=created, reconciled=reconciled),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_sbu_open_statement_line(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.statement_line_id.move_id.id,
            'view_mode': 'form',
        }
