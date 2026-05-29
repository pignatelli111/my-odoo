# -*- coding: utf-8 -*-
from odoo import fields, models


class SbuLogikalProductMap(models.Model):
    _name = 'sbu.logikal.product.map'
    _description = 'Logikal / ReynaPro profile → Odoo product'
    _order = 'profile_code'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)
    profile_code = fields.Char(
        string='Profile / article code',
        required=True,
        index=True,
        help='Code as exported from Logikal or ReynaPro (trimmed, case-sensitive match).',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Odoo product',
        required=True,
    )
    note = fields.Char(string='Note')

    _profile_company_uniq = models.Constraint(
        'unique(company_id, profile_code)',
        'Profile code must be unique per company.',
    )
