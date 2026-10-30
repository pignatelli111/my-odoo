# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import HttpCase, new_test_user, tagged


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
