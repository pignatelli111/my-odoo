# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SbuRevolutAccount(models.Model):
    _name = 'sbu.revolut.account'
    _description = 'SBU Revolut Business account'
    _order = 'company_id, currency_id, name'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company,
    )
    revolut_account_id = fields.Char(string='Revolut account id', required=True, index=True, readonly=True)
    name = fields.Char(string='Account name', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    balance = fields.Monetary(string='Balance', currency_field='currency_id', readonly=True)
    revolut_state = fields.Char(string='Revolut status', readonly=True)
    iban = fields.Char(string='IBAN', readonly=True)
    bic = fields.Char(string='BIC', readonly=True)
    journal_id = fields.Many2one(
        'account.journal',
        string='Odoo journal',
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        help='Bank journal for payments registered from this account (defaults to the company Revolut journal).',
    )
    import_enabled = fields.Boolean(string='Import movements', default=True)
    active = fields.Boolean(default=True)
    last_sync = fields.Datetime(string='Last balance update', readonly=True)

    _sbu_revolut_account_uniq = models.Constraint(
        'unique(company_id, revolut_account_id)',
        'This Revolut account already exists for this company.',
    )

    def _sbu_journal(self):
        self.ensure_one()
        return self.journal_id or self.company_id.sbu_revolut_journal_id

    @api.model
    def _sbu_sync_company_accounts(self, company):
        """Create / update every Revolut account of the company (balances + IBAN)."""
        client = company._sbu_revolut_client()
        Currency = self.env['res.currency'].with_context(active_test=False)
        existing = {
            acc.revolut_account_id: acc
            for acc in self.with_context(active_test=False).search([('company_id', '=', company.id)])
        }
        count = 0
        for data in client.accounts():
            remote_id = data.get('id')
            if not remote_id:
                continue
            currency = Currency.search([('name', '=', data.get('currency'))], limit=1) or company.currency_id
            if not currency.active:
                currency.active = True
            vals = {
                'name': data.get('name') or _('Revolut %s', data.get('currency') or ''),
                'currency_id': currency.id,
                'balance': float(data.get('balance') or 0.0),
                'revolut_state': data.get('state'),
                'active': data.get('state') != 'inactive',
                'last_sync': fields.Datetime.now(),
            }
            iban, bic = self._sbu_iban_bic(client, remote_id)
            if iban:
                vals.update(iban=iban, bic=bic)
            account = existing.get(remote_id)
            if account:
                account.write(vals)
            else:
                account = self.create(dict(vals, company_id=company.id, revolut_account_id=remote_id))
            count += 1
        if not company.sbu_revolut_payment_account_id:
            default = self.search([
                ('company_id', '=', company.id), ('currency_id', '=', company.currency_id.id),
            ], limit=1)
            if default:
                company.sudo().sbu_revolut_payment_account_id = default
        return count

    @api.model
    def _sbu_iban_bic(self, client, account_id):
        try:
            details = client.account_bank_details(account_id)
        except Exception:  # noqa: BLE001 — bank details are optional (not all accounts have an IBAN)
            return False, False
        for item in details or []:
            if item.get('iban'):
                return item['iban'].replace(' ', ''), item.get('bic')
        return False, False

    def _sbu_refresh_balance(self):
        """Update the live balance of this account from Revolut and return it."""
        self.ensure_one()
        data = self.company_id._sbu_revolut_client().account(self.revolut_account_id)
        self.write({
            'balance': float(data.get('balance') or 0.0),
            'revolut_state': data.get('state') or self.revolut_state,
            'last_sync': fields.Datetime.now(),
        })
        return self.balance

    def _sbu_safe_refresh_balances(self):
        for account in self.filtered('active'):
            try:
                account._sbu_refresh_balance()
            except Exception as err:  # noqa: BLE001 — a balance refresh must not break the import cron
                _logger.warning('Revolut balance refresh failed for %s: %s', account.name, err)

    def action_refresh_balance(self):
        for account in self:
            account._sbu_refresh_balance()
        return True
