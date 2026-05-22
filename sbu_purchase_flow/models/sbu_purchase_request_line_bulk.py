# -*- coding: utf-8 -*-
"""Related stored fields on PR lines for search / filters (Cosimo point 3)."""
from odoo import fields, models

class SbuPurchaseRequestLine(models.Model):
    _inherit = 'sbu.purchase.request.line'

    request_type = fields.Selection(
        related='request_id.request_type',
        string='Tipo Odoo',
        store=True,
        readonly=True,
    )
    workflow_route = fields.Selection(
        selection=SBU_WORKFLOW_ROUTE_SELECTION,
        related='request_id.workflow_route',
        string='Route ANACO',
        store=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        related='request_id.project_id',
        string='Project / Job',
        store=True,
        readonly=True,
    )
    technical_data_state = fields.Selection(
        related='request_id.technical_data_state',
        string='Technical data',
        store=True,
        readonly=True,
    )
    request_state = fields.Selection(
        related='request_id.state',
        string='Request status',
        store=True,
        readonly=True,
    )
