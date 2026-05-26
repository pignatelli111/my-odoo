# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from odoo.addons.sbu_qonto.models.sbu_qonto_helpers import sbu_normalize_iban, sbu_qonto_user_error
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
        string='Suggested customer invoice',
        copy=False,
        domain="[('move_type', '=', 'out_invoice')]",
    )
    suggested_vendor_bill_id = fields.Many2one(
        'account.move',
        string='Suggested vendor bill',
        copy=False,
        domain="[('move_type', '=', 'in_invoice')]",
    )
    counterparty_name = fields.Char(string='Counterparty name')
    counterparty_iban = fields.Char(string='Counterparty IBAN', index=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Counterparty',
        help='Matched from Qonto IBAN / beneficiaries sync.',
    )
    match_payment_id = fields.Many2one(
        'account.payment',
        string='Matched payment',
        copy=False,
        tracking=True,
    )
    match_invoice_id = fields.Many2one(
        'account.move',
        string='Matched customer invoice',
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
    match_document_type = fields.Selection(
        [
            ('none', 'None'),
            ('customer_invoice', 'Customer invoice'),
            ('vendor_bill', 'Vendor bill'),
            ('payment', 'Payment'),
        ],
        string='Matched document type',
        compute='_compute_match_document_type',
        store=True,
    )

    _sbu_qonto_remote_company_uniq = models.Constraint(
        'unique(company_id, qonto_remote_id)',
        'This Qonto movement is already imported for this company.',
    )

    @api.depends('match_invoice_id', 'match_vendor_bill_id', 'match_payment_id')
    def _compute_match_document_type(self):
        for rec in self:
            if rec.match_invoice_id:
                rec.match_document_type = 'customer_invoice'
            elif rec.match_vendor_bill_id:
                rec.match_document_type = 'vendor_bill'
            elif rec.match_payment_id:
                rec.match_document_type = 'payment'
            else:
                rec.match_document_type = 'none'

    def _sbu_is_inbound(self):
        self.ensure_one()
        return (self.amount_signed or 0.0) > 0

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

        cp_iban = sbu_normalize_iban(
            tx.get('counterparty_account_number')
            or tx.get('iban')
            or ''
        )
        cp_name = (
            tx.get('clean_counterparty_name')
            or tx.get('counterparty_name')
            or tx.get('label')
            or ''
        )
        Partner = self.env['res.partner']
        partner_id = False
        if cp_iban:
            partner = Partner.search([
                ('sbu_qonto_iban', '=', cp_iban),
                '|', ('company_id', '=', False), ('company_id', '=', company.id),
            ], limit=1)
            if not partner:
                partner = Partner.search([
                    ('bank_ids.acc_number', '=', cp_iban),
                    '|', ('company_id', '=', False), ('company_id', '=', company.id),
                ], limit=1)
            partner_id = partner.id if partner else False

        return {
            'company_id': company.id,
            'qonto_remote_id': remote_id,
            'source': source,
            'side': tx.get('side'),
            'operation_type': tx.get('operation_type'),
            'amount': abs(amount),
            'amount_signed': amount_signed,
            'currency_id': currency.id,
            'label': tx.get('label') or cp_name,
            'reference': tx.get('reference'),
            'note': tx.get('note'),
            'status': tx.get('status'),
            'settled_at': _parse_dt(tx.get('settled_at')),
            'emitted_at': _parse_dt(tx.get('emitted_at')),
            'counterparty_name': cp_name,
            'counterparty_iban': cp_iban or False,
            'partner_id': partner_id,
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
        login, secret, iban = company._sbu_qonto_api_credentials()
        if not login or not secret or not iban:
            raise UserError(_('Configure Qonto login, secret key and IBAN on the company.'))
        company._sbu_qonto_warn_login_shape(login)
        total = 0
        page = 1
        while page <= max_pages:
            txs, meta = qonto_list_transactions(
                login,
                secret,
                iban,
                company.sbu_qonto_use_sandbox,
                page=page,
                per_page=100,
                staging_token=company._sbu_qonto_staging_token(),
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
    def _sbu_post_import_process(self, company):
        """Suggest, auto-link and optionally register payments (Cosimo punto 10)."""
        Transaction = self.env['sbu.qonto.transaction'].sudo()
        if company.sbu_qonto_sync_partners_on_import:
            try:
                company._sbu_sync_qonto_partners()
            except (UserError, QontoHttpError) as e:
                _logger.warning('Qonto partner sync skip company %s: %s', company.id, e)
        pending = Transaction.search([
            ('company_id', '=', company.id),
            ('state', '=', 'imported'),
        ])
        if not pending:
            return
        if company.sbu_qonto_suggest_after_import:
            pending.action_suggest_match()
            pending.invalidate_recordset()

        if company.sbu_qonto_auto_register_inbound:
            inbound = pending.filtered(
                lambda t: t._sbu_is_inbound()
                and t.sbu_match_confidence == 'high'
                and t.suggested_invoice_id
            )
            for tx in inbound:
                try:
                    tx.action_register_invoice_payment()
                except UserError as e:
                    _logger.info('Qonto auto inbound skip %s: %s', tx.id, e)

        if company.sbu_qonto_auto_register_outbound:
            outbound = pending.filtered(
                lambda t: not t._sbu_is_inbound()
                and t.sbu_match_confidence == 'high'
                and t.suggested_vendor_bill_id
            )
            for tx in outbound:
                try:
                    tx.action_register_vendor_payment()
                except UserError as e:
                    _logger.info('Qonto auto outbound skip %s: %s', tx.id, e)

        if company.sbu_qonto_auto_match_high:
            pending = Transaction.search([
                ('company_id', '=', company.id),
                ('state', '=', 'imported'),
            ])
            if pending:
                pending.action_match_odoo()

    @api.model
    def cron_qonto_import(self):
        companies = self.env['res.company'].sudo().search([('sbu_qonto_import_enabled', '=', True)])
        Transaction = self.sudo()
        for company in companies:
            try:
                Transaction.import_transactions_for_company(company, max_pages=2)
                self._sbu_post_import_process(company)
            except (UserError, QontoHttpError) as e:
                _logger.warning('Qonto cron skip company %s: %s', company.id, e)

    @api.model
    def action_import_now(self):
        company = self.env.company
        try:
            n = self.import_transactions_for_company(company, max_pages=3)
        except QontoHttpError as err:
            raise sbu_qonto_user_error(err) from err
        self._sbu_post_import_process(company)
        notif_type = 'success' if n else 'warning'
        message = (
            _('Imported or updated %(n)s movements.', n=n)
            if n
            else _(
                'Qonto returned 0 movements for IBAN %(iban)s. '
                'Check IBAN, account activity, and sandbox vs production keys.'
            ) % {'iban': company.sbu_qonto_iban}
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Qonto'),
                'message': message,
                'type': notif_type,
                'sticky': bool(not n),
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

    def _sbu_find_outbound_payment_match(self):
        """Return (payment, confidence, hint) for vendor outbound payments."""
        self.ensure_one()
        Payment = self.env['account.payment']
        rounding = self.currency_id.rounding
        amt = abs(self.amount_signed)
        if float_compare(amt, 0, precision_rounding=rounding) <= 0:
            return Payment, 'none', ''
        if self._sbu_is_inbound():
            return Payment, 'none', ''

        linked_ids = self._sbu_linked_payment_ids(self.company_id)
        texts = self._sbu_search_texts()
        settled = self._sbu_settled_date()
        date_from = settled - timedelta(days=21)
        date_to = settled + timedelta(days=7)
        base_domain = [
            ('company_id', '=', self.company_id.id),
            ('partner_type', '=', 'supplier'),
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
            ('currency_id', '=', self.currency_id.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        if self.partner_id:
            base_domain.append(('partner_id', '=', self.partner_id.id))

        for text in texts:
            for field in ('payment_reference', 'memo', 'ref'):
                if field not in Payment._fields:
                    continue
                pays = Payment.search(base_domain + [(field, '=', text)], limit=5)
                pays = pays.filtered(lambda p: p.id not in linked_ids)
                for pay in pays:
                    if float_is_zero(pay.amount - amt, precision_rounding=rounding):
                        return pay, 'high', _('Exact outbound %s match: %s') % (field, text)

        amount_candidates = Payment.search(
            base_domain + [('amount', '=', amt)],
            order='date desc',
            limit=50,
        ).filtered(lambda p: p.id not in linked_ids)
        if len(amount_candidates) == 1:
            return amount_candidates[0], 'high', _('Single outbound payment with same amount')
        if len(amount_candidates) > 1:
            return Payment, 'low', _('Several outbound payments with same amount')
        return Payment, 'none', ''

    def _sbu_find_vendor_bill_match(self):
        """Return (vendor bill, confidence, hint) for outbound movements."""
        self.ensure_one()
        Move = self.env['account.move']
        rounding = self.currency_id.rounding
        amt = abs(self.amount_signed)
        if float_compare(amt, 0, precision_rounding=rounding) <= 0:
            return Move, 'none', ''
        if self._sbu_is_inbound():
            return Move, 'none', ''

        texts = self._sbu_search_texts()
        base_domain = [
            ('company_id', '=', self.company_id.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('currency_id', '=', self.currency_id.id),
        ]
        if self.partner_id:
            base_domain.append(('partner_id', '=', self.partner_id.id))

        for inv_name in self._sbu_extract_invoice_names(texts):
            invs = Move.search(base_domain + [('name', '=', inv_name)], limit=2)
            if len(invs) == 1:
                inv = invs[0]
                residual = inv.amount_residual
                if float_is_zero(residual - amt, precision_rounding=rounding) or float_is_zero(
                    inv.amount_total - amt, precision_rounding=rounding
                ):
                    return inv, 'high', _('Vendor bill %s with matching amount') % inv_name
                return inv, 'medium', _('Vendor bill %s (check residual)') % inv_name

        for text in texts:
            invs = Move.search(
                base_domain + [('payment_reference', '=', text)],
                limit=2,
            )
            if len(invs) == 1:
                inv = invs[0]
                if float_is_zero(inv.amount_residual - amt, precision_rounding=rounding):
                    return inv, 'high', _('Vendor payment reference %s') % text
                return inv, 'medium', _('Vendor bill for reference %s') % text

        residual_invs = Move.search(
            base_domain + [('amount_residual', '=', amt)],
            order='invoice_date desc',
            limit=5,
        )
        if len(residual_invs) == 1:
            return residual_invs[0], 'high', _('Unique vendor bill with matching residual')
        if len(residual_invs) > 1:
            return Move, 'low', _('Several vendor bills with same residual')

        return Move, 'none', ''

    def _sbu_find_payment_match(self):
        """Return (payment, confidence, hint) or (empty, 'none', '')."""
        self.ensure_one()
        Payment = self.env['account.payment']
        rounding = self.currency_id.rounding
        amt = abs(self.amount_signed)
        if float_compare(amt, 0, precision_rounding=rounding) <= 0:
            return Payment, 'none', ''
        if not self._sbu_is_inbound():
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
        if not self._sbu_is_inbound():
            return Move, 'none', ''
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
            confidence_order = {'none': 0, 'low': 1, 'medium': 2, 'high': 3}
            best_conf = 'none'
            vals = {
                'suggested_payment_id': False,
                'suggested_invoice_id': False,
                'suggested_vendor_bill_id': False,
            }
            hint = ''
            candidates = []

            if rec._sbu_is_inbound():
                pay, pay_conf, pay_hint = rec._sbu_find_payment_match()
                inv, inv_conf, inv_hint = rec._sbu_find_invoice_match()
                if pay_conf != 'none':
                    candidates.append(('payment', pay, pay_conf, pay_hint))
                if inv_conf != 'none':
                    candidates.append(('customer_invoice', inv, inv_conf, inv_hint))
            else:
                pay, pay_conf, pay_hint = rec._sbu_find_outbound_payment_match()
                bill, bill_conf, bill_hint = rec._sbu_find_vendor_bill_match()
                if pay_conf != 'none':
                    candidates.append(('payment', pay, pay_conf, pay_hint))
                if bill_conf != 'none':
                    candidates.append(('vendor_bill', bill, bill_conf, bill_hint))

            candidates.sort(key=lambda c: confidence_order.get(c[2], 0), reverse=True)
            if candidates:
                kind, doc, best_conf, hint = candidates[0]
                if kind == 'payment':
                    vals['suggested_payment_id'] = doc.id
                elif kind == 'customer_invoice':
                    vals['suggested_invoice_id'] = doc.id
                elif kind == 'vendor_bill':
                    vals['suggested_vendor_bill_id'] = doc.id

            vals['sbu_match_confidence'] = best_conf
            vals['sbu_match_hint'] = hint or False
            rec.write(vals)
        return True

    def action_apply_suggestion(self):
        """User confirms a stored suggestion (medium/high)."""
        for rec in self.filtered(lambda t: t.state == 'imported'):
            vals = {}
            if rec.suggested_payment_id:
                vals['match_payment_id'] = rec.suggested_payment_id.id
                vals['state'] = 'matched'
            elif rec.suggested_invoice_id:
                vals['match_invoice_id'] = rec.suggested_invoice_id.id
                vals['state'] = 'matched'
            elif rec.suggested_vendor_bill_id:
                vals['match_vendor_bill_id'] = rec.suggested_vendor_bill_id.id
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
                elif rec.suggested_vendor_bill_id:
                    vals['match_vendor_bill_id'] = rec.suggested_vendor_bill_id.id
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
            'suggested_vendor_bill_id': False,
        })

    def _sbu_payment_register_date(self):
        self.ensure_one()
        if self.settled_at:
            return fields.Date.to_date(self.settled_at)
        return fields.Date.context_today(self)

    def action_register_invoice_payment(self):
        """Create and post a customer payment for a matched/suggested invoice (Cosimo punto 10)."""
        PaymentRegister = self.env['account.payment.register']
        for rec in self.filtered(lambda t: t.state == 'imported'):
            invoice = rec.match_invoice_id or rec.suggested_invoice_id
            if not invoice:
                raise UserError(
                    _('Select or suggest a customer invoice before registering payment.')
                )
            if invoice.state != 'posted':
                raise UserError(
                    _('Invoice %s must be posted before registering payment.') % invoice.display_name
                )
            if float_compare(invoice.amount_residual, 0.0, precision_rounding=rec.currency_id.rounding) <= 0:
                raise UserError(_('Invoice %s has no residual amount.') % invoice.display_name)
            pay_amount = min(abs(rec.amount_signed), invoice.amount_residual)
            ctx = {
                'active_model': 'account.move',
                'active_ids': invoice.ids,
                'active_id': invoice.id,
            }
            wizard = PaymentRegister.with_context(**ctx).create({
                'amount': pay_amount,
                'payment_date': rec._sbu_payment_register_date(),
            })
            payments = wizard._create_payments()
            payment = payments[:1]
            rec.write({
                'match_invoice_id': invoice.id,
                'match_payment_id': payment.id if payment else False,
                'state': 'matched',
                'sbu_match_hint': _('Payment registered from Qonto movement.'),
            })
        if len(self) == 1:
            payment = self.match_payment_id
            if payment:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.payment',
                    'res_id': payment.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Qonto payment'),
                'message': _('Registered payment(s) for %(n)s movement(s).') % {'n': len(self)},
                'type': 'success',
            },
        }

    def action_register_vendor_payment(self):
        """Post vendor payment for a matched/suggested vendor bill (Cosimo punto 10 passive)."""
        PaymentRegister = self.env['account.payment.register']
        for rec in self.filtered(lambda t: t.state == 'imported'):
            bill = rec.match_vendor_bill_id or rec.suggested_vendor_bill_id
            if not bill:
                raise UserError(
                    _('Select or suggest a vendor bill before registering payment.')
                )
            if bill.state != 'posted':
                raise UserError(
                    _('Vendor bill %s must be posted before registering payment.')
                    % bill.display_name
                )
            if float_compare(bill.amount_residual, 0.0, precision_rounding=rec.currency_id.rounding) <= 0:
                raise UserError(_('Vendor bill %s has no residual amount.') % bill.display_name)
            pay_amount = min(abs(rec.amount_signed), bill.amount_residual)
            ctx = {
                'active_model': 'account.move',
                'active_ids': bill.ids,
                'active_id': bill.id,
            }
            wizard = PaymentRegister.with_context(**ctx).create({
                'amount': pay_amount,
                'payment_date': rec._sbu_payment_register_date(),
            })
            payments = wizard._create_payments()
            payment = payments[:1]
            rec.write({
                'match_vendor_bill_id': bill.id,
                'match_payment_id': payment.id if payment else False,
                'state': 'matched',
                'sbu_match_hint': _('Vendor payment registered from Qonto movement.'),
            })
        if len(self) == 1 and self.match_payment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'res_id': self.match_payment_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Qonto vendor payment'),
                'message': _('Registered vendor payment(s) for %(n)s movement(s).') % {
                    'n': len(self),
                },
                'type': 'success',
            },
        }

    def action_sync_qonto_partners(self):
        """Sync beneficiaries from Qonto for this movement's company."""
        companies = self.mapped('company_id')
        for company in companies:
            company.action_sbu_sync_qonto_partners()
        return True
