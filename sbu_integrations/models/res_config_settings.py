from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_graph_tenant_id = fields.Char(
        string='Microsoft Graph tenant ID',
        config_parameter='sbu.graph_tenant_id',
    )
    sbu_graph_client_id = fields.Char(
        string='Microsoft Graph client ID',
        config_parameter='sbu.graph_client_id',
    )
    sbu_graph_client_secret = fields.Char(
        string='Microsoft Graph client secret',
        config_parameter='sbu.graph_client_secret',
        help='App registration client secret (client credentials flow). Restricted to administrators.',
    )
    sbu_graph_sync_enabled = fields.Boolean(
        string='Enable Microsoft Graph sync',
        config_parameter='sbu.graph_sync_enabled',
        help='When enabled, projects with drive and item ids can pull folder metadata from Graph.',
    )
    sbu_graph_pdf_mode = fields.Selection(
        selection=[
            ('index_only', 'Index metadata only (recommended)'),
            ('fetch_pdfs', 'Also download PDFs into Odoo attachments'),
        ],
        string='Graph PDF handling',
        config_parameter='sbu.graph_pdf_mode',
        default='index_only',
    )
    sbu_graph_pdf_max_bytes = fields.Integer(
        string='Graph PDF max size (bytes)',
        config_parameter='sbu.graph_pdf_max_bytes',
        default=15 * 1024 * 1024,
        help='Safety cap when downloading PDFs from Graph (default 15 MB).',
    )
    sbu_onedrive_folder_prefix = fields.Char(
        string='OneDrive folder prefix',
        config_parameter='sbu.onedrive_folder_prefix',
        help='Prepended to every suggested project folder name (e.g. SBU-).',
    )
    sbu_onedrive_folder_separator = fields.Char(
        string='OneDrive folder separator',
        config_parameter='sbu.onedrive_folder_separator',
        help='Single character between job code and name slug (default _).',
    )
    sbu_onedrive_folder_slug_max = fields.Integer(
        string='OneDrive name slug max length',
        config_parameter='sbu.onedrive_folder_slug_max',
        default=48,
        help='Maximum length of the project name part in the suggested folder name.',
    )
    sbu_onedrive_root_url = fields.Char(
        string='SharePoint / OneDrive root (reference URL)',
        config_parameter='sbu.onedrive_root_url',
        help='Optional link to the library or team site where job folders are created (for staff).',
    )
    sbu_onedrive_ownership_policy = fields.Text(
        string='OneDrive ownership policy (internal)',
        config_parameter='sbu.onedrive_ownership_policy',
        help='Short text shown on projects: who provisions folders, M365 group, break-glass rules.',
    )
    sbu_qonto_org = fields.Char(
        string='Qonto organisation',
        config_parameter='sbu.qonto_org',
    )
    sbu_logikal_base_url = fields.Char(
        string='Logikal API base URL',
        config_parameter='sbu.logikal_base_url',
        help='Middleware base URL for the Logikal/ReynaPro bridge (see module sbu_logikal). Used with API path and bearer token.',
    )
    sbu_m365_collaboration_policy = fields.Text(
        string='Teams / Planner / Outlook policy (internal)',
        config_parameter='sbu.m365_collaboration_policy',
        help='How SBU uses Teams channels, Planner, and Outlook vs Odoo tasks (deep links, no duplicate workflows).',
    )
