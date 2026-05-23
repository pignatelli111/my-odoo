# -*- coding: utf-8 -*-
import base64
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _sbu_folder_slug(text, max_len=48):
    """ASCII-ish slug safe for OneDrive folder names (convention helper)."""
    if not text:
        return 'project'
    s = text.strip()
    s = re.sub(r'[^\w\s-]', '', s, flags=re.UNICODE)
    s = re.sub(r'[-\s]+', '-', s).strip('-')
    if not s:
        return 'project'
    return s[:max_len]


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sbu_external_document_ids = fields.One2many(
        'sbu.external.document',
        'project_id',
        string='External document links',
    )

    sbu_onedrive_folder_name_suggested = fields.Char(
        string='OneDrive folder name (suggested)',
        compute='_compute_sbu_onedrive_folder_name_suggested',
        help='Company naming convention: prefix + job code + name slug. Create the folder in OneDrive '
        'with this name (or set an override below) and paste the web URL in the field from Preventivo / commessa.',
    )
    sbu_onedrive_folder_name_override = fields.Char(
        string='OneDrive folder name (actual)',
        tracking=True,
        copy=False,
        help='If the folder in Microsoft 365 uses a different name than the suggestion, set it here for audit trail.',
    )
    sbu_onedrive_folder_name_effective = fields.Char(
        string='Effective folder name',
        compute='_compute_sbu_onedrive_folder_name_effective',
        help='Actual name used for traceability: override if set, otherwise the suggestion.',
    )

    sbu_onedrive_drive_id = fields.Char(
        string='OneDrive drive ID (Graph)',
        copy=False,
        help='Optional. Microsoft Graph drive id for the project folder (set by administrators).',
    )
    sbu_onedrive_item_id = fields.Char(
        string='OneDrive item ID (Graph)',
        copy=False,
        help='Optional. Microsoft Graph drive item id for the project folder root.',
    )
    sbu_onedrive_custodian_id = fields.Many2one(
        'res.users',
        string='OneDrive / DMS custodian',
        tracking=True,
        domain=[('share', '=', False)],
        help='Internal owner accountable for the project folder (access reviews, lifecycle).',
    )
    sbu_onedrive_linked_at = fields.Datetime(
        string='OneDrive URL last set',
        readonly=True,
        copy=False,
        help='Set automatically when the OneDrive folder URL is updated.',
    )
    sbu_onedrive_access_note = fields.Text(
        string='OneDrive access instructions',
        tracking=True,
        help='Internal only: guest link password, who has M365 access, or how to open the folder '
             '(Odoo does not store Microsoft passwords for auto-login).',
    )

    sbu_teams_team_url = fields.Char(
        string='Teams team URL',
        tracking=True,
        help='Web link to the Microsoft Team hosting this job (avoid duplicating chat in Odoo).',
    )
    sbu_teams_channel_url = fields.Char(
        string='Teams channel URL',
        tracking=True,
        help='Default job channel or standard channel link (shared or not).',
    )
    sbu_teams_shared_channel_note = fields.Text(
        string='Teams shared channels (notes)',
        help='Who creates shared channels, naming, and guests. Work stays in Teams; this is guidance only.',
    )
    sbu_planner_plan_url = fields.Char(
        string='Planner plan / board URL',
        tracking=True,
        help='Deep link to the Planner plan or board for this job. Task execution stays in Planner unless you paste a per-task link on Odoo tasks.',
    )
    sbu_outlook_calendar_url = fields.Char(
        string='Outlook / group calendar URL',
        tracking=True,
        help='Optional link to the Microsoft 365 group calendar or shared mailbox in OWA.',
    )

    sbu_graph_drive_item_ids = fields.One2many(
        'sbu.graph.drive.item',
        'project_id',
        string='Graph folder index',
    )
    sbu_graph_folder_web_url = fields.Char(
        string='Graph folder deep link',
        readonly=True,
        copy=False,
        help='webUrl of the linked folder from the last successful Graph sync.',
    )
    sbu_graph_folder_sync_at = fields.Datetime(
        string='Graph folder last sync',
        readonly=True,
        copy=False,
    )
    sbu_graph_sync_state = fields.Selection(
        selection=[
            ('never', 'Never synced'),
            ('ok', 'OK'),
            ('error', 'Error'),
            ('skipped', 'Skipped'),
        ],
        string='Graph sync state',
        default='never',
        readonly=True,
        copy=False,
    )
    sbu_graph_sync_message = fields.Text(
        string='Graph sync message',
        readonly=True,
        copy=False,
    )

    @api.depends('name', 'sbu_project_code')
    def _compute_sbu_onedrive_folder_name_suggested(self):
        icp = self.env['ir.config_parameter'].sudo()
        prefix = (icp.get_param('sbu.onedrive_folder_prefix') or 'SBU-').strip()
        sep = (icp.get_param('sbu.onedrive_folder_separator') or '_').strip() or '_'
        sep = sep[0]
        raw_max = icp.get_param('sbu.onedrive_folder_slug_max')
        try:
            max_slug = int(raw_max) if raw_max not in (None, '', False) else 48
        except ValueError:
            max_slug = 48
        max_slug = max(8, min(max_slug, 120))
        for project in self:
            code = (project.sbu_project_code or '').strip()
            if not code:
                code = 'P%05d' % project.id if project.id else 'NEW'
            slug = _sbu_folder_slug(project.name or '', max_len=max_slug)
            project.sbu_onedrive_folder_name_suggested = f'{prefix}{code}{sep}{slug}'

    @api.depends('sbu_onedrive_folder_name_suggested', 'sbu_onedrive_folder_name_override')
    def _compute_sbu_onedrive_folder_name_effective(self):
        for project in self:
            project.sbu_onedrive_folder_name_effective = (
                (project.sbu_onedrive_folder_name_override or '').strip()
                or project.sbu_onedrive_folder_name_suggested
                or ''
            )

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if vals.get('sbu_onedrive_url'):
                vals['sbu_onedrive_linked_at'] = now
        records = super().create(vals_list)
        # Odoo 19 forbids @api.depends('id'); invalidate so P##### fallback uses the real id after create.
        records.invalidate_recordset(
            ['sbu_onedrive_folder_name_suggested', 'sbu_onedrive_folder_name_effective']
        )
        return records

    def write(self, vals):
        if 'sbu_onedrive_url' in vals and vals.get('sbu_onedrive_url'):
            vals = dict(vals)
            vals['sbu_onedrive_linked_at'] = fields.Datetime.now()
        return super().write(vals)

    def action_sbu_graph_sync_onedrive_folder(self):
        """List folder children via Microsoft Graph; optional PDF download per company settings."""
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('sbu.graph_sync_enabled') != 'True':
            raise UserError(
                _('Microsoft Graph sync is disabled. Enable it under Settings / SBU / Microsoft Graph.')
            )
        if not (self.sbu_onedrive_drive_id and self.sbu_onedrive_item_id):
            raise UserError(
                _('Set the OneDrive drive ID and folder item ID on this project (Document hub).')
            )

        from odoo.addons.sbu_integrations.services.microsoft_graph import GraphHttpError, SbuMicrosoftGraphClient

        client = SbuMicrosoftGraphClient(self.env)
        if not client.is_configured():
            raise UserError(
                _('Configure Microsoft Graph tenant, client ID, and client secret under Settings / SBU.')
            )

        pdf_mode = icp.get_param('sbu.graph_pdf_mode') or 'index_only'
        try:
            max_pdf = int(icp.get_param('sbu.graph_pdf_max_bytes') or str(15 * 1024 * 1024))
        except ValueError:
            max_pdf = 15 * 1024 * 1024
        max_pdf = max(1024 * 1024, min(max_pdf, 50 * 1024 * 1024))

        try:
            with self.env.cr.savepoint():
                token = client.get_app_access_token()
                root = client.get_drive_item(self.sbu_onedrive_drive_id, self.sbu_onedrive_item_id, token)
                root_web = root.get('webUrl') or ''
                self.sbu_graph_drive_item_ids.unlink()
                Attachment = self.env['ir.attachment'].sudo()
                lines = []
                for it in client.iter_drive_item_children(
                    self.sbu_onedrive_drive_id, self.sbu_onedrive_item_id, token
                ):
                    gid = it.get('id') or ''
                    if not gid:
                        continue
                    is_folder = bool(it.get('folder'))
                    mime = (it.get('file') or {}).get('mimeType') or ''
                    size = int(it.get('size') or 0)
                    lines.append(
                        {
                            'project_id': self.id,
                            'drive_id': self.sbu_onedrive_drive_id,
                            'graph_item_id': gid,
                            'name': it.get('name') or gid,
                            'web_url': it.get('webUrl') or '',
                            'is_folder': is_folder,
                            'mime_type': mime,
                            'size': size,
                            'graph_modified': it.get('lastModifiedDateTime') or '',
                        }
                    )
                    if pdf_mode == 'fetch_pdfs' and not is_folder and mime == 'application/pdf':
                        try:
                            self._sbu_graph_sync_pdf_attachment(
                                client,
                                token,
                                Attachment,
                                gid,
                                it.get('name') or 'document.pdf',
                                max_pdf,
                            )
                        except GraphHttpError as err:
                            _logger.warning(
                                'Graph PDF skip project=%s item=%s: %s', self.id, gid, err
                            )

                self.env['sbu.graph.drive.item'].create(lines)
                self.write(
                    {
                        'sbu_graph_folder_web_url': root_web,
                        'sbu_graph_folder_sync_at': fields.Datetime.now(),
                        'sbu_graph_sync_state': 'ok',
                        'sbu_graph_sync_message': _('Indexed %s item(s) from Graph.') % len(lines),
                    }
                )
        except GraphHttpError as e:
            raise UserError(
                _('Microsoft Graph error (%s): %s\n%s')
                % (e.status, str(e), (e.body or '')[:1500])
            ) from e

        return True

    def _sbu_graph_sync_pdf_attachment(self, client, token, Attachment, graph_item_id, filename, max_bytes):
        self.ensure_one()
        existing = Attachment.search(
            [
                ('res_model', '=', 'project.project'),
                ('res_id', '=', self.id),
                ('sbu_graph_item_id', '=', graph_item_id),
            ],
            limit=1,
        )
        if existing:
            return existing
        raw = client.get_item_content(self.sbu_onedrive_drive_id, graph_item_id, token, max_bytes)
        vals = {
            'name': filename,
            'res_model': 'project.project',
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(raw).decode(),
            'mimetype': 'application/pdf',
            'description': 'Synced from Microsoft Graph (SBU)',
            'sbu_graph_item_id': graph_item_id,
        }
        return Attachment.create(vals)

    def action_sbu_open_planner_board(self):
        """Open the linked Microsoft Planner plan in the browser."""
        self.ensure_one()
        if not self.sbu_planner_plan_url:
            raise UserError(
                _('Set the Planner plan URL on the M365 collaboration tab before opening the board.')
            )
        return {
            'type': 'ir.actions.act_url',
            'url': self.sbu_planner_plan_url,
            'target': 'new',
        }

    def action_sbu_import_planner_tasks_csv(self):
        """Import a Planner CSV export as Odoo project tasks (internal checklist)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Planner tasks (CSV)'),
            'res_model': 'sbu.planner.task.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_project_id': self.id},
        }
