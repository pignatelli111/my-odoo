# -*- coding: utf-8 -*-
from odoo import fields, models


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
    link_kind = fields.Selection(
        selection=[
            ('onedrive', 'OneDrive / SharePoint'),
            ('teams', 'Microsoft Teams (team / general)'),
            ('teams_channel', 'Microsoft Teams (channel)'),
            ('teams_shared', 'Microsoft Teams (shared channel)'),
            ('planner', 'Microsoft Planner'),
            ('outlook', 'Outlook / Exchange'),
            ('m365', 'Microsoft 365 (other)'),
            ('drawing', 'Drawings / CAD'),
            ('logikal', 'Logikal'),
            ('other', 'Other'),
        ],
        string='Kind',
        default='other',
        help='Classify links for reporting; collaboration stays in M365, Odoo stores pointers only.',
    )
    custodian_id = fields.Many2one(
        'res.users',
        string='Link owner',
        help='User responsible for keeping this link valid (optional).',
    )
