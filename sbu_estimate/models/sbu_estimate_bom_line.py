import math

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .sbu_manual_input import SBU_MANUAL_INPUT_STATE


class SbuEstimateBomLine(models.Model):
    """
    The ITEM sheet in ANACO — the 'lavoraccio'.
    Each line is one component of the BOM for one estimate line.
    In Odoo this is calculated automatically from dimensions.
    """
    _name = 'sbu.estimate.bom.line'
    _description = 'SBU Estimate BOM Line (ITEM sheet)'
    _order = 'sequence'
    _rec_name = 'name'

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
    name = fields.Char(
        string='Distinta ITEM',
        compute='_compute_name',
        store=True,
        index=True,
        help='Readable label for dropdowns (position, product, dimensions, qty).',
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
        help='Moltiplicatore applicato alla dimensione calcolata (es. 0,9 = 90%% mq vetro su posizione).',
    )
    sqm_coverage_factor = fields.Float(
        string='Fattore mq posizione',
        default=1.0,
        digits=(16, 4),
        help='Per vetro: tipicamente 0,9 (90%% dei mq totali della posizione).',
    )
    height_adjust_mm = fields.Float(
        string='Aggiunta H (mm)',
        default=0.0,
        digits=(16, 0),
        help='Sommata all\'altezza posizione (es. +300 mm zanzariere/oscuranti).',
    )
    depth_mm = fields.Float(
        string='Profondità (mm)',
        digits=(16, 0),
        help='Profondità non unitaria (P), da documento tecnico o manuale.',
    )
    width_mm_effective = fields.Float(
        string='Larghezza eff. (mm)',
        compute='_compute_effective_dimensions',
        store=True,
        digits=(16, 0),
    )
    height_mm_effective = fields.Float(
        string='Altezza eff. (mm)',
        compute='_compute_effective_dimensions',
        store=True,
        digits=(16, 0),
    )
    sqm_per_piece_effective = fields.Float(
        string='MQ/cad eff.',
        compute='_compute_effective_dimensions',
        store=True,
        digits=(16, 4),
    )
    dimension_display = fields.Char(
        string='Dimensioni',
        compute='_compute_effective_dimensions',
        store=True,
        help='L×H effettivi e mq/cad per RDA/RFQ.',
    )
    data_phase = fields.Selection(
        [
            ('estimate', 'Stima ANACO'),
            ('logikal', 'Bozza Logikal'),
            ('technical', 'Documento tecnico'),
        ],
        string='Fase dati',
        default='estimate',
        required=True,
        help='Stima preventivo → bozza Logikal → misure finali da consulente (RDA/ACO/ACP…).',
    )
    needs_technical_confirm = fields.Boolean(
        string='Richiede conferma tecnica',
        default=False,
        help='Se attivo, la RDA non può passare a «Pronto per PO» finché non è confermato.',
    )
    technical_confirmed = fields.Boolean(
        string='Confermato per PO',
        default=False,
        help='Spunta dopo revisione disegni / documento tecnico del consulente.',
    )
    manual_input_state = fields.Selection(
        selection=SBU_MANUAL_INPUT_STATE,
        string='Manual input status',
        compute='_compute_manual_input_state',
        store=True,
        help='Green list cells when «pending»; gray when «imported» (Logikal / technical file).',
    )
    manual_input_pending = fields.Boolean(
        string='Needs manual entry',
        compute='_compute_manual_input_pending',
        store=True,
    )
    manual_dim_pending = fields.Boolean(
        string='Dimensions need entry',
        compute='_compute_manual_dim_pending',
        store=True,
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

    @api.model
    def _sbu_vals_from_dimension_rule(self, product, estimate_line):
        """Apply vetro 90% / zanzariere +300 mm rules on create (not only onchange)."""
        if not product:
            return {}
        from .sbu_bom_dimension_rules import bom_rule_for_product_and_line
        rule = bom_rule_for_product_and_line(product, estimate_line)
        if not rule:
            return {}
        cov = rule.get('sqm_coverage_factor', 1.0)
        return {
            'calc_type': rule.get('calc_type'),
            'dimension_source': rule.get('dimension_source'),
            'sqm_coverage_factor': cov,
            'qty_formula_factor': cov,
            'height_adjust_mm': rule.get('height_adjust_mm', 0.0),
            'needs_technical_confirm': rule.get('needs_technical_confirm', False),
            'note': rule.get('note') or False,
        }

    @api.model_create_multi
    def create(self, vals_list):
        Line = self.env['sbu.estimate.line']
        Product = self.env['product.product']
        for vals in vals_list:
            eline = Line.browse(vals['estimate_line_id']) if vals.get('estimate_line_id') else Line
            if vals.get('estimate_line_id') and not vals.get('estimate_id'):
                vals['estimate_id'] = eline.estimate_id.id
            elif vals.get('estimate_id') and not vals.get('estimate_line_id'):
                est = self.env['sbu.estimate'].browse(vals['estimate_id'])
                if len(est.line_ids) == 1:
                    vals['estimate_line_id'] = est.line_ids.id
                    vals['estimate_id'] = est.id
            product = Product.browse(vals['product_id']) if vals.get('product_id') else Product
            rule_vals = self._sbu_vals_from_dimension_rule(product, eline)
            for key, value in rule_vals.items():
                if value is not False and key not in vals:
                    vals[key] = value
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

    @api.depends(
        'estimate_line_id.pos',
        'estimate_line_id.name',
        'product_id',
        'product_id.default_code',
        'product_id.name',
        'description',
        'dimension_display',
        'qty_theoretical',
        'calc_type',
        'uom_id',
    )
    def _compute_name(self):
        calc_labels = dict(self._fields['calc_type'].selection)
        for bom in self:
            parts = []
            pos = (bom.estimate_line_id.pos or '').strip()
            if pos:
                parts.append(pos)
            code = (bom.product_id.default_code or '').strip()
            desc = (bom.description or bom.product_id.display_name or '').strip()
            if len(desc) > 48:
                desc = desc[:45] + '...'
            if code and desc:
                parts.append('[%s] %s' % (code, desc))
            elif code:
                parts.append('[%s]' % code)
            elif desc:
                parts.append(desc)
            if bom.dimension_display:
                parts.append(bom.dimension_display)
            qty = bom.qty_theoretical or 0.0
            if qty:
                uom = (bom.uom_id.name or '').strip()
                calc = calc_labels.get(bom.calc_type, '') or ''
                qty_part = '%g %s' % (qty, uom) if uom else '%g' % qty
                if calc:
                    qty_part = '%s (%s)' % (qty_part, calc)
                parts.append(qty_part)
            bom.name = ' — '.join(parts) if parts else _('BOM line %s') % (bom.id or _('new'))

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Search by position, product code, description, or stored label."""
        domain = list(domain or [])
        term = (name or '').strip()
        if term:
            search_domain = [
                '|', '|', '|', '|',
                ('name', operator, term),
                ('description', operator, term),
                ('product_id.default_code', operator, term),
                ('estimate_line_id.pos', operator, term),
                ('estimate_line_id.name', operator, term),
            ] + domain
            records = self.search(search_domain, limit=limit)
            return [(rec.id, rec._sbu_label_for_many2one()) for rec in records.sudo()]
        return super().name_search(name, domain, operator, limit)

    def _sbu_label_for_many2one(self):
        """Safe label for dropdowns (never empty / undefined)."""
        self.ensure_one()
        return (self.name or self.display_name or _('BOM line %s') % self.id)

    @api.onchange('product_id', 'estimate_line_id')
    def _onchange_product_id_apply_dimension_rule(self):
        for line in self:
            if not line.product_id:
                continue
            rule = line._sbu_rule_for_product()
            if not rule:
                continue
            line.calc_type = rule.get('calc_type', line.calc_type)
            line.dimension_source = rule.get('dimension_source', line.dimension_source)
            cov = rule.get('sqm_coverage_factor', 1.0)
            line.sqm_coverage_factor = cov
            line.qty_formula_factor = cov
            line.height_adjust_mm = rule.get('height_adjust_mm', 0.0)
            line.needs_technical_confirm = rule.get('needs_technical_confirm', False)
            if rule.get('note'):
                line.note = rule['note']

    def _sbu_rule_for_product(self):
        self.ensure_one()
        from .sbu_bom_dimension_rules import bom_rule_for_product_and_line
        return bom_rule_for_product_and_line(self.product_id, self.estimate_line_id)

    def _sbu_purchase_line_dimension_vals(self):
        """Values to copy onto sbu.purchase.request.line from this BOM line."""
        self.ensure_one()
        parent = self.estimate_line_id
        qty_pos = parent.qty if parent else 1.0
        sqm_tot = (self.sqm_per_piece_effective or 0.0) * qty_pos
        return {
            'width_mm': self.width_mm_effective,
            'height_mm': self.height_mm_effective,
            'depth_mm': self.depth_mm or 0.0,
            'sqm_per_piece': self.sqm_per_piece_effective,
            'sqm_total': sqm_tot,
            'dimension_mm': self.dimension_display,
        }

    @api.model
    def _sbu_apply_demand_qty_rules(self, theoretical, loss_pct=0.0, moq=0.0, pack_size=0.0):
        """ITEM demand: scrap %, then MOQ, then round up to pack size."""
        qty = theoretical or 0.0
        if loss_pct:
            qty = qty * (1.0 + loss_pct / 100.0)
        if moq > 0:
            qty = max(qty, moq)
        if pack_size > 0:
            qty = math.ceil(qty / pack_size) * pack_size
        return qty

    def _sbu_qty_after_demand_rules(self, theoretical):
        """Apply this BOM line's demand_loss_pct, demand_moq, and pack_size."""
        self.ensure_one()
        return self._sbu_apply_demand_qty_rules(
            theoretical,
            loss_pct=self.demand_loss_pct or 0.0,
            moq=self.demand_moq or 0.0,
            pack_size=self.pack_size or 0.0,
        )

    @api.depends(
        'estimate_line_id.width_mm',
        'estimate_line_id.height_mm',
        'height_adjust_mm',
        'depth_mm',
        'sqm_coverage_factor',
        'calc_type',
        'estimate_line_id.qty',
    )
    def _compute_effective_dimensions(self):
        for line in self:
            parent = line.estimate_line_id
            if not parent:
                line.width_mm_effective = 0.0
                line.height_mm_effective = 0.0
                line.sqm_per_piece_effective = 0.0
                line.dimension_display = ''
                continue
            b_mm = parent.width_mm or 0.0
            h_mm = (parent.height_mm or 0.0) + (line.height_adjust_mm or 0.0)
            p_mm = line.depth_mm or 0.0
            line.width_mm_effective = b_mm
            line.height_mm_effective = h_mm
            if b_mm and h_mm:
                sqm_raw = (b_mm * h_mm) / 1_000_000.0
                cov = line.sqm_coverage_factor or 1.0
                line.sqm_per_piece_effective = sqm_raw * cov
            else:
                line.sqm_per_piece_effective = 0.0
            line.dimension_display = line._sbu_format_dimension_display(b_mm, h_mm, p_mm)

    def _sbu_format_dimension_display(self, b_mm, h_mm, p_mm):
        from .sbu_dimension_format import format_sbu_dimensions
        qty_pos = self.estimate_line_id.qty if self.estimate_line_id else 1.0
        sqm_tot = (self.sqm_per_piece_effective or 0.0) * qty_pos
        text = format_sbu_dimensions(
            width_mm=b_mm,
            height_mm=h_mm,
            depth_mm=p_mm,
            sqm_per_piece=self.sqm_per_piece_effective,
            sqm_total=sqm_tot,
        )
        if text:
            return text
        if self.height_adjust_mm and self.estimate_line_id.height_mm:
            return _('H %(h0).0f+%(adj).0f mm (completare B/H posizione)', h0=self.estimate_line_id.height_mm, adj=self.height_adjust_mm)
        return _('Misure posizione da completare (B/H ANACO)')

    # ── Computed: quantities ──────────────────────────────────────────────────
    @api.depends(
        'calc_type', 'dimension_source', 'qty_formula_factor', 'sqm_coverage_factor',
        'height_adjust_mm', 'pack_size',
        'demand_loss_pct', 'demand_moq',
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
            h_mm = (parent.height_mm or 0.0) + (line.height_adjust_mm or 0.0)
            qty_items = parent.qty or 1.0
            factor = line.qty_formula_factor or line.sqm_coverage_factor or 1.0

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
                # mm² → m²; factor = coverage (e.g. 0.9 glass) on position
                if b_mm and h_mm:
                    sqm = (b_mm * h_mm) / 1_000_000.0
                    theoretical = sqm * factor * qty_items
                else:
                    theoretical = factor * qty_items

            elif line.calc_type == 'pack':
                theoretical = factor * qty_items

            else:
                theoretical = 0.0

            line.qty_theoretical = theoretical
            line.qty_ordered = line._sbu_qty_after_demand_rules(theoretical)

    def _sbu_parent_dimensions_incomplete(self):
        """True when BOM calc needs parent B/H but ANACO row is still empty."""
        self.ensure_one()
        parent = self.estimate_line_id
        if not parent:
            return self.dimension_source == 'manual'
        if self.calc_type == 'surface':
            return not parent.width_mm or not parent.height_mm
        if self.calc_type == 'linear':
            return not parent.width_mm
        return False

    @api.depends(
        'needs_technical_confirm',
        'technical_confirmed',
        'data_phase',
        'dimension_source',
        'calc_type',
        'unit_cost',
        'estimate_line_id.width_mm',
        'estimate_line_id.height_mm',
    )
    def _compute_manual_input_state(self):
        for line in self:
            if line.technical_confirmed:
                line.manual_input_state = 'ok'
            elif line.data_phase in ('technical', 'logikal'):
                line.manual_input_state = 'imported'
            elif line.needs_technical_confirm or line.dimension_source == 'manual':
                line.manual_input_state = 'pending'
            elif line.calc_type == 'lump_sum' and not line.unit_cost:
                line.manual_input_state = 'pending'
            elif line._sbu_parent_dimensions_incomplete():
                line.manual_input_state = 'pending'
            else:
                line.manual_input_state = 'auto'

    @api.depends('manual_input_state')
    def _compute_manual_input_pending(self):
        for line in self:
            line.manual_input_pending = line.manual_input_state == 'pending'

    @api.depends(
        'manual_input_pending',
        'estimate_line_id.width_mm',
        'estimate_line_id.height_mm',
        'depth_mm',
        'dimension_source',
        'calc_type',
    )
    def _compute_manual_dim_pending(self):
        for line in self:
            line.manual_dim_pending = (
                line.manual_input_pending
                and (
                    line._sbu_parent_dimensions_incomplete()
                    or (line.dimension_source == 'manual' and not line.depth_mm)
                )
            )

    # ── Computed: total cost ──────────────────────────────────────────────────
    @api.depends('qty_ordered', 'unit_cost')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = line.qty_ordered * line.unit_cost
