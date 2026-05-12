from odoo import models, fields, api


class SbuEstimateLine(models.Model):
    _name = 'sbu.estimate.line'
    _description = 'SBU Estimate Line (ANACO row)'
    _order = 'sequence, pos'

    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)

    # ── Position / Identity ───────────────────────────────────────────────────
    pos = fields.Char(string='Pos.', help='Posizione item (es. FTF, FT, LA01)')
    item_code = fields.Char(string='Codice Item')
    description = fields.Text(string='Descrizione', required=True)
    note = fields.Text(string='Note')

    # ── Dimensions (from ANACO: B, H, Mq) ────────────────────────────────────
    qty = fields.Float(string='Qt.', default=1.0, digits=(16, 2))
    width_mm = fields.Float(string='B (mm)', digits=(16, 0))
    height_mm = fields.Float(string='H (mm)', digits=(16, 0))
    sqm = fields.Float(
        string='Mq.',
        compute='_compute_sqm',
        store=True,
        digits=(16, 3),
        help='Calcolato automaticamente: B × H / 1.000.000 × Qt.',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='U.M.',
    )

    # ── Discount / commission ─────────────────────────────────────────────────
    commission_pct = fields.Float(string='Comm. %', digits=(16, 2))
    discount_sc1 = fields.Float(string='Sc 1 %', digits=(16, 2))
    discount_sc2 = fields.Float(string='Sc 2 %', digits=(16, 2))
    discount_sc3 = fields.Float(string='Sc 3 %', digits=(16, 2))

    # ── PRICE columns (selling side — from ANACO) ─────────────────────────────
    price_serramento_cad = fields.Float(string='Serramento Scontato CAD', digits=(16, 2))
    price_oscuramento_cad = fields.Float(string='Oscuramento Scontato CAD', digits=(16, 2))
    price_automatismo_cad = fields.Float(string='Automatismo CAD', digits=(16, 2))
    price_zanzariera_cad = fields.Float(string='Zanzariera CAD', digits=(16, 2))
    price_vetro_cad = fields.Float(string='Vetro CAD', digits=(16, 2))
    price_pannello_cad = fields.Float(string='Pannello CAD', digits=(16, 2))
    price_controtelaio_cad = fields.Float(string='Controtelaio CAD', digits=(16, 2))
    price_trasformazione_cad = fields.Float(string='Trasformazione CAD', digits=(16, 2))
    price_accessori_cad = fields.Float(string='Accessori Maniglie CAD', digits=(16, 2))
    price_kit_avvolgimento_cad = fields.Float(string='Kit Avvolgimento CAD', digits=(16, 2))
    price_smontaggio_cad = fields.Float(string='Smontaggio/Posa CAD', digits=(16, 2))
    price_nolo_cad = fields.Float(string='Nolo CAD', digits=(16, 2))
    price_cassonetto_cad = fields.Float(string='Cassonetto CAD', digits=(16, 2))

    # Computed price totals
    price_total_cad = fields.Float(
        string='Prezzo Cliente CAD',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
    )
    price_total_tot = fields.Float(
        string='Prezzo Cliente TOT',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
    )
    price_per_sqm = fields.Float(
        string='Prezzo Cliente MQ',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
    )

    # ── COST columns (buying side — from ANACO) ───────────────────────────────
    cost_coibentazione_cad = fields.Float(string='Coibentazione CAD', digits=(16, 2))
    cost_posa_lamiera_lin_cad = fields.Float(string='Posa Lamiera LIN CAD', digits=(16, 2))
    cost_industrial_pct = fields.Float(
        string='Costi Industriali %',
        digits=(16, 2),
        help='% su costi materiale',
    )
    cost_tech_pm_cad = fields.Float(string='Sviluppo Tecnico/PM CAD', digits=(16, 2))
    cost_mol_pct = fields.Float(
        string='MOL %',
        digits=(16, 2),
        help='Margine Operativo Lordo su base costi materiale',
    )
    cost_trasporto_cad = fields.Float(string='Trasporto/Imballo CAD', digits=(16, 2))
    cost_cantiere_cad = fields.Float(string='Presidio Cantiere/Site Mng CAD', digits=(16, 2))
    cost_staffame_cad = fields.Float(string='ST/LZ Staffame CAD', digits=(16, 2))
    cost_extra_cad = fields.Float(string='Extra CAD', digits=(16, 2))

    # Computed cost totals
    cost_total_cad = fields.Float(
        string='Costo Materiale Lavorato e Posato CAD',
        compute='_compute_cost_totals',
        store=True,
        digits=(16, 2),
    )
    cost_total_tot = fields.Float(
        string='Costo Materiale Lavorato e Posato TOT',
        compute='_compute_cost_totals',
        store=True,
        digits=(16, 2),
    )
    cost_per_sqm = fields.Float(
        string='Costo MQ',
        compute='_compute_cost_totals',
        store=True,
        digits=(16, 2),
    )

    # ── Budget tracking (per item — from ANACO budget columns) ────────────────
    budget_orders_issued = fields.Float(string='Ordini Emessi', digits=(16, 2))
    budget_costs_incurred = fields.Float(string='Costi Sostenuti', digits=(16, 2))
    budget_to_fulfill = fields.Float(
        string='Da Evadere',
        compute='_compute_budget',
        store=True,
        digits=(16, 2),
    )
    budget_pct_paid = fields.Float(
        string='% Pagati su Ordine',
        compute='_compute_budget',
        store=True,
        digits=(16, 2),
    )
    budget_order_progress_pct = fields.Float(
        string='% Ordine Avanzamento',
        compute='_compute_budget',
        store=True,
        digits=(16, 2),
    )
    budget_residual = fields.Float(
        string='Disponibilità Residua su Ordine',
        compute='_compute_budget',
        store=True,
        digits=(16, 2),
    )
    budget_vs_estimate_pct = fields.Float(
        string='% su Preventivato',
        compute='_compute_budget',
        store=True,
        digits=(16, 2),
    )
    budget_advance = fields.Float(
        string='Avanzo su Budget',
        compute='_compute_budget',
        store=True,
        digits=(16, 2),
    )

    # ── BOM lines ─────────────────────────────────────────────────────────────
    bom_line_ids = fields.One2many(
        'sbu.estimate.bom.line',
        'estimate_line_id',
        string='Distinta Base (ITEM)',
    )

    # ── Computed: sqm ─────────────────────────────────────────────────────────
    @api.depends('width_mm', 'height_mm', 'qty')
    def _compute_sqm(self):
        for line in self:
            if line.width_mm and line.height_mm:
                sqm_per_piece = (line.width_mm * line.height_mm) / 1_000_000
                line.sqm = sqm_per_piece * (line.qty or 1)
            else:
                line.sqm = 0.0

    # ── Computed: price totals ────────────────────────────────────────────────
    @api.depends(
        'qty', 'sqm',
        'price_serramento_cad', 'price_oscuramento_cad', 'price_automatismo_cad',
        'price_zanzariera_cad', 'price_vetro_cad', 'price_pannello_cad',
        'price_controtelaio_cad', 'price_trasformazione_cad', 'price_accessori_cad',
        'price_kit_avvolgimento_cad', 'price_smontaggio_cad', 'price_nolo_cad',
        'price_cassonetto_cad',
    )
    def _compute_price_totals(self):
        for line in self:
            cad = (
                line.price_serramento_cad
                + line.price_oscuramento_cad
                + line.price_automatismo_cad
                + line.price_zanzariera_cad
                + line.price_vetro_cad
                + line.price_pannello_cad
                + line.price_controtelaio_cad
                + line.price_trasformazione_cad
                + line.price_accessori_cad
                + line.price_kit_avvolgimento_cad
                + line.price_smontaggio_cad
                + line.price_nolo_cad
                + line.price_cassonetto_cad
            )
            line.price_total_cad = cad
            line.price_total_tot = cad * (line.qty or 1)
            line.price_per_sqm = (line.price_total_tot / line.sqm) if line.sqm else 0.0

    # ── Computed: cost totals ─────────────────────────────────────────────────
    @api.depends(
        'qty', 'sqm',
        'cost_coibentazione_cad', 'cost_posa_lamiera_lin_cad',
        'cost_tech_pm_cad', 'cost_trasporto_cad', 'cost_cantiere_cad',
        'cost_staffame_cad', 'cost_extra_cad',
    )
    def _compute_cost_totals(self):
        for line in self:
            cad = (
                line.cost_coibentazione_cad
                + line.cost_posa_lamiera_lin_cad
                + line.cost_tech_pm_cad
                + line.cost_trasporto_cad
                + line.cost_cantiere_cad
                + line.cost_staffame_cad
                + line.cost_extra_cad
            )
            line.cost_total_cad = cad
            line.cost_total_tot = cad * (line.qty or 1)
            line.cost_per_sqm = (line.cost_total_tot / line.sqm) if line.sqm else 0.0

    # ── Computed: budget ──────────────────────────────────────────────────────
    @api.depends('cost_total_tot', 'budget_orders_issued', 'budget_costs_incurred')
    def _compute_budget(self):
        for line in self:
            line.budget_to_fulfill = line.budget_orders_issued - line.budget_costs_incurred
            if line.budget_orders_issued:
                line.budget_pct_paid = (line.budget_costs_incurred / line.budget_orders_issued) * 100
                line.budget_order_progress_pct = (line.budget_orders_issued / line.cost_total_tot * 100) if line.cost_total_tot else 0.0
            else:
                line.budget_pct_paid = 0.0
                line.budget_order_progress_pct = 0.0
            line.budget_residual = line.cost_total_tot - line.budget_orders_issued
            line.budget_vs_estimate_pct = (line.budget_orders_issued / line.cost_total_tot * 100) if line.cost_total_tot else 0.0
            line.budget_advance = line.cost_total_tot - line.budget_costs_incurred
