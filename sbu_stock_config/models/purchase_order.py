# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_id = fields.Many2one(
        'project.project',
        string='Job / project',
        index=True,
        ondelete='set null',
        tracking=True,
        help='Links vendor orders to the SBU job; receptions inherit this project.',
    )

    sbu_service_line_count = fields.Integer(
        string='Service lines',
        compute='_compute_sbu_logistics_line_mix',
        help='Lines with a service product (no stock receipt; project still links the PO).',
    )
    sbu_stock_line_count = fields.Integer(
        string='Stock lines',
        compute='_compute_sbu_logistics_line_mix',
        help='Consumable or storable product lines (expect stock moves when applicable).',
    )
    sbu_subcontract_line_count = fields.Integer(
        string='Subcontract lines',
        compute='_compute_sbu_logistics_line_mix',
        help='Lines whose product has a subcontract BOM for this vendor (when Manufacturing is installed).',
    )

    @api.depends(
        'order_line',
        'order_line.display_type',
        'order_line.product_id',
        'partner_id',
        'company_id',
    )
    def _compute_sbu_logistics_line_mix(self):
        Bom = self.env['mrp.bom'] if 'mrp.bom' in self.env else None
        for order in self:
            service = stock = subcontract = 0
            for line in order.order_line:
                if line.display_type in ('line_section', 'line_note'):
                    continue
                product = line.product_id
                if not product:
                    continue
                if 'detailed_type' in product._fields:
                    dtype = product.detailed_type
                else:
                    dtype = product.type
                if dtype == 'service':
                    service += 1
                elif dtype in ('consu', 'product', 'combo'):
                    stock += 1
                if (
                    Bom
                    and order.partner_id
                    and hasattr(Bom, '_bom_subcontract_find')
                ):
                    bom = Bom._bom_subcontract_find(
                        product,
                        picking_type=False,
                        company_id=order.company_id.id,
                        subcontractor=order.partner_id,
                    )
                    if bom:
                        subcontract += 1
            order.sbu_service_line_count = service
            order.sbu_stock_line_count = stock
            order.sbu_subcontract_line_count = subcontract

    def _prepare_picking(self):
        res = super()._prepare_picking()
        if self.project_id:
            res['project_id'] = self.project_id.id
        return res
