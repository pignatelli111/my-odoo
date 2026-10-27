# -*- coding: utf-8 -*-
"""Copy every SBU document into the client's OneDrive (one folder per job) and keep full backups there.

Documents are queued (attachments as they are created, report PDFs of confirmed documents by the cron)
and uploaded in the background, so an unreachable OneDrive never blocks the users.
"""
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time

from markupsafe import Markup

import odoo
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import osutil
from odoo.tools.misc import exec_pg_environ, find_pg_tool

from odoo.addons.sbu_integrations.services.microsoft_graph import (
    GraphHttpError,
    SbuMicrosoftGraphClient,
    safe_drive_name,
)

_logger = logging.getLogger(__name__)

ICP_PREFIX = 'sbu.onedrive_sync_'
NO_JOB_FOLDER = 'Senza commessa'
BACKUP_FOLDER = 'Backup Odoo'
MAX_ATTEMPTS = 5
CRON_TIME_BUDGET = 240  # seconds per cron run

# Attachments on these models are copied, into this sub-folder of the job.
ATTACHMENT_FOLDERS = {
    'project.project': '00 Documenti',
    'sbu.estimate': '01 Preventivo',
    'sbu.purchase.request': '02 Acquisti',
    'purchase.order': '02 Acquisti',
    'stock.picking': '03 Logistica',
    'sbu.sal.sheet': '04 SAL',
    'sbu.sal.passive.sheet': '04 SAL',
    'sbu.payment.certificate': '04 SAL',
    'account.move': '05 Fatture',
    'sbu.closure.requirement': '06 Chiusura',
}
# PDF of confirmed documents: (model, domain, report xmlid, sub-folder).
SNAPSHOT_RULES = (
    ('sbu.estimate', [('state', 'in', ('sent', 'won'))], 'sbu_estimate.action_report_sbu_estimate_offer', '01 Preventivo'),
    ('purchase.order', [('state', 'in', ('purchase', 'done'))], 'purchase.action_report_purchase_order', '02 Acquisti'),
    ('stock.picking', [('state', '=', 'done'), ('picking_type_code', 'in', ('outgoing', 'internal'))],
     'sbu_stock_config.action_report_sbu_ddt', '03 Logistica'),
    ('account.move', [('state', '=', 'posted'), ('move_type', 'in', ('out_invoice', 'out_refund'))],
     'account.account_invoices', '05 Fatture'),
)


def _icp(env):
    return env['ir.config_parameter'].sudo()


class SbuOnedriveFolder(models.Model):
    _name = 'sbu.onedrive.folder'
    _description = 'OneDrive folder created by SBU (cache)'

    path = fields.Char(required=True, index=True)
    drive_id = fields.Char(required=True)
    item_id = fields.Char(required=True)

    _sbu_onedrive_folder_uniq = models.Constraint('unique(drive_id, path)', 'Folder already known.')


