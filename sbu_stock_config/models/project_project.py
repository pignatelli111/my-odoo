# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    picking_ids = fields.One2many(
        'stock.picking',
        'project_id',
        string='Stock transfers',
    )
    picking_count = fields.Integer(compute='_compute_picking_count')
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'project_id',
        string='Purchase orders',
    )
    purchase_order_count = fields.Integer(compute='_compute_purchase_order_count')
    sbu_incoming_picking_count = fields.Integer(compute='_compute_sbu_logistics_counts')
    sbu_open_receipt_count = fields.Integer(compute='_compute_sbu_logistics_counts')

    sbu_logistics_state = fields.Selection(
        selection=[
            ('none', 'No material flow'),
            ('ordered', 'Ordered'),
            ('in_transit', 'In transit'),
            ('received', 'Received in warehouse'),
            ('site', 'On site'),
        ],
        string='Logistics',
        compute='_compute_sbu_logistics_state',
        help='Derived from purchase orders and pickings/deliveries linked to this job.',
    )

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for project in self:
            project.picking_count = len(project.picking_ids)

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for project in self:
            project.purchase_order_count = len(project.purchase_order_ids)

    @api.depends('picking_ids', 'picking_ids.state', 'picking_ids.picking_type_id')
    def _compute_sbu_logistics_counts(self):
        for project in self:
            incoming = project.picking_ids.filtered(
                lambda p: p.picking_type_id.code == 'incoming'
            )
            project.sbu_incoming_picking_count = len(incoming)
            project.sbu_open_receipt_count = len(
                incoming.filtered(lambda p: p.state not in ('done', 'cancel'))
            )

    @api.depends(
        'picking_ids.state',
        'picking_ids.picking_type_id',
        'picking_ids.move_ids.location_dest_id',
        'purchase_order_ids.state',
    )
    def _compute_sbu_logistics_state(self):
        site_loc = self.env.ref('sbu_stock_config.stock_location_sbu_site', raise_if_not_found=False)
        site_loc_ids = set()
        if site_loc:
            site_loc_ids = set(
                self.env['stock.location'].search([('id', 'child_of', site_loc.id)]).ids
            )

        for project in self:
            pickings = project.picking_ids
            has_site = False
            has_received = False
            for p in pickings.filtered(lambda x: x.state == 'done'):
                if p.picking_type_id.code == 'outgoing':
                    has_site = True
                    break
                if site_loc_ids:
                    for move in p.move_ids:
                        if move.location_dest_id.id in site_loc_ids:
                            has_site = True
                            break
                if p.picking_type_id.code == 'incoming':
                    has_received = True
                if has_site:
                    break

            has_transit = bool(
                pickings.filtered(
                    lambda x: x.state in ('assigned', 'waiting', 'confirmed')
                    and x.picking_type_id.code in ('incoming', 'outgoing', 'internal')
                )
            )
            has_ordered = bool(
                project.purchase_order_ids.filtered(lambda o: o.state in ('purchase', 'done'))
            )

            if has_site:
                project.sbu_logistics_state = 'site'
            elif has_received:
                project.sbu_logistics_state = 'received'
            elif has_transit:
                project.sbu_logistics_state = 'in_transit'
            elif has_ordered:
                project.sbu_logistics_state = 'ordered'
            else:
                project.sbu_logistics_state = 'none'

    def action_sbu_view_pickings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pickings & deliveries'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'search_view_id': self.env.ref('stock.view_picking_internal_search').id,
            'context': {'default_project_id': self.id},
        }

    def action_sbu_view_incoming_pickings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Receipts (incoming)'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [
                ('project_id', '=', self.id),
                ('picking_type_id.code', '=', 'incoming'),
            ],
            'search_view_id': self.env.ref('stock.view_picking_internal_search').id,
            'context': {
                'default_project_id': self.id,
                'search_default_sbu_incoming': 1,
            },
        }

    def action_sbu_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'search_view_id': self.env.ref('purchase.view_purchase_order_filter').id,
            'context': {'default_project_id': self.id},
        }

    def action_sbu_create_site_delivery(self, from_picking=None):
        """Internal transfer warehouse stock → SBU / Site for this job."""
        self.ensure_one()
        wh = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1
        )
        if not wh:
            raise UserError(_('No warehouse configured for company %s.') % self.company_id.display_name)
        site_loc = self.env.ref('sbu_stock_config.stock_location_sbu_site', raise_if_not_found=False)
        if not site_loc:
            raise UserError(_('SBU site location is not configured.'))
        stock_loc = wh.lot_stock_id
        picking_type = wh.int_type_id

        qty_by_product = defaultdict(float)
        source_pickings = self.picking_ids.filtered(
            lambda p: p.state == 'done' and p.picking_type_id.code == 'incoming'
        )
        if from_picking:
            source_pickings = from_picking.filtered(lambda p: p.state == 'done')
        for picking in source_pickings:
            for move in picking.move_ids:
                if move.product_id:
                    qty_by_product[move.product_id.id] += move.product_uom_qty

        if not qty_by_product:
            raise UserError(
                _('No received quantities on incoming transfers for this job. '
                  'Confirm the purchase receipt first.')
            )

        move_vals = []
        for product_id, qty in qty_by_product.items():
            product = self.env['product.product'].browse(product_id)
            move_vals.append((0, 0, {
                'name': product.display_name,
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': qty,
                'location_id': stock_loc.id,
                'location_dest_id': site_loc.id,
            }))

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': stock_loc.id,
            'location_dest_id': site_loc.id,
            'project_id': self.id,
            'origin': _('Site delivery %s') % (
                self.sbu_project_code if 'sbu_project_code' in self._fields and self.sbu_project_code
                else self.name
            ),
            'sbu_transport_reason': 'internal',
            'move_ids': move_vals,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }
