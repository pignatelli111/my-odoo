# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class AccountMove(models.Model):
    _inherit = 'account.move'

    sbu_revolut_payment_ids = fields.One2many('sbu.revolut.payment', 'move_id', string='Revolut payments')
    sbu_revolut_payment_count = fields.Integer(compute='_compute_sbu_revolut_payment_count')

    def _compute_sbu_revolut_payment_count(self):
        for move in self:
            move.sbu_revolut_payment_count = len(move.sbu_revolut_payment_ids)

    def action_sbu_revolut_pay(self):
        """Create draft Revolut payment orders for the selected vendor bills."""
        bills = self.filtered(lambda m: m.move_type == 'in_invoice' and m.state == 'posted')
        if not bills:
            raise UserError(_('Select posted vendor bills.'))
        Payment = self.env['sbu.revolut.payment']
        orders = Payment.browse()
        for bill in bills:
            vals = Payment._sbu_vals_from_bill(bill)
            if float_compare(vals['amount'], 0.0, precision_rounding=bill.currency_id.rounding) <= 0:
                continue
            orders |= Payment.create(vals)
        if not orders:
            raise UserError(_('Nothing left to pay on the selected bills (already paid or in a Revolut payment).'))
        return self._sbu_revolut_open_payments(orders)

    def action_sbu_revolut_open_payments(self):
        self.ensure_one()
        return self._sbu_revolut_open_payments(self.sbu_revolut_payment_ids)

    def _sbu_revolut_open_payments(self, orders):
        action = self.env['ir.actions.act_window']._for_xml_id('sbu_revolut.action_sbu_revolut_payment')
        if len(orders) == 1:
            action.update(view_mode='form', views=[(False, 'form')], res_id=orders.id)
        else:
            action['domain'] = [('id', 'in', orders.ids)]
        return action
