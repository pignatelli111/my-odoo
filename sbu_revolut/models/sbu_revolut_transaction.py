# -*- coding: utf-8 -*-
import base64
import csv
import io
import json
import logging
import re
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from odoo.addons.sbu_revolut.services.revolut_client import RevolutHttpError

_logger = logging.getLogger(__name__)

_PAGE_SIZE = 1000
_MAX_PAGES = 200
_MIN_REF_LEN = 4
_CSV_FORMULA_CHARS = ('=', '+', '-', '@', '\t', '\r')


def _norm(text):
    return re.sub(r'[^0-9A-Z]', '', (text or '').upper())


class SbuRevolutTransaction(models.Model):
    _name = 'sbu.revolut.transaction'
    _description = 'SBU Revolut bank movement (reference copy)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'settled_at desc, id desc'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    account_id = fields.Many2one('sbu.revolut.account', string='Revolut account', index=True)
    revolut_remote_id = fields.Char(string='Revolut id', required=True, index=True)
    revolut_leg_id = fields.Char(string='Revolut leg id', index=True)
    request_id = fields.Char(string='Revolut request id', index=True)
    source = fields.Selection(
        [('api', 'API import'), ('webhook', 'Webhook')],
        string='Source',
        default='api',
        required=True,
    )
    revolut_type = fields.Char(string='Revolut type')
    revolut_state = fields.Char(string='Revolut state')
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        help='Absolute amount as reported by Revolut.',
    )
    amount_signed = fields.Monetary(
        string='Signed amount',
        currency_field='currency_id',
        help='Positive for money in, negative for money out (Revolut amount sign).',
    )
    fee = fields.Monetary(string='Revolut fee', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', required=True)
    label = fields.Char(string='Label')
    reference = fields.Char(string='Reference')
    note = fields.Char(string='Note')
    settled_at = fields.Datetime(string='Settled at')
    created_at_revolut = fields.Datetime(string='Created at (Revolut)')
    transfer_date = fields.Date(string='Transfer date', index=True)
    counterparty_name = fields.Char(string='Counterparty name')
    counterparty_revolut_id = fields.Char(string='Revolut counterparty id', index=True)
    partner_id = fields.Many2one('res.partner', string='Counterparty', index=True)
    raw_json = fields.Text(string='Raw payload')
    state = fields.Selection(
        [
            ('imported', 'Imported'),
            ('matched', 'Matched in Odoo'),
            ('ignored', 'Ignored'),
        ],
        string='Match state',
        default='imported',
        tracking=True,
    )
    sbu_match_confidence = fields.Selection(
        [('none', 'No suggestion'), ('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        string='Match confidence',
        default='none',
        tracking=True,
    )
    sbu_match_hint = fields.Char(string='Match hint')
    suggested_invoice_id = fields.Many2one(
        'account.move', string='Suggested customer invoice', copy=False,
        domain="[('move_type', '=', 'out_invoice')]",
    )
    suggested_vendor_bill_id = fields.Many2one(
        'account.move', string='Suggested vendor bill', copy=False,
        domain="[('move_type', '=', 'in_invoice')]",
    )
    match_payment_id = fields.Many2one(
        'account.payment',
        string='Matched payment',
        copy=False,
        tracking=True,
    )
    match_invoice_id = fields.Many2one(
        'account.move',
        string='Matched invoice',
        copy=False,
        domain="[('move_type', '=', 'out_invoice')]",
        tracking=True,
    )
    match_vendor_bill_id = fields.Many2one(
        'account.move',
        string='Matched vendor bill',
        copy=False,
        domain="[('move_type', '=', 'in_invoice')]",
        tracking=True,
    )
    revolut_payment_id = fields.Many2one(
        'sbu.revolut.payment', string='Revolut payment order', copy=False, index=True,
    )

    _sbu_revolut_remote_company_uniq = models.Constraint(
        'unique(company_id, revolut_remote_id, revolut_leg_id)',
        'This Revolut movement is already imported for this company.',
    )

    # ── Parsing ───────────────────────────────────────────────────────────────
    @api.model
    def _parse_dt(self, val):
        if not val:
            return False
        try:
            return fields.Datetime.to_string(
                fields.Datetime.to_datetime(str(val).replace('T', ' ').replace('Z', '')[:19])
            )
        except (ValueError, TypeError, OverflowError):
            return False

    @api.model
    def _label_from_tx(self, tx, leg):
        merchant = tx.get('merchant')
        if isinstance(merchant, dict) and merchant.get('name'):
            return merchant['name']
        return leg.get('description') or tx.get('reference') or tx.get('type') or ''

    @api.model
    def _vals_from_leg(self, company, tx, leg, account, source):
        Currency = self.env['res.currency'].with_context(active_test=False)
        cur_code = leg.get('currency') or tx.get('currency')
        currency = (
            Currency.search([('name', '=', cur_code)], limit=1) if cur_code else Currency
        ) or (account.currency_id if account else company.currency_id)
        amount_signed = float(leg.get('amount') or 0.0)
        counterparty = leg.get('counterparty') if isinstance(leg.get('counterparty'), dict) else {}
        cp_id = counterparty.get('id')
        partner = self.env['res.partner']
        if cp_id:
            partner = partner.search([('sbu_revolut_counterparty_id', '=', cp_id)], limit=1)
        settled = self._parse_dt(tx.get('completed_at'))
        created = self._parse_dt(tx.get('created_at'))
        when = settled or created or self._parse_dt(tx.get('updated_at'))
        return {
            'company_id': company.id,
            'account_id': account.id if account else False,
            'revolut_remote_id': str(tx['id']),
            'revolut_leg_id': leg.get('leg_id') or False,
            'request_id': tx.get('request_id') or False,
            'source': source,
            'revolut_type': tx.get('type'),
            'revolut_state': tx.get('state'),
            'amount': abs(amount_signed),
            'amount_signed': amount_signed,
            'fee': float(leg.get('fee') or 0.0),
            'currency_id': currency.id,
            'label': self._label_from_tx(tx, leg),
            'reference': tx.get('reference') or False,
            'note': leg.get('description') or False,
            'settled_at': settled,
            'created_at_revolut': created,
            'transfer_date': fields.Date.to_date(when) if when else False,
            'counterparty_name': (tx.get('merchant') or {}).get('name') if isinstance(tx.get('merchant'), dict) else False,
            'counterparty_revolut_id': cp_id or False,
            'partner_id': partner.id or False,
            'raw_json': json.dumps(tx),
        }

    @api.model
    def revolut_upsert_from_dict(self, company, tx, source, account=None):
        """Create or update one record per leg of ``tx`` that belongs to an account of ``company``."""
        result = self.browse()
        if not isinstance(tx, dict) or not tx.get('id'):
            return result
        legs = tx.get('legs') if isinstance(tx.get('legs'), list) else []
        if not legs and tx.get('amount') is not None:
            legs = [{'amount': tx.get('amount'), 'currency': tx.get('currency'), 'account_id': account and account.revolut_account_id}]
        accounts = {
            acc.revolut_account_id: acc
            for acc in self.env['sbu.revolut.account'].with_context(active_test=False).search(
                [('company_id', '=', company.id)]
            )
        }
        Model = self.sudo().with_company(company)
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            leg_account = accounts.get(leg.get('account_id')) or account
            if accounts and leg.get('account_id') and leg.get('account_id') not in accounts:
                continue
            if account and leg_account != account:
                continue
            vals = self._vals_from_leg(company, tx, leg, leg_account, source)
            domain = [('company_id', '=', company.id), ('revolut_remote_id', '=', vals['revolut_remote_id'])]
            existing = Model.search(domain + [('revolut_leg_id', '=', vals['revolut_leg_id'])], limit=1)
            if not existing:
                existing = Model.search(domain + [('revolut_leg_id', '=', False)], limit=1)
            if existing:
                if existing.source == 'api':
                    vals.pop('source')
                if existing.partner_id and not vals.get('partner_id'):
                    vals.pop('partner_id')
                existing.write(vals)
                result |= existing
            else:
                result |= Model.create(vals)
        return result

    # ── Import ────────────────────────────────────────────────────────────────
    @api.model
    def import_transactions_for_company(self, company, full_history=False):
        """Pull movements for every enabled Revolut account (pages backwards by created_at)."""
        Account = self.env['sbu.revolut.account']
        accounts = Account.search([('company_id', '=', company.id), ('import_enabled', '=', True)])
        if not accounts:
            Account._sbu_sync_company_accounts(company)
            accounts = Account.search([('company_id', '=', company.id), ('import_enabled', '=', True)])
        client = company._sbu_revolut_client()
        date_from = None
        if not full_history:
            date_from = fields.Datetime.now() - timedelta(days=int(company.sbu_revolut_import_lookback_days or 30))
        touched = self.browse()
        for account in accounts:
            date_to = None
            for _page in range(_MAX_PAGES):
                txs = client.transactions(
                    account_id=account.revolut_account_id,
                    date_from=date_from,
                    date_to=date_to,
                    count=_PAGE_SIZE,
                )
                for tx in txs:
                    touched |= self.revolut_upsert_from_dict(company, tx, 'api', account=account)
                if len(txs) < _PAGE_SIZE:
                    break
                oldest = min((t.get('created_at') or '' for t in txs), default='')
                new_to = fields.Datetime.to_datetime(self._parse_dt(oldest)) if oldest else None
                if not new_to or (date_to and new_to >= date_to):
                    break
                date_to = new_to
        company.sudo().sbu_revolut_last_sync = fields.Datetime.now()
        touched._sbu_post_import_process()
        return len(touched)

    @api.model
    def cron_revolut_import(self):
        companies = self.env['res.company'].sudo().search([('sbu_revolut_import_enabled', '=', True)])
        for company in companies:
            try:
                self.sudo().import_transactions_for_company(company)
                company.sbu_revolut_account_ids._sbu_safe_refresh_balances()
            except (UserError, RevolutHttpError) as e:
                _logger.warning('Revolut cron skip company %s: %s', company.id, e)

    @api.model
    def action_import_now(self):
        n = self.import_transactions_for_company(self.env.company)
        return self.env.company._sbu_revolut_notify(_('Revolut'), _('Imported or updated %(n)s movement(s).', n=n))

    # ── Webhook ───────────────────────────────────────────────────────────────
    @api.model
    def revolut_process_webhook_event(self, company, event):
        """Handle a verified Revolut webhook event (TransactionCreated / TransactionStateChanged)."""
        if not isinstance(event, dict):
            return 0
        kind = event.get('event')
        data = event.get('data') if isinstance(event.get('data'), dict) else {}
        if not data.get('id'):
            return 0
        if kind == 'TransactionStateChanged' or not data.get('legs'):
            data = company._sbu_revolut_client().transaction(data['id'])
        records = self.revolut_upsert_from_dict(company, data, 'webhook')
        self.env['sbu.revolut.payment'].sudo()._sbu_update_from_transaction(company, data)
        records._sbu_post_import_process()
        return len(records)

    # ── Matching ──────────────────────────────────────────────────────────────
    def _sbu_post_import_process(self):
        todo = self.filtered(lambda t: t.state == 'imported')
        if not todo:
            return
        todo._sbu_link_payment_orders()
        todo = todo.filtered(lambda t: t.state == 'imported' and t.revolut_state == 'completed')
        todo.action_suggest_match()
        by_company = {}
        for rec in todo:
            by_company.setdefault(rec.company_id, self.browse())
            by_company[rec.company_id] |= rec
        for company, recs in by_company.items():
            high = recs.filtered(lambda t: t.sbu_match_confidence == 'high')
            if company.sbu_revolut_auto_register_inbound:
                inbound = high.filtered(lambda t: t.amount_signed > 0 and t.suggested_invoice_id)
                for rec in inbound:
                    try:
                        with self.env.cr.savepoint():
                            rec.action_register_payment()
                    except UserError as err:
                        rec.sbu_match_hint = _('Auto-registration skipped: %s', err)
            if company.sbu_revolut_auto_match_high:
                high.filtered(lambda t: t.state == 'imported').action_apply_suggestion()

    def _sbu_link_payment_orders(self):
        """Outgoing movements created by an Odoo payment order are matched exactly."""
        Payment = self.env['sbu.revolut.payment'].sudo()
        for rec in self.filtered(lambda t: t.amount_signed < 0):
            order = Payment.search([
                ('company_id', '=', rec.company_id.id),
                '|', ('revolut_transaction_id', '=', rec.revolut_remote_id),
                '&', ('request_id', '!=', False), ('request_id', '=', rec.request_id),
            ], limit=1)
            if not order:
                continue
            vals = {
                'revolut_payment_id': order.id,
                'match_vendor_bill_id': order.move_id.id,
                'sbu_match_confidence': 'high',
                'sbu_match_hint': _('Paid from Odoo (%s).', order.name),
            }
            if order.payment_id:
                vals.update(match_payment_id=order.payment_id.id, state='matched')
            rec.write(vals)

    def _sbu_search_text(self):
        self.ensure_one()
        return _norm(' '.join(filter(None, [self.reference, self.label, self.note])))

    def _sbu_open_moves_domain(self, move_type):
        self.ensure_one()
        return [
            ('company_id', '=', self.company_id.id),
            ('move_type', '=', move_type),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('currency_id', '=', self.currency_id.id),
        ]

    def _sbu_find_move(self, move_type):
        """Return (move, confidence, hint) for the best open invoice / bill."""
        self.ensure_one()
        Move = self.env['account.move']
        rounding = self.currency_id.rounding
        amount = self.amount
        moves = Move.search(self._sbu_open_moves_domain(move_type), order='invoice_date_due, id')

        def same_amount(move):
            return float_is_zero(move.amount_residual - amount, precision_rounding=rounding)

        text = self._sbu_search_text()
        if text:
            by_ref = moves.filtered(lambda m: any(
                len(key) >= _MIN_REF_LEN and key in text
                for key in (_norm(m.name), _norm(m.ref), _norm(m.payment_reference))
            ))
            if by_ref:
                exact = by_ref.filtered(same_amount)
                if len(exact) == 1:
                    return exact, 'high', _('Reference and amount match %s.', exact.name)
                best = (exact or by_ref)[:1]
                return best, 'medium', _('Reference matches %s (amount differs or several matches).', best.name)
        if self.partner_id:
            partner_moves = moves.filtered(
                lambda m: m.commercial_partner_id == self.partner_id.commercial_partner_id and same_amount(m)
            )
            if len(partner_moves) == 1:
                return partner_moves, 'high', _('Same counterparty and open amount (%s).', partner_moves.name)
            if partner_moves:
                return partner_moves[:1], 'medium', _(
                    'Same counterparty and amount; %(n)s open documents, oldest suggested.', n=len(partner_moves),
                )
        amount_moves = moves.filtered(same_amount)
        if len(amount_moves) == 1:
            return amount_moves, 'low', _('Only the amount matches (%s) — check before applying.', amount_moves.name)
        return Move, 'none', False

    def action_suggest_match(self):
        for rec in self.filtered(lambda t: t.state == 'imported'):
            inbound = rec.amount_signed > 0
            move, confidence, hint = rec._sbu_find_move('out_invoice' if inbound else 'in_invoice')
            rec.write({
                'suggested_invoice_id': move.id if inbound else False,
                'suggested_vendor_bill_id': move.id if not inbound else False,
                'sbu_match_confidence': confidence,
                'sbu_match_hint': hint or _('No open invoice or bill matches.'),
            })
        return True

    def action_apply_suggestion(self):
        """Link the suggested document (no accounting entry)."""
        for rec in self.filtered(lambda t: t.state == 'imported'):
            if rec.suggested_invoice_id:
                rec.match_invoice_id = rec.suggested_invoice_id
            elif rec.suggested_vendor_bill_id:
                rec.match_vendor_bill_id = rec.suggested_vendor_bill_id
        return True

    def _sbu_payment_journal(self):
        self.ensure_one()
        return self.account_id._sbu_journal() if self.account_id else self.company_id.sbu_revolut_journal_id

    def action_register_payment(self):
        """Post the Odoo payment for the linked / suggested invoice or bill and mark as matched."""
        PaymentRegister = self.env['account.payment.register']
        for rec in self.filtered(lambda t: t.state == 'imported'):
            inbound = rec.amount_signed > 0
            move = (
                (rec.match_invoice_id or rec.suggested_invoice_id)
                if inbound else (rec.match_vendor_bill_id or rec.suggested_vendor_bill_id)
            )
            if not move:
                raise UserError(_('Link a customer invoice or vendor bill before registering the payment.'))
            if move.state != 'posted':
                raise UserError(_('%s must be posted before registering the payment.', move.display_name))
            if float_compare(move.amount_residual, 0.0, precision_rounding=rec.currency_id.rounding) <= 0:
                raise UserError(_('%s has nothing left to pay.', move.display_name))
            wizard_vals = {
                'amount': min(rec.amount, move.amount_residual),
                'payment_date': rec.transfer_date or fields.Date.context_today(rec),
                'communication': rec.reference or rec.label or move.name,
            }
            journal = rec._sbu_payment_journal()
            if journal:
                wizard_vals['journal_id'] = journal.id
            wizard = PaymentRegister.with_context(
                active_model='account.move', active_ids=move.ids, active_id=move.id,
            ).create(wizard_vals)
            payment = wizard._create_payments()[:1]
            rec.write({
                'match_invoice_id': move.id if inbound else False,
                'match_vendor_bill_id': move.id if not inbound else False,
                'match_payment_id': payment.id,
                'state': 'matched',
            })
        if len(self) == 1 and self.match_payment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'res_id': self.match_payment_id.id,
                'view_mode': 'form',
            }
        return True

    def action_match_odoo(self):
        """Mark as matched when a payment or document is linked."""
        for rec in self.filtered(lambda t: t.state == 'imported'):
            if rec.match_payment_id or rec.match_invoice_id or rec.match_vendor_bill_id:
                rec.state = 'matched'
        return True

    def action_ignore(self):
        self.filtered(lambda t: t.state == 'imported').write({'state': 'ignored'})

    def action_reset_to_imported(self):
        self.filtered(lambda t: t.state == 'ignored').write({'state': 'imported'})

    def action_sync_counterparties(self):
        n = self.env['res.partner']._sbu_revolut_sync_counterparties(self.env.company)
        return self.env.company._sbu_revolut_notify(
            _('Revolut'), _('%(n)s contact(s) linked to Revolut counterparties.', n=n),
        )

    # ── CSV export ────────────────────────────────────────────────────────────
    @staticmethod
    def _csv_safe(value):
        text = '' if value in (None, False) else str(value)
        return "'" + text if text.startswith(_CSV_FORMULA_CHARS) else text

    def action_export_csv(self):
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=';')
        writer.writerow([
            'revolut_id', 'account', 'date', 'amount_signed', 'fee', 'currency', 'label',
            'reference', 'counterparty', 'revolut_type', 'revolut_state', 'match_state',
            'invoice', 'vendor_bill', 'payment',
        ])
        for rec in self:
            writer.writerow([self._csv_safe(v) for v in (
                rec.revolut_remote_id, rec.account_id.name, rec.transfer_date, rec.amount_signed, rec.fee,
                rec.currency_id.name, rec.label, rec.reference, rec.partner_id.name or rec.counterparty_name,
                rec.revolut_type, rec.revolut_state, rec.state, rec.match_invoice_id.name,
                rec.match_vendor_bill_id.name, rec.match_payment_id.name,
            )])
        att = self.env['ir.attachment'].create({
            'name': 'revolut_movements_export.csv',
            'datas': base64.b64encode(buf.getvalue().encode('utf-8-sig')),
            'mimetype': 'text/csv',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{att.id}?download=true',
            'target': 'new',
        }

    @api.model
    def action_export_csv_selection(self):
        ids = self.env.context.get('active_ids') or []
        if not ids:
            raise UserError(_('Select the Revolut movements to export.'))
        return self.browse(ids).action_export_csv()