class SbuOnedriveUpload(models.Model):
    _name = 'sbu.onedrive.upload'
    _description = 'Document to copy to OneDrive'
    _order = 'id desc'

    name = fields.Char(string='Document', readonly=True)
    res_model = fields.Char(string='Model', readonly=True, index=True)
    res_id = fields.Integer(string='Record', readonly=True, index=True)
    attachment_id = fields.Many2one('ir.attachment', readonly=True, ondelete='cascade', index='btree_not_null')
    report_ref = fields.Char(string='Report', readonly=True)
    filename = fields.Char(readonly=True)
    folder_path = fields.Char(string='OneDrive folder', readonly=True)
    state = fields.Selection(
        [('pending', 'To upload'), ('done', 'In OneDrive'), ('error', 'Error')],
        default='pending', required=True, readonly=True, index=True,
    )
    attempts = fields.Integer(readonly=True)
    last_error = fields.Text(readonly=True)
    web_url = fields.Char(string='OneDrive link', readonly=True)
    uploaded_on = fields.Datetime(readonly=True)

    _sbu_onedrive_report_uniq = models.Constraint(
        'unique(res_model, res_id, report_ref)', 'This report is already queued for OneDrive.',
    )
    _sbu_onedrive_attachment_uniq = models.Constraint(
        'unique(attachment_id)', 'This attachment is already queued for OneDrive.',
    )

    # ── Configuration ─────────────────────────────────────────────────────────
    @api.model
    def _sbu_enabled(self):
        return _icp(self.env).get_param(ICP_PREFIX + 'enabled') == 'True'

    @api.model
    def _sbu_root(self):
        icp = _icp(self.env)
        drive_id, item_id = icp.get_param(ICP_PREFIX + 'drive_id'), icp.get_param(ICP_PREFIX + 'item_id')
        if not (drive_id and item_id):
            raise UserError(_('Connect the OneDrive folder first (Settings → OneDrive sync → Connect folder).'))
        return drive_id, item_id

    @api.model
    def _sbu_client(self):
        client = SbuMicrosoftGraphClient(self.env)
        return client, client.get_app_access_token()

    # ── Where a record goes ───────────────────────────────────────────────────
    @api.model
    def _sbu_job_of(self, record):
        if record._name == 'project.project':
            return record
        for field in ('project_id', 'sbu_job_id'):
            if field in record._fields and record[field]:
                return record[field]
        return self.env['project.project']

    @api.model
    def _sbu_folder_path(self, record, subfolder):
        job = self._sbu_job_of(record)
        if job:
            job_folder = getattr(job, 'sbu_onedrive_folder_name_effective', False) or job.display_name
            return '/'.join([safe_drive_name(job_folder), subfolder])
        return '/'.join([NO_JOB_FOLDER, subfolder])

    # ── Queue ─────────────────────────────────────────────────────────────────
    @api.model
    def _sbu_enqueue_attachments(self, attachments):
        attachments = attachments.filtered(
            lambda a: a.res_model in ATTACHMENT_FOLDERS and a.res_id and not a.res_field and a.type == 'binary'
        )
        known = set(self.sudo().search([('attachment_id', 'in', attachments.ids)]).attachment_id.ids)
        vals = []
        for att in attachments.filtered(lambda a: a.id not in known):
            record = self.env[att.res_model].sudo().browse(att.res_id).exists()
            if not record:
                continue
            vals.append({
                'name': f'{record.display_name} — {att.name}',
                'res_model': att.res_model,
                'res_id': att.res_id,
                'attachment_id': att.id,
                'filename': att.name,
                'folder_path': self._sbu_folder_path(record, ATTACHMENT_FOLDERS[att.res_model]),
            })
        return self.sudo().create(vals)

    @api.model
    def _sbu_enqueue_snapshots(self, records=None, limit=500):
        """Queue the PDF of confirmed documents (all of them, or only ``records``)."""
        created = self.browse()
        for model, domain, report_ref, subfolder in SNAPSHOT_RULES:
            if model not in self.env or not self.env.ref(report_ref, raise_if_not_found=False):
                continue
            if records is not None and records._name != model:
                continue
            queued = self.sudo().search([('res_model', '=', model), ('report_ref', '=', report_ref)]).mapped('res_id')
            search_domain = domain + [('id', 'not in', queued)]
            if records is not None:
                search_domain.append(('id', 'in', records.ids))
            for record in self.env[model].sudo().search(search_domain, limit=limit):
                name = safe_drive_name(record.display_name)
                created |= self.sudo().create({
                    'name': record.display_name,
                    'res_model': model,
                    'res_id': record.id,
                    'report_ref': report_ref,
                    'filename': f'{name}.pdf',
                    'folder_path': self._sbu_folder_path(record, subfolder),
                })
        return created

    # ── Upload ────────────────────────────────────────────────────────────────
    def _sbu_content(self):
        self.ensure_one()
        if self.attachment_id:
            return self.attachment_id.sudo().raw or b''
        pdf, _type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(self.report_ref, [self.res_id])
        return pdf

    @api.model
    def _sbu_folder_id(self, client, token, path):
        drive_id, root_id = self._sbu_root()
        Folder = self.env['sbu.onedrive.folder'].sudo()
        parent_id, done = root_id, []
        for segment in [s for s in path.split('/') if s]:
            done.append(segment)
            key = '/'.join(done)
            cached = Folder.search([('drive_id', '=', drive_id), ('path', '=', key)], limit=1)
            if cached:
                parent_id = cached.item_id
                continue
            item = client.ensure_folder(drive_id, parent_id, segment, token)
            Folder.create({'drive_id': drive_id, 'path': key, 'item_id': item['id']})
            parent_id = item['id']
        return parent_id

    def _sbu_upload(self, client, token):
        drive_id, _root = self._sbu_root()
        for entry in self:
            try:
                data = entry._sbu_content()
                folder_id = self._sbu_folder_id(client, token, entry.folder_path)
                item = client.upload_bytes(drive_id, folder_id, entry.filename, data, token) or {}
                entry.write({'state': 'done', 'web_url': item.get('webUrl'), 'uploaded_on': fields.Datetime.now(),
                             'last_error': False})
            except Exception as err:  # noqa: BLE001 — one bad document must not stop the queue
                attempts = entry.attempts + 1
                entry.write({
                    'attempts': attempts,
                    'last_error': str(err)[:2000],
                    'state': 'error' if attempts >= MAX_ATTEMPTS else 'pending',
                })
                _logger.warning('OneDrive upload of %s failed (%s/%s): %s', entry.name, attempts, MAX_ATTEMPTS, err)

    @api.model
    def _sbu_process_queue(self, limit=50, time_budget=None):
        pending = self.sudo().search([('state', '=', 'pending')], order='id', limit=limit)
        if not pending:
            return 0
        client, token = self._sbu_client()
        started = time.monotonic()
        done = 0
        for entry in pending:
            if time_budget and time.monotonic() - started > time_budget:
                break
            entry._sbu_upload(client, token)
            done += entry.state == 'done'
        return done

    @api.model
    def cron_sbu_onedrive_sync(self):
        if not self._sbu_enabled():
            return
        self._sbu_enqueue_snapshots()
        started = time.monotonic()
        while time.monotonic() - started < CRON_TIME_BUDGET:
            if not self._sbu_process_queue(limit=50, time_budget=CRON_TIME_BUDGET):
                break
            if not odoo.tools.config['test_enable']:
                self.env.cr.commit()

    def action_retry(self):
        self.write({'state': 'pending', 'attempts': 0})
        return True

    # ── Full backup ───────────────────────────────────────────────────────────
    @api.model
    def _sbu_build_backup(self, path):
        """Odoo restorable archive: dump.sql + filestore + manifest.json (as the database manager makes)."""
        dbname = self.env.cr.dbname
        with tempfile.TemporaryDirectory() as dump_dir:
            filestore = odoo.tools.config.filestore(dbname)
            if os.path.exists(filestore):
                shutil.copytree(filestore, os.path.join(dump_dir, 'filestore'))
            self.env.cr.execute("SELECT name, latest_version FROM ir_module_module WHERE state = 'installed'")
            manifest = {
                'odoo_dump': '1', 'db_name': dbname, 'version': odoo.release.version,
                'version_info': odoo.release.version_info, 'major_version': odoo.release.major_version,
                'modules': dict(self.env.cr.fetchall()),
            }
            with open(os.path.join(dump_dir, 'manifest.json'), 'w') as fh:
                json.dump(manifest, fh, indent=4)
            cmd = [find_pg_tool('pg_dump'), '--no-owner', '--file=' + os.path.join(dump_dir, 'dump.sql'), dbname]
            subprocess.run(cmd, env=exec_pg_environ(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            with open(path, 'wb') as stream:
                osutil.zip_dir(dump_dir, stream, include_dir=False, fnct_sort=lambda name: name != 'dump.sql')
        return path

    @api.model
    def _sbu_backup_to_onedrive(self):
        icp = _icp(self.env)
        keep = max(int(icp.get_param(ICP_PREFIX + 'backup_keep') or 4), 1)
        dbname = self.env.cr.dbname
        stamp = fields.Datetime.now().strftime('%Y-%m-%d_%H%M')
        filename = f'{dbname}_{stamp}.zip'
        try:
            client, token = self._sbu_client()
            drive_id, _root = self._sbu_root()
            folder_id = self._sbu_folder_id(client, token, BACKUP_FOLDER)
            with tempfile.TemporaryDirectory() as tmp:
                path = self._sbu_build_backup(os.path.join(tmp, filename))
                size = os.path.getsize(path)
                client.upload_file(drive_id, folder_id, filename, path, token)
            backups = sorted(
                (c for c in client.list_children(drive_id, folder_id, token)
                 if c.get('name', '').startswith(f'{dbname}_') and c.get('name', '').endswith('.zip')),
                key=lambda c: c['name'], reverse=True,
            )
            for old in backups[keep:]:
                client.delete_item(drive_id, old['id'], token)
            status = _('OK — %(file)s (%(mb).1f MB), %(n)s backup(s) kept.', file=filename, mb=size / 1048576,
                       n=min(len(backups), keep))
        except (GraphHttpError, UserError, subprocess.CalledProcessError, OSError) as err:
            status = _('FAILED — %s', getattr(err, 'stderr', None) or err)
            _logger.error('OneDrive backup failed: %s', err)
        icp.set_param(ICP_PREFIX + 'backup_last', f'{fields.Datetime.to_string(fields.Datetime.now())} {status}')
        return status

    @api.model
    def cron_sbu_onedrive_backup(self):
        if _icp(self.env).get_param(ICP_PREFIX + 'backup_enabled') == 'True':
            self._sbu_backup_to_onedrive()


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        Upload = self.env['sbu.onedrive.upload']
        if any(v.get('res_model') in ATTACHMENT_FOLDERS for v in vals_list) and Upload._sbu_enabled():
            Upload._sbu_enqueue_attachments(attachments)
        return attachments


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sbu_onedrive_upload_count = fields.Integer(compute='_compute_sbu_onedrive_upload_count')

    def _sbu_onedrive_entries(self):
        self.ensure_one()
        Upload = self.env['sbu.onedrive.upload'].sudo()
        records = [(r._name, r.id) for r, _kind in self._sbu_job_documents()] + [(self._name, self.id)]
        domain = ['|'] * (len(records) - 1)
        for model, res_id in records:
            domain += ['&', ('res_model', '=', model), ('res_id', '=', res_id)]
        return Upload.search(domain)

    def _compute_sbu_onedrive_upload_count(self):
        for project in self:
            project.sbu_onedrive_upload_count = len(project._sbu_onedrive_entries()) if project.id else 0

    def action_sbu_export_job_to_onedrive(self):
        """Queue every document and attachment of the job; the cron uploads them."""
        self.ensure_one()
        Upload = self.env['sbu.onedrive.upload']
        Upload._sbu_root()
        docs = [record for record, _kind in self._sbu_job_documents()] + [self]
        queued = Upload.browse()
        for record in docs:
            attachments = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', record._name), ('res_id', '=', record.id)])
            queued |= Upload._sbu_enqueue_attachments(attachments)
            queued |= Upload._sbu_enqueue_snapshots(records=record.sudo())
        return self.action_sbu_open_onedrive_uploads(
            message=_('%s document(s) queued: they are uploaded in the background.', len(queued)))

    def action_sbu_open_onedrive_uploads(self, message=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('OneDrive copies'),
            'res_model': 'sbu.onedrive.upload',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self._sbu_onedrive_entries().ids)],
            'help': Markup('<p>%s</p>') % (message or _('Nothing copied to OneDrive yet.')),
        }


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_onedrive_sync_link = fields.Char(
        string='OneDrive folder link', config_parameter=ICP_PREFIX + 'link',
        help='Sharing link of the OneDrive / SharePoint folder that receives the documents and backups.',
    )
    sbu_onedrive_sync_enabled = fields.Boolean(string='Copy documents to OneDrive', config_parameter=ICP_PREFIX + 'enabled')
    sbu_onedrive_backup_enabled = fields.Boolean(string='Weekly full backup to OneDrive',
                                                 config_parameter=ICP_PREFIX + 'backup_enabled')
    sbu_onedrive_backup_keep = fields.Integer(string='Backups to keep', config_parameter=ICP_PREFIX + 'backup_keep',
                                              default=4)
    sbu_onedrive_sync_status = fields.Char(string='Connected folder', compute='_compute_sbu_onedrive_sync_status')
    sbu_onedrive_backup_last = fields.Char(string='Last backup', compute='_compute_sbu_onedrive_sync_status')
    sbu_backup_download_last = fields.Char(string='Last downloaded backup', compute='_compute_sbu_onedrive_sync_status')

    def _compute_sbu_onedrive_sync_status(self):
        icp = _icp(self.env)
        for settings in self:
            settings.sbu_onedrive_sync_status = icp.get_param(ICP_PREFIX + 'root_name') or _('Not connected')
            settings.sbu_onedrive_backup_last = icp.get_param(ICP_PREFIX + 'backup_last') or _('Never')
            settings.sbu_backup_download_last = icp.get_param(ICP_PREFIX + 'backup_download_last') or _('Never')

    def _sbu_notify(self, message, kind='success'):
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('OneDrive'), 'message': message, 'type': kind, 'sticky': False}}

    def action_sbu_onedrive_connect(self):
        self.ensure_one()
        self.execute()
        link = (self.sbu_onedrive_sync_link or '').strip()
        if not link:
            raise UserError(_('Paste the sharing link of the OneDrive folder first.'))
        client = SbuMicrosoftGraphClient(self.env)
        try:
            token = client.get_app_access_token()
            item = client.resolve_sharing_link(link, token)
        except GraphHttpError as err:
            raise UserError(_('OneDrive refused the folder (%(err)s). Check the Azure app permissions '
                              '(Files.ReadWrite.All, admin consent).', err=err)) from err
        if 'folder' not in (item or {}):
            raise UserError(_('The link points to a file, not a folder.'))
        icp = _icp(self.env)
        icp.set_param(ICP_PREFIX + 'drive_id', item['parentReference']['driveId'])
        icp.set_param(ICP_PREFIX + 'item_id', item['id'])
        icp.set_param(ICP_PREFIX + 'root_name', item.get('name') or '')
        self.env['sbu.onedrive.folder'].sudo().search([]).unlink()
        return self._sbu_notify(_('Connected to the OneDrive folder "%s".', item.get('name')))

    def action_sbu_onedrive_queue_all(self):
        self.ensure_one()
        Upload = self.env['sbu.onedrive.upload']
        Upload._sbu_root()
        attachments = self.env['ir.attachment'].sudo().search([('res_model', 'in', list(ATTACHMENT_FOLDERS))])
        queued = len(Upload._sbu_enqueue_attachments(attachments)) + len(Upload._sbu_enqueue_snapshots(limit=100000))
        return self._sbu_notify(_('%s document(s) queued for OneDrive.', queued))

    def action_sbu_download_backup(self):
        """Download a full backup to save in OneDrive by hand (no Azure app needed)."""
        return {'type': 'ir.actions.act_url', 'url': '/sbu/backup/download', 'target': 'self'}

    def action_sbu_onedrive_backup_now(self):
        self.ensure_one()
        status = self.env['sbu.onedrive.upload']._sbu_backup_to_onedrive()
        return self._sbu_notify(status, 'success' if status.startswith('OK') else 'danger')

    def action_sbu_onedrive_open_queue(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('OneDrive copies'),
            'res_model': 'sbu.onedrive.upload',
            'view_mode': 'list,form',
        }

    def _sbu_setup_checks(self):
        checks = super()._sbu_setup_checks()
        icp = _icp(self.env)
        connected = bool(icp.get_param(ICP_PREFIX + 'item_id'))
        checks.append({
            'label': _('OneDrive copy of documents and backups'),
            'status': 'ok' if connected and icp.get_param(ICP_PREFIX + 'enabled') == 'True' else 'missing',
            'detail': icp.get_param(ICP_PREFIX + 'root_name') or _('Connect the OneDrive folder.'),
            'url': False,
        })
        return checks
