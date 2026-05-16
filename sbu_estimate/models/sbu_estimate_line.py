from odoo import api, fields, models

from .sbu_contract_uom import SBU_CONTRACT_UOM_SELECTION
from .sbu_cost_family import SBU_COST_FAMILY_SELECTION


def _successive_discount_factor(*percents):
    """Excel-style successive % discounts: factor = ∏(1 - p_i/100)."""
    factor = 1.0
    for p in percents:
        if p:
            factor *= 1.0 - (p / 100.0)
    return factor


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
    note = fields.Text(
        string='Note / assunzioni',
        help='Ipotesi e condizioni specifiche della riga (es. tipo vetro da confermare, esclusioni, listino fornitore, revisione disegno).',
    )

    # ── Dimensions (from ANACO: B, H, Mq) ────────────────────────────────────
    qty = fields.Float(string='Qt.', default=1.0, digits=(16, 2))
    width_mm = fields.Float(string='B (mm)', digits=(16, 0))
    height_mm = fields.Float(string='H (mm)', digits=(16, 0))
    sqm_per_piece = fields.Float(
        string='MQ/Cad.',
        compute='_compute_sqm_dimensions',
        store=True,
        digits=(16, 3),
        help='Superficie di un solo pezzo: B (mm) × H (mm) / 1.000.000.',
    )
    sqm = fields.Float(
        string='Mq tot.',
        compute='_compute_sqm_dimensions',
        store=True,
        digits=(16, 3),
        help='MQ totali riga: MQ/Cad. × Qt. (equiv. ANACO colonna I, MQ TOTALI).',
    )
    calc_uom_type = fields.Selection(
        selection=SBU_CONTRACT_UOM_SELECTION,
        string='U.M. calcolo',
        default='mq',
        required=True,
        help='Unità di misura / tipo calcolo per la riga (come U.M. contrattuale SAL): '
             'MQ (superficie), ML (lineare), Nr/Pz, A corpo (forfait).',
    )
    cost_family = fields.Selection(
        selection=SBU_COST_FAMILY_SELECTION,
        string='Categoria / famiglia costo',
        help='Tipo voce per workflow a valle (es. vetro → VC/VS, staffe → ST, lamiera LA/LZ).',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='U.M. Odoo',
        help='Opzionale: unità di misura prodotto Odoo; la colonna «U.M. calcolo» guida preventivo e SAL.',
    )

    # ── Discount / commission ─────────────────────────────────────────────────
    commission_pct = fields.Float(
        string='Comm. %',
        digits=(16, 2),
        help='Applicato dopo i tre sconti successivi sul listino (moltiplicativo, come da ANACO).',
    )
    discount_sc1 = fields.Float(
        string='Sconto 1 %',
        digits=(16, 2),
        help='Primo sconto successivo sul listino / base CAD.',
    )
    discount_sc2 = fields.Float(
        string='Sconto 2 %',
        digits=(16, 2),
        help='Secondo sconto successivo (dopo Sconto 1).',
    )
    discount_sc3 = fields.Float(
        string='Sconto 3 %',
        digits=(16, 2),
        help='Terzo sconto successivo (dopo Sconto 2).',
    )

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
    price_anaco_bs_cad = fields.Float(
        string='Prezzo unit. ANACO (col. BS)',
        digits=(16, 2),
        help='Se valorizzato, equivale alla cella ANACO BS (PREZZO su OFFERTA): prezzo unitario finale da Excel; ignora somma componenti e sconti Odoo.',
    )

    # Computed price totals (ANACO: listino componenti → sconti successivi → comm %)
    price_gross_cad = fields.Float(
        string='Listino / base CAD',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
        help='Somma componenti prezzo (listino / base prima degli sconti a catena).',
    )
    price_after_discounts_cad = fields.Float(
        string='Prezzo dopo sconti CAD',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
        help='Listino / base CAD × (1−Sc1%) × (1−Sc2%) × (1−Sc3%). Prima della commissione %.',
    )
    price_after_discounts_tot = fields.Float(
        string='Prezzo dopo sconti TOT',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
        help='Prezzo dopo sconti CAD × Qt.',
    )
    price_total_cad = fields.Float(
        string='Prezzo cliente CAD',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
        help='Dopo sconti e commissione %, oppure colonna BS ANACO se valorizzata.',
    )
    price_total_tot = fields.Float(
        string='Prezzo cliente TOT',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
        help='Prezzo cliente CAD × Qt.',
    )
    price_per_sqm = fields.Float(
        string='Prezzo cliente / MQ',
        compute='_compute_price_totals',
        store=True,
        digits=(16, 2),
        help='Prezzo cliente TOT ÷ Mq tot. (€/m² vendita sulla riga).',
    )

    # ── COST columns (buying side — from ANACO) ───────────────────────────────
    cost_coibentazione_cad = fields.Float(string='Coibentazione CAD', digits=(16, 2))
    cost_posa_lamiera_lin_cad = fields.Float(string='Posa Lamiera LIN CAD', digits=(16, 2))
    cost_industrial_pct = fields.Float(
        string='Costi Industriali %',
        digits=(16, 2),
        help='Percentuale applicata su (Coibentazione + Posa lamiera LIN); l\'importo è in «Oneri Industriali CAD» e incluso nel costo totale.',
    )
    cost_tech_pm_cad = fields.Float(string='Sviluppo Tecnico/PM CAD', digits=(16, 2))
    cost_mol_pct = fields.Float(
        string='MOL %',
        digits=(16, 2),
        help='Margine teorico su (Coibentazione + Posa): valorizzato in «MOL su Materiale (€ CAD)»; non sommato al costo totale (come indicatore ANACO).',
    )
    cost_trasporto_cad = fields.Float(string='Trasporto/Imballo CAD', digits=(16, 2))
    cost_cantiere_cad = fields.Float(string='Presidio Cantiere/Site Mng CAD', digits=(16, 2))
    cost_staffame_cad = fields.Float(string='ST/LZ Staffame CAD', digits=(16, 2))
    cost_extra_cad = fields.Float(string='Extra CAD', digits=(16, 2))

    cost_industrial_cad = fields.Float(
        string='Oneri Industriali CAD',
        compute='_compute_cost_totals',
        store=True,
        digits=(16, 2),
        help='Percentuale su (Coibentazione + Posa lamiera LIN), come da ANACO.',
    )
    cost_mol_amount_cad = fields.Float(
        string='MOL su Materiale (€ CAD)',
        compute='_compute_cost_totals',
        store=True,
        digits=(16, 2),
        help='Indicatore: MOL % applicato solo su coibentazione + posa (non sommato al costo totale).',
    )
    cost_bom_total = fields.Float(
        string='Costo da Distinta (ITEM)',
        compute='_compute_cost_bom_total',
        store=True,
        digits=(16, 2),
        help='Somma Σ (qty da distinta × costo unit.) delle righe sbu.estimate.bom.line: unica '
             '«verità» distinta per confronto costi; acquisti collegati usano le stesse righe.',
    )
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
        string='Costo / MQ',
        compute='_compute_cost_totals',
        store=True,
        digits=(16, 2),
        help='Costo materiale lavorato e posato TOT ÷ Mq tot. (€/m² sulla riga).',
    )

    margin_amount = fields.Float(
        string='Margine €',
        compute='_compute_line_margin',
        store=True,
        digits=(16, 2),
        help='Prezzo cliente TOT − costo materiale lavorato e posato TOT.',
    )
    margin_pct = fields.Float(
        string='Margine %',
        compute='_compute_line_margin',
        store=True,
        digits=(16, 2),
        help='Margine € ÷ prezzo cliente TOT × 100.',
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

    # ── Computed: MQ/Cad. and Mq tot. ─────────────────────────────────────────
    @api.depends('width_mm', 'height_mm', 'qty')
    def _compute_sqm_dimensions(self):
        for line in self:
            if line.width_mm and line.height_mm:
                line.sqm_per_piece = (line.width_mm * line.height_mm) / 1_000_000
            else:
                line.sqm_per_piece = 0.0
            line.sqm = line.sqm_per_piece * (line.qty or 1)

    # ── Computed: price totals ────────────────────────────────────────────────
    @api.depends(
        'qty', 'sqm',
        'price_serramento_cad', 'price_oscuramento_cad', 'price_automatismo_cad',
        'price_zanzariera_cad', 'price_vetro_cad', 'price_pannello_cad',
        'price_controtelaio_cad', 'price_trasformazione_cad', 'price_accessori_cad',
        'price_kit_avvolgimento_cad', 'price_smontaggio_cad', 'price_nolo_cad',
        'price_cassonetto_cad',
        'discount_sc1', 'discount_sc2', 'discount_sc3', 'commission_pct',
        'price_anaco_bs_cad',
    )
    def _compute_price_totals(self):
        for line in self:
            gross = (
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
            line.price_gross_cad = gross
            disc_factor = _successive_discount_factor(
                line.discount_sc1,
                line.discount_sc2,
                line.discount_sc3,
            )
            after_discounts = gross * disc_factor
            line.price_after_discounts_cad = after_discounts
            qty = line.qty or 1
            line.price_after_discounts_tot = after_discounts * qty
            if line.price_anaco_bs_cad:
                net_unit = line.price_anaco_bs_cad
            elif line.commission_pct:
                net_unit = after_discounts * (1.0 - line.commission_pct / 100.0)
            else:
                net_unit = after_discounts
            line.price_total_cad = net_unit
            line.price_total_tot = net_unit * qty
            line.price_per_sqm = (line.price_total_tot / line.sqm) if line.sqm else 0.0

    @api.depends('bom_line_ids.total_cost')
    def _compute_cost_bom_total(self):
        for line in self:
            line.cost_bom_total = sum(line.bom_line_ids.mapped('total_cost'))

    # ── Computed: cost totals ─────────────────────────────────────────────────
    @api.depends(
        'qty', 'sqm',
        'cost_coibentazione_cad', 'cost_posa_lamiera_lin_cad',
        'cost_industrial_pct', 'cost_mol_pct',
        'cost_tech_pm_cad', 'cost_trasporto_cad', 'cost_cantiere_cad',
        'cost_staffame_cad', 'cost_extra_cad',
    )
    def _compute_cost_totals(self):
        for line in self:
            material = (
                (line.cost_coibentazione_cad or 0.0)
                + (line.cost_posa_lamiera_lin_cad or 0.0)
            )
            ind_pct = line.cost_industrial_pct or 0.0
            line.cost_industrial_cad = material * (ind_pct / 100.0)
            mol_pct = line.cost_mol_pct or 0.0
            line.cost_mol_amount_cad = material * (mol_pct / 100.0)
            cad = (
                material
                + line.cost_industrial_cad
                + (line.cost_tech_pm_cad or 0.0)
                + (line.cost_trasporto_cad or 0.0)
                + (line.cost_cantiere_cad or 0.0)
                + (line.cost_staffame_cad or 0.0)
                + (line.cost_extra_cad or 0.0)
            )
            line.cost_total_cad = cad
            line.cost_total_tot = cad * (line.qty or 1)
            line.cost_per_sqm = (line.cost_total_tot / line.sqm) if line.sqm else 0.0

    @api.depends('price_total_tot', 'cost_total_tot')
    def _compute_line_margin(self):
        for line in self:
            margin = (line.price_total_tot or 0.0) - (line.cost_total_tot or 0.0)
            line.margin_amount = margin
            if line.price_total_tot:
                line.margin_pct = (margin / line.price_total_tot) * 100.0
            else:
                line.margin_pct = 0.0

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
