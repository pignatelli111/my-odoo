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
    previous_revision_id = fields.Many2one(
        'sbu.estimate',
        string='Revisione precedente',
        ondelete='set null',
        index=True,
        copy=False,
    )
    revision_root_id = fields.Many2one(
        'sbu.estimate',
        string='Radice revisioni',
        compute='_compute_revision_root',
        store=True,
        index=True,
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
    commercial_scenario = fields.Selection(
        selection=[
            ('base', 'Base (listino / standard)'),
            ('aggressive', 'Aggressivo'),
            ('risk', 'Rischio / contingency'),
        ],
        string='Scenario commerciale',
        tracking=True,
    )
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

    approval_required = fields.Boolean(
        string='Richiede approvazione interna',
        default=False,
        tracking=True,
    )
    approval_state = fields.Selection(
        selection=[
            ('na', 'Nessuna'),
            ('pending', 'In approvazione'),
            ('approved', 'Approvato'),
            ('rejected', 'Rifiutato'),
        ],
        string='Stato approvazione',
        default='na',
        copy=False,
        tracking=True,
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approvato da',
        readonly=True,
        copy=False,
    )
    approved_on = fields.Datetime(
        string='Approvato il',
        readonly=True,
        copy=False,
    )
    revision_same_name_count = fields.Integer(
        string='Revisioni (stesso Ns.)',
        compute='_compute_revision_same_name_count',
    )

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
    reference_ids = fields.One2many(
        'sbu.estimate.reference',
        'estimate_id',
        string='Allegati e riferimenti',
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
    total_contract_sal = fields.Monetary(
        string='Totale Contrattuale SAL',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Somma «Tot. € Contrattuali» delle voci SAL (foglio Voci Contrattuali).',
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

    @api.depends('previous_revision_id', 'previous_revision_id.revision_root_id')
    def _compute_revision_root(self):
        for rec in self:
            prev = rec.previous_revision_id
            if prev:
                rec.revision_root_id = prev.revision_root_id or prev
            else:
                rec.revision_root_id = rec

    @api.depends('name')
    def _compute_revision_same_name_count(self):
        Estimate = self.env['sbu.estimate']
        for rec in self:
            name = rec.name
            if not name or name == _('New'):
                rec.revision_same_name_count = 0
            else:
                rec.revision_same_name_count = Estimate.search_count([('name', '=', name)])

    @api.depends(
        'line_ids.price_total_tot',
        'line_ids.cost_total_tot',
        'line_ids.sqm',
        'sal_line_ids.total_contract',
    )
    def _compute_totals(self):
        for rec in self:
            rec.total_sqm = sum(rec.line_ids.mapped('sqm'))
            rec.total_price = sum(rec.line_ids.mapped('price_total_tot'))
            rec.total_cost = sum(rec.line_ids.mapped('cost_total_tot'))
            rec.total_contract_sal = sum(rec.sal_line_ids.mapped('total_contract'))

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
        if self.approval_required and self.approval_state != 'approved':
            raise UserError(
                _('Impossibile inviare: richiesta approvazione interna non completata '
                  '(stato deve essere «Approvato»).')
            )
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
            'previous_revision_id': self.id,
            'project_id': False,
            'approval_state': 'na',
            'approved_by_id': False,
            'approved_on': False,
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

    def action_view_revision_chain(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Revisioni stesso preventivo'),
            'res_model': 'sbu.estimate',
            'view_mode': 'list,form',
            'domain': [('name', '=', self.name)],
            'context': {'default_name': self.name},
        }

    def _require_approver_rights(self):
        if not self.env.user.has_group('sbu_estimate.group_sbu_estimate_approver'):
            raise UserError(_('Operazione riservata agli approvatori preventivi SBU.'))

    def action_request_internal_approval(self):
        for rec in self:
            if not rec.approval_required:
                raise UserError(_('Attivare «Richiede approvazione interna» prima di richiedere l\'approvazione.'))
            if rec.approval_state == 'pending':
                continue
            if rec.approval_state not in ('na', 'rejected'):
                raise UserError(_('Stato approvazione non compatibile con una nuova richiesta.'))
            rec.write({
                'approval_state': 'pending',
                'approved_by_id': False,
                'approved_on': False,
            })

    def action_approve_internal(self):
        self._require_approver_rights()
        for rec in self:
            if rec.approval_state != 'pending':
                raise UserError(_('Solo preventivi «In approvazione» possono essere approvati.'))
            rec.write({
                'approval_state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_on': fields.Datetime.now(),
            })

    def action_reject_internal(self):
        self._require_approver_rights()
        for rec in self:
            if rec.approval_state != 'pending':
                raise UserError(_('Solo preventivi «In approvazione» possono essere rifiutati.'))
            rec.write({
                'approval_state': 'rejected',
                'approved_by_id': False,
                'approved_on': False,
            })
