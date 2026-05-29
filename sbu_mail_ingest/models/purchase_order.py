# -*- coding: utf-8 -*-
from odoo import models


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'mail.alias.mixin.optional']

    def _alias_get_creation_values(self):
        vals = super()._alias_get_creation_values()
        vals['alias_model_id'] = self.env['ir.model']._get_id(self._name)
        vals['alias_defaults'] = '{}'
        if self.id:
            vals['alias_force_thread_id'] = self.id
        vals['alias_contact'] = 'everyone'
        return vals
