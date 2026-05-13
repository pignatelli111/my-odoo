from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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
    sequence = fields.Integer(default=10)

    # ── Item reference ────────────────────────────────────────────────────────
    item_ref = fields.Char(string='Item / Riferimento')
    description = fields.Text(string='Descrizione', required=True)

    # ── Contractual values ────────────────────────────────────────────────────
    uom_type = fields.Selection([
        ('mq', 'MQ'),
        ('ml', 'ML'),
        ('nr', 'Nr/Pz'),
        ('corpo', 'A Corpo'),
    ], string='U.M. Contrattuale', default='mq')

    qty_contract = fields.Float(string='Q.tà Contrattuale', digits=(16, 3))
    unit_price = fields.Float(string='Importo Unitario', digits=(16, 2))
    total_contract = fields.Float(
        string='Tot. € Contrattuali',
        compute='_compute_total',
        store=True,
        digits=(16, 2),
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

    @api.depends('qty_contract', 'unit_price')
    def _compute_total(self):
        for line in self:
            line.total_contract = line.qty_contract * line.unit_price

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
