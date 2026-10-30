# -*- coding: utf-8 -*-
import base64
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_integrations.services.microsoft_graph import GraphHttpError, SbuMicrosoftGraphClient

LINK = 'https://example.sharepoint.com/:f:/g/personal/x/AbCdEf?e=1'


class FakeDrive:
    """Minimal OneDrive: folders by (parent, name), uploads recorded."""

    def __init__(self):
        self.folders, self.uploads, self.deleted, self.fail_uploads = {}, [], [], 0
        self.backups = []

    def token(self, client):
        return 'token'

    def resolve(self, client, url, token):
        return {'id': 'root-item', 'name': 'ERP Odoo', 'folder': {}, 'parentReference': {'driveId': 'drive-1'}}

    def ensure_folder(self, client, drive_id, parent_id, name, token):
        key = (parent_id, name)
        self.folders.setdefault(key, {'id': f'folder-{len(self.folders) + 1}', 'name': name})
        return self.folders[key]

    def upload_bytes(self, client, drive_id, parent_id, filename, data, token):
        if self.fail_uploads:
            self.fail_uploads -= 1
            raise GraphHttpError(503, 'Service unavailable')
        self.uploads.append((parent_id, filename, data))
        return {'id': f'file-{len(self.uploads)}', 'webUrl': f'https://onedrive/{filename}'}

    def upload_file(self, client, drive_id, parent_id, filename, path, token):
        with open(path, 'rb') as fh:
            self.uploads.append((parent_id, filename, fh.read()))
        return {'id': 'backup'}

    def list_children(self, client, drive_id, item_id, token):
        return self.backups

    def delete_item(self, client, drive_id, item_id, token):
        self.deleted.append(item_id)


