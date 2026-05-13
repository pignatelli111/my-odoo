from odoo import models, fields, api


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
