from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .sbu_revision_display import (
    sbu_estimate_revision_label,
    sbu_revision_sort_key,
)


class SbuEstimate(models.Model):
    _name = 'sbu.estimate'
    _description = 'SBU Estimate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Quote no.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    revision = fields.Char(
        string='Revision',
        default='REV00',
        tracking=True,
    )
    previous_revision_id = fields.Many2one(
        'sbu.estimate',
        string='Previous revision',
        ondelete='set null',
        index=True,
        copy=False,
    )
    revision_root_id = fields.Many2one(
        'sbu.estimate',
        string='Revision root',
        compute='_compute_revision_root',
        store=True,
        index=True,
        recursive=True,
    )
    full_name = fields.Char(
        string='Full reference',
        compute='_compute_full_name',
        store=True,
    )
    sbu_display_label = fields.Char(
        string='Display label',
        compute='_compute_sbu_display_label',
        store=True,
        index=True,
        help='Name · REV · date (for lists and linked documents).',
    )
    sbu_is_latest_revision = fields.Boolean(
        string='Latest revision',
        compute='_compute_sbu_is_latest_revision',
        store=True,
        help='True if this is the highest REV among quotes with the same number.',
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    date = fields.Date(
        string='Date',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    validity_date = fields.Date(
        string='Offer validity',
        tracking=True,
    )

    # ── Parties ───────────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
    )
    opportunity_id = fields.Many2one(
        'crm.lead',
        string='CRM opportunity',
        domain=[('type', '=', 'opportunity')],
        tracking=True,
    )
    job_site = fields.Char(
        string='Job site / property',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
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
            ('base', 'Base (standard list)'),
            ('aggressive', 'Aggressive'),
            ('risk', 'Risk / contingency'),
        ],
        string='Commercial scenario',
        tracking=True,
    )
    probability = fields.Float(
        string='Win probability (%)',
        default=50.0,
        tracking=True,
    )
    expected_margin_pct = fields.Float(
        string='Expected margin (%)',
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
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    approval_required = fields.Boolean(
        string='Requires internal approval',
        default=False,
        tracking=True,
    )
    approval_state = fields.Selection(
        selection=[
            ('na', 'N/A'),
            ('pending', 'Pending approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Approval status',
        default='na',
        copy=False,
        tracking=True,
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved by',
        readonly=True,
        copy=False,
    )
    approved_on = fields.Datetime(
        string='Approved on',
        readonly=True,
        copy=False,
    )
    revision_same_name_count = fields.Integer(
        string='Revisions (same quote no.)',
        compute='_compute_revision_same_name_count',
    )

    # ── Lines ─────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'sbu.estimate.line',
        'estimate_id',
        string='Righe Preventivo (ANACO)',
    )
    item_bom_line_ids = fields.One2many(
        'sbu.estimate.bom.line',
        'estimate_id',
        string='Distinta Base (ITEM)',
        help='Componenti distinta per tutte le righe ANACO del preventivo.',
    )
    item_bom_line_count = fields.Integer(
        string='Righe distinta',
        compute='_compute_item_bom_line_count',
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
        string='Total sqm',
        compute='_compute_totals',
        store=True,
        digits=(16, 2),
    )
    total_price = fields.Monetary(
        string='Total customer price',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    client_price_per_sqm = fields.Float(
        string='Customer price / sqm',
        compute='_compute_totals',
        store=True,
        digits=(16, 2),
        help='Prezzo cliente totale del preventivo ÷ MQ totali (€/m² vendita).',
    )
    total_cost = fields.Monetary(
        string='Total cost',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    total_contract_sal = fields.Monetary(
        string='Contract SAL total',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Somma «Tot. € Contrattuali» delle voci SAL (foglio Voci Contrattuali).',
    )
    sal_amount_billed = fields.Monetary(
        string='SAL billed to date',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    sal_amount_remaining = fields.Monetary(
        string='SAL remaining to bill',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    sal_retention_cap = fields.Monetary(
        string='SAL retention amount (cap)',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Sum of contractual retention amounts (garanzia pool on the estimate).',
    )
    sal_retention_withheld = fields.Monetary(
        string='SAL retention withheld',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Garanzia already withheld on progress billing (money held until release).',
    )
    sal_retention_remaining = fields.Monetary(
        string='SAL retention remaining',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    margin_amount = fields.Monetary(
        string='Margin €',
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
        string='Project',
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

    @api.depends('name', 'revision', 'date', 'job_site')
    def _compute_sbu_display_label(self):
        for rec in self:
            rec.sbu_display_label = sbu_estimate_revision_label(rec) or rec.name

    @api.depends('name', 'revision')
    def _compute_sbu_is_latest_revision(self):
        Estimate = self.env['sbu.estimate']
        for rec in self:
            name = rec.name
            if not name or name == _('New'):
                rec.sbu_is_latest_revision = True
                continue
            siblings = Estimate.search([('name', '=', name)])
            if len(siblings) <= 1:
                rec.sbu_is_latest_revision = True
                continue
            my_key = sbu_revision_sort_key(rec.revision)
            max_key = max(sbu_revision_sort_key(s.revision) for s in siblings)
            rec.sbu_is_latest_revision = my_key >= max_key

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

    @api.depends('item_bom_line_ids')
    def _compute_item_bom_line_count(self):
        for rec in self:
            rec.item_bom_line_count = len(rec.item_bom_line_ids)

    @api.depends(
        'line_ids.price_total_tot',
        'line_ids.cost_total_tot',
        'line_ids.sqm',
        'sal_line_ids.total_contract',
        'sal_line_ids.amount_billed',
        'sal_line_ids.amount_remaining',
        'sal_line_ids.retention_amount',
        'sal_line_ids.retention_withheld_to_date',
        'sal_line_ids.retention_remaining',
    )
    def _compute_totals(self):
        for rec in self:
            rec.total_sqm = sum(rec.line_ids.mapped('sqm'))
            rec.total_price = sum(rec.line_ids.mapped('price_total_tot'))
            rec.total_cost = sum(rec.line_ids.mapped('cost_total_tot'))
            rec.total_contract_sal = sum(rec.sal_line_ids.mapped('total_contract'))
            rec.sal_amount_billed = sum(rec.sal_line_ids.mapped('amount_billed'))
            rec.sal_amount_remaining = sum(rec.sal_line_ids.mapped('amount_remaining'))
            rec.sal_retention_cap = sum(rec.sal_line_ids.mapped('retention_amount'))
            rec.sal_retention_withheld = sum(rec.sal_line_ids.mapped('retention_withheld_to_date'))
            rec.sal_retention_remaining = sum(rec.sal_line_ids.mapped('retention_remaining'))
            rec.client_price_per_sqm = (
                rec.total_price / rec.total_sqm if rec.total_sqm else 0.0
            )

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

    def name_get(self):
        if self.env.context.get('sbu_use_estimate_name_only'):
            return super().name_get()
        return [(rec.id, rec.sbu_display_label or rec.name) for rec in self]

    # ── Sequence ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.estimate') or _('New')
        return super().create(vals_list)

    can_delete_preventivo = fields.Boolean(
        string='Can delete',
        compute='_compute_can_delete_preventivo',
        help='Technical: whether this preventivo can be removed (see unlink rules).',
    )

    @api.depends('state', 'project_id', 'sal_line_ids')
    def _compute_can_delete_preventivo(self):
        for rec in self:
            rec.can_delete_preventivo = not bool(rec._sbu_unlink_blocked_reason())

    def _sbu_unlink_blocked_reason(self):
        """Return a translated message if delete is blocked, else empty string."""
        self.ensure_one()
        if self.project_id:
            return _(
                'Cannot delete %s: a project/job is linked. Remove or reassign the project first.'
            ) % self.display_name
        if self.state == 'won':
            return _(
                'Cannot delete a won estimate (%s). Use «Perso» or «Annullato» instead.'
            ) % self.display_name
        if 'sbu.sal.sheet.line' in self.env and self.sal_line_ids:
            billed = self.env['sbu.sal.sheet.line'].search_count([
                ('estimate_sal_line_id', 'in', self.sal_line_ids.ids),
                ('sheet_id.state', 'in', ('confirmed', 'invoiced')),
            ])
            if billed:
                return _(
                    'Cannot delete %s: SAL billing is already confirmed or invoiced.'
                ) % self.display_name
        return ''

    def unlink(self):
        if not self.env.context.get('sbu_force_estimate_unlink'):
            for rec in self:
                reason = rec._sbu_unlink_blocked_reason()
                if reason:
                    raise UserError(reason)
        else:
            self._sbu_check_uat_force_delete_access()
        return super().unlink()

    def action_delete_preventivo(self):
        """Explicit delete entry point (form button + server action)."""
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preventivi'),
            'res_model': 'sbu.estimate',
            'view_mode': 'list,form',
            'target': 'current',
        }

    # ── State transitions ─────────────────────────────────────────────────────
    def action_open_anaco_import_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importa da Excel ANACO'),
            'res_model': 'sbu.estimate.anaco.import.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('sbu_estimate.view_sbu_estimate_anaco_import_wizard_form').id,
            'target': 'new',
            'context': {
                'default_estimate_id': self.id,
                'form_view_initial_mode': 'edit',
            },
        }

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
