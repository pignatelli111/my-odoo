# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_revolut_access_token = fields.Char(related='company_id.sbu_revolut_access_token', readonly=False)
    sbu_revolut_account_id = fields.Char(related='company_id.sbu_revolut_account_id', readonly=False)
    sbu_revolut_use_sandbox = fields.Boolean(related='company_id.sbu_revolut_use_sandbox', readonly=False)
    sbu_revolut_webhook_token = fields.Char(related='company_id.sbu_revolut_webhook_token', readonly=False)
    sbu_revolut_import_enabled = fields.Boolean(related='company_id.sbu_revolut_import_enabled', readonly=False)
    sbu_revolut_import_lookback_days = fields.Integer(related='company_id.sbu_revolut_import_lookback_days', readonly=False)

    def action_revolut_import_now(self):
        self.ensure_one()
        company = self.company_id
        n = self.env['sbu.revolut.transaction'].import_transactions_for_company(company, max_pages=5)
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
