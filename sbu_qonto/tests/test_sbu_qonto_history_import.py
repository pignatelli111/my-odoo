# -*- coding: utf-8 -*-
import base64
import io
import json
import zipfile
from unittest.mock import patch

from reportlab.pdfgen import canvas

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.sbu_qonto.services.qonto_invoice_pdf import parse_vat_summary
from odoo.addons.sbu_qonto.wizards import sbu_qonto_history_import

OWN_IBAN = 'IT95L3609201600156546724241'
SUPPLIER_IBAN = 'IT60X0542811101000000123456'


def _pdf(lines):
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf)
    y = 800
    for line in lines:
        pdf.drawString(40, y, line)
        y -= 16
    pdf.save()
    return buf.getvalue()


def _money(value):
    return {'value': f'{value:.2f}', 'currency': 'EUR'}


def _export_zip():
    einvoice_pdf = _pdf([
        'FATTURA', 'Numero documento: 44', 'Identificativo SDI: 17943662183',
        'Imponibile Imposta IVA (%) Natura/Esigibilita Rif. Normativo',
        '€1.000,00 €220,00 22',
        '€100,00 €10,00 10',
        '€50,00 €0,00 0 N2.2',
        'Importo totale documento', '€ 1.380,00',
    ])
    seller = {'name': 'Orgadata Italy S.r.l.', 'vat_number': '08151110965',
              'address': {'street_address': 'Piazza Vetra 17', 'zip_code': '20123', 'city': 'Milano', 'country_code': 'IT'}}
    base = {'is_einvoice': False, 'is_credit_note': False, 'taxes': None, 'seller': None, 'supplier_snapshot': None}
    suppliers = [
        dict(base, id='si-1', status='paid', supplier_name='Orgadata Italy S.r.l.', vat_number='08151110965',
             invoice_number='44', issue_date='2025-03-01', due_date='2025-03-31', total_amount=_money(1380),
             payable_amount=_money(1380), is_einvoice=True, seller=seller,
             supplier_snapshot={'name': 'Orgadata Italy S.r.l.', 'iban': OWN_IBAN},
             matched_transactions=[{'transaction_id': 'tx-pay-1', 'subject_type': 'transaction'}]),
        dict(base, id='si-2', status='to_review', supplier_name='Ferramenta Rossi', vat_number=None,
             invoice_number='A/7', issue_date='2025-04-02', total_amount=_money(122),
             taxes=[{'tax_amount': _money(22), 'tax_rate': '22'}]),
        dict(base, id='si-3', status='paid', supplier_name='Bar Centrale', invoice_number='99',
             issue_date='2025-05-05', total_amount=_money(15.5), payment_date='2025-05-05'),
        dict(base, id='si-4', status='paid', supplier_name='Orgadata Italy S.r.l.', vat_number='08151110965',
             invoice_number='NC1', issue_date='2025-06-01', total_amount=_money(61), is_credit_note=True,
             taxes=[{'tax_amount': _money(11), 'tax_rate': '22'}]),
        dict(base, id='si-5', status='rejected', supplier_name='Spam Srl', invoice_number='1',
             issue_date='2025-06-01', total_amount=_money(10)),
        dict(base, id='si-6', status='paid', supplier_name='Bar Centrale', invoice_number='99',
             issue_date='2025-05-05', total_amount=_money(15.5)),
    ]
    clients_invoices = [{
        'id': 'ci-1', 'number': 'F-E-(25)-08', 'issue_date': '2025-12-12', 'due_date': '2025-12-31',
        'status': 'paid', 'total_amount': _money(732), 'amount_paid': _money(732), 'einvoicing_status': 'approved',
        'client': {'name': 'Vitruvius & Partners S.r.l.', 'vat_number': 'IT11391180962', 'recipient_code': 'SUBM70N',
                   'billing_address': {'street_address': 'Via Stresa 6', 'zip_code': '20125', 'city': 'Milano',
                                       'country_code': 'IT'}},
        'items': [{'title': 'Anticipo', 'description': 'P1002', 'quantity': '1', 'unit_price': _money(600),
                   'vat_rate': '0.22'}],
    }]
    org = {'organization': {'bank_accounts': [{'id': 'acc-1', 'name': 'Conto principale', 'iban': OWN_IBAN}]}}
    transactions = [{'id': 'tx-pay-1', 'bank_account_id': 'acc-1', 'side': 'debit', 'amount': 1380.0,
                     'currency': 'EUR', 'label': 'ORGADATA', 'status': 'completed',
                     'settled_at': '2025-03-20T10:00:00.000Z'}]
    beneficiaries = [
        {'id': 'b-1', 'name': 'Orgadata Italy S.r.l.', 'iban': SUPPLIER_IBAN},
        {'id': 'b-2', 'name': 'Mario Bianchi', 'iban': 'IT02A0301503200000003517230'},
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        root = 'Qonto_Export/'
        zf.writestr(root + 'organization.json', json.dumps(org))
        zf.writestr(root + 'transactions_Conto_principale.json', json.dumps(transactions))
        zf.writestr(root + 'supplier_invoices.json', json.dumps(suppliers))
        zf.writestr(root + 'supplier_invoices_files_index.csv',
                    'id;number;attachment_id\nsi-1;44;2025-03-01_Orgadata_44.pdf\n')
        zf.writestr(root + 'supplier_invoices/2025-03-01_Orgadata_44.pdf', einvoice_pdf)
        zf.writestr(root + 'client_invoices.json', json.dumps(clients_invoices))
        zf.writestr(root + 'client_invoices_files_index.csv', 'id;number;attachment_id\nci-1;F-E-(25)-08;f8.pdf\n')
        zf.writestr(root + 'client_invoices/f8.pdf', _pdf(['Fattura F-E-(25)-08']))
        zf.writestr(root + 'clients.json', json.dumps([]))
        zf.writestr(root + 'sepa_beneficiaries.json', json.dumps(beneficiaries))
    return base64.b64encode(buf.getvalue()), einvoice_pdf


@tagged('post_install', '-at_install')
class TestSbuQontoHistoryImport(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Tax = cls.env['account.tax']
        common = {'amount_type': 'percent', 'company_id': cls.env.company.id}
        cls.tax_p22 = Tax.create(dict(common, name='22% G', amount=22, type_tax_use='purchase'))
        cls.tax_p10 = Tax.create(dict(common, name='10% G', amount=10, type_tax_use='purchase'))
        cls.tax_p0 = Tax.create(dict(common, name='0% N2.2', amount=0, type_tax_use='purchase'))
        cls.tax_s22 = Tax.create(dict(common, name='22% V', amount=22, type_tax_use='sale'))
        cls.zip_data, cls.einvoice_pdf = _export_zip()

    def _run(self, **vals):
        wizard = self.env['sbu.qonto.export.import.wizard'].create(dict(
            {'data_file': self.zip_data, 'data_filename': 'Qonto_Export.zip'}, **vals))
        wizard.action_import()
        return wizard

    def _bill(self, ref):
        return self.env['account.move'].search([('sbu_qonto_document_id', '!=', False), ('ref', '=', ref)])

    def test_pdf_summary_parser(self):
        from odoo.addons.sbu_qonto.services.qonto_invoice_pdf import extract_pdf_text
        summary = parse_vat_summary(extract_pdf_text(self.einvoice_pdf))
        self.assertEqual(summary['total'], 1380.0)
        self.assertEqual(summary['sdi_id'], '17943662183')
        self.assertEqual(
            [(line['net'], line['tax'], line['rate'], line['nature']) for line in summary['lines']],
            [(1000.0, 220.0, 22.0, False), (100.0, 10.0, 10.0, False), (50.0, 0.0, 0.0, 'N2.2')],
        )

    def test_full_history_import(self):
        wizard = self._run()
        self.assertFalse(wizard.has_more)
        self.assertIn('1 movement(s) imported', wizard.result_message)

        bill = self._bill('44')
        self.assertEqual(len(bill), 1)
        self.assertEqual(bill.state, 'posted')
        self.assertEqual(bill.move_type, 'in_invoice')
        self.assertEqual(bill.journal_id.code, 'QSTA')
        self.assertEqual(bill.sbu_qonto_vat_source, 'pdf')
        self.assertAlmostEqual(bill.amount_untaxed, 1150.0)
        self.assertAlmostEqual(bill.amount_tax, 230.0)
        self.assertAlmostEqual(bill.amount_total, 1380.0)
        self.assertEqual(
            sorted(bill.invoice_line_ids.tax_ids.mapped('name')), ['0% N2.2', '10% G', '22% G'],
        )
        self.assertTrue(bill.message_main_attachment_id)
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        payment = bill.matched_payment_ids[:1] or self.env['account.payment'].search([('memo', '=', bill.name)], limit=1)
        movement = self.env['sbu.qonto.transaction'].search([('qonto_remote_id', '=', 'tx-pay-1')])
        self.assertEqual(movement.state, 'matched')
        self.assertEqual(movement.match_vendor_bill_id, bill)
        self.assertTrue(movement.match_payment_id)
        self.assertEqual(movement.match_payment_id.date.isoformat(), '2025-03-20')
        self.assertEqual(movement.match_payment_id.journal_id.code, 'QNTO')
        del payment

        partner = bill.partner_id
        self.assertEqual(partner.name, 'Orgadata Italy S.r.l.')
        self.assertEqual(partner.city, 'Milano')
        self.assertIn('08151110965', (partner.vat or '') + (partner.comment or ''))
        self.assertEqual(partner.bank_ids.mapped('sanitized_acc_number'), [SUPPLIER_IBAN],
                         'own Qonto IBAN must not be added to the supplier')

        from_qonto = self._bill('A/7')
        self.assertEqual(from_qonto.sbu_qonto_vat_source, 'qonto')
        self.assertAlmostEqual(from_qonto.amount_tax, 22.0)
        self.assertAlmostEqual(from_qonto.amount_total, 122.0)
        self.assertEqual(from_qonto.payment_state, 'not_paid')

        no_vat = self._bill('99')
        self.assertEqual(len(no_vat), 1, 'Qonto duplicate is imported once')
        self.assertEqual(no_vat.sbu_qonto_vat_source, 'none')
        self.assertFalse(no_vat.invoice_line_ids.tax_ids)
        self.assertAlmostEqual(no_vat.amount_total, 15.5)

        refund = self._bill('NC1')
        self.assertEqual(refund.move_type, 'in_refund')
        self.assertAlmostEqual(refund.amount_total, 61.0)

        self.assertFalse(self.env['account.move'].search([('sbu_qonto_document_id', '=', 'si-5')]), 'rejected skipped')

        invoice = self.env['account.move'].search([('sbu_qonto_document_id', '=', 'ci-1')])
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(invoice.journal_id.code, 'QSTV')
        self.assertEqual(invoice.ref, 'F-E-(25)-08')
        self.assertAlmostEqual(invoice.amount_total, 732.0)
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.tax_s22)
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        self.assertEqual(invoice.partner_id.customer_rank, 1)

        individual = self.env['res.partner'].search([('name', '=', 'Mario Bianchi')])
        self.assertEqual(individual.bank_ids.sanitized_acc_number, 'IT02A0301503200000003517230')

    def test_reimport_creates_nothing(self):
        self._run()
        count = self.env['account.move'].search_count([('sbu_qonto_document_id', '!=', False)])
        partners = self.env['res.partner'].search_count([])
        wizard = self._run()
        self.assertIn('0 imported', wizard.result_message)
        self.assertEqual(self.env['account.move'].search_count([('sbu_qonto_document_id', '!=', False)]), count)
        self.assertEqual(self.env['res.partner'].search_count([]), partners)

    def test_totals_only_mode_and_batches(self):
        with patch.object(sbu_qonto_history_import, '_BATCH_SIZE', 2):
            wizard = self._run(vat_mode='total', register_payments=False, import_movements=False)
            self.assertTrue(wizard.has_more)
            wizard.action_continue()
            wizard.action_continue()
            self.assertFalse(wizard.has_more)
        bill = self._bill('44')
        self.assertEqual(bill.sbu_qonto_vat_source, 'none')
        self.assertFalse(bill.invoice_line_ids.tax_ids)
        self.assertAlmostEqual(bill.amount_total, 1380.0)
        self.assertEqual(bill.payment_state, 'not_paid')
        self.assertEqual(self.env['account.move'].search_count([('sbu_qonto_document_id', '!=', False)]), 5)
