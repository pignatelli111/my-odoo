# -*- coding: utf-8 -*-
"""Configurable workflow routes (Cosimo punto 5 — no free-text document types)."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SbuWorkflowRoute(models.Model):
    _name = 'sbu.workflow.route'
    _description = 'SBU purchase workflow route (LA, LZ, ST, …)'
    _order = 'sequence, code'

    code = fields.Char(
        string='Route code',
        required=True,
        index=True,
        help='ANACO route code, e.g. LA, LZ, ST, PAN, OSC, VC/VS.',
    )
    name = fields.Char(string='Label', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    wizard_enabled = fields.Boolean(
        string='Show in create wizard',
        default=True,
        help='If set, route appears in «Nuovo documento acquisto».',
    )
    request_type = fields.Selection(
        selection=[
            ('rda', 'RDA'),
            ('aco', 'ACO'),
            ('acp', 'ACP'),
            ('lds', 'LDS'),
            ('fe', 'FE'),
            ('st', 'ST'),
            ('vt', 'VT'),
            ('other', 'Other'),
        ],
        string='Odoo document type',
        required=True,
        default='rda',
    )
    require_topic = fields.Boolean(
        string='Topic required',
        help='Wizard blocks create if Topic is empty.',
    )
    require_need_by = fields.Boolean(
        string='Need-by date required',
        help='Wizard blocks create if need-by date is empty.',
    )
    notes = fields.Text(string='Notes')

    _sbu_workflow_route_code_uniq = models.Constraint(
        'unique(code)',
        'Route code must be unique.',
    )

    @api.constrains('code')
    def _check_code_format(self):
        for rec in self:
            code = (rec.code or '').strip()
            if not code:
                raise ValidationError(_('Route code is required.'))
            if len(code) > 16:
                raise ValidationError(_('Route code is too long (max 16 characters).'))

    def name_get(self):
        return [(r.id, f'{r.code} — {r.name}') for r in self]

    @api.model
    def _selection_for_field(self, wizard_only=False):
        domain = [('active', '=', True)]
        if wizard_only:
            domain.append(('wizard_enabled', '=', True))
        routes = self.search(domain)
        if routes:
            return [(r.code, f'{r.code} — {r.name}') for r in routes]
        from .sbu_workflow_routing import SBU_WORKFLOW_ROUTE_SELECTION
        return SBU_WORKFLOW_ROUTE_SELECTION

    @api.model
    def route_config(self, code):
        """Return route record or empty recordset."""
        return self.search([('code', '=', (code or '').strip()), ('active', '=', True)], limit=1)

    @api.model
    def request_type_for_code(self, code):
        rec = self.route_config(code)
        if rec:
            return rec.request_type
        from .sbu_workflow_routing import workflow_route_to_request_type
        return workflow_route_to_request_type(code)

    @api.model
    def wizard_requires_for_code(self, code):
        rec = self.route_config(code)
        if rec:
            return {
                'topic': rec.require_topic,
                'need_by': rec.require_need_by,
            }
        from .sbu_workflow_routing import ROUTE_WIZARD_REQUIRES
        return ROUTE_WIZARD_REQUIRES.get((code or '').strip(), {})
