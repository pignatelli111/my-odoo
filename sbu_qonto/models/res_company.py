# -*- coding: utf-8 -*-
from odoo import fields, models


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
