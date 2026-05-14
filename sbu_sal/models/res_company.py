# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sbu_sal_invoice_post_default = fields.Selection(
        selection=[
            ('draft', 'Keep customer invoice in draft'),
            ('posted', 'Validate (post) invoice immediately'),
        ],
        string='SAL customer invoice',
        default='draft',
        help='Default behaviour when creating a customer invoice from a confirmed SAL sheet.',
    )
    sbu_sal_default_tax_ids = fields.Many2many(
        'account.tax',
        'res_company_sbu_sal_default_tax_rel',
        'company_id',
        'tax_id',
        string='SAL default sale taxes',
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'parent_of', id)]",
        help='Applied to SAL-generated invoices when the SAL sheet has no tax override.',
    )
