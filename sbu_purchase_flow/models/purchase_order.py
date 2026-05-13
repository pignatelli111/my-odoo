# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sbu_purchase_request_id = fields.Many2one(
        'sbu.purchase.request',
        string='SBU purchase request',
        index=True,
        ondelete='set null',
        copy=False,
        help='Purchase request this RFQ/PO was generated from (SBU traceability).',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sbu_purchase_request_id') and not vals.get('project_id'):
                pr = self.env['sbu.purchase.request'].browse(vals['sbu_purchase_request_id'])
                if 'project_id' in self._fields and pr.project_id:
                    vals['project_id'] = pr.project_id.id
        return super().create(vals_list)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    sbu_pr_line_id = fields.Many2one(
        'sbu.purchase.request.line',
        string='PR line',
        index=True,
        ondelete='set null',
        copy=False,
        help='Source purchase request line when the RFQ was built from an SBU request.',
    )
    sbu_offer_id = fields.Many2one(
        'sbu.purchase.request.offer',
        string='Chosen supplier offer',
        index=True,
        ondelete='set null',
        copy=False,
        help='Supplier quote row selected for this purchase line (traceability).',
    )
