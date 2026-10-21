# -*- coding: utf-8 -*-
import base64
import io
import json
import zipfile

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def _sample_export_zip():
    org = {'organization': {'bank_accounts': [
        {'id': 'acc-1', 'name': 'Conto principale', 'iban': 'IT00X0000000000000000000001'},
    ]}}
    txs = [
        {
            'id': 'tx-in-1', 'bank_account_id': 'acc-1', 'side': 'credit',
            'amount': 1220.0, 'currency': 'EUR', 'label': 'CLIENTE SPA',
            'status': 'completed', 'settled_at': '2025-03-10T09:00:00.000Z',
            'emitted_at': '2025-03-10T08:00:00.000Z',
        },
        {
            'id': 'tx-out-1', 'bank_account_id': 'acc-1', 'side': 'debit',
            'amount': 45.5, 'currency': 'EUR', 'label': 'FORNITORE SRL',
            'status': 'completed', 'settled_at': '2025-03-11T09:00:00.000Z',
        },
    ]
    index = (
        'attachment_id;transaction_id;date;label;amount;file\n'
        'att-1;tx-out-1;2025-03-11;FORNITORE SRL;45.5;receipt.pdf\n'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('Qonto_Export/organization.json', json.dumps(org))
        zf.writestr('Qonto_Export/transactions_Conto_principale.json', json.dumps(txs))
        zf.writestr('Qonto_Export/attachments_index.csv', index)
        zf.writestr('Qonto_Export/attachments/receipt.pdf', b'%PDF-1.4 test')
    return base64.b64encode(buf.getvalue())


@tagged('post_install', '-at_install')
class TestSbuQontoExportImport(TransactionCase):

    def _run_wizard(self):
        wizard = self.env['sbu.qonto.export.import.wizard'].create({
            'data_file': _sample_export_zip(),
            'data_filename': 'Qonto_Export.zip',
        })
        wizard.action_import()
        return wizard

    def test_import_creates_movements_with_receipts(self):
        self._run_wizard()
        Movement = self.env['sbu.qonto.transaction']
        movements = Movement.search([('qonto_remote_id', 'in', ['tx-in-1', 'tx-out-1'])])
        self.assertEqual(len(movements), 2)
        out = movements.filtered(lambda m: m.qonto_remote_id == 'tx-out-1')
        self.assertEqual(out.source, 'export')
        self.assertEqual(out.amount_signed, -45.5)
        self.assertEqual(str(out.transfer_date), '2025-03-11')
        self.assertIn('Conto principale', out.qonto_account_name)
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'sbu.qonto.transaction'), ('res_id', '=', out.id),
        ])
        self.assertEqual(attachments.mapped('name'), ['receipt.pdf'])
        inbound = movements - out
        self.assertEqual(inbound.state, 'imported')
        self.assertFalse(inbound.match_payment_id)

    def test_reimport_skips_existing(self):
        self._run_wizard()
        wizard = self._run_wizard()
        self.assertIn('0 movement(s) imported, 2 already present, 0 receipt', wizard.result_message)
        self.assertEqual(
            self.env['sbu.qonto.transaction'].search_count([('qonto_remote_id', '=', 'tx-out-1')]), 1,
        )
