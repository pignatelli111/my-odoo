from odoo import fields, models, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sbu_purchase_request_count = fields.Integer(
        string='Purchase requests',
        compute='_compute_sbu_purchase_request_count',
    )

    def _compute_sbu_purchase_request_count(self):
        pr = self.env['sbu.purchase.request'].sudo()
        for project in self:
            project.sbu_purchase_request_count = pr.search_count([('project_id', '=', project.id)])

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
