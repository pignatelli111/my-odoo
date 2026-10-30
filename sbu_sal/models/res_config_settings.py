# -*- coding: utf-8 -*-
from odoo import _, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def _sbu_setup_checks(self):
        checks = super()._sbu_setup_checks()
        company = self.company_id
        url = self._sbu_company_url(company)
        retention_needed = (company.sbu_sal_default_retention_percent or 0.0) > 0
        account = company.sbu_sal_retention_account_id
        checks += [
            {
                'label': _('SAL retention account'),
                'status': 'ok' if account else ('missing' if retention_needed else 'optional'),
                'detail': account.display_name if account else _(
                    'Needed to invoice SAL with retention (default %s%%).',
                    f'{company.sbu_sal_default_retention_percent:g}'),
                'url': url,
            },
            {
                'label': _('SAL invoice default VAT'),
                'status': 'ok' if company.sbu_sal_default_tax_ids else 'missing',
                'detail': ', '.join(company.sbu_sal_default_tax_ids.mapped('name'))
                or _('Choose the sales VAT used on SAL invoices.'),
                'url': url,
            },
            {
                'label': _('SAL invoice posting'),
                'status': 'ok',
                'detail': dict(company._fields['sbu_sal_invoice_post_default'].selection).get(
                    company.sbu_sal_invoice_post_default) or '',
                'url': url,
            },
        ]
        return checks
