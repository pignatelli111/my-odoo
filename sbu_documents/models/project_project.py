from odoo import models, fields


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sbu_external_document_ids = fields.One2many(
        'sbu.external.document',
        'project_id',
        string='External document links',
    )
