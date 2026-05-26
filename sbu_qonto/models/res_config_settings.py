# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.sbu_qonto.models.sbu_qonto_helpers import sbu_qonto_user_error
from odoo.addons.sbu_qonto.services.qonto_client import QontoHttpError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_qonto_login = fields.Char(related='company_id.sbu_qonto_login', readonly=False)
    sbu_qonto_secret_key = fields.Char(related='company_id.sbu_qonto_secret_key', readonly=False)
    sbu_qonto_iban = fields.Char(related='company_id.sbu_qonto_iban', readonly=False)
    sbu_qonto_use_sandbox = fields.Boolean(related='company_id.sbu_qonto_use_sandbox', readonly=False)
    sbu_qonto_staging_token = fields.Char(
        related='company_id.sbu_qonto_staging_token',
        readonly=False,
    )
    sbu_qonto_webhook_token = fields.Char(related='company_id.sbu_qonto_webhook_token', readonly=False)
    sbu_qonto_import_enabled = fields.Boolean(related='company_id.sbu_qonto_import_enabled', readonly=False)
    sbu_qonto_suggest_after_import = fields.Boolean(
        related='company_id.sbu_qonto_suggest_after_import',
        readonly=False,
    )
    sbu_qonto_sync_partners_on_import = fields.Boolean(
        related='company_id.sbu_qonto_sync_partners_on_import',
        readonly=False,
    )
    sbu_qonto_auto_match_high = fields.Boolean(
        related='company_id.sbu_qonto_auto_match_high',
        readonly=False,
    )
    sbu_qonto_auto_register_inbound = fields.Boolean(
        related='company_id.sbu_qonto_auto_register_inbound',
        readonly=False,
    )
    sbu_qonto_auto_register_outbound = fields.Boolean(
        related='company_id.sbu_qonto_auto_register_outbound',
        readonly=False,
    )

    def _sbu_qonto_persist_from_settings(self):
        """Write current settings form values to company (incl. unsaved secret)."""
        self.ensure_one()
        company = self.company_id
        vals = {}
        if self.sbu_qonto_login is not False and self.sbu_qonto_login is not None:
            vals['sbu_qonto_login'] = (self.sbu_qonto_login or '').strip()
        if self.sbu_qonto_secret_key:
            vals['sbu_qonto_secret_key'] = self.sbu_qonto_secret_key.strip()
        if self.sbu_qonto_iban is not False and self.sbu_qonto_iban is not None:
            from odoo.addons.sbu_qonto.models.sbu_qonto_helpers import sbu_normalize_iban
            vals['sbu_qonto_iban'] = (
                sbu_normalize_iban(self.sbu_qonto_iban) or (self.sbu_qonto_iban or '').strip()
            )
        if self.sbu_qonto_staging_token:
            vals['sbu_qonto_staging_token'] = self.sbu_qonto_staging_token.strip()
        vals['sbu_qonto_use_sandbox'] = self.sbu_qonto_use_sandbox
        if vals:
            company.write(vals)
        return company

    def set_values(self):
        """Do not erase stored secret when the password field is left blank."""
        preserve_secret = False
        old_secret = False
        if not self.sbu_qonto_secret_key and self.company_id.sbu_qonto_secret_key:
            preserve_secret = True
            old_secret = self.company_id.sbu_qonto_secret_key
        res = super().set_values()
        if preserve_secret and old_secret:
            self.company_id.sbu_qonto_secret_key = old_secret
        return res

    def action_qonto_import_now(self):
        self.ensure_one()
        company = self._sbu_qonto_persist_from_settings()
        login, secret, _iban = company._sbu_qonto_api_credentials()
        if not login or not secret:
            raise UserError(
                _('Enter Qonto API sign-in and secret key, then click Save or Test connection.')
            )
        try:
            n = self.env['sbu.qonto.transaction'].import_transactions_for_company(
                company, max_pages=3,
            )
        except QontoHttpError as err:
            raise sbu_qonto_user_error(err) from err
        self.env['sbu.qonto.transaction']._sbu_post_import_process(company)
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

    def action_qonto_test_connection(self):
        self.ensure_one()
        company = self._sbu_qonto_persist_from_settings()
        return company.action_sbu_test_qonto_connection()

    def action_qonto_sync_partners(self):
        self.ensure_one()
        company = self._sbu_qonto_persist_from_settings()
        return company.action_sbu_sync_qonto_partners()

    def action_qonto_open_movements(self):
        """Open imported Qonto movements (same list as SBU → Banking → Qonto movements)."""
        self.ensure_one()
        company = self.company_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Qonto movements'),
            'res_model': 'sbu.qonto.transaction',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', company.id)],
            'context': {'default_company_id': company.id},
            'target': 'current',
        }
