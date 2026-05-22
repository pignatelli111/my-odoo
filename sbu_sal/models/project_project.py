from odoo import models, fields, api


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sbu_sal_sheet_count = fields.Integer(
        compute='_compute_sbu_sal_sheet_count',
    )
    sbu_sal_passive_sheet_count = fields.Integer(
        string='Passive SAL count',
        compute='_compute_sbu_sal_passive_sheet_count',
    )

    def _compute_sbu_sal_sheet_count(self):
        sheet = self.env['sbu.sal.sheet'].sudo()
        for project in self:
            project.sbu_sal_sheet_count = sheet.search_count([('project_id', '=', project.id)])

    def _compute_sbu_sal_passive_sheet_count(self):
        sheet = self.env['sbu.sal.passive.sheet'].sudo()
        for project in self:
            project.sbu_sal_passive_sheet_count = sheet.search_count([('project_id', '=', project.id)])

    def action_view_sbu_sal_sheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'SAL sheets',
            'res_model': 'sbu.sal.sheet',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id, 'default_company_id': self.company_id.id},
        }

    def action_view_sbu_sal_passive_sheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Passive SAL (subcontract)',
            'res_model': 'sbu.sal.passive.sheet',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'default_company_id': self.company_id.id,
                'default_subcontract_scope': 'posa',
            },
        }
