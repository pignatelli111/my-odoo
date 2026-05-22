from odoo import fields, models, _
from odoo.exceptions import UserError

from .sbu_workflow_routing import (
    collect_workflow_routes_from_estimate,
    workflow_route_to_request_type,
)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sbu_budget_family_ids = fields.One2many(
        'sbu.project.budget.family',
        'project_id',
        string='Budget by cost family',
    )
    sbu_budget_po_unlock = fields.Boolean(
        string='Unlock PO over budget',
        copy=False,
        help='When enabled, purchase orders on this job can be confirmed even if a cost '
             'family exceeds the ANACO budget (admin only).',
    )
    sbu_purchase_request_count = fields.Integer(
        string='Purchase requests',
        compute='_compute_sbu_purchase_request_count',
    )
    sbu_site_subcontractor_id = fields.Many2one(
        'res.partner',
        string='Site subcontractor (terzista)',
        domain="[('is_company', '=', True)]",
        help='Default intermediate delivery point for aluminum, ACO, and glass '
             '(when «via terzista» is selected).',
    )
    sbu_system_supplier_id = fields.Many2one(
        'res.partner',
        string='System supplier (sistemista)',
        domain="[('supplier_rank', '>', 0)]",
        help='Your default system supplier (aluminum / workshop paths).',
    )
    sbu_glass_delivery_mode = fields.Selection(
        [
            ('direct', 'Glass supplier → site'),
            ('via_terzista', 'Glass supplier → site subcontractor → site'),
        ],
        string='Glass delivery',
        default='via_terzista',
        help='Per-job choice: direct to site or via the same site subcontractor as aluminum.',
    )

    def _compute_sbu_purchase_request_count(self):
        pr = self.env['sbu.purchase.request'].sudo()
        for project in self:
            project.sbu_purchase_request_count = pr.search_count([('project_id', '=', project.id)])

    def action_sbu_refresh_budget_families(self):
        """Rebuild budget vs engaged rows from estimate + PR/PO (Cosimo point 11)."""
        self.ensure_one()
        self.env['sbu.project.budget.family'].refresh_project(self)
        return True

    def action_sbu_apply_delivery_on_all_prs(self):
        """Re-apply delivery standard rules on all open PR lines of this job."""
        self.ensure_one()
        lines = self.env['sbu.purchase.request.line'].search([
            ('request_id.project_id', '=', self.id),
            ('request_id.state', '!=', 'cancelled'),
        ])
        lines._sbu_apply_delivery_standard(overwrite=True)
        return True

    def action_sbu_open_budget_dashboard(self):
        """Single screen: preventive budget, engaged, residual, traffic lights."""
        self.ensure_one()
        self.action_sbu_refresh_budget_families()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase budget by family'),
            'res_model': 'sbu.project.budget.family',
            'view_mode': 'list',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'search_default_project_id': self.id,
            },
        }

    def action_view_sbu_purchase_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase requests',
            'res_model': 'sbu.purchase.request',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id, 'default_company_id': self.company_id.id},
        }

    def action_sbu_open_purchase_request_create_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nuovo documento acquisto'),
            'res_model': 'sbu.purchase.request.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }

    def action_sbu_create_demand_rda_from_estimate(self):
        """Step 3.2: won estimate → explode BOM into RDA demand lines (loss %, packs, MOQ)."""
        self.ensure_one()
        est = self.sbu_estimate_id
        if not est:
            raise UserError(_('Set «Preventivo di Origine» on the project (won estimate) first.'))
        if est.state != 'won':
            raise UserError(
                _('Demand generation needs the source estimate in «Won» state (current: %s).')
                % (est.state,)
            )
        PurchaseRequest = self.env['sbu.purchase.request']
        pr = PurchaseRequest.create({
            'project_id': self.id,
            'request_type': 'rda',
            'company_id': self.company_id.id,
            'demand_loss_pct': 3.0,
            'need_by_date': est.validity_date,
        })
        pr._load_lines_from_estimate_bom(clear=True)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Demand RDA'),
            'res_model': 'sbu.purchase.request',
            'res_id': pr.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_sbu_create_purchase_requests_by_workflow(self):
        """One purchase request per workflow route on linked estimate ANACO lines."""
        self.ensure_one()
        est = self.sbu_estimate_id
        if not est:
            raise UserError(_('Set «Preventivo di Origine» on the project (won estimate) first.'))
        if est.state != 'won':
            raise UserError(
                _('Workflow purchase requests need the source estimate in «Won» state (current: %s).')
                % (est.state,)
            )
        routes = collect_workflow_routes_from_estimate(est)
        if not routes:
            raise UserError(
                _('No workflow routes on estimate lines. Set «Categoria / famiglia costo» on ANACO rows first.')
            )
        PurchaseRequest = self.env['sbu.purchase.request']
        created = PurchaseRequest
        for route in routes:
            pr = PurchaseRequest.create({
                'project_id': self.id,
                'request_type': workflow_route_to_request_type(route),
                'workflow_route': route,
                'company_id': self.company_id.id,
                'demand_loss_pct': 3.0,
                'need_by_date': est.validity_date,
            })
            pr._load_lines_from_estimate_bom(clear=True, workflow_route=route)
            created |= pr
        if len(created) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase request'),
                'res_model': 'sbu.purchase.request',
                'res_id': created.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase requests by workflow'),
            'res_model': 'sbu.purchase.request',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
            'target': 'current',
        }