@tagged('post_install', '-at_install')
class TestSbuOnedriveSync(TransactionCase):

    def setUp(self):
        super().setUp()
        self.drive = FakeDrive()
        for name, method in (('get_app_access_token', self.drive.token), ('resolve_sharing_link', self.drive.resolve),
                             ('ensure_folder', self.drive.ensure_folder), ('upload_bytes', self.drive.upload_bytes),
                             ('upload_file', self.drive.upload_file), ('list_children', self.drive.list_children),
                             ('delete_item', self.drive.delete_item)):
            # A plain function becomes a method of the client: the fake receives the client first.
            patcher = patch.object(SbuMicrosoftGraphClient, name,
                                   lambda client, *args, _m=method: _m(client, *args))
            patcher.start()
            self.addCleanup(patcher.stop)
        settings = self.env['res.config.settings'].create({
            'sbu_onedrive_sync_link': LINK, 'sbu_onedrive_sync_enabled': True, 'sbu_onedrive_backup_keep': 2,
        })
        settings.action_sbu_onedrive_connect()
        self.Upload = self.env['sbu.onedrive.upload']
        customer = self.env['res.partner'].create({'name': 'OneDrive customer'})
        self.estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        self.job = self.env['project.project'].create({'name': 'OD job', 'sbu_estimate_id': self.estimate.id})

    def _attach(self, record, name='drawing.pdf'):
        return self.env['ir.attachment'].create({
            'name': name, 'res_model': record._name, 'res_id': record.id, 'datas': base64.b64encode(b'%PDF test'),
        })

    def test_connect_stores_the_folder(self):
        icp = self.env['ir.config_parameter'].sudo()
        self.assertEqual(icp.get_param('sbu.onedrive_sync_drive_id'), 'drive-1')
        self.assertEqual(icp.get_param('sbu.onedrive_sync_item_id'), 'root-item')
        self.assertEqual(icp.get_param('sbu.onedrive_sync_root_name'), 'ERP Odoo')

    def test_attachments_are_queued_per_job_and_uploaded(self):
        self._attach(self.job, 'contract.pdf')
        other = self.env['sbu.estimate'].create({'partner_id': self.estimate.partner_id.id})
        self._attach(other, 'request.pdf')
        entries = self.Upload.search([('attachment_id', '!=', False)])
        folders = dict(zip(entries.mapped('filename'), entries.mapped('folder_path')))
        job_folder = self.job.sbu_onedrive_folder_name_effective
        self.assertEqual(folders['contract.pdf'], f'{job_folder}/00 Documenti')
        self.assertEqual(folders['request.pdf'], 'Senza commessa/01 Preventivo')

        self.Upload.cron_sbu_onedrive_sync()
        self.assertEqual(set(entries.mapped('state')), {'done'})
        self.assertEqual(sorted(name for _p, name, _d in self.drive.uploads), ['contract.pdf', 'request.pdf'])
        self.assertTrue(all(entries.mapped('web_url')))
        self.assertEqual(len(self.drive.folders), 4, 'job, 00 Documenti, Senza commessa, 01 Preventivo')
        self._attach(self.job, 'photo.jpg')
        self.Upload.cron_sbu_onedrive_sync()
        self.assertEqual(len(self.drive.folders), 4, 'folders are created once')

    def test_failed_upload_is_retried_then_flagged(self):
        self._attach(self.job)
        entry = self.Upload.search([])
        self.drive.fail_uploads = 1
        with self.assertLogs('odoo.addons.sbu_documents.models.sbu_onedrive_sync', level='WARNING'):
            self.Upload._sbu_process_queue()
        self.assertEqual((entry.state, entry.attempts), ('pending', 1))
        self.Upload._sbu_process_queue()
        self.assertEqual(entry.state, 'done')
        self._attach(self.job, 'broken.pdf')
        broken = self.Upload.search([('filename', '=', 'broken.pdf')])
        self.drive.fail_uploads = 99
        with self.assertLogs('odoo.addons.sbu_documents.models.sbu_onedrive_sync', level='WARNING') as logs:
            for _attempt in range(5):
                self.Upload._sbu_process_queue()
        self.assertEqual(len(logs.output), 5)
        self.assertEqual(broken.state, 'error')
        self.assertIn('503', broken.last_error)

    def test_offer_pdf_snapshot_and_job_export(self):
        self.estimate.state = 'sent'
        with patch.object(type(self.env['ir.actions.report']), '_render_qweb_pdf',
                          lambda self, ref, ids, data=None: (b'%PDF offer', 'pdf')):
            queued = self.Upload._sbu_enqueue_snapshots()
            self.assertEqual(queued.report_ref, 'sbu_estimate.action_report_sbu_estimate_offer')
            self.assertTrue(queued.folder_path.endswith('/01 Preventivo'))
            self.assertFalse(self.Upload._sbu_enqueue_snapshots(), 'a document is queued once')
            self.Upload._sbu_process_queue()
        self.assertEqual(self.drive.uploads[-1][2], b'%PDF offer')
        self._attach(self.estimate, 'calc.xlsx')
        self.job.action_sbu_export_job_to_onedrive()
        self.assertEqual(self.job.sbu_onedrive_upload_count, 2)

    def test_disabled_sync_queues_nothing(self):
        self.env['ir.config_parameter'].sudo().set_param('sbu.onedrive_sync_enabled', 'False')
        self._attach(self.job)
        self.assertFalse(self.Upload.search([]))

    def test_backup_upload_and_retention(self):
        dbname = self.env.cr.dbname

        def fake_build(_self, path):
            with open(path, 'wb') as fh:
                fh.write(b'zip')
            return path

        self.drive.backups = [{'id': f'old-{i}', 'name': f'{dbname}_2026-0{i}-01_0100.zip'} for i in range(1, 5)]
        with patch.object(type(self.Upload), '_sbu_build_backup', fake_build):
            status = self.Upload._sbu_backup_to_onedrive()
        self.assertTrue(status.startswith('OK'), status)
        self.assertTrue(self.drive.uploads[-1][1].startswith(f'{dbname}_'))
        self.assertEqual(sorted(self.drive.deleted), ['old-1', 'old-2'], 'only the 2 most recent are kept')
        self.assertIn('OK', self.env['ir.config_parameter'].sudo().get_param('sbu.onedrive_sync_backup_last'))
