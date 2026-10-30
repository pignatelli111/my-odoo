# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from .sbu_anaco_bom import ANACO_LINE_FIELD_TO_PRODUCT_CODE
from .sbu_anaco_engine import ANACO_OVERHEADS

_OVERHEAD_LABELS = {cad_field: label for _pct, cad_field, _tot, _cc, _tc, label in ANACO_OVERHEADS}


class SbuEstimateColumnSupplier(models.Model):
    """Supplier of one ANACO cost column (e.g. PVC windows, glass, installation) for an estimate."""
    _name = 'sbu.estimate.column.supplier'
    _description = 'Supplier per ANACO column'
    _order = 'sequence, id'

    estimate_id = fields.Many2one('sbu.estimate', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer()
    column_field = fields.Char(string='ANACO column field', required=True, readonly=True)
    name = fields.Char(string='ANACO column', readonly=True)
    product_id = fields.Many2one('product.product', string='BOM product', readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Supplier',
        help='Purchase requests and RFQs for this column go to this supplier.',
    )
    currency_id = fields.Many2one(related='estimate_id.currency_id')
    column_total = fields.Monetary(string='Column total', compute='_compute_column_total', currency_field='currency_id')

    _sbu_column_supplier_uniq = models.Constraint(
        'unique(estimate_id, column_field)',
        'Each ANACO column has one supplier row per estimate.',
    )

    @api.depends('estimate_id.line_ids', 'column_field')
    def _compute_column_total(self):
        for row in self:
            lines = row.estimate_id.line_ids
            field = row.column_field
            if field in lines._fields and field.endswith('_cad'):
                row.column_total = sum((line[field] or 0.0) * (line.qty or 0.0) for line in lines)
            else:
                row.column_total = 0.0


class SbuEstimate(models.Model):
    _inherit = 'sbu.estimate'

    column_supplier_ids = fields.One2many(
        'sbu.estimate.column.supplier', 'estimate_id', string='Suppliers per ANACO column',
    )

    def action_sbu_prepare_column_suppliers(self):
        """One row per ANACO column used by the estimate; suppliers already chosen are kept."""
        Product = self.env['product.product']
        products = {
            (p.default_code or '').strip().upper(): p
            for p in Product.search([('default_code', 'in', list(ANACO_LINE_FIELD_TO_PRODUCT_CODE.values()))])
        }
        for estimate in self:
            labels = estimate._sbu_anaco_labels()
            existing = {row.column_field: row for row in estimate.column_supplier_ids}
            lines = estimate.line_ids
            for sequence, (field, code) in enumerate(ANACO_LINE_FIELD_TO_PRODUCT_CODE.items()):
                if field not in lines._fields or not any(lines.mapped(field)):
                    continue
                vals = {
                    'sequence': sequence,
                    'name': labels.get(field) or _OVERHEAD_LABELS.get(field) or lines._fields[field].string,
                    'product_id': products.get(code.upper(), Product).id,
                }
                if field in existing:
                    existing[field].write(vals)
                else:
                    self.env['sbu.estimate.column.supplier'].create(
                        dict(vals, estimate_id=estimate.id, column_field=field))
        return True

    def _sbu_create_bom_from_anaco_lines(self):
        self.action_sbu_prepare_column_suppliers()
        return super()._sbu_create_bom_from_anaco_lines()

    def _sbu_column_supplier_for_product(self, product):
        self.ensure_one()
        return self.column_supplier_ids.filtered(lambda row: row.product_id == product)[:1].partner_id


class SbuEstimateBomLine(models.Model):
    _inherit = 'sbu.estimate.bom.line'

    vendor_id = fields.Many2one(
        'res.partner', string='Supplier', compute='_compute_vendor_id', store=True, readonly=False,
        help='From the estimate "Suppliers per ANACO column"; can be changed on a single line.',
    )

    @api.depends('product_id', 'estimate_id.column_supplier_ids.partner_id', 'estimate_id.column_supplier_ids.product_id')
    def _compute_vendor_id(self):
        for line in self:
            estimate = line.estimate_id
            line.vendor_id = estimate._sbu_column_supplier_for_product(line.product_id) if estimate else False
