# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sbu_revolut_access_token = fields.Char(
        string='Revolut access token',
        groups='account.group_account_manager',
        help='Bearer JWT from Revolut Business API (short-lived; refresh in Revolut when it expires).',
    )
    sbu_revolut_account_id = fields.Char(
        string='Revolut account id',
        help='UUID of the Revolut Business account (GET /accounts). Used to filter /transactions.',
    )
    sbu_revolut_use_sandbox = fields.Boolean(
        string='Revolut sandbox API',
        help='Use sandbox-b2b.revolut.com for tests.',
    )
    sbu_revolut_webhook_token = fields.Char(
        string='Revolut webhook URL token',
        copy=False,
        help='Secret path segment for POST /revolut/webhook/<token>.',
    )
    sbu_revolut_import_enabled = fields.Boolean(
        string='Enable Revolut import cron',
        help='When enabled, the scheduled action imports recent transactions for this company.',
    )
    sbu_revolut_import_lookback_days = fields.Integer(
        string='Revolut import lookback (days)',
        default=30,
        help='First API page requests transactions from now back this many days.',
    )
