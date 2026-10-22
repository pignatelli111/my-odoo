from odoo import _, api, fields, models

from .sbu_anaco_engine import ANACO_COMPONENT_FIELDS, ANACO_OVERHEADS
from .sbu_contract_uom import SBU_CONTRACT_UOM_SELECTION
from .sbu_cost_family import COST_FAMILY_WORKFLOW_ROUTE, SBU_COST_FAMILY_SELECTION


def _successive_discount_factor(*percents):
    """Excel-style successive % discounts: factor = ∏(1 - p_i/100)."""
    factor = 1.0
    for p in percents:
        if p:
            factor *= 1.0 - (p / 100.0)
    return factor


class SbuEstimateLine(models.Model):
    """One ANACO row. Amounts are stored at full precision (like Excel) and shown with 2 decimals."""
    _name = 'sbu.estimate.line'
    _description = 'SBU Estimate Line (ANACO row)'
    _rec_name = 'name'
    _order = 'sequence, pos'

    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo',
        required=True,
        ondelete='cascade',
    )
    sal_contract_line_ids = fields.Many2many(
        'sbu.estimate.sal.line',
        'sbu_estimate_sal_line_estimate_line_rel',
        'estimate_line_id',
        'sal_line_id',
        string='SAL contractual items',
    )
    sequence = fields.Integer(default=10)

    # ── Position / Identity ───────────────────────────────────────────────────
    pos = fields.Char(string='Pos.', help='Posizione item (es. FTF, FT, LA01)')
    item_code = fields.Char(string='Codice Item')
    description = fields.Text(string='Descrizione', required=True)
    name = fields.Char(
        string='Nome riga ANACO',
        compute='_compute_name',
        store=True,
        index=True,
    )
    note = fields.Text(
        string='Note / assunzioni',
        help='Ipotesi e condizioni specifiche della riga (es. tipo vetro da confermare, esclusioni, listino fornitore, revisione disegno).',
    )

    # ── Dimensions (from ANACO: B, H, Mq) ────────────────────────────────────
    qty = fields.Float(string='Qt.', default=1.0)
    width_mm = fields.Float(string='B (mm)', digits=(16, 0))
    height_mm = fields.Float(string='H (mm)', digits=(16, 0))
    sqm_per_piece = fields.Float(
        string='MQ/Cad.',
        compute='_compute_sqm_dimensions',
        store=True,
        help='Superficie di un solo pezzo: B (mm) × H (mm) / 1.000.000.',
    )
    sqm = fields.Float(
        string='Mq tot.',
        compute='_compute_sqm_dimensions',
        store=True,
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
    workflow_route = fields.Char(
        string='Workflow route',
        compute='_compute_workflow_route',
        store=True,
        help='Suggested downstream workflow code from cost family (VC/VS, ST, PAN, LA, LZ, …).',
    )
    manual_input_pending = fields.Boolean(
        string='Needs manual entry',
        compute='_compute_manual_input_pending',
        store=True,
        help='Green highlight on empty B/H when U.M. is MQ or ML (ANACO manual cells).',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='U.M. Odoo',
        help='Opzionale: unità di misura prodotto Odoo; la colonna «U.M. calcolo» guida preventivo e SAL.',
    )

    # ── Discount / commission ─────────────────────────────────────────────────
    commission_pct = fields.Float(
        string='Comm. %',
        help='Commissione opzionale sul prezzo cliente (0 = prezzo ANACO BS invariato).',
    )
    discount_sc1 = fields.Float(
        string='Sconto 1 %',
        help='Informativo: sconto fornitore ANACO K5, già incluso nel costo serramento scontato (col. N).',
    )
    discount_sc2 = fields.Float(
        string='Sconto 2 %',
        help='Informativo: sconto fornitore ANACO L5, già incluso nel costo serramento scontato (col. N).',
    )
    discount_sc3 = fields.Float(
        string='Sconto 3 %',
        help='Informativo: sconto fornitore ANACO M5, già incluso nel costo serramento scontato (col. N).',
    )

    # ── PRICE columns (selling side — from ANACO) ─────────────────────────────
    price_serramento_cad = fields.Float(string='Serramento Scontato CAD')
    price_oscuramento_cad = fields.Float(string='Oscuramento Scontato CAD')
    price_automatismo_cad = fields.Float(string='Automatismo CAD')
    price_zanzariera_cad = fields.Float(string='Zanzariera CAD')
    price_vetro_cad = fields.Float(string='Vetro CAD')
    price_pannello_cad = fields.Float(string='Pannello CAD')
    price_controtelaio_cad = fields.Float(string='Controtelaio CAD')
    price_trasformazione_cad = fields.Float(string='Trasformazione CAD')
    price_accessori_cad = fields.Float(string='Accessori Maniglie CAD')
    price_kit_avvolgimento_cad = fields.Float(string='Kit Avvolgimento CAD')
    price_smontaggio_cad = fields.Float(string='Smontaggio/Posa CAD')
    price_nolo_cad = fields.Float(string='Nolo CAD')
    price_cassonetto_cad = fields.Float(string='Cassonetto CAD')
    price_anaco_bs_cad = fields.Float(
        string='Prezzo unit. ANACO (col. BS)',
        help='Prezzo unitario manuale: sostituisce il prezzo calcolato BS (in Excel: cella BS digitata a mano, '
             'oppure righe solo OFFERTA). Vuoto = prezzo calcolato come in ANACO.',
    )
    anaco_price_cad = fields.Float(
        string='Prezzo calcolato ANACO (BS)',
        compute='_compute_cost_totals',
        store=True,
        help='BB + trasporto + sviluppo tecnico/PM + presidio cantiere + extra + oneri industriali + MOL (col. BS).',
    )
    anaco_excel_bs_cad = fields.Float(
        string='BS letto da Excel',
        readonly=True,
        help='Valore della cella BS al momento dell\'import (controllo di parità con il calcolo Odoo).',
    )
    anaco_check_warning = fields.Char(
        string='Controllo Excel',
        compute='_compute_anaco_check_warning',
        help='Differenze tra il calcolo Odoo e i valori BB / BS letti da Excel.',
    )
    cost_anaco_bb_cad = fields.Float(
        string='Costo unit. ANACO (col. BB)',
        readonly=True,
        help='Valore della cella BB al momento dell\'import (controllo di parità con il calcolo Odoo).',
    )
    cost_anaco_bc_tot = fields.Float(
        string='Costo tot. ANACO (col. BC)',
        readonly=True,
        help='Valore della cella BC al momento dell\'import (controllo).',
    )

    # Computed price totals (ANACO: listino componenti → sconti successivi → comm %)
    price_gross_cad = fields.Float(
        string='Listino / base CAD',
        compute='_compute_price_totals',
        store=True,
        help='Somma componenti prezzo (listino / base prima degli sconti a catena).',
    )
    price_after_discounts_cad = fields.Float(
        string='Prezzo dopo sconti CAD',
        compute='_compute_price_totals',
        store=True,
        help='Listino / base CAD × (1−Sc1%) × (1−Sc2%) × (1−Sc3%). Prima della commissione %.',
    )
    price_after_discounts_tot = fields.Float(
        string='Prezzo dopo sconti TOT',
        compute='_compute_price_totals',
        store=True,
        help='Prezzo dopo sconti CAD × Qt.',
    )
    price_total_cad = fields.Float(
        string='Prezzo cliente CAD',
        compute='_compute_price_totals',
        store=True,
        help='Dopo sconti e commissione %, oppure colonna BS ANACO se valorizzata.',
    )
    price_total_tot = fields.Float(
        string='Prezzo cliente TOT',
        compute='_compute_price_totals',
        store=True,
        help='Prezzo cliente CAD × Qt.',
    )
    price_per_sqm = fields.Float(
        string='Prezzo cliente / MQ',
        compute='_compute_price_totals',
        store=True,
        help='Prezzo cliente TOT ÷ Mq tot. (col. BU = BT / I).',
    )
    price_unit_rate = fields.Float(
        string='Client unit rate',
        compute='_compute_unit_rates',
        store=True,
        help='Client price per calculation unit (€/m², €/pz, or lump sum per line).',
    )
    unit_rate_label = fields.Char(
        string='Unit rate basis',
        compute='_compute_unit_rates',
        store=True,
    )

    # ── COST columns (buying side — from ANACO) ───────────────────────────────
    cost_coibentazione_cad = fields.Float(string='Coibentazione CAD')
    cost_posa_lamiera_lin_cad = fields.Float(string='Posa Lamiera LIN CAD')
    cost_industrial_pct = fields.Float(
        string='Costi Industriali %',
        help='Costi industriali % sul costo materiale lavorato e posato (col. BM; BN = BB × BM). Incluso nel costo totale.',
    )
    cost_tech_pm_cad = fields.Float(
        string='Sviluppo Tecnico/PM CAD', compute='_compute_cost_totals', store=True,
        help='BB × % sviluppo tecnico e PM del preventivo (col. BG = BB × $BG$5).',
    )
    cost_mol_pct = fields.Float(
        string='MOL %',
        help='MOL % sul costo materiale lavorato e posato (col. BP; BQ = BB × BP). Entra nel prezzo BS, non nel costo.',
    )
    cost_trasporto_cad = fields.Float(
        string='Trasporto/Imballo CAD', compute='_compute_cost_totals', store=True,
        help='BB × % trasporto e imballo del preventivo (col. BE = BB × $BE$5).',
    )
    cost_cantiere_cad = fields.Float(
        string='Presidio Cantiere/Site Mng CAD', compute='_compute_cost_totals', store=True,
        help='BB × % presidio cantiere del preventivo (col. BI = BB × $BI$5).',
    )
    cost_staffame_cad = fields.Float(string='ST/LZ Staffame CAD')
    cost_extra_cad = fields.Float(
        string='Extra CAD', compute='_compute_cost_totals', store=True,
        help='BB × % extra del preventivo (col. BK = BB × $BK$5).',
    )

    # ANACO cost rollup (Cosimo schema: materiale → add-on → subtotale → industriali → MOL)
    cost_material_worked_cad = fields.Float(
        string='Costo materiale lavorato e posato CAD',
        compute='_compute_cost_totals',
        store=True,
        help='Somma delle 16 colonne costo CAD (col. BB = N+R+V+AB+AD+AF+AH+AJ+AL+AN+AP+AR+AT+AV+AX+AZ).',
    )
    cost_material_worked_tot = fields.Float(
        string='Costo materiale lavorato e posato TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_trasporto_tot = fields.Float(
        string='Trasporto e imballo TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_tech_pm_tot = fields.Float(
        string='Sviluppo tecnico e PM TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_cantiere_tot = fields.Float(
        string='Presidio cantiere / site mng TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_staffame_tot = fields.Float(
        string='ST/LZ staffame TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_extra_tot = fields.Float(
        string='Extra TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_subtotal_cad = fields.Float(
        string='Subtotale costo CAD',
        compute='_compute_cost_totals',
        store=True,
        help='BB + trasporto + sviluppo tecnico/PM + presidio cantiere + extra (prima degli oneri industriali).',
    )
    cost_subtotal_tot = fields.Float(
        string='Subtotale costo TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_industrial_tot = fields.Float(
        string='Oneri industriali TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_mol_amount_tot = fields.Float(
        string='MOL su materiale TOT',
        compute='_compute_cost_totals',
        store=True,
        help='MOL TOT (col. BR = BC × BP): margine incluso nel prezzo cliente.',
    )

    cost_gross_cad = fields.Float(
        string='List cost / base CAD',
        compute='_compute_cost_discount_chain',
        store=True,
        help='Sum of cost component columns before chained discounts (audit, like listino costo).',
    )
    cost_after_discounts_cad = fields.Float(
        string='Cost after discounts CAD',
        compute='_compute_cost_discount_chain',
        store=True,
        help='List cost CAD × (1−Sc1%) × (1−Sc2%) × (1−Sc3%), same chain as selling price.',
    )
    cost_after_discounts_tot = fields.Float(
        string='Cost after discounts TOT',
        compute='_compute_cost_discount_chain',
        store=True,
        help='Cost after discounts CAD × Qt.',
    )
    cost_industrial_cad = fields.Float(
        string='Oneri Industriali CAD',
        compute='_compute_cost_totals',
        store=True,
        help='Oneri industriali CAD (col. BN = BB × BM).',
    )
    cost_mol_amount_cad = fields.Float(
        string='MOL su Materiale (€ CAD)',
        compute='_compute_cost_totals',
        store=True,
        help='MOL CAD (col. BQ = BB × BP): margine incluso nel prezzo cliente BS.',
    )
    cost_bom_total = fields.Float(
        string='Costo da Distinta (ITEM)',
        compute='_compute_cost_bom_total',
        store=True,
        help='Somma Σ (qty da distinta × costo unit.) delle righe sbu.estimate.bom.line: unica '
             '«verità» distinta per confronto costi; acquisti collegati usano le stesse righe.',
    )
    # Computed cost totals (final, includes oneri industriali)
    cost_total_cad = fields.Float(
        string='Costo totale CAD',
        compute='_compute_cost_totals',
        store=True,
        help='Costo pieno: subtotale + oneri industriali (prezzo BS − MOL).',
    )
    cost_total_tot = fields.Float(
        string='Costo totale TOT',
        compute='_compute_cost_totals',
        store=True,
    )
    cost_per_sqm = fields.Float(
        string='Costo / MQ',
        compute='_compute_cost_totals',
        store=True,
        help='Costo materiale lavorato e posato TOT ÷ Mq tot. (col. BD = BC / I).',
    )
    cost_unit_rate = fields.Float(
        string='Cost unit rate',
        compute='_compute_unit_rates',
        store=True,
        help='Cost per calculation unit (€/m², €/pz, or lump sum per line).',
    )

    margin_amount = fields.Float(
        string='Margine €',
        compute='_compute_line_margin',
        store=True,
        help='Prezzo cliente TOT − costo totale TOT.',
    )
    margin_pct = fields.Float(
        string='Margine %',
        compute='_compute_line_margin',
        store=True,
        help='Margine € ÷ prezzo cliente TOT × 100.',
    )

    # ── Budget tracking (per item — from ANACO budget columns) ────────────────
    budget_orders_issued = fields.Float(string='Ordini Emessi')
    budget_costs_incurred = fields.Float(string='Costi Sostenuti')
    budget_to_fulfill = fields.Float(
        string='Da Evadere',
        compute='_compute_budget',
        store=True,
    )
    budget_pct_paid = fields.Float(
        string='% Pagati su Ordine',
        compute='_compute_budget',
        store=True,
    )
    budget_order_progress_pct = fields.Float(
        string='% Ordine Avanzamento',
        compute='_compute_budget',
        store=True,
    )
    budget_residual = fields.Float(
        string='Disponibilità Residua su Ordine',
        compute='_compute_budget',
        store=True,
    )
    budget_vs_estimate_pct = fields.Float(
        string='% su Preventivato',
        compute='_compute_budget',
        store=True,
    )
    budget_advance = fields.Float(
        string='Avanzo su Budget',
        compute='_compute_budget',
        store=True,
    )

    # ── BOM lines ─────────────────────────────────────────────────────────────
    bom_line_ids = fields.One2many(
        'sbu.estimate.bom.line',
        'estimate_line_id',
        string='BOM (ITEM)',
    )

    # ── Computed: MQ/Cad. and Mq tot. ─────────────────────────────────────────
    @api.depends('width_mm', 'height_mm', 'qty')
    def _compute_sqm_dimensions(self):
        for line in self:
            if line.width_mm and line.height_mm:
                line.sqm_per_piece = (line.width_mm * line.height_mm) / 1_000_000
            else:
                line.sqm_per_piece = 0.0
            line.sqm = line.sqm_per_piece * (line.qty or 0.0)  # Excel I = G × H

    # ── ANACO engine (same formulas as the Excel sheet, see sbu_anaco_engine) ──
    _ANACO_DEPENDS = ANACO_COMPONENT_FIELDS + (
        'qty', 'sqm', 'cost_industrial_pct', 'cost_mol_pct', 'commission_pct', 'price_anaco_bs_cad',
        'estimate_id.anaco_pct_transport', 'estimate_id.anaco_pct_tech_pm',
        'estimate_id.anaco_pct_site', 'estimate_id.anaco_pct_extra',
    )

    @api.depends(*_ANACO_DEPENDS, 'anaco_price_cad')
    def _compute_price_totals(self):
        for line in self:
            qty = line.qty or 0.0
            # BS: computed like Excel, unless a manual price was typed (Excel override / OFFERTA rows).
            base = line.price_anaco_bs_cad or line.anaco_price_cad
            line.price_gross_cad = base
            line.price_after_discounts_cad = base
            line.price_after_discounts_tot = base * qty
            net_unit = base * (1.0 - line.commission_pct / 100.0) if line.commission_pct else base
            line.price_total_cad = net_unit
            line.price_total_tot = net_unit * qty
            line.price_per_sqm = line.price_total_tot / line.sqm if line.sqm else 0.0

    @api.depends('cost_family')
    def _compute_workflow_route(self):
        for line in self:
            line.workflow_route = (
                COST_FAMILY_WORKFLOW_ROUTE.get(line.cost_family or '', '') or False
            )

    @api.depends('calc_uom_type', 'width_mm', 'height_mm')
    def _compute_manual_input_pending(self):
        for line in self:
            if line.calc_uom_type == 'mq':
                line.manual_input_pending = not line.width_mm or not line.height_mm
            elif line.calc_uom_type == 'ml':
                line.manual_input_pending = not line.width_mm
            else:
                line.manual_input_pending = False

    @api.depends(*_ANACO_DEPENDS)
    def _compute_cost_discount_chain(self):
        """Legacy audit fields: supplier discounts are already inside the ANACO costs (col. N)."""
        for line in self:
            bb = sum(line[f] or 0.0 for f in ANACO_COMPONENT_FIELDS)
            line.cost_gross_cad = bb
            line.cost_after_discounts_cad = bb
            line.cost_after_discounts_tot = bb * (line.qty or 0.0)

    @api.depends(
        'calc_uom_type', 'price_total_tot', 'cost_total_tot', 'sqm', 'qty',
    )
    def _compute_unit_rates(self):
        for line in self:
            qty = line.qty or 1.0
            uom = line.calc_uom_type or 'mq'
            if uom == 'mq' and line.sqm:
                line.price_unit_rate = line.price_total_tot / line.sqm
                line.cost_unit_rate = line.cost_total_tot / line.sqm
                line.unit_rate_label = '€/m²'
            elif uom == 'nr':
                line.price_unit_rate = line.price_total_tot / qty
                line.cost_unit_rate = line.cost_total_tot / qty
                line.unit_rate_label = '€/pc'
            elif uom == 'ml':
                line.price_unit_rate = line.price_total_tot / qty
                line.cost_unit_rate = line.cost_total_tot / qty
                line.unit_rate_label = '€/m (per qty)'
            else:  # corpo / lump sum
                line.price_unit_rate = line.price_total_tot
                line.cost_unit_rate = line.cost_total_tot
                line.unit_rate_label = 'Lump sum'

    @api.depends('pos', 'description')
    def _compute_name(self):
        for line in self:
            pos = (line.pos or '').strip()
            desc = (line.description or '').strip()
            if pos and desc:
                line.name = f'{pos} — {desc}'
            elif desc:
                line.name = desc
            elif pos:
                line.name = pos
            else:
                line.name = _('ANACO line %s') % line.id

    @api.depends('bom_line_ids.total_cost')
    def _compute_cost_bom_total(self):
        for line in self:
            line.cost_bom_total = sum(line.bom_line_ids.mapped('total_cost'))

    # ── Computed: cost totals (ANACO BB … BS) ──────────────────────────────────
    @api.depends(*_ANACO_DEPENDS)
    def _compute_cost_totals(self):
        for line in self:
            qty = line.qty or 0.0
            estimate = line.estimate_id
            bb = sum(line[f] or 0.0 for f in ANACO_COMPONENT_FIELDS)
            bc = bb * qty
            line.cost_material_worked_cad = bb
            line.cost_material_worked_tot = bc
            line.cost_staffame_tot = (line.cost_staffame_cad or 0.0) * qty
            overhead_cad = 0.0
            for pct_field, cad_field, tot_field, *_cols in ANACO_OVERHEADS:
                pct = (estimate[pct_field] or 0.0) / 100.0
                line[cad_field] = bb * pct
                line[tot_field] = bc * pct
                overhead_cad += bb * pct
            line.cost_subtotal_cad = bb + overhead_cad
            line.cost_subtotal_tot = line.cost_subtotal_cad * qty
            ind = (line.cost_industrial_pct or 0.0) / 100.0
            mol = (line.cost_mol_pct or 0.0) / 100.0
            line.cost_industrial_cad = bb * ind
            line.cost_industrial_tot = bc * ind
            line.cost_mol_amount_cad = bb * mol
            line.cost_mol_amount_tot = bc * mol
            line.cost_total_cad = line.cost_subtotal_cad + line.cost_industrial_cad
            line.cost_total_tot = line.cost_total_cad * qty
            line.anaco_price_cad = line.cost_total_cad + line.cost_mol_amount_cad
            line.cost_per_sqm = bc / line.sqm if line.sqm else 0.0

    @api.depends('anaco_price_cad', 'cost_material_worked_cad', 'anaco_excel_bs_cad', 'cost_anaco_bb_cad',
                 'price_anaco_bs_cad')
    def _compute_anaco_check_warning(self):
        for line in self:
            issues = []
            if line.cost_anaco_bb_cad and abs(line.cost_anaco_bb_cad - line.cost_material_worked_cad) > 0.01:
                issues.append(_('BB Excel %(excel).2f ≠ Odoo %(odoo).2f',
                                excel=line.cost_anaco_bb_cad, odoo=line.cost_material_worked_cad))
            if (line.anaco_excel_bs_cad and not line.price_anaco_bs_cad
                    and abs(line.anaco_excel_bs_cad - line.anaco_price_cad) > 0.01):
                issues.append(_('BS Excel %(excel).2f ≠ Odoo %(odoo).2f',
                                excel=line.anaco_excel_bs_cad, odoo=line.anaco_price_cad))
            line.anaco_check_warning = '; '.join(issues) or False

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

    # ── ANACO row rules (formulas of columns P / R and AV, read from the workbook) ──
    _ANACO_RULE_TRIGGERS = ('width_mm', 'height_mm', 'estimate_id')

    def _sbu_anaco_rule_values(self, width_mm, height_mm):
        """Values of staffame (R) and installation (AV) from the estimate rules, if any.

        R  = 2 × (B + H) / 1000 × €/ml × Q5 × R5       (e.g. =2*(D13+F13)/1000*9)
        AV = MAX(MQ/cad, min MQ) × €/m²                  (e.g. =MAX(G13,1.8)*60)
        """
        self.ensure_one()
        estimate = self.estimate_id
        vals = {}
        if estimate.anaco_staffame_rate_ml and width_mm and height_mm:
            perimeter_ml = 2.0 * (width_mm + height_mm) / 1000.0
            vals['cost_staffame_cad'] = perimeter_ml * estimate.anaco_staffame_rate_ml * (
                estimate.anaco_staffame_multiplier or 1.0)
        if estimate.anaco_posa_rate_sqm and width_mm and height_mm:
            sqm_piece = width_mm * height_mm / 1_000_000.0
            vals['price_smontaggio_cad'] = max(sqm_piece, estimate.anaco_posa_min_sqm or 0.0) * (
                estimate.anaco_posa_rate_sqm)
        return vals

    @api.onchange('width_mm', 'height_mm')
    def _onchange_anaco_rules(self):
        for line in self:
            for fname, value in line._sbu_anaco_rule_values(line.width_mm, line.height_mm).items():
                line[fname] = value

    def _sbu_apply_anaco_rules(self):
        for line in self:
            rule_vals = line._sbu_anaco_rule_values(line.width_mm, line.height_mm)
            if rule_vals:
                super(SbuEstimateLine, line).write(rule_vals)

    @api.model_create_multi
    def create(self, vals_list):
        Estimate = self.env['sbu.estimate']
        for vals in vals_list:
            estimate = Estimate.browse(vals.get('estimate_id') or self.env.context.get('default_estimate_id'))
            if estimate:
                vals.setdefault('cost_industrial_pct', estimate.anaco_pct_industrial)
                vals.setdefault('cost_mol_pct', estimate.anaco_pct_mol)
        lines = super().create(vals_list)
        for line, vals in zip(lines, vals_list):
            rule_vals = {
                k: v for k, v in line._sbu_anaco_rule_values(line.width_mm, line.height_mm).items()
                if k not in vals  # a value read from Excel (even 0) always wins over the rule
            }
            if rule_vals:
                super(SbuEstimateLine, line).write(rule_vals)
        return lines

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('sbu_skip_anaco_rules') and any(k in vals for k in self._ANACO_RULE_TRIGGERS):
            for line in self:
                rule_vals = {
                    k: v for k, v in line._sbu_anaco_rule_values(line.width_mm, line.height_mm).items()
                    if k not in vals
                }
                if rule_vals:
                    super(SbuEstimateLine, line).write(rule_vals)
        return res
