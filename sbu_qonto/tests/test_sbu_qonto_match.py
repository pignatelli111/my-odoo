# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuQontoMatch(TransactionCase):
    def test_payment_reference_high_confidence(self):
        partner = self.env['res.partner'].create({'name': 'Qonto UAT Customer'})
        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        self.assertTrue(journal, 'Bank journal required for payment UAT test')
        pay_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'amount': 500.0,
            'date': '2026-05-10',
            'journal_id': journal.id,
        }
        if 'payment_reference' in self.env['account.payment']._fields:
            pay_vals['payment_reference'] = 'SAL-MAY-2026'
        elif 'memo' in self.env['account.payment']._fields:
            pay_vals['memo'] = 'SAL-MAY-2026'
        payment = self.env['account.payment'].create(pay_vals)
        payment.action_post()

        tx = self.env['sbu.qonto.transaction'].create({
            'company_id': self.env.company.id,
            'qonto_remote_id': 'qonto-uat-001',
            'amount': 500.0,
            'amount_signed': 500.0,
            'currency_id': self.env.company.currency_id.id,
            'side': 'credit',
            'reference': 'SAL-MAY-2026',
            'settled_at': '2026-05-10 12:00:00',
        })
        tx.action_suggest_match()
        self.assertEqual(tx.sbu_match_confidence, 'high')
        self.assertEqual(tx.suggested_payment_id, payment)

        tx.action_match_odoo()
        self.assertEqual(tx.state, 'matched')
        self.assertEqual(tx.match_payment_id, payment)

    def test_invoice_number_high_confidence(self):
        partner = self.env['res.partner'].create({'name': 'Qonto UAT Customer 2'})
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': '2026-05-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Service',
                'quantity': 1,
                'price_unit': 120.0,
            })],
        })
        move.action_post()

        tx = self.env['sbu.qonto.transaction'].create({
            'company_id': self.env.company.id,
            'qonto_remote_id': 'qonto-uat-002',
            'amount': move.amount_total,
            'amount_signed': move.amount_total,
            'currency_id': self.env.company.currency_id.id,
            'side': 'credit',
            'label': 'Payment %s' % move.name,
            'settled_at': '2026-05-12 10:00:00',
        })
        tx.action_suggest_match()
        self.assertIn(tx.sbu_match_confidence, ('high', 'medium'))
        self.assertEqual(tx.suggested_invoice_id, move)

    def test_cron_active_when_company_import_enabled(self):
        self.env.company.sbu_qonto_import_enabled = True
        self.env['res.company']._sbu_sync_qonto_cron_active()
        cron = self.env.ref('sbu_qonto.ir_cron_qonto_import')
        self.assertTrue(cron.active)
        self.env.company.sbu_qonto_import_enabled = False
        self.env['res.company']._sbu_sync_qonto_cron_active()
        self.assertFalse(cron.active)
