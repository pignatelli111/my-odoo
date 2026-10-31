# -*- coding: utf-8 -*-
import json
import os
import zipfile
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools.misc import find_pg_tool


def _fake_build(_self, path):
    with open(path, 'wb') as fh:
        fh.write(b'PK backup')
    return path


@tagged('post_install', '-at_install')
class TestSbuBackupDownload(HttpCase):

    def test_admin_downloads_backup(self):
        self.authenticate('admin', 'admin')
        with patch.object(type(self.env['sbu.onedrive.upload']), '_sbu_build_backup', _fake_build):
            response = self.url_open('/sbu/backup/download')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'PK backup')
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertIn('.zip', response.headers['Content-Disposition'])
        self.assertIn('MB', self.env['ir.config_parameter'].sudo().get_param('sbu.onedrive_sync_backup_download_last'))

    def test_other_users_are_refused(self):
        new_test_user(self.env, 'backup_user', password='backup_user_pw', groups='base.group_user')
        self.authenticate('backup_user', 'backup_user_pw')
        with patch.object(type(self.env['sbu.onedrive.upload']), '_sbu_build_backup', _fake_build):
            response = self.url_open('/sbu/backup/download')
        self.assertEqual(response.status_code, 403)

    def test_failure_shows_the_reason(self):
        def _broken(_self, path):
            raise UserError('pg_dump failed: disk full')

        self.authenticate('admin', 'admin')
        with patch.object(type(self.env['sbu.onedrive.upload']), '_sbu_build_backup', _broken), \
                self.assertLogs('odoo.addons.sbu_documents.controllers.main', level='ERROR'):
            response = self.url_open('/sbu/backup/download')
        self.assertEqual(response.status_code, 500)
        self.assertIn('pg_dump failed: disk full', response.text)
        self.assertIn('Back to Settings', response.text)

    def test_real_backup_is_a_restorable_zip(self):
        try:
            find_pg_tool('pg_dump')
        except Exception:  # noqa: BLE001
            self.skipTest('pg_dump is not installed here')
        Upload = self.env['sbu.onedrive.upload']
        with Upload._sbu_backup_tmpdir() as tmp:
            path = Upload._sbu_build_backup(os.path.join(tmp, 'b.zip'))
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                manifest = json.loads(zf.read('manifest.json'))
        self.assertIn('dump.sql', names)
        self.assertEqual(manifest['db_name'], self.env.cr.dbname)
        self.assertIn('sbu_documents', manifest['modules'])
