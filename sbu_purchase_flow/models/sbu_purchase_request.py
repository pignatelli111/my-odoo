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
    vendor_id = fields.Many2one(
        'res.partner',
        string='Preferred vendor',
        domain=[('supplier_rank', '>', 0)],
        tracking=True,
        help='Used as supplier when generating a draft RFQ (Excel: main supplier for the request).',
    )
    # Header fields aligned with RDA/ACP/ACO Excel templates (row «Project», signatures, topic)
    excel_item = fields.Char(
        string='Item (foglio Excel)',
        help='Colonna «item» del modello RDA (es. FT, LA01).',
    )
    topic = fields.Char(
        string='Topic / Argomento',
        help='TOPIC / ARGOMENTO come nel template RDA.',
    )
    drawn_by = fields.Char(
        string='Redatto da',
        help='Drawn by / Redatto da (come scheda RDA o SOTTOMISSIONE).',
    )
    check_by = fields.Char(
        string='Verificato da',
        help='Check by / Verificato da.',
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

    def action_load_lines_from_estimate_bom_append(self):
        return self._load_lines_from_estimate_bom(clear=False)

    def action_load_lines_from_estimate_bom_replace(self):
        return self._load_lines_from_estimate_bom(clear=True)

    def action_refresh_all_bom_quantities(self):
        self.line_ids.action_refresh_qty_from_bom()
        self.message_post(body=_('Quantities refreshed from estimate BOM lines.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _load_lines_from_estimate_bom(self, clear=False):
        self.ensure_one()
        estimate = self.estimate_id
        if not estimate:
            raise UserError(_('The project has no linked source estimate (won estimate).'))
        if clear:
            self.line_ids.unlink()
        existing_bom = {bid for bid in self.line_ids.mapped('source_bom_line_id').ids if bid}
        Line = self.env['sbu.purchase.request.line']
        created = 0
        for eline in estimate.line_ids:
            pos = eline.pos or ''
            for bom in eline.bom_line_ids:
                if not bom.product_id:
                    continue
                if bom.id in existing_bom:
                    continue
                existing_bom.add(bom.id)
                Line.create({
                    'request_id': self.id,
                    'source_bom_line_id': bom.id,
                    'bom_qty_sync': True,
                    'product_id': bom.product_id.id,
                    'product_uom': bom.uom_id.id,
                    'product_qty': bom.qty_ordered,
                    'name': bom.description or bom.product_id.display_name,
                    'pos': pos,
                    'article_code': bom.product_id.default_code or '',
                    'procurement_mode': 'purchase',
                })
                created += 1
        self.message_post(
            body=_('Loaded %(n)d purchase line(s) from estimate BOM.') % {'n': created}
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_rfq(self):
        """Create a draft purchase.order linked to this request (MVP)."""
        self.ensure_one()
        self.line_ids.action_refresh_qty_from_bom()
        if not self.line_ids:
            raise UserError(_('Add at least one line before creating an RFQ.'))
        if not self.line_ids.filtered('product_id'):
            raise UserError(_('At least one line must have a product to generate purchase lines.'))
        vendor = self.vendor_id
        if not vendor or not vendor.supplier_rank:
            vendor = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=1)
        if not vendor:
            raise UserError(_('Set a preferred vendor on the request or create at least one vendor contact (supplier) before generating an RFQ.'))
        po = self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'origin': self.name,
            'company_id': self.company_id.id,
        })
        for line in self.line_ids:
            if not line.product_id:
                continue
            parts = []
            if line.pos:
                parts.append(f'[{line.pos}]')
            if line.article_code:
                parts.append(line.article_code)
            if line.dimension_mm:
                parts.append(line.dimension_mm)
            prefix = ' '.join(parts) + ' — ' if parts else ''
            desc = (line.name or line.product_id.display_name).strip()
            self.env['purchase.order.line'].create({
                'order_id': po.id,
                'product_id': line.product_id.id,
                'product_qty': line.product_qty,
                'product_uom_id': line.product_uom.id,
                'name': prefix + desc,
                'date_planned': fields.Datetime.now(),
            })
        self.purchase_order_ids = [(4, po.id)]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
        }
