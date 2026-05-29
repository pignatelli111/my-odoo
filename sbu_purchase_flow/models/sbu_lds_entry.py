# -*- coding: utf-8 -*-
"""TMS LDS shipping register (M.4.4.A reg_LDS sheet)."""
from odoo import fields, models, api

from .sbu_tms_helpers import resolve_tms_uom


class SbuLdsEntry(models.Model):
    _name = 'sbu.lds.entry'
    _description = 'SBU LDS shipping register entry'
    _order = 'delivery_date desc, lds_number, pos'

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project / Job',
        required=True,
        ondelete='cascade',
        index=True,
    )
    lds_number = fields.Char(string='LDS number', index=True)
    delivery_date = fields.Date(string='Delivery date')
    pos = fields.Char(string='Pos.')
    route_type = fields.Char(string='RT')
    product_type = fields.Char(string='Product type')
    reference_rda = fields.Char(string='Ref. RDA')
    reference_acp = fields.Char(string='Ref. ACP')
    reference_aco = fields.Char(string='Ref. ACO')
    order_number = fields.Char(string='Order n°')
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase order',
        ondelete='set null',
    )
    description = fields.Char(string='Description')
    article_code = fields.Char(string='Article code')
    product_qty = fields.Float(string='Qty', digits='Product Unit of Measure', default=1.0)
    product_uom = fields.Many2one(
        'uom.uom',
        string='UoM',
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False),
    )
    material_present = fields.Boolean(string='Material present')
    expected_date = fields.Date(string='Expected date')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('expected', 'Expected'),
            ('delivered', 'Delivered'),
            ('checked', 'Checked'),
        ],
        string='Status',
        default='draft',
    )
    note = fields.Char(string='Notes')

    @api.model
    def import_tms_rows(self, project, rows, update_mode='merge'):
        """Create or update LDS register rows from TMS reg_LDS sheet."""
        created = updated = 0
        for row in rows:
            domain = [('project_id', '=', project.id)]
            if row.get('lds_number'):
                domain.append(('lds_number', '=', row['lds_number']))
            if row.get('pos'):
                domain.append(('pos', '=', row['pos']))
            existing = self.search(domain, limit=1) if update_mode == 'merge' else self.browse()
            vals = {
                'project_id': project.id,
                'lds_number': row.get('lds_number') or False,
                'delivery_date': row.get('delivery_date') or False,
                'pos': row.get('pos') or False,
                'route_type': row.get('route_type') or False,
                'product_type': row.get('product_type') or False,
                'reference_rda': row.get('reference_rda') or False,
                'reference_acp': row.get('reference_acp') or False,
                'reference_aco': row.get('reference_aco') or False,
                'order_number': row.get('order_number') or False,
                'description': row.get('description') or False,
                'article_code': row.get('article_code') or False,
                'product_qty': row.get('product_qty') or 1.0,
                'material_present': bool(row.get('material_present')),
                'expected_date': row.get('expected_date') or False,
                'note': row.get('note') or False,
            }
            uom_code = row.get('product_uom_code')
            if uom_code:
                uom = resolve_tms_uom(self.env, uom_code)
                if uom:
                    vals['product_uom'] = uom.id
            if existing:
                existing.write(vals)
                updated += 1
            else:
                self.create(vals)
                created += 1
        return {'created': created, 'updated': updated}
