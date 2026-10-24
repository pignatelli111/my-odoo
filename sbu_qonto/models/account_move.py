# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    sbu_qonto_document_id = fields.Char(
        string='Qonto document id', copy=False, index='btree_not_null', readonly=True,
        help='Set on invoices imported from the Qonto history.',
    )
    sbu_qonto_vat_source = fields.Selection(
        [
            ('pdf', 'E-invoice summary'),
            ('qonto', 'Qonto data'),
            ('none', 'VAT to check'),
        ],
        string='Qonto VAT source', copy=False, readonly=True,
        help='Where the VAT lines of this historical invoice come from.',
    )
