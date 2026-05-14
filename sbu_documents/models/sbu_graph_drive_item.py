# -*- coding: utf-8 -*-
from odoo import fields, models


class SbuGraphDriveItem(models.Model):
    _name = 'sbu.graph.drive.item'
    _description = 'SBU Microsoft Graph drive item (cached)'
    _order = 'is_folder desc, name'

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    drive_id = fields.Char(string='Drive id', required=True, index=True)
    graph_item_id = fields.Char(string='Graph item id', required=True, index=True)
    name = fields.Char(string='Name', required=True)
    web_url = fields.Char(string='Deep link (webUrl)')
    is_folder = fields.Boolean(string='Is folder', index=True)
    mime_type = fields.Char(string='MIME type')
    size = fields.Integer(string='Size (bytes)')
    graph_modified = fields.Char(
        string='Last modified (Graph)',
        help='ISO 8601 timestamp from Microsoft Graph.',
    )
