# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

from odoo.addons.sbu_estimate.models.sbu_cost_family import SBU_COST_FAMILY_SELECTION

from .sbu_budget_helpers import sbu_cost_family_for_pr_line


class SbuDeliveryStandard(models.Model):
    _name = 'sbu.delivery.standard'
    _description = 'SBU default delivery route'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Empty = rule applies to all companies.',
    )
    cost_family = fields.Selection(
        selection=SBU_COST_FAMILY_SELECTION,
        string='Cost family',
        help='Leave empty to match any family (use workflow or document type to narrow).',
    )
    workflow_route = fields.Char(
        string='Workflow route',
        help='ANACO route code (LA, LZ, VC/VS, OSC, …). Empty = any route.',
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
        string='Document type',
    )
    glass_mode = fields.Selection(
        [
            ('any', 'Any (non-glass)'),
            ('direct', 'Glass: vetraio → cantiere'),
            ('via_terzista', 'Glass: vetraio → terzista → cantiere'),
        ],
        string='Glass delivery',
        default='any',
        required=True,
        help='For glass / VT only: must match the setting on the job (commessa).',
    )
    delivery_pattern = fields.Selection(
        [
            ('direct_site', 'Supplier → site'),
            ('via_terzista', 'Supplier → site subcontractor → site'),
            (
                'via_sistemista_terzista',
                'Supplier (system supplier) → site subcontractor → site (multi-stop)',
            ),
        ],
        string='Pattern',
        required=True,
        default='via_terzista',
    )
    intermediate_stops = fields.Integer(
        string='Typical intermediate stops',
        default=5,
        help='Shown in the destination text (e.g. 4–5 legs before the site).',
    )
    note = fields.Text(string='Internal note')

    @api.model
    def match_for_pr_line(self, pr_line, project):
        """Best matching active rule for company + line context."""
        company = pr_line.request_id.company_id or self.env.company
        cost_family = sbu_cost_family_for_pr_line(pr_line)
        route = (pr_line.request_id.workflow_route or '').strip()
        req_type = pr_line.request_id.request_type
        glass_mode = 'any'
        if cost_family == 'glass' or req_type == 'vt':
            glass_mode = (project.sbu_glass_delivery_mode if project else 'via_terzista') or 'via_terzista'

        domain = [('active', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company.id)]
        rules = self.search(domain, order='sequence, id')
        candidates = []
        for rule in rules:
            if rule.cost_family and rule.cost_family != cost_family:
                continue
            rule_route = (rule.workflow_route or '').strip()
            if rule_route and rule_route != route:
                continue
            if rule.request_type and rule.request_type != req_type:
                continue
            if rule.glass_mode != 'any':
                if cost_family != 'glass' and req_type != 'vt':
                    continue
                if rule.glass_mode != glass_mode:
                    continue
            score = 0
            if rule_route:
                score += 40
            if rule.cost_family:
                score += 20
            if rule.request_type:
                score += 10
            if rule.glass_mode != 'any':
                score += 30
            candidates.append((score, rule.sequence, rule.id, rule))
        if not candidates:
            return self.browse()
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        return candidates[0][3]

    def format_destination(self, project):
        """Human-readable DESTINAZIONE for buyers (not full stock routing)."""
        self.ensure_one()
        site = project.display_name if project else _('Site')
        terzista = (
            project.sbu_site_subcontractor_id.display_name
            if project and project.sbu_site_subcontractor_id
            else _('site subcontractor (set on job)')
        )
        sistemista = (
            project.sbu_system_supplier_id.display_name
            if project and project.sbu_system_supplier_id
            else _('system supplier')
        )
        pattern = self.delivery_pattern
        if pattern == 'direct_site':
            return _('Supplier → site (%s)') % site
        if pattern == 'via_terzista':
            return _('Supplier → %s → site (%s)') % (terzista, site)
        stops = self.intermediate_stops or 0
        stop_note = ''
        if stops:
            stop_note = _(' · approx. %s–%s stops') % (max(stops - 1, 1), stops)
        return _('Supplier (%s) → %s → … → site (%s)%s') % (
            sistemista,
            terzista,
            site,
            stop_note,
        )
