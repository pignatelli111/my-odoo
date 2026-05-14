# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sbu_logikal_import_ids = fields.One2many(
        'sbu.logikal.import.batch',
        'project_id',
        string='Logikal / ReynaPro imports',
    )
    sbu_logikal_import_count = fields.Integer(
        compute='_compute_sbu_logikal_import_count',
        string='Logikal imports',
    )

    def _compute_sbu_logikal_import_count(self):
        for project in self:
            project.sbu_logikal_import_count = len(project.sbu_logikal_import_ids)

    def action_view_sbu_logikal_imports(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Logikal / ReynaPro imports',
            'res_model': 'sbu.logikal.import.batch',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id, 'default_company_id': self.company_id.id},
        }
