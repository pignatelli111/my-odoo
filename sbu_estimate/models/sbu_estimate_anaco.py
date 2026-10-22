# -*- coding: utf-8 -*-
import json

from markupsafe import Markup, escape

from odoo import _, api, fields, models

from .sbu_anaco_engine import ANACO_COMPONENTS, ANACO_OVERHEADS, is_installation_label

_RULE_FIELDS = ('anaco_staffame_rate_ml', 'anaco_staffame_multiplier', 'anaco_posa_rate_sqm', 'anaco_posa_min_sqm')


class SbuEstimate(models.Model):
    _inherit = 'sbu.estimate'

    # ── ANACO row 5 parameters ────────────────────────────────────────────────
    anaco_layout = fields.Selection(
        [('rev7', 'ANACO standard (REV7)'), ('p1002', 'ANACO P1002 (facciate)')],
        string='Modello ANACO', default='rev7',
        help='Modello del file Excel importato: cambia solo le intestazioni delle 16 colonne costo.',
    )
    anaco_pct_transport = fields.Float(
        string='Trasporto e imballo %', digits=(16, 4),
        help='ANACO $BE$5: trasporto = costo materiale lavorato e posato (BB) × %.',
    )
    anaco_pct_tech_pm = fields.Float(
        string='Sviluppo tecnico e PM %', digits=(16, 4),
        help='ANACO $BG$5: sviluppo tecnico e PM = BB × %.',
    )
    anaco_pct_site = fields.Float(
        string='Presidio cantiere %', digits=(16, 4),
        help='ANACO $BI$5: presidio cantiere / site management = BB × %.',
    )
    anaco_pct_extra = fields.Float(
        string='Extra %', digits=(16, 4),
        help='ANACO $BK$5: extra = BB × %.',
    )
    anaco_pct_industrial = fields.Float(
        string='Costi industriali % (default righe)', digits=(16, 4),
        help='ANACO $BM$5: valore proposto sulle nuove righe (ogni riga ha il suo %).',
    )
    anaco_pct_mol = fields.Float(
        string='MOL % (default righe)', digits=(16, 4),
        help='ANACO $BP$5: valore proposto sulle nuove righe (ogni riga ha il suo %).',
    )
    anaco_staffame_rate_ml = fields.Float(
        string='Staffame €/ml perimetro', digits=(16, 4),
        help='Regola colonna P: staffame CAD = 2 × (B + H) / 1000 × €/ml. 0 = valore inserito a mano.',
    )
    anaco_staffame_multiplier = fields.Float(
        string='Staffame moltiplicatori (Q5 × R5)', digits=(16, 4), default=1.0,
        help='Sconti / ricarichi sullo staffame: R = P × $Q$5 × $R$5.',
    )
    anaco_posa_rate_sqm = fields.Float(
        string='Posa €/m²', digits=(16, 4),
        help='Regola colonna AV: posa CAD = MAX(MQ/cad, MQ minimo) × €/m². 0 = valore inserito a mano.',
    )
    anaco_posa_min_sqm = fields.Float(
        string='Posa MQ minimo per pezzo', digits=(16, 3),
        help='MQ minimo fatturato per la posa di un pezzo (es. 1,8 in =MAX(G13;1,8)*60).',
    )
    anaco_discount_after_sign = fields.Float(
        string='Sconto dopo firma %', digits=(16, 4),
        help='SUMMARY COSTI C26: percentuale di sconto dopo firma (rebate da fornitori).',
    )
    anaco_column_labels = fields.Text(
        string='Intestazioni colonne ANACO',
        help='JSON {campo: intestazione Excel} letto dalla riga 4 del file importato.',
    )
    anaco_installation_total = fields.Monetary(
        string='Posa TOT',
        compute='_compute_anaco_summary_totals',
        store=True,
        currency_field='currency_id',
        help='Somma delle colonne posa del file (es. "Smontaggio Posa Ser e Oscur." AW + "Posa Lamiera" AY).',
    )
    anaco_overhead_total = fields.Monetary(
        string='Trasporto + PM + cantiere + extra TOT',
        compute='_compute_anaco_summary_totals',
        store=True,
        currency_field='currency_id',
    )
    anaco_summary_html = fields.Html(
        string='Riepilogo costi (SUMMARY COSTI)',
        compute='_compute_anaco_summary_html',
        sanitize=False,
    )

    def _sbu_anaco_labels(self):
        self.ensure_one()
        labels = {field: label for field, _cad, _tot, label in ANACO_COMPONENTS}
        try:
            labels.update(json.loads(self.anaco_column_labels or '{}'))
        except ValueError:
            pass
        return labels

    def _sbu_anaco_component_totals(self):
        """[(label, total)] per ANACO cost column (Excel O, S, W … BA), in Excel order."""
        self.ensure_one()
        labels = self._sbu_anaco_labels()
        totals = []
        for field, _cad, _tot, _label in ANACO_COMPONENTS:
            total = sum((line[field] or 0.0) * (line.qty or 0.0) for line in self.line_ids)
            totals.append((field, labels[field], total))
        return totals

    @api.depends(
        'line_ids.qty', 'line_ids.cost_trasporto_tot', 'line_ids.cost_tech_pm_tot',
        'line_ids.cost_cantiere_tot', 'line_ids.cost_extra_tot', 'anaco_column_labels',
        *(f'line_ids.{c[0]}' for c in ANACO_COMPONENTS),
    )
    def _compute_anaco_summary_totals(self):
        for estimate in self:
            estimate.anaco_installation_total = sum(
                total for _f, label, total in estimate._sbu_anaco_component_totals() if is_installation_label(label)
            )
            estimate.anaco_overhead_total = sum(
                sum(estimate.line_ids.mapped(tot_field)) for _p, _c, tot_field, *_rest in ANACO_OVERHEADS
            )

    def _compute_anaco_summary_html(self):
        for estimate in self:
            if not estimate.line_ids:
                estimate.anaco_summary_html = False
                continue
            factor = 1.0 - (estimate.anaco_discount_after_sign or 0.0) / 100.0
            rows = [(label, total) for _f, label, total in estimate._sbu_anaco_component_totals()]
            rows += [
                (label, sum(estimate.line_ids.mapped(tot_field)))
                for _p, _c, tot_field, _cc, _tc, label in ANACO_OVERHEADS
            ]
            rows += [
                (_('Costi industriali da costi materiale'), sum(estimate.line_ids.mapped('cost_industrial_tot'))),
                (_('MOL su base costi materiale'), sum(estimate.line_ids.mapped('cost_mol_amount_tot'))),
            ]
            fmt = estimate._sbu_anaco_format_amount
            body = Markup('').join(
                Markup('<tr><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td></tr>') % (
                    label, fmt(total), fmt(total * factor))
                for label, total in rows
            )
            grand = sum(total for _label, total in rows)
            estimate.anaco_summary_html = Markup(
                '<table class="table table-sm o_sbu_anaco_summary"><thead><tr>'
                '<th>%s</th><th class="text-end">%s</th><th class="text-end">%s</th></tr></thead>'
                '<tbody>%s</tbody><tfoot>'
                '<tr><td>%s</td><td class="text-end">%s</td><td></td></tr>'
                '<tr><th>%s</th><th class="text-end">%s</th><th class="text-end">%s</th></tr>'
                '</tfoot></table>'
            ) % (
                _('Voce'), _('Totale'), _('Dopo sconto firma'), body,
                _('Rebate da fornitori totale'), fmt(grand * (1.0 - factor)),
                _('Totale'), fmt(grand), fmt(grand * factor),
            )

    def _sbu_anaco_format_amount(self, amount):
        self.ensure_one()
        return escape(self.currency_id.format(amount) if self.currency_id else f'{amount:,.2f}')

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in _RULE_FIELDS):
            self.line_ids._sbu_apply_anaco_rules()
        return res
