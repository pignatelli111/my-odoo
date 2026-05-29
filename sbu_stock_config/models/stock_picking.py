# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    project_id = fields.Many2one(
        'project.project',
        string='Job / project',
        index=True,
        ondelete='set null',
        tracking=True,
        help='SBU job this transfer belongs to (incoming from PO, internal, or deliveries).',
    )
    sbu_ddt_number = fields.Char(
        string='DDT number',
        copy=False,
        tracking=True,
        help='Transport document number (aligned with paper DDT from the carrier).',
    )
    sbu_carrier_name = fields.Char(string='Carrier / vettore')
    sbu_vehicle_plate = fields.Char(string='Vehicle plate')
    sbu_transport_reason = fields.Selection(
        selection=[
            ('purchase', 'Purchase / supply to warehouse'),
            ('sale', 'Delivery to customer / site'),
            ('internal', 'Internal transfer'),
            ('return', 'Return'),
            ('other', 'Other'),
        ],
        string='Transport reason',
        default='purchase',
    )

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._sbu_sync_project_from_sources()
        pickings._sbu_default_transport_reason()
        return pickings

    def write(self, vals):
        res = super().write(vals)
        if 'move_ids' in vals or 'move_line_ids' in vals:
            self._sbu_sync_project_from_sources()
        return res

    def _sbu_default_transport_reason(self):
        for picking in self:
            if picking.sbu_transport_reason:
                continue
            code = picking.picking_type_id.code
            if code == 'incoming':
                picking.sbu_transport_reason = 'purchase'
            elif code == 'outgoing':
                picking.sbu_transport_reason = 'sale'
            elif code == 'internal':
                picking.sbu_transport_reason = 'internal'

    def _sbu_sync_project_from_sources(self):
        """Fill project_id on pickings when missing (service/subcontract/MRP paths)."""
        for picking in self.filtered(lambda p: not p.project_id):
            project = picking._sbu_project_from_moves()
            if project:
                picking.project_id = project

    def _sbu_project_from_moves(self):
        self.ensure_one()
        for move in self.move_ids:
            pol = move.purchase_line_id
            if pol and pol.order_id.project_id:
                return pol.order_id.project_id
        for move in self.move_ids:
            mo = False
            if 'raw_material_production_id' in move._fields and move.raw_material_production_id:
                mo = move.raw_material_production_id
            elif 'production_id' in move._fields and move.production_id:
                mo = move.production_id
            if mo and 'project_id' in mo._fields and mo.project_id:
                return mo.project_id
        return False

    def _sbu_assign_ddt_number_if_missing(self):
        seq = self.env['ir.sequence'].next_by_code
        for picking in self:
            if picking.sbu_ddt_number:
                continue
            if picking.picking_type_id.code not in ('incoming', 'outgoing', 'internal'):
                continue
            picking.sbu_ddt_number = seq('sbu.stock.ddt') or picking.name

    def button_validate(self):
        self._sbu_assign_ddt_number_if_missing()
        return super().button_validate()

    def action_sbu_print_ddt(self):
        self.ensure_one()
        report = self.env.ref('sbu_stock_config.action_report_sbu_ddt')
        return report.with_context(discard_logo_check=True).report_action(self)

    def action_sbu_deliver_to_site(self):
        """Create internal transfer Stock → Site cantiere for done incoming qty on this job."""
        self.ensure_one()
        if not self.project_id:
            raise UserError(_('Set the job / project on this transfer first.'))
        return self.project_id.action_sbu_create_site_delivery(from_picking=self)
