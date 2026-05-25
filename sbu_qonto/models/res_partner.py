# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sbu_qonto_beneficiary_id = fields.Char(
        string='Qonto beneficiary id',
        copy=False,
        index=True,
        help='External id from Qonto SEPA beneficiaries API.',
    )
    sbu_qonto_iban = fields.Char(
        string='Qonto IBAN',
        copy=False,
        index=True,
        help='IBAN synced from Qonto (used to match bank movements).',
    )
    sbu_qonto_partner_synced = fields.Boolean(
        string='Synced from Qonto',
        copy=False,
        help='True when created or last updated from Qonto beneficiaries import.',
    )
