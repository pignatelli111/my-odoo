# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from odoo.addons.sbu_qonto.services.qonto_client import QontoHttpError, qonto_list_transactions

_logger = logging.getLogger(__name__)

_INVOICE_REF_RE = re.compile(
    r'\b([A-Z]{2,12}/\d{4}/\d+)\b',
    re.IGNORECASE,
)


class SbuQontoTransaction(models.Model):
    _name = 'sbu.qonto.transaction'
    _description = 'SBU Qonto bank movement (reference copy)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'settled_at desc, id desc'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    qonto_remote_id = fields.Char(string='Qonto id', required=True, index=True)
    source = fields.Selection(
        [('api', 'API import'), ('webhook', 'Webhook')],
        string='Source',
        default='api',
        required=True,
    )
    side = fields.Char(string='Side')
    operation_type = fields.Char(string='Operation type')
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        help='Absolute amount as reported by Qonto.',
    )
    amount_signed = fields.Monetary(
        string='Signed amount',
        currency_field='currency_id',
        help='Credit (in) positive, debit (out) negative for matching heuristics.',
    )
    currency_id = fields.Many2one('res.currency', required=True)
    label = fields.Char(string='Label')
    reference = fields.Char(string='Reference')
    note = fields.Char(string='Note')
    status = fields.Char(string='Qonto status')
    settled_at = fields.Datetime(string='Settled at')
    emitted_at = fields.Datetime(string='Emitted at')
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
        [
            ('none', 'No suggestion'),
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
        ],
        string='Match confidence',
        default='none',
        tracking=True,
        help='Heuristic confidence for the suggested link (does not post accounting entries).',
    )
    sbu_match_hint = fields.Char(
        string='Match hint',
        help='Why this payment or invoice was suggested.',
    )
    suggested_payment_id = fields.Many2one(
        'account.payment',
        string='Suggested payment',
        copy=False,
    )
    suggested_invoice_id = fields.Many2one(
        'account.move',
        string='Suggested invoice',
        copy=False,
        domain="[('move_type', '=', 'out_invoice')]",
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

    _sbu_qonto_remote_company_uniq = models.Constraint(
        'unique(company_id, qonto_remote_id)',
        'This Qonto movement is already imported for this company.',
    )

    @api.model
    def _parse_qonto_amount(self, tx):
        if tx.get('amount_cents') is not None:
            try:
                return int(tx['amount_cents']) / 100.0
            except (TypeError, ValueError):
                pass
        a = tx.get('amount')
        if isinstance(a, (int, float)):
            return float(a)
        if isinstance(a, str):
            try:
                return float(a.replace(',', '.').replace(' ', ''))
            except ValueError:
                return 0.0
        return 0.0

    @api.model
    def _vals_from_qonto_dict(self, company, tx, source):
        remote_id = str(tx.get('id') or tx.get('transaction_id') or '').strip()
        if not remote_id:
            return None
        amount = self._parse_qonto_amount(tx)
        side = (tx.get('side') or '').lower()
        if side == 'debit':
            amount_signed = -abs(amount)
        else:
            amount_signed = abs(amount)
        cur_code = tx.get('currency') or company.currency_id.name
        currency = self.env['res.currency'].search([('name', '=', cur_code)], limit=1) or company.currency_id

        def _parse_dt(val):
            if not val:
                return False
            try:
                dt = fields.Datetime.to_datetime(val)
                return fields.Datetime.to_string(dt)
            except (ValueError, TypeError, OverflowError):
                return False

        return {
            'company_id': company.id,
            'qonto_remote_id': remote_id,
            'source': source,
            'side': tx.get('side'),
            'operation_type': tx.get('operation_type'),
            'amount': abs(amount),
            'amount_signed': amount_signed,
            'currency_id': currency.id,
            'label': tx.get('label') or tx.get('clean_counterparty_name'),
            'reference': tx.get('reference'),
            'note': tx.get('note'),
            'status': tx.get('status'),
            'settled_at': _parse_dt(tx.get('settled_at')),
            'emitted_at': _parse_dt(tx.get('emitted_at')),
            'raw_json': json.dumps(tx),
        }

    @api.model
    def qonto_upsert_from_dict(self, company, tx, source):
        vals = self._vals_from_qonto_dict(company, tx, source)
        if not vals:
            return self.env['sbu.qonto.transaction']
        existing = self.search(
            [('company_id', '=', company.id), ('qonto_remote_id', '=', vals['qonto_remote_id'])],
            limit=1,
        )
        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)

    @api.model
    def qonto_process_webhook_payload(self, company, raw: str):
        """Parse Qonto webhook JSON (envelope with data, or raw transaction dict)."""
        if not raw:
            return 0
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            _logger.warning('Qonto webhook invalid JSON')
            return 0
        count = 0
        if isinstance(body, dict):
            if isinstance(body.get('data'), dict):
                self.qonto_upsert_from_dict(company, body['data'], 'webhook')
                count = 1
            elif isinstance(body.get('data'), list):
                for tx in body['data']:
                    if isinstance(tx, dict):
                        self.qonto_upsert_from_dict(company, tx, 'webhook')
                        count += 1
            elif isinstance(body.get('transactions'), list):
                for tx in body['transactions']:
                    self.qonto_upsert_from_dict(company, tx, 'webhook')
                    count += 1
            elif body.get('id') or body.get('transaction_id'):
                self.qonto_upsert_from_dict(company, body, 'webhook')
                count = 1
        elif isinstance(body, list):
            for item in body:
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get('data'), dict):
                    self.qonto_upsert_from_dict(company, item['data'], 'webhook')
                    count += 1
                elif item.get('id') or item.get('transaction_id'):
                    self.qonto_upsert_from_dict(company, item, 'webhook')
                    count += 1
        return count

    @api.model
    def import_transactions_for_company(self, company, max_pages=3):
        """Pull pages from Qonto list transactions API."""
        if not (company.sbu_qonto_login and company.sbu_qonto_secret_key and company.sbu_qonto_iban):
            raise UserError(_('Configure Qonto login, secret key and IBAN on the company.'))
        total = 0
        page = 1
        while page <= max_pages:
            txs, meta = qonto_list_transactions(
                company.sbu_qonto_login,
                company.sbu_qonto_secret_key,
                company.sbu_qonto_iban.replace(' ', ''),
                company.sbu_qonto_use_sandbox,
                page=page,
                per_page=100,
            )
            for tx in txs:
                self.qonto_upsert_from_dict(company, tx, 'api')
                total += 1
            next_page = meta.get('next_page')
            if not next_page:
                break
            try:
                page = int(next_page)
            except (TypeError, ValueError):
                break
        return total

    @api.model
    def cron_qonto_import(self):
        companies = self.env['res.company'].sudo().search([('sbu_qonto_import_enabled', '=', True)])
        Transaction = self.sudo()
        for company in companies:
            try:
                Transaction.import_transactions_for_company(company, max_pages=2)
                if company.sbu_qonto_suggest_after_import:
                    pending = Transaction.search([
                        ('company_id', '=', company.id),
                        ('state', '=', 'imported'),
                    ])
                    pending.action_suggest_match()
            except (UserError, QontoHttpError) as e:
                _logger.warning('Qonto cron skip company %s: %s', company.id, e)

    @api.model
    def action_import_now(self):
        company = self.env.company
        n = self.import_transactions_for_company(company, max_pages=3)
        if company.sbu_qonto_suggest_after_import:
            self.search([
                ('company_id', '=', company.id),
                ('state', '=', 'imported'),
            ]).action_suggest_match()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Qonto'),
                'message': _('Imported or updated %(n)s movements.', n=n),
                'type': 'success',
                'sticky': False,
            },
        }

  # --- Matching heuristics (suggest / link aid — no bank reconciliation) ---

    def _sbu_settled_date(self):
        self.ensure_one()
        if self.settled_at:
            return fields.Date.to_date(self.settled_at)
        return fields.Date.context_today(self)

    def _sbu_search_texts(self):
        self.ensure_one()
        parts = [self.reference, self.label, self.note]
        return [p.strip() for p in parts if p and p.strip()]

    @api.model
    def _sbu_normalize_ref(self, text):
        return (text or '').strip().upper()

    @api.model
    def _sbu_extract_invoice_names(self, texts):
        names = []
        for text in texts:
            names.extend(_INVOICE_REF_RE.findall(text))
        seen = set()
        ordered = []
        for name in names:
            key = name.upper()
            if key not in seen:
                seen.add(key)
                ordered.append(name)
        return ordered

    @api.model
    def _sbu_linked_payment_ids(self, company):
        return set(self.search([
            ('company_id', '=', company.id),
            ('match_payment_id', '!=', False),
            ('state', '=', 'matched'),
        ]).mapped('match_payment_id').ids)

    def _sbu_find_payment_match(self):
        """Return (payment, confidence, hint) or (empty, 'none', '')."""
        self.ensure_one()
        Payment = self.env['account.payment']
        rounding = self.currency_id.rounding
        amt = abs(self.amount_signed)
        if float_compare(amt, 0, precision_rounding=rounding) <= 0:
            return Payment, 'none', ''
        if (self.side or '').lower() not in ('credit', ''):
            return Payment, 'none', ''

        linked_ids = self._sbu_linked_payment_ids(self.company_id)
        texts = self._sbu_search_texts()
        settled = self._sbu_settled_date()
        date_from = settled - timedelta(days=21)
        date_to = settled + timedelta(days=7)

        base_domain = [
            ('company_id', '=', self.company_id.id),
            ('partner_type', '=', 'customer'),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('currency_id', '=', self.currency_id.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]

        for text in texts:
            norm = self._sbu_normalize_ref(text)
            if not norm:
                continue
            for field in ('payment_reference', 'memo', 'ref'):
                if field not in Payment._fields:
                    continue
                pays = Payment.search(base_domain + [(field, '=', text)], limit=5)
                pays = pays.filtered(lambda p: p.id not in linked_ids)
                for pay in pays:
                    if float_is_zero(pay.amount - amt, precision_rounding=rounding):
                        return pay, 'high', _('Exact %s match: %s') % (field, text)

        amount_candidates = Payment.search(
            base_domain + [('amount', '=', amt)],
            order='date desc',
            limit=50,
        ).filtered(lambda p: p.id not in linked_ids)

        if len(amount_candidates) == 1:
            pay = amount_candidates[0]
            return pay, 'high', _('Single inbound payment with same amount and date window')

        ref_hits = []
        for text in texts:
            for field in ('payment_reference', 'memo', 'ref'):
                if field not in Payment._fields:
                    continue
                ref_hits.extend(
                    amount_candidates.filtered(
                        lambda p, f=field, t=text: (getattr(p, f) or '').strip() == text
                    )
                )
        ref_hits = list({p.id: p for p in ref_hits}.values())
        if len(ref_hits) == 1:
            return ref_hits[0], 'medium', _('Amount + reference match')

        if len(amount_candidates) == 1:
            return amount_candidates[0], 'medium', _('Amount match in date window (verify manually)')

        if len(amount_candidates) > 1:
            return Payment, 'low', _('Several payments with same amount — pick manually')

        return Payment, 'none', ''

    def _sbu_find_invoice_match(self):
        """Return (invoice, confidence, hint) or (empty, 'none', '')."""
        self.ensure_one()
        Move = self.env['account.move']
        rounding = self.currency_id.rounding
        amt = abs(self.amount_signed)
        if float_compare(amt, 0, precision_rounding=rounding) <= 0:
            return Move, 'none', ''

        texts = self._sbu_search_texts()
        base_domain = [
            ('company_id', '=', self.company_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('currency_id', '=', self.currency_id.id),
        ]

        for inv_name in self._sbu_extract_invoice_names(texts):
            invs = Move.search(base_domain + [('name', '=', inv_name)], limit=2)
            if len(invs) == 1:
                inv = invs[0]
                residual = inv.amount_residual
                if float_is_zero(residual - amt, precision_rounding=rounding) or float_is_zero(
                    inv.amount_total - amt, precision_rounding=rounding
                ):
                    return inv, 'high', _('Invoice number %s with matching amount') % inv_name
                return inv, 'medium', _('Invoice number %s (check residual)') % inv_name

        for text in texts:
            invs = Move.search(
                base_domain + [('payment_reference', '=', text)],
                limit=2,
            )
            if len(invs) == 1:
                inv = invs[0]
                if float_is_zero(inv.amount_residual - amt, precision_rounding=rounding):
                    return inv, 'high', _('Payment reference %s with matching residual') % text
                return inv, 'medium', _('Payment reference %s') % text

        for text in texts:
            if len(text) < 4:
                continue
            invs = Move.search(
                base_domain + [
                    '|',
                    ('name', 'ilike', text),
                    ('payment_reference', 'ilike', text),
                ],
                limit=5,
            )
            if len(invs) == 1:
                inv = invs[0]
                if float_is_zero(inv.amount_residual - amt, precision_rounding=rounding):
                    return inv, 'high', _('Unique invoice match on text %s') % text
                return inv, 'medium', _('Unique invoice on text %s (check amount)') % text

        return Move, 'none', ''

    def action_suggest_match(self):
        """Compute suggestions only — does not set Matched state or post entries."""
        for rec in self.filtered(lambda t: t.state == 'imported'):
            pay, pay_conf, pay_hint = rec._sbu_find_payment_match()
            inv, inv_conf, inv_hint = rec._sbu_find_invoice_match()

            confidence_order = {'none': 0, 'low': 1, 'medium': 2, 'high': 3}
            best_conf = 'none'
            vals = {
                'suggested_payment_id': False,
                'suggested_invoice_id': False,
            }
            hint = ''

            if confidence_order.get(pay_conf, 0) >= confidence_order.get(inv_conf, 0) and pay_conf != 'none':
                vals['suggested_payment_id'] = pay.id
                best_conf = pay_conf
                hint = pay_hint
            elif inv_conf != 'none':
                vals['suggested_invoice_id'] = inv.id
                best_conf = inv_conf
                hint = inv_hint

            vals['sbu_match_confidence'] = best_conf
            vals['sbu_match_hint'] = hint or False
            rec.write(vals)
        return True

    def action_apply_suggestion(self):
        """User confirms a stored suggestion (medium/high)."""
        for rec in self.filtered(lambda t: t.state == 'imported'):
            vals = {}
            if rec.suggested_payment_id and not rec.suggested_invoice_id:
                vals['match_payment_id'] = rec.suggested_payment_id.id
                vals['state'] = 'matched'
            elif rec.suggested_invoice_id and not rec.suggested_payment_id:
                vals['match_invoice_id'] = rec.suggested_invoice_id.id
                vals['state'] = 'matched'
            elif rec.suggested_payment_id:
                vals['match_payment_id'] = rec.suggested_payment_id.id
                vals['state'] = 'matched'
            if vals:
                rec.write(vals)
        return True

    def action_match_odoo(self):
        """Link only when confidence is high; otherwise store a suggestion for review."""
        matched = 0
        suggested = 0
        for rec in self.filtered(lambda t: t.state == 'imported'):
            rec.action_suggest_match()
            if rec.sbu_match_confidence == 'high':
                vals = {}
                if rec.suggested_payment_id:
                    vals['match_payment_id'] = rec.suggested_payment_id.id
                    vals['state'] = 'matched'
                elif rec.suggested_invoice_id:
                    vals['match_invoice_id'] = rec.suggested_invoice_id.id
                    vals['state'] = 'matched'
                if vals:
                    rec.write(vals)
                    matched += 1
            elif rec.sbu_match_confidence in ('medium', 'low'):
                suggested += 1

        if not self.env.context.get('from_cron'):
            message = _('Linked %(m)s movement(s) with high confidence.', m=matched)
            if suggested:
                message += ' ' + _(
                    '%(s)s need review — use Apply suggestion or open the form.',
                    s=suggested,
                )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Qonto match'),
                    'message': message,
                    'type': 'success' if matched else 'warning',
                    'sticky': bool(suggested),
                },
            }
        return True

    def action_ignore(self):
        self.filtered(lambda t: t.state == 'imported').write({
            'state': 'ignored',
            'sbu_match_confidence': 'none',
            'sbu_match_hint': False,
            'suggested_payment_id': False,
            'suggested_invoice_id': False,
        })
