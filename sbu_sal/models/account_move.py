# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super().write(vals)
        touch_moves = self.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund'))
        if vals.get('payment_state'):
            touch_moves._sbu_sal_sync_certificates_payment_state()
        if touch_moves and vals.keys() & {'payment_state', 'state', 'name', 'ref'}:
            touch_moves._sbu_sal_touch_contractual_sal_lines()
        return res

    def _sbu_sal_touch_contractual_sal_lines(self):
        if 'sbu.estimate.sal.line' not in self.env:
            return
        sheets = self.env['sbu.sal.sheet'].search([('invoice_id', 'in', self.ids)])
        sal_lines = sheets.line_ids.mapped('estimate_sal_line_id')
        if sal_lines:
            sal_lines._sbu_recompute_billing_from_sheet_lines()

    def _sbu_sal_sync_certificates_payment_state(self):
        Certificate = self.env['sbu.payment.certificate'].sudo()
        for move in self:
            if move.payment_state != 'paid':
                continue
            certs = Certificate.search(
                [('sal_sheet_id.invoice_id', '=', move.id), ('state', '=', 'issued')]
            )
            if certs:
                certs.write({'state': 'paid'})
                certs._sbu_link_payment_from_invoice()
