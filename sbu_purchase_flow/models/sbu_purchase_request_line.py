from odoo import models, fields


class SbuPurchaseRequestLine(models.Model):
    _name = 'sbu.purchase.request.line'
    _description = 'SBU Purchase Request Line'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'sbu.purchase.request',
        string='Request',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Description', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    product_qty = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure')
    product_uom = fields.Many2one(
        'uom.uom',
        string='Unit of measure',
        required=True,
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False),
    )
    date_required = fields.Date(string='Required date')
    note = fields.Char(string='Notes')
