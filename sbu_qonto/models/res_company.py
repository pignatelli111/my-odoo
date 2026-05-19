# -*- coding: utf-8 -*-
from odoo import api, fields, models


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
    sbu_qonto_webhook_token = fields.Char(
        string='Qonto webhook URL token',
        copy=False,
        help='Secret path segment for /qonto/webhook/<token>. Set in Qonto webhook URL on their side.',
    )
    sbu_qonto_import_enabled = fields.Boolean(
        string='Enable Qonto import cron',
        help='When enabled, the scheduled action imports recent transactions for this company.',
    )
    sbu_qonto_suggest_after_import = fields.Boolean(
        string='Suggest matches after import',
        default=True,
        help='After each import (cron or manual), run matching heuristics and store suggestions '
             'without auto-linking (except when you click Match with high confidence).',
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
