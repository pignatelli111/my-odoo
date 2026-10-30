# -*- coding: utf-8 -*-
import base64

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

JOURNAL_IBAN = 'IT60X0542811101000000123456'
CUSTOMER_IBAN = 'IT02A0301503200000003517230'


@tagged('post_install', '-at_install')
class TestSbuBankStatementImport(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.env['account.journal'].create({
            'name': 'Banca Test', 'code': 'BTST', 'type': 'bank', 'bank_acc_number': JOURNAL_IBAN,
        })
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente Spa'})
        cls.env['res.partner.bank'].create({'partner_id': cls.customer.id, 'acc_number': CUSTOMER_IBAN})
        cls.cur = cls.journal.currency_id.name or cls.env.company.currency_id.name

    def _import(self, content, filename='estratto.csv', **vals):
        wizard = self.env['sbu.bank.statement.import.wizard'].create(dict({
            'journal_id': self.journal.id, 'data_file': base64.b64encode(content), 'filename': filename,
        }, **vals))
        wizard.action_import()
        return wizard

    def _lines(self):
        return self.env['account.bank.statement.line'].search([('journal_id', '=', self.journal.id)])

    def test_italian_csv_pays_invoice_and_skips_duplicates(self):
        invoice = self.init_invoice('out_invoice', partner=self.customer, amounts=[1220.0], taxes=[], post=True)
        csv_file = (
            'Estratto conto;;;;;\n'
            'Data contabile;Data valuta;Descrizione;Dare;Avere;Divisa\n'
            f'02/03/2026;02/03/2026;BONIFICO DA CLIENTE SPA SALDO {invoice.name};;1.220,00;{self.cur}\n'
            f'03/03/2026;03/03/2026;ADDEBITO SDD TIM;54,05;;{self.cur}\n'
            f'03/03/2026;03/03/2026;ADDEBITO SDD TIM;54,05;;{self.cur}\n'
            ';;Saldo finale;;12.000,00;\n'
        ).encode('cp1252')
        wizard = self._import(csv_file)
        lines = self._lines()
        self.assertEqual(len(lines), 3, 'two identical debits are two lines; the balance line is ignored')
        self.assertAlmostEqual(sum(lines.mapped('amount')), 1220.0 - 108.10)
        paid_line = lines.filtered(lambda l: l.amount > 0)
        self.assertTrue(paid_line.is_reconciled)
        self.assertEqual(paid_line.partner_id, self.customer)
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        self.assertIn('1 by paying the invoice', wizard.result_message)

        again = self._import(csv_file)
        self.assertEqual(len(self._lines()), 3, 'importing the same file again adds nothing')
        self.assertIn('3 already present', again.result_message)

    def test_camt_reconciles_existing_payment(self):
        invoice = self.init_invoice('out_invoice', partner=self.customer, amounts=[500.0], taxes=[], post=True)
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': fields.Date.to_date('2026-03-01'), 'journal_id': self.journal.id})._create_payments()
        camt = f'''<?xml version="1.0"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt>
  <Acct><Id><IBAN>{JOURNAL_IBAN}</IBAN></Id><Ccy>{self.cur}</Ccy></Acct>
  <Ntry><Amt Ccy="{self.cur}">500.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts>
    <BookgDt><Dt>2026-03-03</Dt></BookgDt><AcctSvcrRef>BANK-REF-1</AcctSvcrRef>
    <NtryDtls><TxDtls><RltdPties><Dbtr><Nm>Cliente Spa</Nm></Dbtr><DbtrAcct><Id><IBAN>{CUSTOMER_IBAN}</IBAN></Id></DbtrAcct>
    </RltdPties><RmtInf><Ustrd>Acconto</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>
  <Ntry><Amt Ccy="{self.cur}">80.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts><Cd>PDNG</Cd></Sts>
    <BookgDt><Dt>2026-03-04</Dt></BookgDt></Ntry>
</Stmt></BkToCstmrStmt></Document>'''.encode()
        self._import(camt, 'statement.xml')
        line = self._lines()
        self.assertEqual(len(line), 1, 'pending entries are not imported')
        self.assertEqual(line.sbu_import_ref, 'cBANK-REF-1')
        self.assertEqual(line.partner_id, self.customer, 'counterparty found by IBAN')
        self.assertTrue(line.is_reconciled)
        self.assertTrue(payment.is_matched)

    def test_wrong_account_currency_or_file_is_refused(self):
        other_iban = f'''<Document><BkToCstmrStmt><Stmt><Acct><Id><IBAN>{CUSTOMER_IBAN}</IBAN></Id></Acct>
<Ntry><Amt Ccy="{self.cur}">1.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><BookgDt><Dt>2026-03-03</Dt></BookgDt></Ntry>
</Stmt></BkToCstmrStmt></Document>'''.encode()
        with self.assertRaises(UserError):
            self._import(other_iban, 'statement.xml')
        with self.assertRaises(UserError):
            self._import(b'Date,Amount,Currency\n2026-03-03,10.00,XXX\n')
        with self.assertRaises(UserError):
            self._import(b'just some text without columns')
        self.assertFalse(self._lines())
