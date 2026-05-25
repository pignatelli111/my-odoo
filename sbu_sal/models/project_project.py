from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
            'search_view_id': self.env.ref('sbu_sal.view_sbu_sal_sheet_search').id,
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
            'search_view_id': self.env.ref('sbu_sal.view_sbu_sal_passive_sheet_search').id,
            'context': {
                'default_project_id': self.id,
                'default_company_id': self.company_id.id,
                'default_subcontract_scope': 'posa',
            },
        }

    def action_sbu_contractual_billing_overview(self):
        """Cosimo punto 13: contractual SAL items with invoice/CDP links on the estimate."""
        self.ensure_one()
        estimate = self.sbu_estimate_id
        if not estimate:
            raise UserError(_('Link a won estimate to this project to open contractual billing.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contractual billing'),
            'res_model': 'sbu.estimate.sal.line',
            'view_mode': 'list,form',
            'domain': [('estimate_id', '=', estimate.id)],
            'search_view_id': self.env.ref('sbu_estimate.view_sbu_estimate_sal_line_search').id,
            'context': {
                'default_estimate_id': estimate.id,
                'search_default_estimate_id': estimate.id,
            },
        }
