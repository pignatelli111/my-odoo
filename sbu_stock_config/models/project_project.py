# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


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

    sbu_logistics_state = fields.Selection(
        selection=[
            ('none', 'No material flow'),
            ('ordered', 'Ordered'),
            ('in_transit', 'In transit'),
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
            for p in pickings.filtered(lambda x: x.state == 'done'):
                if p.picking_type_id.code == 'outgoing':
                    has_site = True
                    break
                if site_loc_ids:
                    for move in p.move_ids:
                        if move.location_dest_id.id in site_loc_ids:
                            has_site = True
                            break
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
            'context': {'default_project_id': self.id},
        }

    def action_sbu_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
