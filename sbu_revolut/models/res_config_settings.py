# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_revolut_connection_state = fields.Selection(related='company_id.sbu_revolut_connection_state')
    sbu_revolut_import_enabled = fields.Boolean(related='company_id.sbu_revolut_import_enabled', readonly=False)
    sbu_revolut_import_lookback_days = fields.Integer(related='company_id.sbu_revolut_import_lookback_days', readonly=False)

    def action_revolut_open_company(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.company',
            'res_id': self.company_id.id,
            'view_mode': 'form',
        }

    def action_revolut_import_now(self):
        self.ensure_one()
        return self.env['sbu.revolut.transaction'].with_company(self.company_id).action_import_now()
