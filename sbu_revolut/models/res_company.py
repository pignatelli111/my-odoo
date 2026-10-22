# -*- coding: utf-8 -*-
import logging
import secrets
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

from odoo.addons.sbu_revolut.services import revolut_client as rc

_logger = logging.getLogger(__name__)

_SECRET_GROUP = 'base.group_system'


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ── Connection (Phase 1) ──────────────────────────────────────────────────
    sbu_revolut_use_sandbox = fields.Boolean(
        string='Revolut sandbox API',
        help='Use the Revolut sandbox (test money) instead of the live bank.',
    )
    sbu_revolut_client_id = fields.Char(
        string='Revolut client ID',
        help='Shown in Revolut Business → Settings → APIs → Business API after uploading the certificate.',
    )
    sbu_revolut_certificate = fields.Text(
        string='Revolut public certificate',
        readonly=True,
        copy=False,
        help='Paste this certificate in Revolut Business → Settings → APIs → Business API.',
    )
    sbu_revolut_private_key = fields.Text(
        string='Revolut private key',
        groups=_SECRET_GROUP,
        copy=False,
    )
    sbu_revolut_access_token = fields.Char(
        string='Revolut access token',
        groups=_SECRET_GROUP,
        copy=False,
    )
    sbu_revolut_token_expiry = fields.Datetime(string='Revolut token expiry', copy=False, readonly=True)
    sbu_revolut_refresh_token = fields.Char(
        string='Revolut refresh token',
        groups=_SECRET_GROUP,
        copy=False,
    )
    sbu_revolut_oauth_state = fields.Char(groups=_SECRET_GROUP, copy=False)
    sbu_revolut_connection_state = fields.Selection(
        [
            ('not_configured', 'Not configured'),
            ('pending', 'Waiting for authorization'),
            ('connected', 'Connected'),
            ('error', 'Error — re-authorize'),
        ],
        string='Revolut connection',
        default='not_configured',
        readonly=True,
        copy=False,
    )
    sbu_revolut_last_error = fields.Text(string='Revolut last error', readonly=True, copy=False)
    sbu_revolut_redirect_uri = fields.Char(
        string='Revolut OAuth redirect URI',
        compute='_compute_sbu_revolut_redirect_uri',
        help='Enter exactly this URL as OAuth redirect URI in Revolut.',
    )
    sbu_revolut_account_ids = fields.One2many(
        'sbu.revolut.account', 'company_id', string='Revolut accounts',
    )

    # ── Import ────────────────────────────────────────────────────────────────
    sbu_revolut_import_enabled = fields.Boolean(
        string='Enable Revolut import cron',
        help='When enabled, the scheduled action imports recent transactions for this company.',
    )
    sbu_revolut_import_lookback_days = fields.Integer(
        string='Revolut import lookback (days)',
        default=30,
        help='How far back each scheduled import looks (first import: use "Import full history").',
    )
    sbu_revolut_last_sync = fields.Datetime(string='Revolut last import', readonly=True, copy=False)
    sbu_revolut_journal_id = fields.Many2one(
        'account.journal',
        string='Revolut default journal',
        domain="[('type', '=', 'bank'), ('company_id', '=', id)]",
        help='Bank journal used for payments registered from Revolut (unless set per Revolut account).',
    )

    # ── Webhook (Phase 2) ─────────────────────────────────────────────────────
    sbu_revolut_webhook_token = fields.Char(
        string='Revolut webhook URL token',
        groups=_SECRET_GROUP,
        copy=False,
        help='Secret path segment for POST /revolut/webhook/{token}.',
    )
    sbu_revolut_webhook_id = fields.Char(string='Revolut webhook id', readonly=True, copy=False)
    sbu_revolut_webhook_secret = fields.Char(
        string='Revolut webhook signing secret',
        groups=_SECRET_GROUP,
        copy=False,
    )

    # ── Matching (Phase 3) ────────────────────────────────────────────────────
    sbu_revolut_auto_match_high = fields.Boolean(
        string='Revolut: auto-link high confidence',
        default=True,
        help='Link movements to the suggested invoice / bill when confidence is high (no accounting entry).',
    )
    sbu_revolut_auto_register_inbound = fields.Boolean(
        string='Revolut: auto-register customer payments',
        default=False,
        help='Post the customer payment automatically for high-confidence incoming movements.',
    )

    # ── Payments (Phase 4) ────────────────────────────────────────────────────
    sbu_revolut_payment_account_id = fields.Many2one(
        'sbu.revolut.account',
        string='Revolut paying account',
        domain="[('company_id', '=', id)]",
        help='Default Revolut account used to pay vendor bills.',
    )
    sbu_revolut_second_approval_amount = fields.Monetary(
        string='Revolut: second approval from',
        currency_field='currency_id',
        help='Payments of this amount or more need a second, different approver. 0 = never.',
    )

    def _compute_sbu_revolut_redirect_uri(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        for company in self:
            company.sbu_revolut_redirect_uri = f'{base}/revolut/oauth/callback' if base else False

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _sbu_revolut_check_admin(self):
        if not (self.env.su or self.env.user.has_group(_SECRET_GROUP)):
            raise UserError(_('Only administrators can configure the Revolut connection.'))

    def _sbu_revolut_assertion(self):
        self.ensure_one()
        company = self.sudo()
        if not (company.sbu_revolut_private_key and company.sbu_revolut_client_id):
            raise UserError(_('Generate the certificate and enter the Revolut client ID first.'))
        issuer = rc.issuer_from_redirect_uri(company.sbu_revolut_redirect_uri or '')
        return rc.build_client_assertion(
            company.sbu_revolut_private_key, company.sbu_revolut_client_id.strip(), issuer,
        )

    def _sbu_revolut_store_tokens(self, payload):
        self.ensure_one()
        if not payload or not payload.get('access_token'):
            raise rc.RevolutHttpError(0, 'Revolut returned no access token.')
        expires_in = int(payload.get('expires_in') or 2400)
        vals = {
            'sbu_revolut_access_token': payload['access_token'],
            'sbu_revolut_token_expiry': fields.Datetime.now() + timedelta(seconds=expires_in),
            'sbu_revolut_connection_state': 'connected',
            'sbu_revolut_last_error': False,
        }
        if payload.get('refresh_token'):
            vals['sbu_revolut_refresh_token'] = payload['refresh_token']
        self.sudo().write(vals)
        # Revolut may rotate refresh tokens: never lose a new one to a later rollback.
        if not tools.config['test_enable']:
            self.env.cr.commit()

    def _sbu_revolut_set_error(self, message):
        self.sudo().write({
            'sbu_revolut_connection_state': 'error',
            'sbu_revolut_last_error': message,
        })

    def _sbu_revolut_exchange_code(self, code):
        self.ensure_one()
        payload = rc.request_token(self.sbu_revolut_use_sandbox, {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.sudo().sbu_revolut_client_id.strip(),
            'client_assertion_type': rc.CLIENT_ASSERTION_TYPE,
            'client_assertion': self._sbu_revolut_assertion(),
        })
        self._sbu_revolut_store_tokens(payload)

    def _sbu_revolut_access_token(self):
        """Valid access token, refreshed automatically when about to expire."""
        self.ensure_one()
        company = self.sudo()
        expiry = company.sbu_revolut_token_expiry
        if company.sbu_revolut_access_token and expiry and expiry > fields.Datetime.now() + timedelta(minutes=2):
            return company.sbu_revolut_access_token
        if not company.sbu_revolut_refresh_token:
            raise UserError(_('Revolut is not connected. Click "Authorize in Revolut" on the company.'))
        try:
            payload = rc.request_token(company.sbu_revolut_use_sandbox, {
                'grant_type': 'refresh_token',
                'refresh_token': company.sbu_revolut_refresh_token,
                'client_id': company.sbu_revolut_client_id.strip(),
                'client_assertion_type': rc.CLIENT_ASSERTION_TYPE,
                'client_assertion': company._sbu_revolut_assertion(),
            })
        except rc.RevolutHttpError as err:
            if err.status in (400, 401):
                company._sbu_revolut_set_error(str(err))
                if not tools.config['test_enable']:
                    self.env.cr.commit()
            raise
        company._sbu_revolut_store_tokens(payload)
        return company.sbu_revolut_access_token

    def _sbu_revolut_client(self):
        self.ensure_one()
        return rc.RevolutClient(self._sbu_revolut_access_token(), self.sbu_revolut_use_sandbox)

    # ── Buttons ───────────────────────────────────────────────────────────────
    def action_sbu_revolut_generate_certificate(self):
        self.ensure_one()
        self._sbu_revolut_check_admin()
        if self.sbu_revolut_connection_state == 'connected':
            raise UserError(_('Disconnect Revolut before generating a new certificate.'))
        key_pem, cert_pem = rc.generate_private_key_and_certificate(self.name)
        self.sudo().write({
            'sbu_revolut_private_key': key_pem,
            'sbu_revolut_certificate': cert_pem,
            'sbu_revolut_connection_state': 'not_configured',
        })
        return True

    def action_sbu_revolut_authorize(self):
        self.ensure_one()
        self._sbu_revolut_check_admin()
        company = self.sudo()
        if not (company.sbu_revolut_certificate and company.sbu_revolut_client_id):
            raise UserError(_('Generate the certificate, add it in Revolut, then enter the client ID.'))
        if not (company.sbu_revolut_redirect_uri or '').startswith('https://'):
            raise UserError(_('Revolut requires an https:// address for this Odoo (web.base.url).'))
        state = secrets.token_urlsafe(24)
        company.write({'sbu_revolut_oauth_state': state, 'sbu_revolut_connection_state': 'pending'})
        return {
            'type': 'ir.actions.act_url',
            'url': rc.consent_url(
                company.sbu_revolut_use_sandbox, company.sbu_revolut_client_id.strip(),
                company.sbu_revolut_redirect_uri, f'{company.id}:{state}',
            ),
            'target': 'self',
        }

    def action_sbu_revolut_disconnect(self):
        self.ensure_one()
        self._sbu_revolut_check_admin()
        self.sudo().write({
            'sbu_revolut_access_token': False,
            'sbu_revolut_refresh_token': False,
            'sbu_revolut_token_expiry': False,
            'sbu_revolut_connection_state': 'not_configured' if not self.sbu_revolut_certificate else 'pending',
            'sbu_revolut_import_enabled': False,
        })
        return True

    def action_sbu_revolut_sync_accounts(self):
        self.ensure_one()
        n = self.env['sbu.revolut.account']._sbu_sync_company_accounts(self)
        return self._sbu_revolut_notify(_('Revolut'), _('%(n)s Revolut account(s) synchronized.', n=n))

    def action_sbu_revolut_import_history(self):
        self.ensure_one()
        n = self.env['sbu.revolut.transaction'].import_transactions_for_company(self, full_history=True)
        return self._sbu_revolut_notify(_('Revolut'), _('Imported or updated %(n)s movement(s).', n=n))

    def action_sbu_revolut_register_webhook(self):
        self.ensure_one()
        self._sbu_revolut_check_admin()
        company = self.sudo()
        base = (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')
        if not base.startswith('https://'):
            raise UserError(_('Revolut webhooks need an https:// address for this Odoo (web.base.url).'))
        client = company._sbu_revolut_client()
        if company.sbu_revolut_webhook_id:
            try:
                client.delete_webhook(company.sbu_revolut_webhook_id)
            except rc.RevolutHttpError as err:
                if err.status != 404:
                    raise
        token = secrets.token_urlsafe(32)
        hook = client.create_webhook(f'{base}/revolut/webhook/{token}')
        if not hook.get('signing_secret'):
            raise UserError(_('Revolut did not return a signing secret for the webhook.'))
        company.write({
            'sbu_revolut_webhook_token': token,
            'sbu_revolut_webhook_id': hook.get('id'),
            'sbu_revolut_webhook_secret': hook['signing_secret'],
        })
        return self._sbu_revolut_notify(_('Revolut'), _('Webhook registered: new movements arrive in real time.'))

    def _sbu_revolut_notify(self, title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind, 'sticky': False},
        }

    @api.model
    def _sbu_revolut_toggle_import_cron(self):
        cron = self.env.ref('sbu_revolut.ir_cron_revolut_import', raise_if_not_found=False)
        if cron:
            active = bool(self.sudo().search_count([('sbu_revolut_import_enabled', '=', True)]))
            if cron.active != active:
                cron.sudo().active = active

    def write(self, vals):
        res = super().write(vals)
        if 'sbu_revolut_import_enabled' in vals:
            self._sbu_revolut_toggle_import_cron()
        return res
