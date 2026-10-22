# -*- coding: utf-8 -*-
import base64
import csv
import io
import json
import posixpath
import zipfile

from odoo import fields, models, _
from odoo.exceptions import UserError


class SbuQontoExportImportWizard(models.TransientModel):
    """Load a full Qonto export (zip) into Qonto movements — no API needed.

    Expected zip content (any top folder): ``organization.json``,
    ``transactions_*.json`` (Qonto API transaction dicts), and optionally
    ``attachments_index.csv`` + ``attachments/`` with the receipt files.
    """
    _name = 'sbu.qonto.export.import.wizard'
    _description = 'Import Qonto export archive'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    data_file = fields.Binary(string='Qonto export (.zip)', required=True)
    data_filename = fields.Char(string='File name')
    import_movements = fields.Boolean(string='Bank movements', default=True)
    movements_done = fields.Boolean()
    import_attachments = fields.Boolean(
        string='Attach receipts to movements',
        default=True,
        help='Attach the receipt files listed in attachments_index.csv to each imported movement.',
    )
    result_message = fields.Text(string='Result', readonly=True)

    def _sbu_open_zip(self):
        self.ensure_one()
        try:
            return zipfile.ZipFile(io.BytesIO(base64.b64decode(self.data_file)))
        except (zipfile.BadZipFile, ValueError) as err:
            raise UserError(_('The file is not a valid zip archive: %s', err)) from err

    @staticmethod
    def _sbu_members_by_basename(zf):
        return {posixpath.basename(n): n for n in zf.namelist() if not n.endswith('/')}

    @staticmethod
    def _sbu_account_names(zf, members):
        """Map Qonto bank_account_id → 'name (IBAN)' from organization.json."""
        if 'organization.json' not in members:
            return {}
        org = json.loads(zf.read(members['organization.json']).decode('utf-8'))
        accounts = (org.get('organization') or org).get('bank_accounts') or []
        return {
            acc.get('id'): ' '.join(filter(None, [acc.get('name'), acc.get('iban') and f"({acc['iban']})"]))
            for acc in accounts
        }

    @staticmethod
    def _sbu_receipts_by_transaction(zf, members):
        """transaction_id → [zip member path] from attachments_index.csv."""
        if 'attachments_index.csv' not in members:
            return {}
        index_path = members['attachments_index.csv']
        folder = posixpath.join(posixpath.dirname(index_path), 'attachments')
        text = zf.read(index_path).decode('utf-8-sig')
        names = set(zf.namelist())
        result = {}
        for row in csv.DictReader(io.StringIO(text), delimiter=';'):
            path = posixpath.join(folder, row.get('file') or '')
            if row.get('transaction_id') and path in names:
                result.setdefault(row['transaction_id'], []).append(path)
        return result

    def _sbu_attach_receipts(self, zf, movement, paths):
        Attachment = self.env['ir.attachment'].sudo()
        existing = set(Attachment.search([
            ('res_model', '=', movement._name),
            ('res_id', '=', movement.id),
        ]).mapped('name'))
        count = 0
        for path in paths:
            name = posixpath.basename(path)
            if name in existing:
                continue
            Attachment.create({
                'name': name,
                'datas': base64.b64encode(zf.read(path)),
                'res_model': movement._name,
                'res_id': movement.id,
            })
            count += 1
        return count

    def action_import(self):
        self.ensure_one()
        zf = self._sbu_open_zip()
        members = self._sbu_members_by_basename(zf)
        messages = []
        if self.import_movements and not self.movements_done:
            messages.append(self._sbu_import_movements(zf, members))
            self.movements_done = True
        messages += self._sbu_import_history(zf, members)
        if not messages:
            raise UserError(_('Nothing selected to import.'))
        self.result_message = '\n'.join(filter(None, [self.result_message] + messages))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _sbu_import_history(self, zf, members):
        """Hook for contacts and invoices (sbu_qonto_history_import)."""
        return []

    def _sbu_import_movements(self, zf, members):
        company = self.company_id
        tx_files = sorted(
            path for name, path in members.items()
            if name.startswith('transactions_') and name.endswith('.json')
        )
        if not tx_files:
            raise UserError(_('No transactions_*.json file found in the archive.'))
        account_names = self._sbu_account_names(zf, members)
        receipts = self._sbu_receipts_by_transaction(zf, members) if self.import_attachments else {}

        Movement = self.env['sbu.qonto.transaction'].sudo().with_company(company)
        created = skipped = attached = 0
        for path in tx_files:
            txs = json.loads(zf.read(path).decode('utf-8'))
            if isinstance(txs, dict):
                txs = txs.get('transactions') or []
            for tx in txs:
                remote_id = str(tx.get('id') or tx.get('transaction_id') or '').strip()
                if not remote_id:
                    continue
                movement = Movement.search([
                    ('company_id', '=', company.id),
                    ('qonto_remote_id', '=', remote_id),
                ], limit=1)
                if movement:
                    skipped += 1
                else:
                    movement = Movement.qonto_upsert_from_dict(company, tx, 'export')
                    created += 1
                if not movement.qonto_account_name and tx.get('bank_account_id') in account_names:
                    movement.qonto_account_name = account_names[tx['bank_account_id']]
                if remote_id in receipts:
                    attached += self._sbu_attach_receipts(zf, movement, receipts[remote_id])

        return _(
            '%(created)s movement(s) imported, %(skipped)s already present, '
            '%(attached)s receipt file(s) attached.',
            created=created, skipped=skipped, attached=attached,
        )

    def action_open_movements(self):
        return self.env['ir.actions.act_window']._for_xml_id('sbu_qonto.action_sbu_qonto_transaction')
