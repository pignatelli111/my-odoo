from odoo import models, fields


class SbuExternalDocument(models.Model):
    """Manual registry of links (OneDrive, Logikal, etc.) per job."""
    _name = 'sbu.external.document'
    _description = 'SBU external document link'
    _order = 'sequence, id'

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Title', required=True)
    url = fields.Char(string='URL', required=True)
    note = fields.Char(string='Note')
