from odoo import api, fields, models

from .sbu_revision_display import sbu_project_revision_label


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
    sbu_estimate_revision = fields.Char(
        string='Revisione preventivo',
        related='sbu_estimate_id.revision',
        store=True,
        readonly=True,
    )
    sbu_estimate_date = fields.Date(
        string='Data preventivo',
        related='sbu_estimate_id.date',
        store=True,
        readonly=True,
    )
    sbu_revision_label = fields.Char(
        string='Riferimento commessa',
        compute='_compute_sbu_revision_label',
        store=True,
        index=True,
    )
    sbu_is_latest_revision = fields.Boolean(
        string='Revisione più recente',
        compute='_compute_sbu_is_latest_revision',
        store=True,
        help='True when the linked estimate is the highest REV for the same Ns. preventivo.',
    )

    @api.depends(
        'name',
        'sbu_project_code',
        'sbu_job_site',
        'sbu_estimate_id',
        'sbu_estimate_id.revision',
        'sbu_estimate_id.date',
        'create_date',
    )
    def _compute_sbu_revision_label(self):
        for project in self:
            project.sbu_revision_label = sbu_project_revision_label(project) or project.name

    @api.depends('sbu_estimate_id', 'sbu_estimate_id.sbu_is_latest_revision')
    def _compute_sbu_is_latest_revision(self):
        for project in self:
            est = project.sbu_estimate_id
            project.sbu_is_latest_revision = est.sbu_is_latest_revision if est else True

    def name_get(self):
        if self.env.context.get('sbu_use_project_name_only'):
            return super().name_get()
        result = []
        for project in self:
            if project.sbu_estimate_id and project.sbu_revision_label:
                result.append((project.id, project.sbu_revision_label))
            else:
                result.append((project.id, project.name))
        return result
