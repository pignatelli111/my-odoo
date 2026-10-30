# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

IBAN = 'IT95L3609201600156546724241'
VAT_IBAN = 'IT56R3609201600530790556788'


@tagged('post_install', '-at_install')
class TestSbuQontoBankStatement(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].create({
            'name': 'Qonto main', 'code': 'QTST', 'type': 'bank', 'bank_acc_number': IBAN,
            'company_id': cls.company.id,
        })
        cls.company.write({
            'sbu_qonto_iban': IBAN,
            'sbu_bank_statement_start_date': fields.Date.to_date('2026-01-01'),
            'sbu_qonto_auto_register_inbound': False,
            'sbu_qonto_auto_match_high': False,
        })
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente Qonto'})

    def _movement(self, remote_id, amount, date, status='completed', account_name=False):
        return self.env['sbu.qonto.transaction'].create({
            'company_id': self.company.id,
            'qonto_remote_id': remote_id,
            'amount': abs(amount),
            'amount_signed': amount,
            'side': 'credit' if amount > 0 else 'debit',
            'currency_id': self.company.currency_id.id,
            'label': f'Movement {remote_id}',
            'status': status,
            'settled_at': f'{date} 10:00:00',
            'partner_id': self.customer.id,
            'qonto_account_name': account_name,
        })

    def _pay(self, movement, invoice):
        movement.write({'match_invoice_id': invoice.id})
        movement.with_context(default_journal_id=self.journal.id).action_register_invoice_payment()
        return movement.match_payment_id

    def test_statement_lines_opening_balance_and_reconciliation(self):
        invoice = self.init_invoice('out_invoice', partner=self.customer, amounts=[1220.0], taxes=[], post=True)
        before = self._movement('q-old', 500.0, '2025-12-01')
        pending = self._movement('q-pending', 80.0, '2026-02-01', status='pending')
        paid = self._movement('q-paid', 1220.0, '2026-03-10')
        payment = self._pay(paid, invoice)
        unpaid = self._movement('q-unpaid', -300.0, '2026-03-12')

        Transaction = self.env['sbu.qonto.transaction']
        created, reconciled = Transaction._sbu_sync_company_statements(self.company)
        self.assertEqual((created, reconciled), (2, 1))
        self.assertFalse(before.statement_line_id, 'before the start date: only in the opening balance')
        self.assertFalse(pending.statement_line_id, 'pending movements are not in Accounting')
        opening = self.env['account.bank.statement.line'].search([
            ('journal_id', '=', self.journal.id), ('sbu_opening_balance', '=', True)])
        self.assertEqual(opening.amount, 500.0)
        self.assertEqual(str(opening.date), '2025-12-31')

        line = paid.statement_line_id
        self.assertEqual(line.journal_id, self.journal)
        self.assertEqual(line.amount, 1220.0)
        self.assertEqual(str(line.date), '2026-03-10')
        self.assertTrue(line.is_reconciled)
        self.assertEqual(paid.statement_status, 'reconciled')
        self.assertTrue(payment.is_matched)
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))

        self.assertEqual(unpaid.statement_status, 'to_reconcile')
        self.assertEqual(unpaid.statement_line_id.amount, -300.0)
        lines = self.env['account.bank.statement.line'].search([('journal_id', '=', self.journal.id)])
        self.assertAlmostEqual(sum(lines.mapped('amount')), 1420.0, msg='opening 500 + 1220 − 300')

        self.assertEqual(Transaction._sbu_sync_company_statements(self.company), (0, 0), 'no duplicates')

    def test_payment_registered_later_reconciles(self):
        invoice = self.init_invoice('out_invoice', partner=self.customer, amounts=[450.0], taxes=[], post=True)
        movement = self._movement('q-late', 450.0, '2026-04-01')
        self.env['sbu.qonto.transaction']._sbu_sync_company_statements(self.company)
        self.assertEqual(movement.statement_status, 'to_reconcile')
        self._pay(movement, invoice)
        self.assertEqual(movement.statement_status, 'reconciled')

    def test_no_start_date_no_sync_and_journal_creation(self):
        self.company.sbu_bank_statement_start_date = False
        movement = self._movement('q-none', 10.0, '2026-05-01', account_name=f'ACCANTONAMENTO IVA ({VAT_IBAN})')
        self.assertEqual(self.env['sbu.qonto.transaction']._sbu_sync_company_statements(self.company), (0, 0))
        self.assertFalse(movement._sbu_stmt_journal())
        self.env['sbu.qonto.transaction'].action_sbu_create_bank_journals()
        journal = movement._sbu_stmt_journal()
        self.assertEqual(journal.bank_account_id.sanitized_acc_number, VAT_IBAN)
        self.assertIn('ACCANTONAMENTO IVA', journal.name)
