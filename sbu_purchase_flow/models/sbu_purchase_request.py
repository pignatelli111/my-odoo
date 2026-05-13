from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SbuPurchaseRequest(models.Model):
    _name = 'sbu.purchase.request'
    _description = 'SBU Purchase Request (RDA / ACO / ACP / …)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    request_type = fields.Selection(
        selection=[
            ('rda', 'RDA — Primary materials'),
            ('aco', 'ACO — Workshop accessories'),
            ('acp', 'ACP — Installation accessories'),
            ('lds', 'LDS — Shipping list'),
            ('fe', 'FE — Steel workshop'),
            ('st', 'ST — Brackets'),
            ('vt', 'VT — Glass'),
            ('other', 'Other'),
        ],
        string='Document type',
        required=True,
        default='rda',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project / Job',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Source estimate',
        readonly=True,
        related='project_id.sbu_estimate_id',
        store=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
    )
    line_ids = fields.One2many(
        'sbu.purchase.request.line',
        'request_id',
        string='Lines',
    )
    purchase_order_ids = fields.Many2many(
        'purchase.order',
        string='Related RFQs / POs',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.purchase.request') or _('New')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_create_rfq(self):
        """Create a draft purchase.order linked to this request (MVP)."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Add at least one line before creating an RFQ.'))
        if not self.line_ids.filtered('product_id'):
            raise UserError(_('At least one line must have a product to generate purchase lines.'))
        vendor = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=1)
        if not vendor:
            raise UserError(_('Create at least one vendor contact (supplier) before generating an RFQ.'))
        po = self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'origin': self.name,
            'company_id': self.company_id.id,
        })
        for line in self.line_ids:
            if not line.product_id:
                continue
            self.env['purchase.order.line'].create({
                'order_id': po.id,
                'product_id': line.product_id.id,
                'product_qty': line.product_qty,
                'product_uom_id': line.product_uom.id,
                'name': line.name or line.product_id.display_name,
                'date_planned': fields.Datetime.now(),
            })
        self.purchase_order_ids = [(4, po.id)]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
        }
