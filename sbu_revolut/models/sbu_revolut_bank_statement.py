# -*- coding: utf-8 -*-
from odoo import api, models


class SbuRevolutTransaction(models.Model):
    _name = 'sbu.revolut.transaction'
    _inherit = ['sbu.revolut.transaction', 'sbu.bank.statement.sync.mixin']

    def _sbu_stmt_journal(self):
        self.ensure_one()
        journal = self._sbu_payment_journal()
        if journal and journal.currency_id and journal.currency_id != self.currency_id:
            return journal.browse()  # a EUR journal cannot hold a USD account's movements
        return journal

    def _sbu_stmt_is_final(self):
        return self.revolut_state == 'completed'

    def _sbu_stmt_date(self):
        return self.transfer_date

    def _sbu_stmt_amount(self):
        # Revolut charges the fee on top of the amount: the balance moves by amount − fee.
        return self.amount_signed - (self.fee or 0.0)

    def _sbu_stmt_label(self):
        return ' — '.join(filter(None, [self.label, self.reference]))

    def _sbu_stmt_payment(self):
        return self.match_payment_id

    @api.model
    def _sbu_sync_company_statements(self, company):
        if not company.sbu_bank_statement_start_date:
            return 0, 0
        movements = self.sudo().search([
            ('company_id', '=', company.id),
            '|', ('statement_line_id', '=', False), ('statement_line_id.is_reconciled', '=', False),
        ])
        return movements._sbu_sync_statement_lines()

    def _sbu_post_import_process(self):
        res = super()._sbu_post_import_process()
        for company in self.company_id:
            self._sbu_sync_company_statements(company)
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get('match_payment_id'):
            for rec in self.filtered('statement_line_id'):
                rec._sbu_reconcile_statement_line()
        return res
