from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SbuEstimate(models.Model):
    _name = 'sbu.estimate'
    _description = 'SBU Estimate / Preventivo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Ns. Preventivo',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    revision = fields.Char(
        string='Revisione',
        default='REV00',
        tracking=True,
    )
    full_name = fields.Char(
        string='Riferimento Completo',
        compute='_compute_full_name',
        store=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    date = fields.Date(
        string='Data',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    validity_date = fields.Date(
        string='Validità Offerta',
        tracking=True,
    )

    # ── Parties ───────────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
    )
    opportunity_id = fields.Many2one(
        'crm.lead',
        string='Opportunità CRM',
        domain=[('type', '=', 'opportunity')],
        tracking=True,
    )
    job_site = fields.Char(
        string='Cantiere / Immobile',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsabile',
        default=lambda self: self.env.user,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ── Commercial scenario ───────────────────────────────────────────────────
    probability = fields.Float(
        string='Probabilità Chiusura (%)',
        default=50.0,
        tracking=True,
    )
    expected_margin_pct = fields.Float(
        string='Margine Atteso (%)',
        compute='_compute_margin',
        store=True,
    )

    # ── Delivery / payment conditions (from OFFERTA sheet) ───────────────────
    delivery_terms = fields.Char(
        string='Resa',
        default='Franco cantiere',
    )
    delivery_timing = fields.Text(
        string='Tempi di Consegna / Planning',
    )
    payment_terms_text = fields.Text(
        string='Modalità di Pagamento',
        default='40% - Acconto all\'ordine rimessa diretta\n'
                '30% - Firma Esecutivi\n'
                '30% SAL mensili - Rimessa Diretta',
    )
    validity_days = fields.Integer(
        string='Validità (gg solari)',
        default=15,
    )
    inclusions = fields.Text(string='Inclusioni')
    exclusions = fields.Text(string='Esclusioni')
    special_notes = fields.Text(string='Specifiche Particolari')

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Bozza'),
        ('sent', 'Inviato'),
        ('won', 'Vinto'),
        ('lost', 'Perso'),
        ('cancelled', 'Annullato'),
    ], string='Stato', default='draft', tracking=True)

    # ── Lines ─────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'sbu.estimate.line',
        'estimate_id',
        string='Righe Preventivo (ANACO)',
    )
    sal_line_ids = fields.One2many(
        'sbu.estimate.sal.line',
        'estimate_id',
        string='Voci Contrattuali SAL',
    )

    # ── Totals (computed from lines) ──────────────────────────────────────────
    total_sqm = fields.Float(
        string='MQ Totali',
        compute='_compute_totals',
        store=True,
        digits=(16, 2),
    )
    total_price = fields.Monetary(
        string='Prezzo Cliente Totale',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    total_cost = fields.Monetary(
        string='Costo Totale',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    margin_amount = fields.Monetary(
        string='Margine €',
        compute='_compute_margin',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.EUR'),
    )

    # ── Project link (after won) ───────────────────────────────────────────────
    project_id = fields.Many2one(
        'project.project',
        string='Commessa',
        readonly=True,
        copy=False,
    )
    project_count = fields.Integer(
        compute='_compute_project_count',
    )

    # ── Computed fields ───────────────────────────────────────────────────────
    @api.depends('name', 'revision')
    def _compute_full_name(self):
        for rec in self:
            rec.full_name = f"{rec.name or ''} {rec.revision or ''}".strip()

    @api.depends('line_ids.price_total_tot', 'line_ids.cost_total_tot', 'line_ids.sqm')
    def _compute_totals(self):
        for rec in self:
            rec.total_sqm = sum(rec.line_ids.mapped('sqm'))
            rec.total_price = sum(rec.line_ids.mapped('price_total_tot'))
            rec.total_cost = sum(rec.line_ids.mapped('cost_total_tot'))

    @api.depends('total_price', 'total_cost')
    def _compute_margin(self):
        for rec in self:
            rec.margin_amount = rec.total_price - rec.total_cost
            if rec.total_price:
                rec.expected_margin_pct = (rec.margin_amount / rec.total_price) * 100
            else:
                rec.expected_margin_pct = 0.0

    def _compute_project_count(self):
        for rec in self:
            rec.project_count = 1 if rec.project_id else 0

    # ── Sequence ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.estimate') or _('New')
        return super().create(vals_list)

    # ── State transitions ─────────────────────────────────────────────────────
    def action_send(self):
        self.ensure_one()
        self.state = 'sent'

    def action_won(self):
        self.ensure_one()
        self.state = 'won'
        return self.action_create_project()

    def action_lost(self):
        self.ensure_one()
        self.state = 'lost'

    def action_reset_draft(self):
        self.ensure_one()
        self.state = 'draft'

    def action_new_revision(self):
        """Create a new revision of this estimate."""
        self.ensure_one()
        # Parse current revision number
        current = self.revision or 'REV00'
        try:
            num = int(current.replace('REV', ''))
            new_rev = f'REV{str(num + 1).zfill(2)}'
        except ValueError:
            new_rev = 'REV01'

        new_estimate = self.copy({
            'revision': new_rev,
            'state': 'draft',
            'name': self.name,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.estimate',
            'res_id': new_estimate.id,
            'view_mode': 'form',
        }

    # ── Project creation ──────────────────────────────────────────────────────
    def action_create_project(self):
        self.ensure_one()
        if self.project_id:
            raise UserError(_('Una commessa è già stata creata per questo preventivo.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.estimate.to.project.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_estimate_id': self.id},
        }

    def action_view_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'res_id': self.project_id.id,
            'view_mode': 'form',
        }
