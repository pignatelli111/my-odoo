# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.base.models.res_bank import sanitize_account_number


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sbu_revolut_counterparty_id = fields.Char(
        string='Revolut counterparty id', copy=False, index=True,
        help='Revolut Business counterparty linked to this contact (synced by IBAN).',
    )
    sbu_revolut_counterparty_account_id = fields.Char(string='Revolut counterparty account id', copy=False)
    sbu_revolut_counterparty_iban = fields.Char(
        string='Revolut counterparty IBAN', copy=False,
        help='IBAN of the Revolut counterparty account used for payments.',
    )

    @api.model
    def _sbu_revolut_sync_counterparties(self, company):
        """Link Odoo contacts to existing Revolut counterparties when an IBAN matches."""
        Bank = self.env['res.partner.bank']
        linked = 0
        for cp in company._sbu_revolut_client().counterparties():
            for acc in cp.get('accounts') or []:
                iban = sanitize_account_number(acc.get('iban') or '')
                if not iban:
                    continue
                bank = Bank.search([
                    ('sanitized_acc_number', '=', iban),
                    '|', ('company_id', '=', False), ('company_id', '=', company.id),
                ], limit=1)
                if not bank:
                    continue
                partner = bank.partner_id.commercial_partner_id
                if partner.sbu_revolut_counterparty_id != cp.get('id') or partner.sbu_revolut_counterparty_iban != iban:
                    partner.write({
                        'sbu_revolut_counterparty_id': cp.get('id'),
                        'sbu_revolut_counterparty_account_id': acc.get('id'),
                        'sbu_revolut_counterparty_iban': iban,
                    })
                    linked += 1
                break
        return linked

    def _sbu_revolut_counterparty_payload(self, partner_bank, currency):
        self.ensure_one()
        iban = sanitize_account_number(partner_bank.acc_number)
        payload = {
            'bank_country': iban[:2],
            'currency': currency.name,
            'iban': iban,
        }
        if partner_bank.bank_bic:
            payload['bic'] = partner_bank.bank_bic.replace(' ', '')
        if self.is_company or not self.name or ' ' not in self.name.strip():
            payload['company_name'] = self.name
        else:
            first, last = self.name.strip().split(' ', 1)
            payload['individual_name'] = {'first_name': first, 'last_name': last}
        if self.street and self.city and self.country_id:
            payload['address'] = {
                'street_line1': self.street,
                'postcode': self.zip or '',
                'city': self.city,
                'country': self.country_id.code,
            }
        return payload

    def _sbu_revolut_ensure_counterparty(self, company, partner_bank, currency):
        """Return (counterparty_id, counterparty_account_id) for the bank account, creating it in Revolut."""
        self.ensure_one()
        partner = self.commercial_partner_id
        iban = sanitize_account_number(partner_bank.acc_number)
        if partner.sbu_revolut_counterparty_id and partner.sbu_revolut_counterparty_iban == iban:
            return partner.sbu_revolut_counterparty_id, partner.sbu_revolut_counterparty_account_id
        cp = company._sbu_revolut_client().create_counterparty(
            partner._sbu_revolut_counterparty_payload(partner_bank, currency),
        )
        account = next(
            (a for a in cp.get('accounts') or [] if sanitize_account_number(a.get('iban') or '') == iban),
            (cp.get('accounts') or [{}])[0],
        )
        if not (cp.get('id') and account.get('id')):
            raise UserError(_('Revolut did not return the counterparty account for %s.', partner.display_name))
        partner.write({
            'sbu_revolut_counterparty_id': cp['id'],
            'sbu_revolut_counterparty_account_id': account['id'],
            'sbu_revolut_counterparty_iban': iban,
        })
        return cp['id'], account['id']
