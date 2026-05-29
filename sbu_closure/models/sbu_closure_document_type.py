# -*- coding: utf-8 -*-
from odoo import fields, models


class SbuClosureDocumentType(models.Model):
    _name = 'sbu.closure.document.type'
    _description = 'SBU closure document type (DOP, certification, …)'
    _order = 'sequence, name'

    name = fields.Char(string='Label', required=True, translate=True)
    code = fields.Char(
        string='Code',
        help='Short stable code for exports and integrations.',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description', translate=True)
    init_on_project = fields.Boolean(
        string='Add to checklist on init',
        default=True,
        help='When “Initialize closure checklist” runs on a job, create a line for this type if not already present.',
    )
    default_required = fields.Boolean(
        string='Required by default',
        default=True,
        help='New checklist lines start as required (can be changed per job).',
    )
