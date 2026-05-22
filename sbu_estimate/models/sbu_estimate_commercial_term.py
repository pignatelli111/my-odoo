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
