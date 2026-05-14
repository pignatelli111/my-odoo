# -*- coding: utf-8 -*-
import base64
import csv
import io
import json
import logging
from datetime import datetime, timedelta, timezone

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from odoo.addons.sbu_revolut.services.revolut_client import RevolutHttpError, revolut_list_transactions

_logger = logging.getLogger(__name__)


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
    revolut_remote_id = fields.Char(string='Revolut id', required=True, index=True)
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
    currency_id = fields.Many2one('res.currency', required=True)
    label = fields.Char(string='Label')
    reference = fields.Char(string='Reference')
    note = fields.Char(string='Note')
    settled_at = fields.Datetime(string='Settled at')
    created_at_revolut = fields.Datetime(string='Created at (Revolut)')
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

    _sbu_revolut_remote_company_uniq = models.Constraint(
        'unique(company_id, revolut_remote_id)',
        'This Revolut movement is already imported for this company.',
    )

    @api.model
    def _amount_and_currency(self, tx):
        legs = tx.get('legs')
        if isinstance(legs, list) and legs:
            leg = legs[0]
            if isinstance(leg, dict):
                amt = float(leg.get('amount', 0) or 0)
                cur = leg.get('currency') or tx.get('currency') or 'EUR'
                return amt, cur
        return float(tx.get('amount', 0) or 0), (tx.get('currency') or 'EUR')

    @api.model
    def _label_from_tx(self, tx):
        merchant = tx.get('merchant')
        if isinstance(merchant, dict):
            name = merchant.get('name')
            if name:
                return name
        return tx.get('description') or tx.get('reference') or tx.get('type') or ''

    @api.model
    def _vals_from_revolut_dict(self, company, tx, source):
        remote_id = str(tx.get('id', '')).strip()
        if not remote_id:
            return None
        amount_signed, cur_code = self._amount_and_currency(tx)
        amount = abs(amount_signed)
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
            'revolut_remote_id': remote_id,
            'source': source,
            'revolut_type': tx.get('type'),
            'revolut_state': tx.get('state'),
            'amount': amount,
            'amount_signed': amount_signed,
            'currency_id': currency.id,
            'label': self._label_from_tx(tx),
            'reference': tx.get('reference') or tx.get('id'),
            'note': tx.get('comment') if isinstance(tx.get('comment'), str) else False,
            'settled_at': _parse_dt(tx.get('completed_at')) or _parse_dt(tx.get('updated_at')),
            'created_at_revolut': _parse_dt(tx.get('created_at')),
            'raw_json': json.dumps(tx),
        }

    @api.model
    def revolut_upsert_from_dict(self, company, tx, source):
        vals = self._vals_from_revolut_dict(company, tx, source)
        if not vals:
            return self.env['sbu.revolut.transaction']
        existing = self.search(
            [('company_id', '=', company.id), ('revolut_remote_id', '=', vals['revolut_remote_id'])],
            limit=1,
        )
        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)

    @api.model
    def revolut_process_webhook_payload(self, company, raw: str):
        if not raw:
            return 0
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            _logger.warning('Revolut webhook invalid JSON')
            return 0
        count = 0

        def _one(d):
            nonlocal count
            if isinstance(d, dict) and d.get('id'):
                self.revolut_upsert_from_dict(company, d, 'webhook')
                count += 1

        if isinstance(body, dict):
            if isinstance(body.get('data'), dict):
                _one(body['data'])
            elif isinstance(body.get('data'), list):
                for item in body['data']:
                    if isinstance(item, dict):
                        _one(item)
            elif isinstance(body.get('transaction'), dict):
                _one(body['transaction'])
            elif body.get('id'):
                _one(body)
        elif isinstance(body, list):
            for item in body:
                if isinstance(item, dict):
                    if isinstance(item.get('data'), dict):
                        _one(item['data'])
                    elif item.get('id'):
                        _one(item)
        return count

    @api.model
    def import_transactions_for_company(self, company, max_pages=5):
        if not (company.sbu_revolut_access_token and company.sbu_revolut_account_id):
            raise UserError(_('Configure Revolut access token and account id on the company.'))
        lookback = int(company.sbu_revolut_import_lookback_days or 30)
        date_from = datetime.now(timezone.utc) - timedelta(days=lookback)
        date_to = None
        total = 0
        count = 200
        for _page in range(max_pages):
            txs = revolut_list_transactions(
                company.sbu_revolut_access_token.strip(),
                company.sbu_revolut_account_id.strip(),
                company.sbu_revolut_use_sandbox,
                date_from=date_from if date_to is None else None,
                date_to=date_to,
                count=count,
            )
            if not txs:
                break
            for tx in txs:
                self.revolut_upsert_from_dict(company, tx, 'api')
                total += 1
            if len(txs) < count:
                break
            last = txs[-1]
            created = last.get('created_at')
            if not created:
                break
            try:
                date_to = fields.Datetime.to_datetime(created)
                if date_to.tzinfo is None:
                    date_to = date_to.replace(tzinfo=timezone.utc)
                else:
                    date_to = date_to.astimezone(timezone.utc)
            except (ValueError, TypeError, OverflowError):
                break
        return total

    @api.model
    def cron_revolut_import(self):
        companies = self.env['res.company'].sudo().search([('sbu_revolut_import_enabled', '=', True)])
        for company in companies:
            try:
                self.sudo().import_transactions_for_company(company, max_pages=3)
            except (UserError, RevolutHttpError) as e:
                _logger.warning('Revolut cron skip company %s: %s', company.id, e)

    @api.model
    @api.model
    def action_import_now(self):
        company = self.env.company
        n = self.import_transactions_for_company(company, max_pages=5)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Revolut'),
                'message': _('Imported or updated %(n)s movements.', n=n),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_match_odoo(self):
        Payment = self.env['account.payment']
        Move = self.env['account.move']
        for rec in self:
            if rec.state != 'imported':
                continue
            rounding = rec.currency_id.rounding
            amt = abs(rec.amount_signed)
            vals = {}
            if float_compare(rec.amount_signed, 0, precision_rounding=rounding) > 0:
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

    def action_export_csv(self):
        self = self.sudo()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                'revolut_id',
                'settled_at',
                'amount_signed',
                'currency',
                'label',
                'reference',
                'revolut_type',
                'match_state',
                'match_payment_id',
                'match_invoice_id',
            ]
        )
        for rec in self:
            writer.writerow(
                [
                    rec.revolut_remote_id,
                    rec.settled_at or '',
                    rec.amount_signed,
                    rec.currency_id.name,
                    rec.label or '',
                    rec.reference or '',
                    rec.revolut_type or '',
                    rec.state,
                    rec.match_payment_id.id or '',
                    rec.match_invoice_id.id or '',
                ]
            )
        data = base64.b64encode(buf.getvalue().encode('utf-8')).decode('ascii')
        att = self.env['ir.attachment'].sudo().create(
            {
                'name': 'revolut_movements_export.csv',
                'datas': data,
                'mimetype': 'text/csv',
                'type': 'binary',
            }
        )
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{att.id}?download=true',
            'target': 'new',
        }

    @api.model
    def action_export_csv_selection(self):
        ids = self.env.context.get('active_ids') or []
        records = self.browse(ids) if ids else self.search([], limit=5000, order='id desc')
        if not records:
            raise UserError(_('No Revolut movements to export.'))
        return records.action_export_csv()
