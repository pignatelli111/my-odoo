# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.sbu_qonto.models.sbu_qonto_helpers import (
    sbu_beneficiary_display_name,
    sbu_beneficiary_iban,
    sbu_beneficiary_remote_id,
    sbu_normalize_iban,
)
from odoo.addons.sbu_qonto.models.sbu_qonto_helpers import sbu_qonto_user_error
from odoo.addons.sbu_qonto.services.qonto_client import (
    QontoHttpError,
    qonto_get_organization,
    qonto_list_legacy_beneficiaries,
    qonto_list_sepa_beneficiaries,
)


class ResCompany(models.Model):
    _inherit = 'res.company'

    sbu_qonto_login = fields.Char(
        string='Qonto API login',
        help='Sign-in / login used with the secret key (not an email password).',
    )
    sbu_qonto_secret_key = fields.Char(
        string='Qonto secret key',
        groups='account.group_account_manager',
        help='API secret from Qonto (Integrations). Stored on the company record.',
    )
    sbu_qonto_iban = fields.Char(
        string='Qonto bank account IBAN',
        help='IBAN of the Qonto account to pull transactions for (list transactions API).',
    )
    sbu_qonto_use_sandbox = fields.Boolean(
        string='Qonto sandbox API',
        help='Use Qonto staging host for tests.',
    )
    sbu_qonto_staging_token = fields.Char(
        string='Qonto staging token',
        groups='account.group_account_manager',
        help='Required when «Qonto sandbox» is on: X-Qonto-Staging-Token from the Qonto Developer Portal.',
    )
    sbu_qonto_webhook_token = fields.Char(
        string='Qonto webhook URL token',
        copy=False,
        help='Secret path segment for /qonto/webhook/{token}. Set in Qonto webhook URL on their side.',
    )
    sbu_qonto_import_enabled = fields.Boolean(
        string='Enable Qonto import cron',
        help='When enabled, the scheduled action imports recent transactions for this company.',
    )
    sbu_qonto_suggest_after_import = fields.Boolean(
        string='Suggest matches after import',
        default=True,
        help='After each import, run matching heuristics on new movements.',
    )
    sbu_qonto_sync_partners_on_import = fields.Boolean(
        string='Sync Qonto beneficiaries on import',
        default=True,
        help='Refresh suppliers/customers from Qonto SEPA beneficiaries before matching.',
    )
    sbu_qonto_auto_match_high = fields.Boolean(
        string='Auto-link high-confidence matches',
        default=True,
        help='After import, automatically link movements when match confidence is high.',
    )
    sbu_qonto_auto_register_inbound = fields.Boolean(
        string='Auto-register customer payments',
        default=True,
        help='Post customer payments on high-confidence inbound movements (reconciles customer invoices).',
    )
    sbu_qonto_auto_register_outbound = fields.Boolean(
        string='Auto-register vendor payments',
        default=False,
        help='Post vendor payments on high-confidence outbound movements (reconciles vendor bills). '
             'Off by default — review before paying suppliers automatically.',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'sbu_qonto_import_enabled' in vals:
            self.env['res.company']._sbu_sync_qonto_cron_active()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        if any(v.get('sbu_qonto_import_enabled') for v in vals_list):
            self.env['res.company']._sbu_sync_qonto_cron_active()
        return companies

    @api.model
    def _sbu_sync_qonto_cron_active(self):
        cron = self.env.ref('sbu_qonto.ir_cron_qonto_import', raise_if_not_found=False)
        if not cron:
            return
        active = bool(self.search_count([('sbu_qonto_import_enabled', '=', True)]))
        cron.sudo().write({'active': active})

    def _sbu_qonto_credentials_ok(self):
        self.ensure_one()
        login, secret, iban = self._sbu_qonto_api_credentials()
        return bool(login and secret and iban)

    def _sbu_qonto_api_credentials(self):
        """Return stripped (login, secret) used for Authorization header."""
        self.ensure_one()
        login = (self.sbu_qonto_login or '').strip()
        secret = (self.sbu_qonto_secret_key or '').strip()
        iban = sbu_normalize_iban(self.sbu_qonto_iban) or (self.sbu_qonto_iban or '').strip()
        return login, secret, iban

    @api.model
    def _sbu_qonto_warn_login_shape(self, login):
        login = (login or '').strip()
        if '@' in login:
            raise UserError(
                _(
                    'Qonto API login looks like an email («%(login)s»). '
                    'Use the API «Sign-in» slug from Qonto → Integrations → API key '
                    '(example: pied-piper-7132), not your user email.'
                ) % {'login': login}
            )

    def _sbu_qonto_staging_token(self):
        self.ensure_one()
        return (self.sbu_qonto_staging_token or '').strip() or None

    def _sbu_fetch_qonto_beneficiaries(self):
        self.ensure_one()
        login, secret, _iban = self._sbu_qonto_api_credentials()
        token = self._sbu_qonto_staging_token()
        rows = qonto_list_sepa_beneficiaries(
            login,
            secret,
            self.sbu_qonto_use_sandbox,
            staging_token=token,
        )
        if not rows:
            rows = qonto_list_legacy_beneficiaries(
                login,
                secret,
                self.sbu_qonto_use_sandbox,
                staging_token=token,
            )
        return rows

    def action_sbu_test_qonto_connection(self):
        """GET /v2/organization — validates credentials before import."""
        self.ensure_one()
        login, secret, iban = self._sbu_qonto_api_credentials()
        if not login or not secret or not iban:
            raise UserError(_('Configure Qonto login, secret key and IBAN on the company first.'))
        self._sbu_qonto_warn_login_shape(login)
        try:
            payload = qonto_get_organization(
                login,
                secret,
                self.sbu_qonto_use_sandbox,
                staging_token=self._sbu_qonto_staging_token(),
            )
        except QontoHttpError as err:
            raise sbu_qonto_user_error(err) from err
        org = payload.get('organization') or payload
        name = (org.get('legal_name') or org.get('name') or '').strip() or _('(unknown)')
        slug = (org.get('slug') or '').strip()
        msg = _('Connected to Qonto organization «%(name)s»%(slug)s.') % {
            'name': name,
            'slug': f' ({slug})' if slug else '',
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Qonto connection OK'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def _sbu_partner_bank_iban(self, partner):
        for bank in partner.bank_ids:
            iban = sbu_normalize_iban(bank.acc_number)
            if iban:
                return iban
        return ''

    def _sbu_upsert_partner_bank(self, partner, iban):
        if not iban or 'acc_number' not in self.env['res.partner.bank']._fields:
            return
        Bank = self.env['res.partner.bank']
        existing = partner.bank_ids.filtered(
            lambda b: sbu_normalize_iban(b.acc_number) == iban
        )
        if existing:
            return
        vals = {
            'partner_id': partner.id,
            'acc_number': iban,
        }
        if 'acc_type' in Bank._fields:
            vals['acc_type'] = 'iban'
        Bank.create(vals)

    def action_sbu_sync_qonto_partners(self):
        """Import / update res.partner from Qonto beneficiaries (Cosimo punto 14)."""
        self.ensure_one()
        if not self._sbu_qonto_credentials_ok():
            raise UserError(_('Configure Qonto login, secret key and IBAN on the company first.'))
        try:
            stats = self._sbu_sync_qonto_partners()
        except QontoHttpError as err:
            raise sbu_qonto_user_error(err) from err
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Qonto partners'),
                'message': _(
                    'Beneficiaries: %(total)s — created %(created)s, updated %(updated)s, '
                    'skipped %(skipped)s.'
                ) % stats,
                'type': 'success',
                'sticky': False,
            },
        }

    def _sbu_sync_qonto_partners(self):
        """Return stats dict {total, created, updated, skipped}."""
        self.ensure_one()
        Partner = self.env['res.partner'].with_context(active_test=False)
        created = updated = skipped = 0
        beneficiaries = self._sbu_fetch_qonto_beneficiaries()
        for ben in beneficiaries:
            name = sbu_beneficiary_display_name(ben)
            iban = sbu_beneficiary_iban(ben)
            remote_id = sbu_beneficiary_remote_id(ben)
            if not name and not iban and not remote_id:
                skipped += 1
                continue
            partner = Partner.browse()
            if remote_id:
                partner = Partner.search([
                    ('sbu_qonto_beneficiary_id', '=', remote_id),
                    '|', ('company_id', '=', False), ('company_id', '=', self.id),
                ], limit=1)
            if not partner and iban:
                partner = Partner.search([
                    ('sbu_qonto_iban', '=', iban),
                    '|', ('company_id', '=', False), ('company_id', '=', self.id),
                ], limit=1)
            if not partner and iban:
                partner = Partner.search([
                    ('bank_ids.acc_number', 'ilike', iban[-8:]),
                    '|', ('company_id', '=', False), ('company_id', '=', self.id),
                ], limit=1)
                if partner and sbu_normalize_iban(self._sbu_partner_bank_iban(partner)) != iban:
                    partner = Partner.browse()

            vals = {
                'sbu_qonto_beneficiary_id': remote_id or False,
                'sbu_qonto_iban': iban or False,
                'sbu_qonto_partner_synced': True,
            }
            if name and (not partner or not partner.name or partner.name == '/'):
                vals['name'] = name
            if not partner:
                vals.update({
                    'company_id': self.id,
                    'supplier_rank': 1,
                })
                partner = Partner.create(vals)
                created += 1
            else:
                write_vals = dict(vals)
                if not partner.supplier_rank:
                    write_vals['supplier_rank'] = 1
                partner.write(write_vals)
                updated += 1
            if iban:
                self._sbu_upsert_partner_bank(partner, iban)
        return {
            'total': len(beneficiaries),
            'created': created,
            'updated': updated,
            'skipped': skipped,
        }
