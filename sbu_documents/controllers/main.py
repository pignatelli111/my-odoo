# -*- coding: utf-8 -*-
import logging
import os
import tempfile

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
        with tempfile.TemporaryDirectory() as tmp:
            path = env['sbu.onedrive.upload']._sbu_build_backup(os.path.join(tmp, filename))
            size = os.path.getsize(path)
            stream = open(path, 'rb')  # noqa: SIM115 — closed by the response once sent
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
