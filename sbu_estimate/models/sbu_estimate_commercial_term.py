# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

SBU_COMMERCIAL_TERM_CATEGORY = [
    ('payment', 'Modalità di pagamento'),
    ('retention', 'Ritenuta / garanzia'),
    ('warranty', 'Garanzia'),
    ('delivery', 'Resa e tempi'),
    ('inclusion', 'Inclusione'),
    ('exclusion', 'Esclusione'),
    ('other', 'Altro'),
]

SBU_COMMERCIAL_TERM_CHOICE = [
    ('included', 'Incluso (verde)'),
    ('excluded', 'Escluso (rosso)'),
    ('note', 'Nota / informativo'),
]


class SbuEstimateCommercialTerm(models.Model):
    _name = 'sbu.estimate.commercial.term'
    _description = 'SBU Estimate commercial condition (offer print)'
    _order = 'estimate_id, sequence, id'

    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    term_category = fields.Selection(
        selection=SBU_COMMERCIAL_TERM_CATEGORY,
        string='Categoria',
        required=True,
        default='payment',
    )
    name = fields.Char(
        string='Condizione',
        required=True,
        help='Etichetta come in ANACO / OFFERTA (es. «40% acconto all\'ordine»).',
    )
    detail = fields.Text(
        string='Dettaglio',
        help='Testo aggiuntivo (note legali, riferimenti normativi, ecc.).',
    )
    choice = fields.Selection(
        selection=SBU_COMMERCIAL_TERM_CHOICE,
        string='Scelta offerta',
        required=True,
        default='included',
        help='Incluso = flag verde in stampa; Escluso = flag rosso; Nota = neutro.',
    )
    percent_value = fields.Float(
        string='%',
        digits=(16, 2),
        help='Quota pagamento o % ritenuta quando applicabile.',
    )
    currency_id = fields.Many2one(
        related='estimate_id.currency_id',
        store=True,
        readonly=True,
    )
    choice_label = fields.Char(
        string='Flag',
        compute='_compute_choice_label',
    )

    @api.depends('choice')
    def _compute_choice_label(self):
        labels = dict(SBU_COMMERCIAL_TERM_CHOICE)
        for term in self:
            term.choice_label = labels.get(term.choice, '')

    def _sbu_is_printable(self):
        self.ensure_one()
        return self.choice != 'excluded'

    @api.model_create_multi
    def create(self, vals_list):
        terms = super().create(vals_list)
        terms.mapped('estimate_id')._sbu_sync_offer_retention_from_terms()
        return terms

    def write(self, vals):
        res = super().write(vals)
        if any(
            key in vals
            for key in ('term_category', 'choice', 'percent_value', 'estimate_id')
        ):
            self.mapped('estimate_id')._sbu_sync_offer_retention_from_terms()
        return res

    def unlink(self):
        estimates = self.mapped('estimate_id')
        res = super().unlink()
        estimates._sbu_sync_offer_retention_from_terms()
        return res
