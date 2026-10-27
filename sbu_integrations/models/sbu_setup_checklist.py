# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, fields, models

# Document numbering of the SBU modules: (sequence code, model that uses it, label).
# A row is shown only when its model exists (module installed).
SBU_SEQUENCES = (
    ('sbu.estimate', 'sbu.estimate', 'Estimates'),
    ('sbu.project', 'sbu.estimate', 'Job codes'),
    ('sbu.purchase.request', 'sbu.purchase.request', 'Purchase requests (RDA)'),
    ('sbu.sal.sheet', 'sbu.sal.sheet', 'SAL sheets'),
    ('sbu.sal.passive.sheet', 'sbu.sal.passive.sheet', 'Subcontractor SAL'),
    ('sbu.payment.certificate', 'sbu.payment.certificate', 'Payment certificates (CDP)'),
    ('sbu.stock.ddt', 'stock.picking', 'Delivery notes (DDT)'),
    ('sbu.revolut.payment', 'sbu.revolut.payment', 'Revolut payment orders'),
)

_STATUS = {
    'ok': ('text-bg-success', '✔'),
    'missing': ('text-bg-danger', '✖'),
    'optional': ('text-bg-secondary', '–'),
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_setup_checklist_html = fields.Html(
        string='SBU setup checklist',
        compute='_compute_sbu_setup_checklist_html',
        sanitize=False,
    )

    def _sbu_company_url(self, company):
        return f'/odoo/action-base.action_res_company_form/{company.id}'

    def _sbu_setup_checks(self):
        """Rows of the go-live checklist: dicts with label, status (ok / missing / optional), detail, url.

        Modules extend this to add their own settings (SAL accounts, bank connections…).
        """
        self.ensure_one()
        company = self.company_id
        company_url = self._sbu_company_url(company)
        checks = [
            {
                'label': _('Company VAT number'),
                'status': 'ok' if company.vat else 'missing',
                'detail': company.vat or _('Set the VAT number on the company.'),
                'url': company_url,
            },
            {
                'label': _('Company country and currency'),
                'status': 'ok' if company.country_id and company.currency_id else 'missing',
                'detail': ' / '.join(filter(None, [company.country_id.name, company.currency_id.name])),
                'url': company_url,
            },
        ]
        checks += self._sbu_sequence_checks()
        return checks

    def _sbu_sequence_checks(self):
        Sequence = self.env['ir.sequence'].sudo()
        company = self.company_id
        checks = []
        for code, model, label in SBU_SEQUENCES:
            if model not in self.env:
                continue
            sequence = Sequence.search([
                ('code', '=', code), ('company_id', 'in', [company.id, False]),
            ], order='company_id', limit=1)
            checks.append({
                'label': _('Numbering: %s', _(label)),
                'status': 'ok' if sequence else 'missing',
                'detail': _('Next number: %s', sequence.get_next_char(sequence.number_next_actual))
                if sequence else _('Sequence "%s" is missing: upgrade the module.', code),
                'url': f'/odoo/action-base.ir_sequence_form/{sequence.id}' if sequence else False,
            })
        return checks

    def _compute_sbu_setup_checklist_html(self):
        for settings in self:
            checks = settings._sbu_setup_checks()
            rows = []
            for check in checks:
                badge_class, symbol = _STATUS[check['status']]
                link = (
                    Markup('<a href="%s" target="_blank">%s</a>') % (check['url'], _('Open'))
                    if check.get('url') else ''
                )
                rows.append(Markup(
                    '<tr><td><span class="badge %s">%s</span></td><td>%s</td><td class="text-muted">%s</td>'
                    '<td class="text-end">%s</td></tr>'
                ) % (badge_class, symbol, check['label'], check.get('detail') or '', link))
            missing = sum(1 for check in checks if check['status'] == 'missing')
            summary = (
                _('Ready to go live: nothing missing.') if not missing
                else _('%s setting(s) missing before go-live.', missing)
            )
            settings.sbu_setup_checklist_html = Markup(
                '<p class="fw-bold %s">%s</p><table class="table table-sm align-middle mb-0"><tbody>%s</tbody></table>'
            ) % ('text-success' if not missing else 'text-danger', summary, Markup('').join(rows))
