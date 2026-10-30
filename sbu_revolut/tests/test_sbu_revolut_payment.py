# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.sbu_revolut.services import revolut_client as rc
from odoo.addons.sbu_revolut.tests.common import RevolutTestCommon


@tagged('post_install', '-at_install')
class TestSbuRevolutPayment(RevolutTestCommon):

    def _order(self, amount=1000.0):
        bill = self.make_bill(amount)
        action = bill.with_user(self.billing_user).action_sbu_revolut_pay()
        return self.env['sbu.revolut.payment'].browse(action['res_id']), bill

    def _fake_pay(self, fake, state='pending', balance=50000.0):
        fake.on('GET', '/1.0/accounts/acc-eur', {'id': 'acc-eur', 'balance': balance, 'currency': self.eur.name, 'state': 'active'})
        fake.on('POST', '/1.0/counterparty', {
            'id': 'cp-new', 'name': 'Fornitore Srl',
            'accounts': [{'id': 'cpa-new', 'iban': 'IT60X0542811101000000123456', 'currency': self.eur.name}],
        })
        fake.on('POST', '/1.0/pay', lambda body, url: {
            'id': 'rev-tx-1', 'state': state, 'created_at': '2026-10-22T09:00:00Z',
            'completed_at': '2026-10-22T09:00:05Z' if state == 'completed' else None,
        })

    def test_order_defaults_from_bill(self):
        order, bill = self._order(1000.0)
        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.name.startswith('RVP/'))
        self.assertEqual(order.amount, 1000.0)
        self.assertEqual(order.partner_bank_id, self.supplier_bank)
        self.assertEqual(order.account_id, self.rev_eur)
        self.assertEqual(order.reference, 'FT-2026-77')
        self.assertTrue(order.request_id)
        self.assertEqual(bill.sbu_revolut_payment_count, 1)

    def test_cannot_pay_more_than_residual(self):
        order, bill = self._order(1000.0)
        with self.assertRaises(UserError):
            self.env['sbu.revolut.payment'].create(dict(
                self.env['sbu.revolut.payment']._sbu_vals_from_bill(bill), amount=10.0,
            ))
        with self.assertRaises(UserError):
            order.amount = 1500.0

    def test_billing_user_cannot_approve(self):
        order, _bill = self._order()
        with self.assertRaises(UserError):
            order.with_user(self.billing_user).action_approve()

    def test_untrusted_bank_account_blocked(self):
        order, _bill = self._order()
        self.supplier_bank.allow_out_payment = False
        with self.assertRaises(UserError):
            order.with_user(self.approver).action_approve()

    def test_second_approval_must_be_another_person(self):
        self.company.sbu_revolut_second_approval_amount = 5000.0
        order, _bill = self._order(6000.0)
        order.with_user(self.approver).action_approve()
        self.assertEqual(order.state, 'waiting_second')
        with self.assertRaises(UserError):
            order.with_user(self.approver).action_approve()
        order.with_user(self.approver2).action_approve()
        self.assertEqual(order.state, 'approved')
        self.assertEqual(order.second_approved_by_id, self.approver2)

    def test_locked_after_approval(self):
        order, _bill = self._order()
        order.with_user(self.approver).action_approve()
        with self.assertRaises(UserError):
            order.amount = 10.0
        with self.assertRaises(UserError):
            order.unlink()

    def test_send_and_complete_registers_payment(self):
        order, bill = self._order(1000.0)
        order.with_user(self.approver).action_approve()
        self.assertEqual(order.iban, 'IT60X0542811101000000123456')
        with self.fake_revolut() as fake:
            self._fake_pay(fake, state='pending')
            order.with_user(self.approver).action_send_now()
            pay = fake.called('POST', '/1.0/pay')[0]['json']
            self.assertEqual(pay['request_id'], order.request_id)
            self.assertEqual(pay['account_id'], 'acc-eur')
            self.assertEqual(pay['receiver'], {'counterparty_id': 'cp-new', 'account_id': 'cpa-new'})
            self.assertEqual(pay['amount'], 1000.0)
            self.assertEqual(pay['currency'], self.eur.name)
            self.assertEqual(pay['reference'], 'FT-2026-77')
            counterparty = fake.called('POST', '/1.0/counterparty')[0]['json']
            self.assertEqual(counterparty['iban'], 'IT60X0542811101000000123456')
            self.assertEqual(counterparty['company_name'], 'Fornitore Srl')
            self.assertEqual(order.state, 'sent')
            self.assertEqual(self.supplier.sbu_revolut_counterparty_id, 'cp-new')

            # Webhook: the transfer is completed in Revolut.
            completed = self.tx('rev-tx-1', -1000.0, request_id=order.request_id)
            fake.on('GET', '/1.0/transaction/rev-tx-1', completed)
            self.env['sbu.revolut.transaction'].revolut_process_webhook_event(
                self.company, {'event': 'TransactionStateChanged', 'data': {'id': 'rev-tx-1', 'new_state': 'completed'}},
            )
        self.assertEqual(order.state, 'paid')
        self.assertTrue(order.payment_id)
        self.assertEqual(order.payment_id.journal_id, self.bank_journal)
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        movement = self.env['sbu.revolut.transaction'].search([('revolut_remote_id', '=', 'rev-tx-1')])
        self.assertEqual(movement.state, 'matched')
        self.assertEqual(movement.revolut_payment_id, order)
        self.assertEqual(movement.match_vendor_bill_id, bill)

    def test_existing_counterparty_reused_and_immediate_completion(self):
        self.supplier.write({
            'sbu_revolut_counterparty_id': 'cp-old', 'sbu_revolut_counterparty_account_id': 'cpa-old',
            'sbu_revolut_counterparty_iban': 'IT60X0542811101000000123456',
        })
        order, bill = self._order(250.0)
        order.with_user(self.approver).action_approve()
        with self.fake_revolut() as fake:
            self._fake_pay(fake, state='completed')
            order.with_user(self.approver).action_send_now()
            self.assertFalse(fake.called('POST', '/1.0/counterparty'))
            self.assertEqual(fake.called('POST', '/1.0/pay')[0]['json']['receiver']['counterparty_id'], 'cp-old')
        self.assertEqual(order.state, 'paid')
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))

    def test_insufficient_balance_keeps_order_approved(self):
        order, _bill = self._order(1000.0)
        order.with_user(self.approver).action_approve()
        with self.fake_revolut() as fake:
            self._fake_pay(fake, balance=10.0)
            with self.assertRaises(UserError):
                order.with_user(self.approver).action_send_now()
            self.assertFalse(fake.called('POST', '/1.0/pay'))
        self.assertEqual(order.state, 'approved')

    def test_cron_sends_due_payments_and_records_errors(self):
        order, _bill = self._order(1000.0)
        order.with_user(self.approver).action_approve()
        with self.fake_revolut() as fake:
            self._fake_pay(fake)
            fake.on('POST', '/1.0/pay', rc.RevolutHttpError(400, 'Revolut API request failed', '{"message":"Insufficient funds"}'))
            with self.assertLogs('odoo.addons.sbu_revolut.models.sbu_revolut_payment', level='WARNING') as logs:
                self.env['sbu.revolut.payment'].cron_sbu_revolut_payments()
        self.assertIn('Insufficient funds', logs.output[0])
        self.assertEqual(order.state, 'approved')
        self.assertIn('Insufficient funds', order.error_message)

    def test_declined_payment_fails_and_reset_gets_new_request_id(self):
        order, _bill = self._order(1000.0)
        order.with_user(self.approver).action_approve()
        with self.fake_revolut() as fake:
            self._fake_pay(fake, state='pending')
            order.with_user(self.approver).action_send_now()
            fake.on('GET', '/1.0/transaction/rev-tx-1', {'id': 'rev-tx-1', 'state': 'declined', 'reason_code': 'compliance'})
            self.env['sbu.revolut.payment'].cron_sbu_revolut_payments()
        self.assertEqual(order.state, 'failed')
        old_request = order.request_id
        order.action_reset_to_draft()
        self.assertEqual(order.state, 'draft')
        self.assertNotEqual(order.request_id, old_request)
        self.assertFalse(order.approved_by_id)

    def test_trust_removed_after_approval_blocks_send(self):
        order, _bill = self._order(1000.0)
        order.with_user(self.approver).action_approve()
        self.supplier_bank.allow_out_payment = False
        with self.fake_revolut() as fake:
            self._fake_pay(fake)
            with self.assertRaises(UserError):
                order.with_user(self.approver).action_send_now()
            self.assertFalse(fake.called('POST', '/1.0/pay'))

    def test_completed_payment_is_reconciled_in_accounting(self):
        self.company.sbu_bank_statement_start_date = '2026-01-01'
        order, _bill = self._order(1000.0)
        order.with_user(self.approver).action_approve()
        with self.fake_revolut() as fake:
            self._fake_pay(fake, state='pending')
            order.with_user(self.approver).action_send_now()
            fake.on('GET', '/1.0/transaction/rev-tx-1', self.tx('rev-tx-1', -1000.0, request_id=order.request_id))
            self.env['sbu.revolut.transaction'].revolut_process_webhook_event(
                self.company, {'event': 'TransactionStateChanged', 'data': {'id': 'rev-tx-1'}},
            )
        movement = self.env['sbu.revolut.transaction'].search([('revolut_remote_id', '=', 'rev-tx-1')])
        self.assertEqual(movement.statement_line_id.journal_id, self.bank_journal)
        self.assertEqual(movement.statement_line_id.amount, -1000.0)
        self.assertEqual(movement.statement_status, 'reconciled')
        self.assertTrue(order.payment_id.is_matched)
