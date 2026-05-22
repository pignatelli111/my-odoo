# -*- coding: utf-8 -*-
"""Structured commercial conditions + offer print (Cosimo point 16)."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SbuEstimateCommercial(models.Model):
    _inherit = 'sbu.estimate'

    commercial_term_ids = fields.One2many(
        'sbu.estimate.commercial.term',
        'estimate_id',
        string='Condizioni commerciali strutturate',
        copy=True,
    )
    commercial_term_count = fields.Integer(
        compute='_compute_commercial_term_count',
    )
    offer_retention_percent = fields.Float(
        string='Ritenuta offerta (%)',
        digits=(16, 2),
        help='% garanzia indicata in offerta (allineata a SAL / azienda).',
    )
    payment_terms_synced = fields.Text(
        string='Riepilogo pagamento (da righe)',
        compute='_compute_payment_terms_synced',
        help='Generato dalle righe strutturate — confronto con il testo libero legacy.',
    )

    @api.depends('commercial_term_ids')
    def _compute_commercial_term_count(self):
        for rec in self:
            rec.commercial_term_count = len(rec.commercial_term_ids)

    @api.depends(
        'commercial_term_ids',
        'commercial_term_ids.name',
        'commercial_term_ids.choice',
        'commercial_term_ids.percent_value',
        'commercial_term_ids.term_category',
    )
    def _compute_payment_terms_synced(self):
        for rec in self:
            lines = rec.commercial_term_ids.filtered(
                lambda t: t.term_category == 'payment' and t.choice == 'included'
            ).sorted('sequence')
            parts = []
            for term in lines:
                chunk = (term.name or '').strip()
                if term.percent_value and '%' not in chunk[:8]:
                    chunk = f'{term.percent_value:g}% — {chunk}'
                parts.append(chunk)
            rec.payment_terms_synced = '\n'.join(parts) if parts else ''

    @api.model
    def _sbu_default_offer_retention_percent(self):
        company = self.env.company
        if hasattr(company, 'sbu_sal_default_retention_percent'):
            return company.sbu_sal_default_retention_percent or 5.0
        return 5.0

    def _sbu_default_commercial_term_vals_list(self):
        """Standard Suburban offer rows (ANACO green/red flags)."""
        self.ensure_one()
        retention = self.offer_retention_percent or self._sbu_default_offer_retention_percent()
        return [
            {'sequence': 5, 'term_category': 'payment',
             'name': 'Acconto all\'ordine (rimessa diretta)', 'choice': 'included', 'percent_value': 40.0},
            {'sequence': 10, 'term_category': 'payment',
             'name': 'Firma esecutivi', 'choice': 'included', 'percent_value': 30.0},
            {'sequence': 15, 'term_category': 'payment',
             'name': 'SAL mensili (rimessa diretta)', 'choice': 'included', 'percent_value': 30.0},
            {'sequence': 20, 'term_category': 'retention',
             'name': 'Ritenuta a garanzia su SAL e fatture', 'choice': 'included',
             'percent_value': retention},
            {'sequence': 25, 'term_category': 'warranty',
             'name': 'Garanzia per vizi e difetti secondo capitolato', 'choice': 'included'},
            {'sequence': 30, 'term_category': 'delivery',
             'name': 'Resa: franco cantiere', 'choice': 'included'},
            {'sequence': 35, 'term_category': 'delivery',
             'name': 'Tempi di consegna secondo planning approvato', 'choice': 'note'},
            {'sequence': 40, 'term_category': 'inclusion',
             'name': 'Fornitura in opera secondo capitolato e disegni approvati', 'choice': 'included'},
            {'sequence': 45, 'term_category': 'exclusion',
             'name': 'Opere edili, ponteggi, permessi non espressamente inclusi', 'choice': 'excluded'},
            {'sequence': 50, 'term_category': 'exclusion',
             'name': 'Trattamento superfici non previsto in capitolato', 'choice': 'excluded'},
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'offer_retention_percent' not in vals:
                vals['offer_retention_percent'] = self._sbu_default_offer_retention_percent()
        records = super().create(vals_list)
        for rec in records:
            if not rec.commercial_term_ids:
                rec.action_load_default_commercial_terms()
        return records

    def action_load_default_commercial_terms(self):
        """Replace structured terms with Suburban / ANACO defaults."""
        Term = self.env['sbu.estimate.commercial.term']
        for rec in self:
            rec.commercial_term_ids.unlink()
            Term.create([
                dict(vals, estimate_id=rec.id)
                for vals in rec._sbu_default_commercial_term_vals_list()
            ])
            rec._sbu_sync_legacy_condition_fields()
        return True

    def _sbu_sync_legacy_condition_fields(self):
        """Align legacy free-text fields from structured rows."""
        for rec in self:
            included_pay = rec.commercial_term_ids.filtered(
                lambda t: t.term_category == 'payment' and t.choice == 'included'
            ).sorted('sequence')
            if included_pay:
                rec.payment_terms_text = '\n'.join(
                    (t.name or '').strip() for t in included_pay if t.name
                )
            inc = rec.commercial_term_ids.filtered(
                lambda t: t.term_category == 'inclusion' and t.choice == 'included'
            )
            if inc:
                rec.inclusions = '\n'.join(f'• {t.name}' for t in inc if t.name)
            exc = rec.commercial_term_ids.filtered(
                lambda t: t.term_category == 'exclusion'
            )
            if exc:
                rec.exclusions = '\n'.join(
                    f'• {t.name}' for t in exc if t.name
                )

    def action_sync_conditions_from_terms(self):
        self._sbu_sync_legacy_condition_fields()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Condizioni aggiornate'),
                'message': _('Pagamento, inclusioni ed esclusioni allineati alle righe strutturate.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_print_offer(self):
        self.ensure_one()
        report = self.env.ref(
            'sbu_estimate.action_report_sbu_estimate_offer',
            raise_if_not_found=False,
        )
        if not report:
            raise UserError(_('Report offerta SBU non trovato.'))
        return report.with_context(discard_logo_check=True).report_action(self)

    def _sbu_offer_lines_for_report(self):
        """Client-facing rows (OFFERTA-style)."""
        self.ensure_one()
        uom_labels = dict(self.env['sbu.estimate.line']._fields['calc_uom_type'].selection)
        lines = []
        for line in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            unit = line.price_anaco_bs_cad or line.price_total_cad or 0.0
            total = line.price_total_tot or (unit * (line.qty or 0.0))
            if not unit and not total:
                continue
            lines.append({
                'pos': line.pos or '',
                'description': line.description or line.name or '',
                'uom': uom_labels.get(line.calc_uom_type, ''),
                'qty': line.qty or 0.0,
                'unit_price': unit,
                'total': total,
            })
        return lines

    def _sbu_commercial_terms_by_category(self, category):
        self.ensure_one()
        return self.commercial_term_ids.filtered(
            lambda t: t.term_category == category
        ).sorted('sequence')
