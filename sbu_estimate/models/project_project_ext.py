from odoo import models, fields


class ProjectProjectSbu(models.Model):
    """Extend project.project with SBU-specific fields."""
    _inherit = 'project.project'

    sbu_estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo di Origine',
        readonly=True,
        copy=False,
    )
    sbu_project_code = fields.Char(
        string='Codice Commessa',
        copy=False,
        tracking=True,
    )
    sbu_job_site = fields.Char(
        string='Cantiere / Immobile',
    )
    sbu_onedrive_url = fields.Char(
        string='Cartella OneDrive',
        help='URL della cartella OneDrive per questa commessa',
    )
    sbu_state = fields.Selection([
        ('setup', 'In Impostazione'),
        ('active', 'In Corso'),
        ('closing', 'In Chiusura'),
        ('closed', 'Chiusa'),
        ('archived', 'Archiviata'),
    ], string='Stato Commessa', default='setup', tracking=True)
