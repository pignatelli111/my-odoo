from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SbuPurchaseRequestLine(models.Model):
    _name = 'sbu.purchase.request.line'
    _description = 'SBU Purchase Request Line'
    _order = 'sequence, id'

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
    dimension_mm = fields.Char(
        string='Dimensione mm',
        help='Es. L=6000 come nel template RDA.',
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
                line.product_qty = line.request_id._sbu_demand_qty_from_bom(line.source_bom_line_id)
