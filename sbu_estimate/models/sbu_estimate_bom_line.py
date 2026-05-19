import math

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SbuEstimateBomLine(models.Model):
    """
    The ITEM sheet in ANACO — the 'lavoraccio'.
    Each line is one component of the BOM for one estimate line.
    In Odoo this is calculated automatically from dimensions.
    """
    _name = 'sbu.estimate.bom.line'
    _description = 'SBU Estimate BOM Line (ITEM sheet)'
    _order = 'sequence'

    estimate_line_id = fields.Many2one(
        'sbu.estimate.line',
        string='Riga Preventivo',
        required=True,
        ondelete='cascade',
    )
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)

    # ── Product ───────────────────────────────────────────────────────────────
    product_id = fields.Many2one(
        'product.product',
        string='Prodotto / Componente',
        required=True,
    )
    product_category_id = fields.Many2one(
        related='product_id.categ_id',
        string='Categoria',
        store=True,
    )
    description = fields.Char(
        string='Descrizione',
        compute='_compute_description',
        store=True,
        readonly=False,
    )

    # ── Calculation type ──────────────────────────────────────────────────────
    calc_type = fields.Selection([
        ('lump_sum', 'A Corpo (Lump Sum)'),
        ('per_piece', 'A Pezzo (Nr/Pz)'),
        ('linear', 'Lineare (ml)'),
        ('surface', 'A Superficie (mq)'),
        ('pack', 'A Confezione (Pack/Kit)'),
    ], string='Tipo Calcolo', required=True, default='per_piece')

    # ── Dimension source ──────────────────────────────────────────────────────
    dimension_source = fields.Selection([
        ('width', 'Larghezza (B)'),
        ('height', 'Altezza (H)'),
        ('perimeter', 'Perimetro (2B+2H)'),
        ('surface', 'Superficie (B×H)'),
        ('manual', 'Manuale'),
    ], string='Fonte Dimensione', default='manual')

    # ── Quantity calculation ──────────────────────────────────────────────────
    qty_formula_factor = fields.Float(
        string='Fattore Formula',
        default=1.0,
        digits=(16, 4),
        help='Moltiplicatore applicato alla dimensione calcolata',
    )
    qty_theoretical = fields.Float(
        string='Quantità Teorica',
        compute='_compute_qty',
        store=True,
        digits=(16, 3),
    )
    pack_size = fields.Float(
        string='Confezione Minima',
        digits=(16, 3),
        help='Quantità minima acquistabile (es. 6m per barra, 10pz per scatola)',
    )
    demand_loss_pct = fields.Float(
        string='Perdita demand %',
        digits=(16, 2),
        default=0.0,
        help='Scarto applicato alla quantità distinta per generare la domanda (0 = usa %% della richiesta acquisto). Es. 3 = +3%%.',
    )
    demand_moq = fields.Float(
        string='MOQ demand',
        digits=(16, 3),
        default=0.0,
        help='Quantità minima d\'ordine per questa voce (0 = prova dal fornitore preferito sul prodotto).',
    )
    qty_ordered = fields.Float(
        string='Quantità da Ordinare',
        compute='_compute_qty',
        store=True,
        digits=(16, 3),
        help='Arrotondato alla confezione minima',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='U.M.',
        required=True,
    )

    # ── Pricing ───────────────────────────────────────────────────────────────
    unit_cost = fields.Float(
        string='Costo Unitario',
        digits=(16, 4),
    )
    total_cost = fields.Float(
        string='Costo Totale',
        compute='_compute_total_cost',
        store=True,
        digits=(16, 2),
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    note = fields.Char(string='Note / Utilizzo')

    @api.model_create_multi
    def create(self, vals_list):
        Line = self.env['sbu.estimate.line']
        for vals in vals_list:
            eline = Line.browse(vals['estimate_line_id']) if vals.get('estimate_line_id') else Line
            if vals.get('estimate_line_id') and not vals.get('estimate_id'):
                vals['estimate_id'] = eline.estimate_id.id
            elif vals.get('estimate_id') and not vals.get('estimate_line_id'):
                est = self.env['sbu.estimate'].browse(vals['estimate_id'])
                if len(est.line_ids) == 1:
                    vals['estimate_line_id'] = est.line_ids.id
                    vals['estimate_id'] = est.id
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'estimate_line_id' in vals:
            for bom in self:
                if bom.estimate_line_id:
                    bom.estimate_id = bom.estimate_line_id.estimate_id
        return res

    @api.constrains('estimate_line_id', 'estimate_id')
    def _check_estimate_matches_line(self):
        for bom in self:
            if (
                bom.estimate_line_id
                and bom.estimate_id
                and bom.estimate_line_id.estimate_id != bom.estimate_id
            ):
                raise ValidationError(
                    _('BOM line must belong to the same preventivo as its ANACO row.')
                )

    # ── Computed: description from product ───────────────────────────────────
    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            line.description = line.product_id.name or ''

    # ── Computed: quantities ──────────────────────────────────────────────────
    @api.depends(
        'calc_type', 'dimension_source', 'qty_formula_factor', 'pack_size',
        'estimate_line_id.width_mm', 'estimate_line_id.height_mm',
        'estimate_line_id.qty',
    )
    def _compute_qty(self):
        for line in self:
            parent = line.estimate_line_id
            if not parent:
                line.qty_theoretical = 0.0
                line.qty_ordered = 0.0
                continue

            b_mm = parent.width_mm or 0.0
            h_mm = parent.height_mm or 0.0
            qty_items = parent.qty or 1.0
            factor = line.qty_formula_factor or 1.0

            if line.calc_type == 'lump_sum':
                # Fixed quantity regardless of dimensions
                theoretical = factor * qty_items

            elif line.calc_type == 'per_piece':
                theoretical = factor * qty_items

            elif line.calc_type == 'linear':
                # Convert mm to m based on dimension source
                if line.dimension_source == 'width':
                    dim_m = b_mm / 1000.0
                elif line.dimension_source == 'height':
                    dim_m = h_mm / 1000.0
                elif line.dimension_source == 'perimeter':
                    dim_m = (2 * b_mm + 2 * h_mm) / 1000.0
                else:
                    dim_m = 0.0
                theoretical = dim_m * factor * qty_items

            elif line.calc_type == 'surface':
                # Convert mm² to m²
                sqm = (b_mm * h_mm) / 1_000_000.0
                theoretical = sqm * factor * qty_items

            elif line.calc_type == 'pack':
                # Calculate theoretical then round up to pack size
                theoretical = factor * qty_items

            else:
                theoretical = 0.0

            line.qty_theoretical = theoretical

            # Round up to minimum pack size
            if line.pack_size and line.pack_size > 0:
                line.qty_ordered = math.ceil(theoretical / line.pack_size) * line.pack_size
            else:
                line.qty_ordered = theoretical

    # ── Computed: total cost ──────────────────────────────────────────────────
    @api.depends('qty_ordered', 'unit_cost')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = line.qty_ordered * line.unit_cost
