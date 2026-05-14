# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from odoo.addons.sbu_qonto.services.qonto_client import QontoHttpError, qonto_list_transactions

_logger = logging.getLogger(__name__)


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

    _sql_constraints = [
        (
            'sbu_qonto_remote_company_uniq',
            'unique(company_id, qonto_remote_id)',
            'This Qonto movement is already imported for this company.',
        ),
    ]

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
        for company in companies:
            try:
                self.sudo().import_transactions_for_company(company, max_pages=2)
            except (UserError, QontoHttpError) as e:
                _logger.warning('Qonto cron skip company %s: %s', company.id, e)

    @api.model
    def action_import_now(self):
        company = self.env.company
        n = self.import_transactions_for_company(company, max_pages=3)
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

    def action_match_odoo(self):
        """Heuristic match to customer inbound payments or posted customer invoices."""
        Payment = self.env['account.payment']
        Move = self.env['account.move']
        for rec in self:
            if rec.state != 'imported':
                continue
            rounding = rec.currency_id.rounding
            amt = abs(rec.amount_signed)
            vals = {}
            if rec.side == 'credit' and float_compare(amt, 0, precision_rounding=rounding) > 0:
                candidates = Payment.search(
                    [
                        ('company_id', '=', rec.company_id.id),
                        ('partner_type', '=', 'customer'),
                        ('payment_type', '=', 'inbound'),
                        ('state', '=', 'posted'),
                        ('currency_id', '=', rec.currency_id.id),
                    ],
                    order='date desc',
                    limit=30,
                )
                for pay in candidates:
                    if float_is_zero(pay.amount - amt, precision_rounding=rounding):
                        vals['match_payment_id'] = pay.id
                        vals['state'] = 'matched'
                        break
            if not vals.get('match_payment_id'):
                ref = (rec.reference or rec.label or '').strip()
                if ref:
                    invs = Move.search(
                        [
                            ('company_id', '=', rec.company_id.id),
                            ('move_type', '=', 'out_invoice'),
                            ('state', '=', 'posted'),
                            '|',
                            ('name', 'ilike', ref),
                            ('payment_reference', 'ilike', ref),
                        ],
                        limit=5,
                    )
                    if len(invs) == 1:
                        vals['match_invoice_id'] = invs.id
                        vals['state'] = 'matched'
            if vals:
                rec.write(vals)
        return True

    def action_ignore(self):
        self.filtered(lambda t: t.state == 'imported').write({'state': 'ignored'})
