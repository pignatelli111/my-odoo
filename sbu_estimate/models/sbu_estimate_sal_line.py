from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .sbu_contract_uom import SBU_CONTRACT_UOM_SELECTION

SAL_STATUS_SELECTION = [
    ('draft', 'Draft'),
    ('prepared', 'Prepared'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('invoiced', 'Invoiced'),
    ('paid', 'Paid'),
]


class SbuEstimateSalLine(models.Model):
    """
    Voci Contrattuali SAL — from the 'Voci Contrattuali_SAL' sheet in ANACO.
    These are the contractual billing items used to generate SAL documents.
    """
    _name = 'sbu.estimate.sal.line'
    _description = 'SBU Estimate SAL Contractual Line'
    _order = 'sequence'

    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        related='estimate_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='estimate_id.currency_id',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)

    estimate_line_ids = fields.Many2many(
        'sbu.estimate.line',
        'sbu_estimate_sal_line_estimate_line_rel',
        'sal_line_id',
        'estimate_line_id',
        string='Linked estimate lines',
        domain="[('estimate_id', '=', estimate_id)]",
        help='ANACO rows that support this contractual item (one, many, or none if manual).',
    )

    # ── Item reference ────────────────────────────────────────────────────────
    item_ref = fields.Char(string='Item / Riferimento')
    description = fields.Text(string='Descrizione', required=True)

    # ── Contractual values ────────────────────────────────────────────────────
    uom_type = fields.Selection(
        selection=SBU_CONTRACT_UOM_SELECTION,
        string='U.M. Contrattuale',
        default='mq',
    )

    qty_contract = fields.Float(string='Q.tà Contrattuale', digits=(16, 3))
    unit_price = fields.Float(string='Importo Unitario', digits=(16, 2))
    total_contract = fields.Monetary(
        string='Tot. € Contrattuali',
        compute='_compute_total',
        store=True,
        currency_field='currency_id',
    )

    retention_percent = fields.Float(
        string='Retention %',
        digits=(16, 2),
        help='Contractual withholding % (garanzia). Defaults to the same rate as SBU SAL sheets. '
             'Used for the retention cap and to interpret withheld amounts on progress billing.',
    )
    retention_amount = fields.Monetary(
        string='Retention amount',
        compute='_compute_retention_amount',
        store=True,
        currency_field='currency_id',
        help='Total garanzia on this contract item (contract total × retention %). '
             'This is the maximum holdback pool for the item.',
    )
    retention_withheld_to_date = fields.Monetary(
        string='Retention withheld to date',
        compute='_compute_billing_summary',
        store=True,
        currency_field='currency_id',
        help='Garanzia already withheld on confirmed/invoiced SAL billing linked to this item. '
             'This is real money held until release (tracked from SAL / CDP when SBU SAL is used).',
    )
    retention_on_unbilled = fields.Monetary(
        string='Retention on unbilled balance',
        compute='_compute_billing_summary',
        store=True,
        currency_field='currency_id',
        help='Projected holdback if the remaining contract value is billed at the current retention %.',
    )
    retention_remaining = fields.Monetary(
        string='Retention remaining (pool)',
        compute='_compute_billing_summary',
        store=True,
        currency_field='currency_id',
        help='Retention amount minus withheld to date (how much garanzia can still be held on this item).',
    )

    certificate_ref = fields.Char(
        string='Invoice / CDP reference',
        help='Links SAL progress to finance documents. '
             'Filled automatically from linked SAL sheets (invoices and payment certificates) when SBU SAL is used; '
             'you can still type a reference before billing exists.',
    )

    sal_status = fields.Selection(
        selection=SAL_STATUS_SELECTION,
        string='SAL status',
        compute='_compute_sal_status',
        store=True,
        help='Lifecycle: planned on estimate → SAL prepared/submitted → approved → invoiced → paid '
             '(updated from linked SAL sheets, invoices and payment certificates when SBU SAL is used).',
    )

    amount_billed = fields.Monetary(
        string='Billed to date',
        compute='_compute_billing_summary',
        store=True,
        currency_field='currency_id',
        help='Gross progress billed on linked SBU SAL sheet lines (confirmed or invoiced sheets only).',
    )
    amount_remaining = fields.Monetary(
        string='Remaining amount',
        compute='_compute_billing_summary',
        store=True,
        currency_field='currency_id',
        help='Contract total minus billed to date.',
    )
    billing_progress_pct = fields.Float(
        string='% billed',
        compute='_compute_billing_summary',
        store=True,
        digits=(16, 2),
        help='Billed to date ÷ contract total.',
    )

    # ── Floor / orientation breakdown ─────────────────────────────────────────
    floor_pt = fields.Float(string='PT', digits=(16, 2))
    floor_p1 = fields.Float(string='P1', digits=(16, 2))
    floor_p2 = fields.Float(string='P2', digits=(16, 2))
    floor_p3 = fields.Float(string='P3', digits=(16, 2))
    floor_p4 = fields.Float(string='P4', digits=(16, 2))
    floor_p5 = fields.Float(string='P5', digits=(16, 2))
    floor_p6 = fields.Float(string='P6', digits=(16, 2))
    floor_p7 = fields.Float(string='P7', digits=(16, 2))
    floor_p8 = fields.Float(string='P8', digits=(16, 2))

    # ── SAL progress columns (SAL-1 to SAL-10) ────────────────────────────────
    sal_1_pct = fields.Float(string='SAL-1 %', digits=(16, 2))
    sal_2_pct = fields.Float(string='SAL-2 %', digits=(16, 2))
    sal_3_pct = fields.Float(string='SAL-3 %', digits=(16, 2))
    sal_4_pct = fields.Float(string='SAL-4 %', digits=(16, 2))
    sal_5_pct = fields.Float(string='SAL-5 %', digits=(16, 2))
    sal_6_pct = fields.Float(string='SAL-6 %', digits=(16, 2))
    sal_7_pct = fields.Float(string='SAL-7 %', digits=(16, 2))
    sal_8_pct = fields.Float(string='SAL-8 %', digits=(16, 2))
    sal_9_pct = fields.Float(string='SAL-9 %', digits=(16, 2))
    sal_10_pct = fields.Float(string='SAL-10 %', digits=(16, 2))

    cumulative_pct = fields.Float(
        string='Avanzamento Cumulativo %',
        compute='_compute_cumulative',
        store=True,
        digits=(16, 2),
    )

    sal_sheet_line_count = fields.Integer(
        compute='_compute_sal_sheet_line_count',
        string='SAL sheet lines',
    )

    @api.model
    def _sbu_default_retention_percent(self):
        company = self.env.company
        pct = getattr(company, 'sbu_sal_default_retention_percent', None)
        return pct if pct is not None else 5.0

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'retention_percent' in fields_list and not res.get('retention_percent'):
            res['retention_percent'] = self._sbu_default_retention_percent()
        return res

    @api.depends('qty_contract', 'unit_price')
    def _compute_total(self):
        for line in self:
            line.total_contract = line.qty_contract * line.unit_price

    @api.depends('total_contract', 'retention_percent')
    def _compute_retention_amount(self):
        for line in self:
            line.retention_amount = (line.total_contract or 0.0) * (line.retention_percent or 0.0) / 100.0

    @api.depends(
        'sal_1_pct', 'sal_2_pct', 'sal_3_pct', 'sal_4_pct', 'sal_5_pct',
        'sal_6_pct', 'sal_7_pct', 'sal_8_pct', 'sal_9_pct', 'sal_10_pct',
    )
    def _compute_cumulative(self):
        for line in self:
            line.cumulative_pct = (
                line.sal_1_pct + line.sal_2_pct + line.sal_3_pct
                + line.sal_4_pct + line.sal_5_pct + line.sal_6_pct
                + line.sal_7_pct + line.sal_8_pct + line.sal_9_pct
                + line.sal_10_pct
            )

    @api.depends('total_contract', 'retention_percent', 'retention_amount')
    def _compute_billing_summary(self):
        """Defaults without sbu_sal; sbu_sal overrides with SAL sheet line depends."""
        for line in self:
            total = line.total_contract or 0.0
            cap = line.retention_amount or 0.0
            rp = line.retention_percent or 0.0
            line.amount_billed = 0.0
            line.amount_remaining = total
            line.retention_withheld_to_date = 0.0
            line.retention_on_unbilled = total * rp / 100.0
            line.retention_remaining = cap
            line.billing_progress_pct = 0.0

    def _sbu_retention_withheld_for_sheet_line(self, sheet_line):
        """Retention € for one SAL sheet line (override in sbu_sal to use CDP / invoice amounts)."""
        self.ensure_one()
        sheet = sheet_line.sheet_id
        progress = sheet_line.amount_this_sal or 0.0
        if not progress:
            return 0.0
        rp = sheet.retention_percent if sheet.retention_percent else (self.retention_percent or 0.0)
        return progress * rp / 100.0

    @api.depends(
        'estimate_line_ids',
        'cumulative_pct',
        'total_contract',
        'qty_contract',
        'unit_price',
    )
    def _compute_sal_status(self):
        """Without sbu_sal: draft vs prepared from estimate data only."""
        for line in self:
            if line._sbu_sal_status_is_prepared(line):
                line.sal_status = 'prepared'
            else:
                line.sal_status = 'draft'

    def _sbu_sal_status_is_prepared(self, line):
        return bool(
            line.estimate_line_ids
            or line.cumulative_pct
            or (line.qty_contract and line.unit_price)
            or line.total_contract
        )

    def _compute_sal_sheet_line_count(self):
        if 'sbu.sal.sheet.line' not in self.env:
            for line in self:
                line.sal_sheet_line_count = 0
            return
        data = self.env['sbu.sal.sheet.line'].read_group(
            [('estimate_sal_line_id', 'in', self.ids)],
            ['estimate_sal_line_id'],
            ['estimate_sal_line_id'],
        )
        counts = {row['estimate_sal_line_id'][0]: row['estimate_sal_line_id_count'] for row in data}
        for line in self:
            line.sal_sheet_line_count = counts.get(line.id, 0)

    def action_view_sal_sheet_lines(self):
        self.ensure_one()
        if 'sbu.sal.sheet.line' not in self.env:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('SAL sheet lines'),
            'res_model': 'sbu.sal.sheet.line',
            'view_mode': 'list,form',
            'domain': [('estimate_sal_line_id', '=', self.id)],
            'context': {'default_estimate_sal_line_id': self.id},
        }

    @api.constrains(
        'sal_1_pct', 'sal_2_pct', 'sal_3_pct', 'sal_4_pct', 'sal_5_pct',
        'sal_6_pct', 'sal_7_pct', 'sal_8_pct', 'sal_9_pct', 'sal_10_pct',
    )
    def _check_sal_progress_cap(self):
        for line in self:
            total = (
                line.sal_1_pct + line.sal_2_pct + line.sal_3_pct
                + line.sal_4_pct + line.sal_5_pct + line.sal_6_pct
                + line.sal_7_pct + line.sal_8_pct + line.sal_9_pct
                + line.sal_10_pct
            )
            if total > 100.0000001:
                raise ValidationError(
                    _('La somma SAL-1…SAL-10 non può superare il 100%% (riga: %s).')
                    % ((line.description or '')[:80] or line.item_ref or line.id)
                )

    @api.constrains('estimate_line_ids', 'estimate_id')
    def _check_estimate_lines_same_estimate(self):
        for sal in self:
            for eline in sal.estimate_line_ids:
                if eline.estimate_id != sal.estimate_id:
                    raise ValidationError(
                        _('Linked estimate lines must belong to the same estimate as this SAL item.')
                    )
