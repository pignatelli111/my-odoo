# -*- coding: utf-8 -*-
import logging
import os

from markupsafe import Markup, escape
from werkzeug.exceptions import Forbidden
from werkzeug.wsgi import wrap_file

from odoo import fields, http
from odoo.http import content_disposition, request

_logger = logging.getLogger(__name__)


class SbuBackupController(http.Controller):

    @http.route('/sbu/backup/download', type='http', auth='user', methods=['GET'])
    def sbu_backup_download(self):
        """Full Odoo backup (.zip: database + files), streamed to the administrator's browser."""
        self._sbu_check_admin()
        filename = f'{request.env.cr.dbname}_{fields.Datetime.now().strftime("%Y-%m-%d_%H%M")}.zip'
        return self._sbu_send_zip(filename, request.env['sbu.onedrive.upload']._sbu_build_backup)

    @http.route('/sbu/backup/documents', type='http', auth='user', methods=['GET'])
    def sbu_backup_documents(self):
        """Every document and attachment in job folders, without the database (works on Odoo.sh)."""
        self._sbu_check_admin()
        filename = f'{request.env.cr.dbname}_documenti_{fields.Datetime.now().strftime("%Y-%m-%d_%H%M")}.zip'
        return self._sbu_send_zip(filename, request.env['sbu.onedrive.upload']._sbu_build_files_backup)

    def _sbu_check_admin(self):
        if not request.env.user.has_group('base.group_system'):
            raise Forbidden()

    def _sbu_send_zip(self, filename, build):
        env = request.env
        try:
            with env['sbu.onedrive.upload']._sbu_backup_tmpdir() as tmp:
                path = os.path.join(tmp, filename)
                build(path)
                size = os.path.getsize(path)
                stream = open(path, 'rb')  # noqa: SIM115 — closed by the response once sent
        except Exception as err:  # noqa: BLE001 — show the reason instead of a bare "Internal Server Error"
            _logger.exception('Backup download failed')
            return self._sbu_page(env._('The backup could not be created'), Markup(
                '<p><b>%s</b></p><pre style="white-space:pre-wrap;background:#f4f4f4;padding:1rem">%s</pre>'
            ) % (env._('Reason:'), escape(str(err.args[0] if err.args else err))), status=500)
        # The directory is gone but the open file stays readable until the download ends.
        env['ir.config_parameter'].sudo().set_param(
            'sbu.onedrive_sync_backup_download_last',
            f'{fields.Datetime.to_string(fields.Datetime.now())} {filename} ({size / 1048576:.1f} MB) — {env.user.name}',
        )
        _logger.info('Backup %s downloaded by %s', filename, env.user.login)
        return request.make_response(
            wrap_file(request.httprequest.environ, stream),
            headers=[
                ('Content-Type', 'application/zip'),
                ('Content-Length', str(size)),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )

    def _sbu_page(self, title, content, links=(), status=200):
        links = list(links) + [('/odoo/settings', request.env._('Back to Settings'))]
        body = Markup(
            '<!DOCTYPE html><html><head><meta charset="utf-8"><title>%s</title></head>'
            '<body style="font-family:sans-serif;max-width:46rem;margin:3rem auto;padding:0 1rem;line-height:1.5">'
            '<h2>%s</h2>%s<p style="display:flex;gap:1.5rem;flex-wrap:wrap">%s</p></body></html>'
        ) % (title, title, content, Markup('').join(Markup('<a href="%s">%s</a>') % link for link in links))
        return request.make_response(str(body), status=status, headers=[('Content-Type', 'text/html; charset=utf-8')])
