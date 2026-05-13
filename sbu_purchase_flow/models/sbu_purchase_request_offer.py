# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SbuPurchaseRequestOffer(models.Model):
    _name = 'sbu.purchase.request.offer'
    _description = 'SBU supplier offer (per purchase request line)'
    _order = 'request_line_id, vendor_id, id'

    request_id = fields.Many2one(
        'sbu.purchase.request',
        string='Purchase request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    request_line_id = fields.Many2one(
        'sbu.purchase.request.line',
        string='Request line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        domain=[('supplier_rank', '>', 0)],
        index=True,
    )
    name = fields.Char(
        string='Quote ref.',
        help='Supplier quote number or internal label.',
    )
    unit_price = fields.Monetary(
        string='Unit price',
        currency_field='currency_id',
        default=0.0,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    lead_time_days = fields.Integer(
        string='Lead time (days)',
    )
    offer_date = fields.Date(
        string='Offer date',
        default=fields.Date.today,
    )
    notes = fields.Text(
        string='Email / notes',
        help='Paste supplier email excerpt or free-text conditions.',
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'sbu_purchase_request_offer_attachment_rel',
        'offer_id',
        'attachment_id',
        string='PDF / Excel',
    )
    price_evaluated = fields.Monetary(
        string='Evaluated price',
        currency_field='currency_id',
        compute='_compute_price_evaluated',
        help='Unit price including the request comparison markup %%.',
    )

    @api.depends('unit_price', 'currency_id', 'request_id.offer_comparison_markup_pct')
    def _compute_price_evaluated(self):
        for offer in self:
            pct = offer.request_id.offer_comparison_markup_pct or 0.0
            offer.price_evaluated = offer.unit_price * (1.0 + pct / 100.0)

    @api.constrains('request_line_id', 'request_id')
    def _check_line_matches_request(self):
        for offer in self:
            if offer.request_line_id.request_id != offer.request_id:
                raise ValidationError(
                    _('Offer line %(line)s does not belong to purchase request %(req)s.')
                    % {'line': offer.request_line_id.display_name, 'req': offer.request_id.display_name}
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('request_line_id') and not vals.get('request_id'):
                line = self.env['sbu.purchase.request.line'].browse(vals['request_line_id'])
                vals['request_id'] = line.request_id.id
        return super().create(vals_list)
