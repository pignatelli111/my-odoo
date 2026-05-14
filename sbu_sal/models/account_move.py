# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super().write(vals)
        if vals.get('payment_state'):
            self.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund'))._sbu_sal_sync_certificates_payment_state()
        return res

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
