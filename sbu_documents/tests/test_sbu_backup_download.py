# -*- coding: utf-8 -*-
import base64
import io
import json
import os
import zipfile
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged


def _fake_build(_self, path):
    with open(path, 'wb') as fh:
        fh.write(b'PK backup')
    return path


@tagged('post_install', '-at_install')
class TestSbuBackupDownload(HttpCase):

    def setUp(self):
        super().setUp()
        self.Upload = self.env['sbu.onedrive.upload']

    def test_admin_downloads_backup(self):
        self.authenticate('admin', 'admin')
        with patch.object(type(self.Upload), '_sbu_build_backup', _fake_build):
            response = self.url_open('/sbu/backup/download')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'PK backup')
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertIn('.zip', response.headers['Content-Disposition'])
        self.assertIn('MB', self.env['ir.config_parameter'].sudo().get_param('sbu.onedrive_sync_backup_download_last'))

    def test_other_users_are_refused(self):
        new_test_user(self.env, 'backup_user', password='backup_user_pw', groups='base.group_user')
        self.authenticate('backup_user', 'backup_user_pw')
        with patch.object(type(self.Upload), '_sbu_build_backup', _fake_build):
            self.assertEqual(self.url_open('/sbu/backup/download').status_code, 403)
            self.assertEqual(self.url_open('/sbu/backup/documents').status_code, 403)

    def test_failure_shows_the_reason(self):
        def _broken(_self, path):
            raise UserError('pg_dump failed: disk full')

        self.authenticate('admin', 'admin')
        with patch.object(type(self.Upload), '_sbu_build_backup', _broken), \
                self.assertLogs('odoo.addons.sbu_documents.controllers.main', level='ERROR'):
            response = self.url_open('/sbu/backup/download')
        self.assertEqual(response.status_code, 500)
        self.assertIn('pg_dump failed: disk full', response.text)
        self.assertIn('Back to Settings', response.text)

    def test_documents_zip_has_readable_folders(self):
        partner = self.env['res.partner'].create({'name': 'Fornitore Test'})
        for name in ('offerta.pdf', 'offerta.pdf'):
            self.env['ir.attachment'].create({
                'name': name, 'res_model': 'res.partner', 'res_id': partner.id, 'datas': base64.b64encode(b'%PDF x'),
            })
        self.authenticate('admin', 'admin')
        response = self.url_open('/sbu/backup/documents')
        self.assertEqual(response.status_code, 200)
        self.assertIn('_documenti_', response.headers['Content-Disposition'])
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = [n for n in zf.namelist() if 'Fornitore Test' in n]
            self.assertEqual(len(names), 2, zf.namelist())
            self.assertTrue(all(n.startswith('Altri documenti/') for n in names))
            self.assertTrue(any(n.endswith('offerta (2).pdf') for n in names), 'same name twice is kept twice')
            self.assertEqual(zf.read(names[0]), b'%PDF x')

    def _check_backup_zip(self, path):
        with zipfile.ZipFile(path) as zf:
            manifest = json.loads(zf.read('manifest.json'))
            dump = zf.read('dump.sql').decode()
        self.assertEqual(manifest['db_name'], self.env.cr.dbname)
        self.assertIn('sbu_documents', manifest['modules'])
        return dump

    def test_full_backup_without_pg_dump_rights(self):
        """Odoo.sh refuses pg_dump (no access to pg_settings): the built-in dump makes the same backup."""
        with patch.object(type(self.Upload), '_sbu_pg_dump_allowed', lambda _self: False), \
                self.Upload._sbu_backup_tmpdir() as tmp:
            dump = self._check_backup_zip(self.Upload._sbu_build_backup(os.path.join(tmp, 'b.zip')))
        self.assertIn('without pg_dump', dump)
        self.assertIn('CREATE TABLE "public"."res_partner" (', dump)
        self.assertIn('CREATE TABLE "public"."ir_act_window" (', dump)
        self.assertIn('INHERITS ("public"."ir_actions")', dump, 'Odoo action tables use table inheritance')
        self.assertIn('COPY "public"."res_partner" (', dump)
        self.assertIn('CREATE VIEW "public"."sbu_job_overview" AS', dump)
        self.assertIn('ADD CONSTRAINT "res_partner_pkey" PRIMARY KEY (id)', dump)
        self.assertIn("SELECT pg_catalog.setval('\"public\".\"res_partner_id_seq\"'", dump)
        self.assertTrue(dump.rstrip().endswith('-- Dump complete'))
        self.env.cr.execute('SHOW search_path')
        self.assertNotEqual(self.env.cr.fetchone()[0], '""', 'the request cursor keeps its search_path')

    def test_real_backup_is_a_restorable_zip(self):
        if not self.Upload._sbu_pg_dump_allowed():
            self.skipTest('pg_dump cannot run here; covered by test_full_backup_without_pg_dump_rights')
        with self.Upload._sbu_backup_tmpdir() as tmp:
            dump = self._check_backup_zip(self.Upload._sbu_build_backup(os.path.join(tmp, 'b.zip')))
        self.assertIn('PostgreSQL database dump', dump)
