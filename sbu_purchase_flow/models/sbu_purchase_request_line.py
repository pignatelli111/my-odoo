from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
        string='Cod. articolo',
        help='COD. ARTICOLO (Excel); se vuoto si può usare il codice prodotto Odoo.',
    )
    width_mm = fields.Float(string='Larghezza L (mm)', digits=(16, 0))
    height_mm = fields.Float(string='Altezza H (mm)', digits=(16, 0))
    depth_mm = fields.Float(
        string='Profondità P (mm)',
        digits=(16, 0),
        help='Profondità non unitaria (spessore / pacco / vetro stratificato, ecc.).',
    )
    sqm_per_piece = fields.Float(string='MQ/cad', digits=(16, 4))
    sqm_total = fields.Float(string='MQ tot.', digits=(16, 4))
    dimension_mm = fields.Char(
        string='Dimensioni',
        compute='_compute_dimension_mm',
        store=True,
        help='Riepilogo L×H×P + mq/cad + mq tot.',
    )
    data_phase = fields.Selection(
        related='source_bom_line_id.data_phase',
        string='Fase dati',
        readonly=True,
    )
    needs_technical_confirm = fields.Boolean(
        related='source_bom_line_id.needs_technical_confirm',
        string='Needs technical confirm',
        readonly=True,
    )
    technical_confirmed = fields.Boolean(
        related='source_bom_line_id.technical_confirmed',
        string='Confirmed for PO',
        readonly=True,
    )
    utilization = fields.Char(
        string='Utilizzo',
        help='UTILIZZO (montante, profili, …).',
    )
    weight_kg = fields.Float(string='Peso Kg', digits=(16, 3))
    product_id = fields.Many2one('product.product', string='Product')
    product_qty = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure')
    product_uom = fields.Many2one(
        'uom.uom',
        string='Unit of measure',
        required=True,
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False),
    )
    date_required = fields.Date(
        string='Data consegna',
        help='DATA CONSEGNA richiesta (template RDA).',
    )
    destination = fields.Char(
        string='Destinazione',
        help='DESTINATION / DESTINAZIONE (es. lavorazione conto terzi).',
    )
    procurement_mode = fields.Selection(
        [
            ('purchase', 'Acquisto'),
            ('warehouse', 'Magazzino'),
        ],
        string='Approvvigionamento',
        help='MAGAZZINO vs ACQUISTO come ultima colonna del template RDA.',
    )
    note = fields.Char(string='Notes')
    line_priority = fields.Selection(
        [
            ('0', 'Normal'),
            ('1', 'Medium'),
            ('2', 'High'),
            ('3', 'Critical'),
        ],
        string='Priority',
        default='0',
        required=True,
        help='Line-level priority (defaults from request when exploding BOM).',
    )

    # ── Single BOM truth (Phase 3.1) ───────────────────────────────────────────
    source_bom_line_id = fields.Many2one(
        'sbu.estimate.bom.line',
        string='Distinta preventivo',
        ondelete='set null',
        index=True,
        help='Se impostata, la quantità può seguire la distinta ITEM (qty ordinata confezione).',
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

    @api.depends('offer_ids')
    def _compute_offer_count(self):
        for line in self:
            line.offer_count = len(line.offer_ids)

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

    def _sbu_po_line_dimension_vals(self):
        self.ensure_one()
        return {
            'sbu_width_mm': self.width_mm,
            'sbu_height_mm': self.height_mm,
            'sbu_depth_mm': self.depth_mm,
            'sbu_sqm_per_piece': self.sqm_per_piece,
            'sbu_sqm_total': self.sqm_total,
            'sbu_dimension_summary': self.dimension_mm,
        }

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
        dim_keys = {'width_mm', 'height_mm', 'depth_mm', 'sqm_per_piece', 'sqm_total'}
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
                    _('La riga distinta collegata non appartiene al preventivo della commessa (%s).')
                    % (est.display_name,)
                )
            dup = self.search_count([
                ('request_id', '=', line.request_id.id),
                ('source_bom_line_id', '=', line.source_bom_line_id.id),
                ('id', '!=', line.id),
            ])
            if dup:
                raise ValidationError(
                    _('Ogni riga distinta può essere collegata una sola volta per richiesta (duplicato: %s).')
                    % (line.source_bom_line_id.display_name,)
                )

    def action_refresh_qty_from_bom(self):
        for line in self:
            if line.bom_qty_sync and line.source_bom_line_id and line.request_id:
                bom = line.source_bom_line_id
                line.product_qty = line.request_id._sbu_demand_qty_from_bom(bom)
                line._sbu_apply_dimension_vals_from_bom(bom)
