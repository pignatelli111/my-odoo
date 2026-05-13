# -*- coding: utf-8 -*-
from odoo import fields, models


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
