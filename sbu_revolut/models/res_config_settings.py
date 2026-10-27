# -*- coding: utf-8 -*-
from odoo import _, fields, models


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

    def _sbu_setup_checks(self):
        checks = super()._sbu_setup_checks()
        company = self.company_id
        state = company.sbu_revolut_connection_state or 'not_configured'
        status = {'connected': 'ok', 'not_configured': 'optional'}.get(state, 'missing')
        detail = dict(company._fields['sbu_revolut_connection_state'].selection).get(state)
        if state == 'connected':
            detail = _('%(state)s — %(n)s account(s)', state=detail, n=len(company.sbu_revolut_account_ids))
        checks.append({
            'label': _('Revolut connection'),
            'status': status,
            'detail': detail,
            'url': self._sbu_company_url(company),
        })
        return checks
