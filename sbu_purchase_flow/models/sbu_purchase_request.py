from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .sbu_workflow_routing import (
    SBU_WORKFLOW_ROUTE_SELECTION,
    bom_product_workflow_route,
    estimate_line_matches_route,
    workflow_route_to_request_type,
)


class SbuPurchaseRequest(models.Model):
    _name = 'sbu.purchase.request'
    _description = 'SBU Purchase Request (RDA / ACO / ACP / …)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    workflow_route = fields.Selection(
        selection=SBU_WORKFLOW_ROUTE_SELECTION,
        string='Percorso / route',
        index=True,
        tracking=True,
        help='Codice ANACO (LA, LZ, ST, PAN, OSC, VC/VS, …). Usare il wizard «Nuovo documento» '
             'per evitare tipi incoerenti.',
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
    priority = fields.Selection(
        [
            ('0', 'Normal'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Critical'),
        ],
        string='Priorità testata',
        default='0',
        required=True,
        tracking=True,
        index=True,
        help='Operational priority for RDA / ACP / ACO / LDS follow-up.',
    )
    need_by_date = fields.Date(
        string='Need by',
        tracking=True,
        index=True,
        help='Target date for materials / deliverables on this request.',
    )
    site_required_date = fields.Date(
        string='Site / install date',
        tracking=True,
        help='Optional date when goods must be on site (ACP / ACO / LDS).',
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
        help='Used when «RFQ vendors» is empty: one draft RFQ is created for this supplier.',
    )
    vendor_ids = fields.Many2many(
        'res.partner',
        'sbu_purchase_request_vendor_rel',
        'request_id',
        'partner_id',
        string='RFQ vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Multi-vendor RFQ: one draft purchase order per supplier. If empty, the preferred vendor is used.',
    )
    offer_comparison_markup_pct = fields.Float(
        string='Offer comparison markup %',
        default=4.0,
        digits=(16, 2),
        tracking=True,
        help='Applied to captured unit prices in «Evaluated price» for comparison (+4%% buffer).',
    )
    comparison_margin_buffer_pct = fields.Float(
        string='Comparison margin buffer %',
        default=3.0,
        digits=(16, 2),
        tracking=True,
        help='Added to «Margin impact (pp)» for side-by-side comparison (+3%% typical buffer).',
    )
    offer_ids = fields.One2many(
        'sbu.purchase.request.offer',
        'request_id',
        string='Supplier offers',
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
    demand_loss_pct = fields.Float(
        string='Default demand loss %',
        default=3.0,
        digits=(16, 2),
        tracking=True,
        help='Wastage %% applied when exploding BOM to demand lines (used for BOM components with loss %% = 0).',
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
        string='Request lines',
    )
    purchase_order_ids = fields.Many2many(
        'purchase.order',
        string='Related RFQs / POs',
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'sbu_purchase_request_attachment_rel',
        'request_id',
        'attachment_id',
        string='Supporting files',
        help='Drawings, supplier PDFs, e-mail extracts (in addition to chatter).',
    )
    submitted_date = fields.Datetime(
        string='Submitted on',
        readonly=True,
        copy=False,
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved by',
        readonly=True,
        copy=False,
    )
    approved_date = fields.Datetime(
        string='Approved on',
        readonly=True,
        copy=False,
    )
    date_done = fields.Datetime(
        string='Closed on',
        readonly=True,
        copy=False,
    )
    cancel_reason = fields.Text(
        string='Cancel / reject notes',
        copy=False,
        help='Reason when cancelling or rolling back (operational audit).',
    )
    technical_data_state = fields.Selection(
        [
            ('estimate_bom', 'Stima da distinta ANACO'),
            ('technical_review', 'Revisione documento tecnico'),
            ('ready_for_po', 'Pronto per RFQ/PO'),
        ],
        string='Dati tecnici',
        default='estimate_bom',
        tracking=True,
        help='ANACO/distinta = stima; dopo documento consulente (RDA/ACO/ACP…) → pronto per ordine.',
    )

    def _sbu_loss_pct_for_bom_line(self, bom):
        """Per-component loss overrides request default when > 0."""
        self.ensure_one()
        if bom.demand_loss_pct and bom.demand_loss_pct > 0:
            return bom.demand_loss_pct
        return self.demand_loss_pct or 0.0

    def _sbu_supplier_moq(self, product):
        """Minimum order qty from product supplierinfo (optional preferred vendor)."""
        self.ensure_one()
        if not product:
            return 0.0
        company = self.company_id
        tmpl = product.product_tmpl_id
        sellers = tmpl.seller_ids.filtered(
            lambda s: (not s.company_id or s.company_id == company) and s.min_qty
        )
        if self.vendor_id:
            sellers = sellers.filtered(lambda s: s.partner_id == self.vendor_id)
        if not sellers:
            return 0.0
        return max(sellers.mapped('min_qty'))

    def _sbu_demand_qty_from_bom(self, bom):
        """Same ITEM rules as distinta; request loss %% when BOM line loss is 0."""
        self.ensure_one()
        BomLine = self.env['sbu.estimate.bom.line']
        loss_pct = self._sbu_loss_pct_for_bom_line(bom)
        moq = bom.demand_moq or 0.0
        if moq <= 0:
            moq = self._sbu_supplier_moq(bom.product_id) or 0.0
        return BomLine._sbu_apply_demand_qty_rules(
            bom.qty_theoretical,
            loss_pct=loss_pct,
            moq=moq,
            pack_size=bom.pack_size or 0.0,
        )

    @api.onchange('workflow_route')
    def _onchange_workflow_route(self):
        if self.workflow_route:
            self.request_type = workflow_route_to_request_type(self.workflow_route)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.purchase.request') or _('New')
            route = vals.get('workflow_route')
            if route and not vals.get('request_type'):
                vals['request_type'] = workflow_route_to_request_type(route)
        return super().create(vals_list)

    def action_submit(self):
        self.write({
            'state': 'submitted',
            'submitted_date': fields.Datetime.now(),
        })

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })

    def action_done(self):
        self.write({
            'state': 'done',
            'date_done': fields.Datetime.now(),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({
            'state': 'draft',
            'approved_by_id': False,
            'approved_date': False,
            'submitted_date': False,
            'date_done': False,
            'cancel_reason': False,
        })

    def action_start_technical_review(self):
        self.write({'technical_data_state': 'technical_review'})
        self.message_post(
            body=_(
                'Revisione tecnica avviata: aggiornare misure/costi da documento consulente '
                '(Excel RDA/ACO/ACP o DWG/DF) e confermare le righe distinta collegate.'
            ),
        )

    def action_mark_ready_for_po(self):
        for req in self:
            pending = req.line_ids.filtered(
                lambda l: l.source_bom_line_id
                and l.source_bom_line_id.needs_technical_confirm
                and not l.source_bom_line_id.technical_confirmed
            )
            if pending:
                names = ', '.join(pending.mapped('display_name')[:5])
                raise UserError(
                    _(
                        'Confermare le righe distinta prima del PO. '
                        'Righe in attesa: %(names)s',
                        names=names,
                    )
                )
            req.write({'technical_data_state': 'ready_for_po'})
            req.message_post(
                body=_('Dati tecnici confermati: si possono creare RFQ/PO con misure finali.'),
            )

    def _sbu_check_ready_for_po(self):
        self.ensure_one()
        if self.technical_data_state == 'ready_for_po':
            return
        raise UserError(
            _(
                'I documenti tecnici (RDA/ACO/ACP/VT…) devono essere applicati prima del PO. '
                'Usare «Avvia revisione tecnica», aggiornare misure sulle righe distinta, '
                'spuntare «Confermato per PO», poi «Pronto per RFQ/PO».'
            )
        )

    def action_view_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.project_id.display_name,
            'res_model': 'project.project',
            'res_id': self.project_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_load_lines_from_estimate_bom_append(self):
        return self._load_lines_from_estimate_bom(clear=False)

    def action_load_lines_from_estimate_bom_replace(self):
        return self._load_lines_from_estimate_bom(clear=True)

    def action_refresh_all_bom_quantities(self):
        self.line_ids.action_refresh_qty_from_bom()
        self.line_ids._sbu_propagate_dimensions_to_po_lines()
        self.message_post(body=_('Quantities and dimensions refreshed from estimate BOM / RDA lines.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_bulk_update_lines(self):
        """Open bulk wizard for all lines on this request."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Apply to selected lines'),
            'res_model': 'sbu.purchase.request.line.bulk.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_line_ids': [(6, 0, self.line_ids.ids)],
            },
        }

    def action_open_offer_comparison_matrix(self):
        """Pivot/list on supplier offers (matrix: line × vendor, measures)."""
        self.ensure_one()
        pivot_id = self.env.ref('sbu_purchase_flow.view_sbu_purchase_request_offer_pivot').id
        list_id = self.env.ref('sbu_purchase_flow.view_sbu_purchase_request_offer_list_matrix').id
        search_id = self.env.ref('sbu_purchase_flow.view_sbu_purchase_request_offer_search').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Supplier comparison'),
            'res_model': 'sbu.purchase.request.offer',
            'view_mode': 'pivot,list',
            'views': [(pivot_id, 'pivot'), (list_id, 'list')],
            'search_view_id': search_id,
            'domain': [('request_id', '=', self.id)],
            'context': {
                'default_request_id': self.id,
            },
        }

    def _load_lines_from_estimate_bom(self, clear=False, workflow_route=None):
        self.ensure_one()
        estimate = self.estimate_id
        if not estimate:
            raise UserError(_('The project has no linked source estimate (won estimate).'))
        if clear:
            self.line_ids.unlink()
        existing_bom = {bid for bid in self.line_ids.mapped('source_bom_line_id').ids if bid}
        Line = self.env['sbu.purchase.request.line']
        created = 0
        route_filter = workflow_route or self.workflow_route
        for eline in estimate.line_ids:
            if route_filter and not estimate_line_matches_route(eline, route_filter):
                continue
            pos = eline.pos or ''
            for bom in eline.bom_line_ids:
                if not bom.product_id:
                    continue
                if route_filter in ('OSC', 'ZANZ', 'VC/VS'):
                    bom_route = bom_product_workflow_route(bom)
                    if bom_route and bom_route != route_filter:
                        continue
                    if route_filter == 'VC/VS' and bom_route in ('OSC', 'ZANZ'):
                        continue
                if bom.id in existing_bom:
                    continue
                existing_bom.add(bom.id)
                line_vals = {
                    'request_id': self.id,
                    'source_bom_line_id': bom.id,
                    'bom_qty_sync': True,
                    'product_id': bom.product_id.id,
                    'product_uom': bom.uom_id.id,
                    'product_qty': self._sbu_demand_qty_from_bom(bom),
                    'name': bom.description or bom.product_id.display_name,
                    'pos': pos,
                    'article_code': bom.product_id.default_code or '',
                    'procurement_mode': 'purchase',
                    'line_priority': self.priority,
                }
                if hasattr(bom, '_sbu_purchase_line_dimension_vals'):
                    line_vals.update(bom._sbu_purchase_line_dimension_vals())
                Line.create(line_vals)
                created += 1
        self.message_post(
            body=_('Loaded %(n)d demand line(s) from estimate BOM (loss %%, packs, MOQ).') % {'n': created}
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _sbu_offer_for_po_line(self, partner, pr_line):
        """Prefer chosen offer for this vendor & line, else any offer from that vendor."""
        self.ensure_one()
        Offer = self.env['sbu.purchase.request.offer']
        base = [
            ('request_line_id', '=', pr_line.id),
            ('vendor_id', '=', partner.id),
        ]
        chosen = Offer.search(base + [('is_chosen', '=', True)], limit=1)
        if chosen:
            return chosen
        return Offer.search(base, limit=1)

    def _sbu_create_rfq_po_lines(self, po, pr_lines):
        """Append purchase.order.line rows from PR lines onto ``po``."""
        Pol = self.env['purchase.order.line']
        for line in pr_lines:
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
            planned = fields.Datetime.now()
            if line.date_required:
                planned = fields.Datetime.to_datetime(line.date_required)
            offer = self._sbu_offer_for_po_line(po.partner_id, line)
            pol_vals = {
                'order_id': po.id,
                'product_id': line.product_id.id,
                'product_qty': line.product_qty,
                'product_uom_id': line.product_uom.id,
                'name': prefix + desc,
                'date_planned': planned,
                'sbu_pr_line_id': line.id,
            }
            if offer:
                pol_vals['sbu_offer_id'] = offer.id
                if offer.unit_price:
                    pol_vals['price_unit'] = offer.unit_price
            pol_vals.update(line._sbu_po_line_dimension_vals())
            Pol.create(pol_vals)

    def _sbu_rfq_vendor_partners(self):
        """Partners to receive draft RFQs (explicit PR choice wins over supplier_rank filter)."""
        self.ensure_one()
        vendors = (self.vendor_ids | self.vendor_id).filtered('id')
        if vendors:
            # Quick-created UAT contacts may lack supplier_rank; trust explicit PR selection.
            to_fix = vendors.filtered(lambda p: not p.supplier_rank)
            if to_fix:
                to_fix.write({'supplier_rank': 1})
            return vendors
        return self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=1)

    def action_create_rfq(self):
        """Create one draft purchase.order per RFQ vendor (multi-vendor RFQ)."""
        self.ensure_one()
        self._sbu_check_ready_for_po()
        self.line_ids.action_refresh_qty_from_bom()
        if not self.line_ids:
            raise UserError(_('Add at least one line before creating an RFQ.'))
        if not self.line_ids.filtered('product_id'):
            raise UserError(_('At least one line must have a product to generate purchase lines.'))
        vendors = self._sbu_rfq_vendor_partners()
        if not vendors:
            raise UserError(
                _('Set «RFQ vendors» and/or a preferred vendor on this request, '
                  'or create a supplier contact (Purchase tab: Vendor) before generating RFQs.')
            )
        Po = self.env['purchase.order']
        created = Po.browse()
        for vendor in vendors:
            po_vals = {
                'partner_id': vendor.id,
                'origin': _('%s — %s') % (self.name, vendor.name),
                'company_id': self.company_id.id,
                'sbu_purchase_request_id': self.id,
            }
            if 'project_id' in Po._fields:
                po_vals['project_id'] = self.project_id.id
            po = Po.create(po_vals)
            self._sbu_create_rfq_po_lines(po, self.line_ids)
            created |= po
        for po in created:
            self.purchase_order_ids = [(4, po.id)]
        if len(created) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': created.id,
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Draft RFQs'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
            'target': 'current',
        }
