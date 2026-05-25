# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_qonto_login = fields.Char(related='company_id.sbu_qonto_login', readonly=False)
    sbu_qonto_secret_key = fields.Char(related='company_id.sbu_qonto_secret_key', readonly=False)
    sbu_qonto_iban = fields.Char(related='company_id.sbu_qonto_iban', readonly=False)
    sbu_qonto_use_sandbox = fields.Boolean(related='company_id.sbu_qonto_use_sandbox', readonly=False)
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

    def action_qonto_import_now(self):
        self.ensure_one()
        company = self.company_id
        n = self.env['sbu.qonto.transaction'].import_transactions_for_company(company, max_pages=3)
        self.env['sbu.qonto.transaction']._sbu_post_import_process(company)
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

    def action_qonto_sync_partners(self):
        self.ensure_one()
        return self.company_id.action_sbu_sync_qonto_partners()
