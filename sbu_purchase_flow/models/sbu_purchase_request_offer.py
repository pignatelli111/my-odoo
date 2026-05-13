# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_CTX_SKIP_OFFER_EXCLUSIVE = 'sbu_skip_offer_exclusivity'


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
    moq = fields.Float(
        string='MOQ',
        digits='Product Unit of Measure',
        help='Minimum order quantity quoted by the supplier.',
    )
    offer_uom_id = fields.Many2one(
        'uom.uom',
        string='Supplier UoM',
        help='Quoted unit of measure (defaults from the request line when empty).',
    )
    payment_delivery_terms = fields.Text(
        string='Terms',
        help='Payment, delivery, warranty, incoterms, etc.',
    )
    technical_fit_score = fields.Integer(
        string='Technical fit (0–5)',
        default=0,
        help='Subjective score for specification / quality fit (matrix & pivot).',
    )
    margin_impact_pct = fields.Float(
        string='Margin impact (pp)',
        digits=(16, 2),
        help='Estimated effect on gross margin in percentage points vs. internal baseline (negative = improves margin).',
    )
    margin_impact_evaluated = fields.Float(
        string='Margin impact (comparison)',
        digits=(16, 2),
        compute='_compute_margin_impact_evaluated',
        store=True,
        help='Margin impact adjusted by the request «comparison margin buffer %» (e.g. +3%).',
    )
    is_chosen = fields.Boolean(
        string='Chosen for PO',
        help='At most one chosen offer per request line. Used when generating draft RFQs for that vendor.',
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
        store=True,
        help='Unit price including the request offer comparison markup %%.',
    )

    @api.depends('unit_price', 'currency_id', 'request_id.offer_comparison_markup_pct')
    def _compute_price_evaluated(self):
        for offer in self:
            pct = offer.request_id.offer_comparison_markup_pct or 0.0
            offer.price_evaluated = offer.unit_price * (1.0 + pct / 100.0)

    @api.depends('margin_impact_pct', 'request_id.comparison_margin_buffer_pct')
    def _compute_margin_impact_evaluated(self):
        for offer in self:
            buf = offer.request_id.comparison_margin_buffer_pct or 0.0
            offer.margin_impact_evaluated = (offer.margin_impact_pct or 0.0) + buf

    @api.constrains('request_line_id', 'request_id')
    def _check_line_matches_request(self):
        for offer in self:
            if offer.request_line_id.request_id != offer.request_id:
                raise ValidationError(
                    _('Offer line %(line)s does not belong to purchase request %(req)s.')
                    % {'line': offer.request_line_id.display_name, 'req': offer.request_id.display_name}
                )

    @api.constrains('technical_fit_score')
    def _check_technical_fit_range(self):
        for offer in self:
            if offer.technical_fit_score < 0 or offer.technical_fit_score > 5:
                raise ValidationError(_('Technical fit must be between 0 and 5.'))

    @api.constrains('is_chosen', 'request_line_id')
    def _check_single_chosen_per_line(self):
        for line in self.mapped('request_line_id'):
            chosen = line.offer_ids.filtered('is_chosen')
            if len(chosen) > 1:
                raise ValidationError(
                    _('Only one «Chosen for PO» offer is allowed per line (%s).')
                    % (line.display_name,)
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('request_line_id') and not vals.get('request_id'):
                line = self.env['sbu.purchase.request.line'].browse(vals['request_line_id'])
                vals['request_id'] = line.request_id.id
            if vals.get('request_line_id') and not vals.get('offer_uom_id'):
                line = self.env['sbu.purchase.request.line'].browse(vals['request_line_id'])
                vals['offer_uom_id'] = line.product_uom.id
        records = super().create(vals_list)
        if not self.env.context.get(_CTX_SKIP_OFFER_EXCLUSIVE):
            for rec in records.filtered('is_chosen'):
                others = rec.request_line_id.offer_ids - rec
                if others:
                    others.with_context(**{_CTX_SKIP_OFFER_EXCLUSIVE: True}).write({'is_chosen': False})
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get(_CTX_SKIP_OFFER_EXCLUSIVE):
            return res
        if vals.get('is_chosen'):
            for rec in self.filtered('is_chosen'):
                others = rec.request_line_id.offer_ids - rec
                if others:
                    others.with_context(**{_CTX_SKIP_OFFER_EXCLUSIVE: True}).write({'is_chosen': False})
        return res

    @api.onchange('request_line_id')
    def _onchange_request_line_id_uom(self):
        for offer in self:
            if offer.request_line_id and not offer.offer_uom_id:
                offer.offer_uom_id = offer.request_line_id.product_uom
