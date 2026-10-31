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
        if not request.env.user.has_group('base.group_system'):
            raise Forbidden()
        env = request.env
        filename = f'{env.cr.dbname}_{fields.Datetime.now().strftime("%Y-%m-%d_%H%M")}.zip'
        try:
            with env['sbu.onedrive.upload']._sbu_backup_tmpdir() as tmp:
                path = env['sbu.onedrive.upload']._sbu_build_backup(os.path.join(tmp, filename))
                size = os.path.getsize(path)
                stream = open(path, 'rb')  # noqa: SIM115 — closed by the response once sent
        except Exception as err:  # noqa: BLE001 — show the reason instead of a bare "Internal Server Error"
            _logger.exception('Backup download failed')
            return self._sbu_backup_error(err.args[0] if err.args else err)
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

    def _sbu_backup_error(self, reason):
        _ = request.env._
        body = Markup(
            '<!DOCTYPE html><html><head><meta charset="utf-8"><title>%s</title></head>'
            '<body style="font-family:sans-serif;max-width:46rem;margin:3rem auto;padding:0 1rem">'
            '<h2>%s</h2><p><b>%s</b></p><pre style="white-space:pre-wrap;background:#f4f4f4;padding:1rem">%s</pre>'
            '<p>%s</p><p><a href="/odoo/settings">%s</a></p></body></html>'
        ) % (
            _('Backup failed'), _('The backup could not be created'), _('Reason:'), escape(str(reason)),
            _('On Odoo.sh you can also download a backup from the Odoo.sh project, tab Backups.'),
            _('Back to Settings'),
        )
        return request.make_response(str(body), status=500, headers=[('Content-Type', 'text/html; charset=utf-8')])
