from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero

from odoo.addons.sbu_estimate.models.sbu_manual_input import SBU_MANUAL_INPUT_STATE

from .sbu_budget_helpers import sbu_cost_family_for_pr_line, sbu_cost_family_label
from .sbu_delivery_helpers import sbu_delivery_destination_for_line

SBU_PO_ACTIVE_STATES = ('draft', 'sent', 'to approve', 'purchase', 'done')
SBU_PO_DRAFT_STATES = ('draft', 'sent', 'to approve')


class SbuPurchaseRequestLine(models.Model):
    _name = 'sbu.purchase.request.line'
    _description = 'SBU Purchase Request Line'
    _order = 'line_priority desc, sequence, id'

    request_id = fields.Many2one(
        'sbu.purchase.request',
        string='Request',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    pos = fields.Char(
        string='Pos.',
        help='POS. — come colonna righe template RDA.',
    )
    name = fields.Char(string='Description', required=True)
    article_code = fields.Char(
        string='Item code',
        help='Excel item code; if empty, product internal reference may be used.',
    )
    width_mm = fields.Float(string='Width L (mm)', digits=(16, 0))
    height_mm = fields.Float(string='Height H (mm)', digits=(16, 0))
    depth_mm = fields.Float(
        string='Depth P (mm)',
        digits=(16, 0),
        help='Non-unit depth (thickness, pack, laminated glass, etc.).',
    )
    sqm_per_piece = fields.Float(string='Sqm/pc', digits=(16, 4))
    sqm_total = fields.Float(string='Sqm total', digits=(16, 4))
    dimension_mm = fields.Char(
        string='Dimensions',
        compute='_compute_dimension_mm',
        store=True,
        help='Riepilogo L×H×P + mq/cad + mq tot.',
    )
    data_phase = fields.Selection(
        related='source_bom_line_id.data_phase',
        string='Data phase',
        readonly=True,
    )
    needs_technical_confirm = fields.Boolean(
        related='source_bom_line_id.needs_technical_confirm',
        string='Needs technical confirm',
        readonly=True,
    )
    technical_confirmed = fields.Boolean(
        string='Confirmed for PO',
        compute='_compute_technical_confirmed',
        inverse='_inverse_technical_confirmed',
        readonly=False,
        help='Updates the linked estimate BOM (ITEM) row. '
             'Not stored: avoids full-table recompute on production upgrade (Odoo.sh RAM). '
             'Set on the estimate BOM tab if the line has no distinta link.',
    )

    @api.depends('source_bom_line_id.technical_confirmed')
    def _compute_technical_confirmed(self):
        for line in self:
            bom = line.source_bom_line_id
            line.technical_confirmed = bool(bom and bom.technical_confirmed)

    def _inverse_technical_confirmed(self):
        for line in self:
            if line.source_bom_line_id:
                line.source_bom_line_id.technical_confirmed = line.technical_confirmed
    manual_input_state = fields.Selection(
        selection=SBU_MANUAL_INPUT_STATE,
        string='Manual input status',
        compute='_compute_manual_input_state',
        store=True,
        readonly=True,
    )
    manual_input_pending = fields.Boolean(
        string='Needs manual entry',
        compute='_compute_manual_input_pending',
        store=True,
        readonly=True,
    )
    utilization = fields.Char(
        string='Utilization',
        help='Utilization (mullion, profiles, …).',
    )
    weight_kg = fields.Float(string='Weight kg', digits=(16, 3))
    product_id = fields.Many2one('product.product', string='Product')
    product_qty = fields.Float(
        string='Qty requested',
        default=1.0,
        digits='Product Unit of Measure',
        help='Quantità richiesta (distinta + perdita %% / MOQ / confezione). '
             'Non confondere con l’unità di misura (colonna U.M.).',
    )
    product_uom = fields.Many2one(
        'uom.uom',
        string='UoM',
        required=True,
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False),
    )
    po_line_ids = fields.One2many(
        'purchase.order.line',
        'sbu_pr_line_id',
        string='RFQ/PO lines',
    )
    qty_ordered = fields.Float(
        string='Qty on RFQ/PO',
        compute='_compute_qty_order_balance',
        store=True,
        digits='Product Unit of Measure',
        help='Somma quantità su righe ordine collegate (esclusi ordini annullati).',
    )
    qty_remaining = fields.Float(
        string='Qty remaining',
        compute='_compute_qty_order_balance',
        store=True,
        digits='Product Unit of Measure',
        help='Residuo da ordinare = quantità richiesta − quantità già su RFQ/PO.',
    )
    qty_fully_ordered = fields.Boolean(
        string='Fully ordered',
        compute='_compute_qty_order_balance',
        store=True,
    )
    qty_demand_hint = fields.Char(
        string='Qty breakdown',
        compute='_compute_qty_demand_hint',
        help='Spiega arrotondamenti distinta (es. 1 × 1,03 = 1,03 per +3%% perdita).',
    )
    date_required = fields.Date(
        string='Required delivery date',
        help='Required delivery date (RDA template).',
    )
    destination = fields.Char(
        string='Destination',
        help='Delivery destination (e.g. subcontract processing).',
    )
    procurement_mode = fields.Selection(
        [
            ('purchase', 'Purchase'),
            ('warehouse', 'Warehouse'),
        ],
        string='Procurement',
        help='Warehouse vs purchase (RDA template last column).',
    )
    note = fields.Char(string='Notes')
    line_priority = fields.Selection(
        [
            ('0', 'Normal'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Critical'),
        ],
        string='Line priority',
        default='0',
        required=True,
        help='Line-level priority (defaults from request when exploding BOM).',
    )

    # ── Single BOM truth (Phase 3.1) ───────────────────────────────────────────
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Source estimate',
        related='request_id.estimate_id',
        readonly=True,
    )
    source_bom_line_id = fields.Many2one(
        'sbu.estimate.bom.line',
        string='Estimate BOM line',
        ondelete='set null',
        index=True,
        domain="[('estimate_id', '=', estimate_id)]",
        help='When set, quantity can follow the ITEM BOM line (pack qty ordered).',
    )
    bom_qty_sync = fields.Boolean(
        string='Sync qty with BOM',
        default=True,
        help='If set, quantity follows demand rules from the linked BOM line (loss %%, packs, MOQ).',
    )
    bom_qty_ordered_ref = fields.Float(
        related='source_bom_line_id.qty_ordered',
        string='BOM qty (pack)',
        digits=(16, 3),
    )
    offer_ids = fields.One2many(
        'sbu.purchase.request.offer',
        'request_line_id',
        string='Supplier offers',
    )
    offer_count = fields.Integer(
        string='# Offers',
        compute='_compute_offer_count',
    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        to_fill = lines.filtered(lambda ln: not ln.destination)
        if to_fill:
            to_fill._sbu_apply_delivery_standard(overwrite=False)
        return lines

    def _sbu_apply_delivery_standard(self, overwrite=False):
        """Fill DESTINAZIONE from company rules + job logistics (Cosimo point 17).

        Returns (updated_count, skipped_lines) where each skip dict has keys:
        name, cost_family, cost_family_label, route, reason.
        """
        updated = 0
        skipped = []
        for line in self:
            if line.destination and not overwrite:
                skipped.append({
                    'name': line.name or line.product_id.display_name,
                    'cost_family': sbu_cost_family_for_pr_line(line),
                    'route': (line.workflow_route or line.request_id.workflow_route or '').strip() or '—',
                    'reason': 'already_set',
                })
                continue
            dest = sbu_delivery_destination_for_line(
                self.env, line, overwrite=overwrite,
            )
            if dest:
                line.destination = dest
                updated += 1
            else:
                fam = sbu_cost_family_for_pr_line(line)
                skipped.append({
                    'name': line.name or line.product_id.display_name,
                    'cost_family': fam,
                    'cost_family_label': sbu_cost_family_label(self.env, fam),
                    'route': (line.workflow_route or line.request_id.workflow_route or '').strip() or '—',
                    'reason': 'no_rule',
                })
        return updated, skipped

    @api.depends('offer_ids')
    def _compute_offer_count(self):
        for line in self:
            line.offer_count = len(line.offer_ids)

    @api.depends(
        'product_qty',
        'product_uom',
        'po_line_ids.product_qty',
        'po_line_ids.order_id.state',
    )
    def _compute_qty_order_balance(self):
        for line in self:
            active_lines = line.po_line_ids.filtered(
                lambda pol: pol.order_id.state in SBU_PO_ACTIVE_STATES and not pol.display_type
            )
            ordered = sum(active_lines.mapped('product_qty'))
            rounding = line.product_uom.rounding if line.product_uom else 0.01
            line.qty_ordered = ordered
            remaining = (line.product_qty or 0.0) - ordered
            if float_compare(remaining, 0.0, precision_rounding=rounding) <= 0:
                line.qty_remaining = 0.0
                line.qty_fully_ordered = True
            else:
                line.qty_remaining = remaining
                line.qty_fully_ordered = False

    @api.depends(
        'product_qty',
        'source_bom_line_id',
        'source_bom_line_id.qty_theoretical',
        'source_bom_line_id.demand_loss_pct',
        'request_id.demand_loss_pct',
        'bom_qty_sync',
    )
    def _compute_qty_demand_hint(self):
        for line in self:
            bom = line.source_bom_line_id
            req = line.request_id
            if not bom or not line.bom_qty_sync:
                line.qty_demand_hint = False
                continue
            theoretical = bom.qty_theoretical or 0.0
            loss = bom.demand_loss_pct if bom.demand_loss_pct else (req.demand_loss_pct or 0.0)
            if float_is_zero(theoretical, precision_digits=3):
                line.qty_demand_hint = _('From BOM')
                continue
            if loss:
                line.qty_demand_hint = _(
                    '%(theo)s × (1 + %(loss)s%%) = %(qty)s (perdita fabbisogno)'
                ) % {
                    'theo': theoretical,
                    'loss': loss,
                    'qty': line.product_qty,
                }
            else:
                line.qty_demand_hint = _('BOM theoretical: %(theo)s → requested %(qty)s') % {
                    'theo': theoretical,
                    'qty': line.product_qty,
                }

    @api.constrains('product_qty', 'qty_ordered', 'product_uom')
    def _check_product_qty_not_below_ordered(self):
        if self.env.context.get('sbu_skip_pr_qty_check'):
            return
        for line in self:
            rounding = line.product_uom.rounding if line.product_uom else 0.01
            if float_compare(
                line.product_qty,
                line.qty_ordered,
                precision_rounding=rounding,
            ) < 0:
                raise ValidationError(
                    _(
                        'La quantità richiesta (%.2f) non può essere inferiore alla quantità '
                        'già su RFQ/PO (%.2f) per «%s».'
                    )
                    % (line.product_qty, line.qty_ordered, line.display_name)
                )

    @api.depends(
        'source_bom_line_id.manual_input_state',
        'needs_technical_confirm',
        'width_mm',
        'height_mm',
    )
    def _compute_manual_input_state(self):
        for line in self:
            bom = line.source_bom_line_id
            if bom:
                line.manual_input_state = bom.manual_input_state
            elif line.needs_technical_confirm:
                line.manual_input_state = 'pending'
            elif not line.width_mm and not line.height_mm:
                line.manual_input_state = 'pending'
            else:
                line.manual_input_state = 'auto'

    @api.depends(
        'manual_input_state',
        'width_mm',
        'height_mm',
        'depth_mm',
        'product_qty',
        'date_required',
        'article_code',
    )
    def _compute_manual_input_pending(self):
        for line in self:
            if line.manual_input_state != 'pending':
                line.manual_input_pending = False
                continue
            line.manual_input_pending = (
                not line.width_mm
                or not line.height_mm
                or not line.product_qty
                or not line.date_required
            )

    @api.depends('width_mm', 'height_mm', 'depth_mm', 'sqm_per_piece', 'sqm_total')
    def _compute_dimension_mm(self):
        from odoo.addons.sbu_estimate.models.sbu_dimension_format import format_sbu_dimensions
        for line in self:
            line.dimension_mm = format_sbu_dimensions(
                width_mm=line.width_mm,
                height_mm=line.height_mm,
                depth_mm=line.depth_mm,
                sqm_per_piece=line.sqm_per_piece,
                sqm_total=line.sqm_total,
            )

    def _sbu_qty_remaining_to_order(self):
        """Live residual (qty richiesta − somma RFQ/PO); safe before stored compute is flushed."""
        self.ensure_one()
        active_lines = self.po_line_ids.filtered(
            lambda pol: pol.order_id.state in SBU_PO_ACTIVE_STATES and not pol.display_type
        )
        ordered = sum(active_lines.mapped('product_qty'))
        rounding = self.product_uom.rounding if self.product_uom else 0.01
        remaining = (self.product_qty or 0.0) - ordered
        if float_compare(remaining, 0.0, precision_rounding=rounding) <= 0:
            return 0.0
        return remaining

    def _sbu_po_line_dimension_vals(self):
        self.ensure_one()
        vals = {
            'sbu_width_mm': self.width_mm,
            'sbu_height_mm': self.height_mm,
            'sbu_depth_mm': self.depth_mm,
            'sbu_sqm_per_piece': self.sqm_per_piece,
            'sbu_sqm_total': self.sqm_total,
            'sbu_dimension_summary': self.dimension_mm,
        }
        if 'sbu_utilization' in self.env['purchase.order.line']._fields:
            vals['sbu_utilization'] = self.utilization or False
        return vals

    def _sbu_propagate_dimensions_to_po_lines(self):
        Pol = self.env['purchase.order.line']
        for pr_line in self:
            po_lines = Pol.search([
                ('sbu_pr_line_id', '=', pr_line.id),
                ('order_id.state', 'in', ('draft', 'sent', 'to approve')),
            ])
            if po_lines:
                po_lines.write(pr_line._sbu_po_line_dimension_vals())

    def write(self, vals):
        res = super().write(vals)
        dim_keys = {
            'width_mm', 'height_mm', 'depth_mm', 'sqm_per_piece', 'sqm_total', 'utilization',
        }
        if dim_keys & set(vals.keys()):
            self._sbu_propagate_dimensions_to_po_lines()
        return res

    @api.onchange('product_id')
    def _onchange_product_id_article(self):
        for line in self:
            if line.product_id and not line.article_code:
                line.article_code = line.product_id.default_code or ''

    @api.onchange('source_bom_line_id')
    def _onchange_source_bom_line_id(self):
        for line in self:
            bom = line.source_bom_line_id
            if not bom:
                continue
            line.product_id = bom.product_id
            line.product_uom = bom.uom_id
            line.product_qty = line.request_id._sbu_demand_qty_from_bom(bom)
            line.bom_qty_sync = True
            line.name = (bom.description or (bom.product_id.display_name if bom.product_id else '')) or line.name
            eline = bom.estimate_line_id
            if eline and eline.pos:
                line.pos = eline.pos
            if bom.product_id and not line.article_code:
                line.article_code = bom.product_id.default_code or ''
            line._sbu_apply_dimension_vals_from_bom(bom)

    def _sbu_apply_dimension_vals_from_bom(self, bom):
        if not bom or not hasattr(bom, '_sbu_purchase_line_dimension_vals'):
            return
        for key, val in bom._sbu_purchase_line_dimension_vals().items():
            if key in self._fields:
                self[key] = val

    @api.constrains('request_id', 'source_bom_line_id')
    def _check_bom_link_constraints(self):
        for line in self:
            bom = line.source_bom_line_id
            if not bom:
                continue
            est = line.request_id.estimate_id
            if est and bom.estimate_line_id.estimate_id != est:
                raise ValidationError(
                    _('Linked BOM line does not belong to the job estimate (%s).')
                    % (est.display_name,)
                )
            dup = self.search_count([
                ('request_id', '=', line.request_id.id),
                ('source_bom_line_id', '=', line.source_bom_line_id.id),
                ('id', '!=', line.id),
            ])
            if dup:
                raise ValidationError(
                    _('Each BOM line can be linked only once per request (duplicate: %s).')
                    % (line.source_bom_line_id.display_name,)
                )

    def action_refresh_qty_from_bom(self):
        for line in self.with_context(sbu_skip_pr_qty_check=True):
            if line.bom_qty_sync and line.source_bom_line_id and line.request_id:
                bom = line.source_bom_line_id
                self.env.flush_all()
                bom.invalidate_recordset(['qty_theoretical', 'qty_ordered'])
                line.product_qty = line.request_id._sbu_demand_qty_from_bom(bom)
                line._sbu_apply_dimension_vals_from_bom(bom)

    def _sbu_draft_po_lines(self, purchase_order):
        """Draft RFQ lines on ``purchase_order`` linked to this RDA line."""
        self.ensure_one()
        return self.po_line_ids.filtered(
            lambda pol: (
                pol.order_id == purchase_order
                and pol.order_id.state in SBU_PO_DRAFT_STATES
                and not pol.display_type
            )
        )

    def _sbu_upsert_rfq_po_line(self, purchase_order, qty):
        """Create or update a single draft PO line with ``qty`` (residual to order)."""
        self.ensure_one()
        Pol = self.env['purchase.order.line']
        po = purchase_order
        if float_is_zero(qty, precision_rounding=self.product_uom.rounding):
            return Pol.browse()
        draft_lines = self._sbu_draft_po_lines(po)
        if len(draft_lines) > 1:
            draft_lines[1:].unlink()
            draft_lines = draft_lines[:1]
        if draft_lines:
            draft_lines.write({'product_qty': qty})
            return draft_lines
        parts = []
        if self.pos:
            parts.append(f'[{self.pos}]')
        if self.article_code:
            parts.append(self.article_code)
        if self.dimension_mm:
            parts.append(self.dimension_mm)
        prefix = ' '.join(parts) + ' — ' if parts else ''
        desc = (self.name or self.product_id.display_name).strip()
        planned = fields.Datetime.now()
        if self.date_required:
            planned = fields.Datetime.to_datetime(self.date_required)
        offer = self.request_id._sbu_offer_for_po_line(po.partner_id, self)
        pol_vals = {
            'order_id': po.id,
            'product_id': self.product_id.id,
            'product_qty': qty,
            'product_uom_id': self.product_uom.id,
            'name': prefix + desc,
            'date_planned': planned,
            'sbu_pr_line_id': self.id,
        }
        if offer:
            pol_vals['sbu_offer_id'] = offer.id
            if offer.unit_price:
                pol_vals['price_unit'] = offer.unit_price
        pol_vals.update(self._sbu_po_line_dimension_vals())
        return Pol.create(pol_vals)
