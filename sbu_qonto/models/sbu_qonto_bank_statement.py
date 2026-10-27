# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models

from odoo.addons.base.models.res_bank import sanitize_account_number

_IBAN_IN_NAME = re.compile(r'\(([A-Z]{2}\d{2}[A-Z0-9]{10,30})\)')


class SbuQontoTransaction(models.Model):
    _name = 'sbu.qonto.transaction'
    _inherit = ['sbu.qonto.transaction', 'sbu.bank.statement.sync.mixin']

    def _sbu_qonto_iban(self):
        """IBAN of the Qonto account of the movement (export import), else the company Qonto IBAN."""
        self.ensure_one()
        match = _IBAN_IN_NAME.search(self.qonto_account_name or '')
        return sanitize_account_number(match.group(1) if match else (self.company_id.sbu_qonto_iban or ''))

    @api.model
    def _sbu_qonto_journal_for_iban(self, company, iban):
        cache = self.env.context.get('sbu_qonto_journal_cache')
        if cache is not None and (company.id, iban) in cache:
            return cache[(company.id, iban)]
        journal = self.env['account.journal'].search([
            ('company_id', '=', company.id), ('type', '=', 'bank'),
            ('bank_account_id.sanitized_acc_number', '=', iban),
        ], limit=1) if iban else self.env['account.journal']
        if cache is not None:
            cache[(company.id, iban)] = journal
        return journal

    def _sbu_stmt_journal(self):
        self.ensure_one()
        return self._sbu_qonto_journal_for_iban(self.company_id, self._sbu_qonto_iban())

    def _sbu_stmt_is_final(self):
        return (self.status or '').lower() == 'completed'

    def _sbu_stmt_date(self):
        return self.transfer_date

    def _sbu_stmt_amount(self):
        return self.amount_signed

    def _sbu_stmt_label(self):
        return ' — '.join(filter(None, [self.label, self.reference]))

    def _sbu_stmt_payment(self):
        return self.match_payment_id

    def _sbu_sync_statement_lines(self):
        return super(SbuQontoTransaction, self.with_context(sbu_qonto_journal_cache={}))._sbu_sync_statement_lines()

    @api.model
    def _sbu_sync_company_statements(self, company):
        if not company.sbu_bank_statement_start_date:
            return 0, 0
        movements = self.sudo().search([
            ('company_id', '=', company.id),
            '|', ('statement_line_id', '=', False), ('statement_line_id.is_reconciled', '=', False),
        ])
        return movements._sbu_sync_statement_lines()

    def _sbu_post_import_process(self, company):
        res = super()._sbu_post_import_process(company)
        self._sbu_sync_company_statements(company)
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get('match_payment_id'):
            for rec in self.filtered('statement_line_id'):
                rec._sbu_reconcile_statement_line()
        return res

    def action_sbu_create_bank_journals(self):
        """Create a bank journal for every Qonto IBAN of the imported movements that has none."""
        company = self.env.company
        movements = self.search([('company_id', '=', company.id)])
        accounts = {}
        for rec in movements:
            iban = rec._sbu_qonto_iban()
            if iban and iban not in accounts:
                accounts[iban] = (rec.qonto_account_name or '').split(' (')[0].strip()
        Journal = self.env['account.journal']
        created = []
        for iban, name in accounts.items():
            if self._sbu_qonto_journal_for_iban(company, iban):
                continue
            code, n = 'QNT', 1
            while Journal.search_count([('company_id', '=', company.id), ('code', '=', code)]):
                n += 1
                code = f'QNT{n}'
            journal = Journal.create({
                'name': _('Qonto %s', name) if name else 'Qonto',
                'code': code,
                'type': 'bank',
                'company_id': company.id,
                'bank_acc_number': iban,
            })
            created.append(journal.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Qonto bank journals'),
                'message': _('Created: %s', ', '.join(created)) if created else _('Every Qonto account has a journal.'),
                'type': 'success',
                'sticky': False,
            },
        }
