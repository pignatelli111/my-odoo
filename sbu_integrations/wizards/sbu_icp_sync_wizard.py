# -*- coding: utf-8 -*-
import json

from odoo import _, fields, models
from odoo.exceptions import UserError


class SbuIcpSyncWizard(models.TransientModel):
    _name = 'sbu.icp.sync.wizard'
    _description = 'Export / import SBU ir.config_parameter keys (sbu.*)'

    json_text = fields.Text(
        string='JSON',
        help='Export fills this field. On the target database, paste the same JSON and click Import.',
    )

    def action_export(self):
        """Dump all system parameters whose key starts with sbu."""
        ICP = self.env['ir.config_parameter'].sudo()
        rows = ICP.search([('key', 'like', 'sbu.%')])
        data = {p.key: p.value or '' for p in rows}
        payload = json.dumps(dict(sorted(data.items())), indent=2, ensure_ascii=False)
        self.write({'json_text': payload})
        return self._reload_action()

    def action_import(self):
        """Apply JSON object keys to ir.config_parameter (keys must start with sbu.)."""
        self.ensure_one()
        raw = (self.json_text or '').strip()
        if not raw:
            raise UserError(_('Paste JSON from the development export first.'))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise UserError(_('Invalid JSON: %s') % e) from e
        if not isinstance(data, dict):
            raise UserError(_('JSON must be an object with string keys, e.g. {"sbu.graph_tenant_id": "..."}.'))
        for key, val in data.items():
            if not isinstance(key, str) or not key.startswith('sbu.'):
                raise UserError(_('Illegal key (must be a string starting with «sbu.»): %s') % key)
            if val is not None and not isinstance(val, (str, int, float, bool)):
                raise UserError(_('Value for %s must be a string, number, boolean, or null.') % key)
            self.env['ir.config_parameter'].sudo().set_param(key, '' if val is None else str(val))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SBU settings'),
                'message': _('Imported %s keys into ir.config_parameter.') % len(data),
                'type': 'success',
                'sticky': False,
            },
        }

    def _reload_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('SBU settings JSON'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
