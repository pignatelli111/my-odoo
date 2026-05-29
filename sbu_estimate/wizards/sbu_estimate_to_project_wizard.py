from odoo import models, fields, api, _
from odoo.exceptions import UserError
import datetime


class SbuEstimateToProjectWizard(models.TransientModel):
    _name = 'sbu.estimate.to.project.wizard'
    _description = 'Wizard: Preventivo → Commessa'

    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo',
        required=True,
        readonly=True,
    )
    project_name = fields.Char(
        string='Nome Commessa',
        required=True,
    )
    project_code = fields.Char(
        string='Codice Commessa',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        related='estimate_id.partner_id',
        string='Cliente',
        readonly=True,
    )
    job_site = fields.Char(
        related='estimate_id.job_site',
        string='Cantiere',
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Project Manager',
        default=lambda self: self.env.user,
    )
    date_start = fields.Date(
        string='Data Inizio',
        default=fields.Date.today,
    )
    date_end = fields.Date(string='Data Fine Prevista')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        estimate_id = self.env.context.get('default_estimate_id')
        if estimate_id:
            estimate = self.env['sbu.estimate'].browse(estimate_id)
            # Generate project code: P{year}_{sequence}
            year = datetime.date.today().year
            seq = self.env['ir.sequence'].next_by_code('sbu.project') or '0001'
            code = f'P{seq}_{year}'
            res.update({
                'estimate_id': estimate_id,
                'project_name': estimate.job_site or estimate.partner_id.name or '',
                'project_code': code,
            })
        return res

    def action_create_project(self):
        self.ensure_one()
        estimate = self.estimate_id

        if estimate.project_id:
            raise UserError(_('Una commessa esiste già per questo preventivo.'))

        # Same company as the estimate (avoids multi-company "no read access" on project.project)
        company = estimate.company_id

        # Create the project
        project = self.env['project.project'].create({
            'name': f'[{self.project_code}] {self.project_name}',
            'company_id': company.id,
            'partner_id': estimate.partner_id.id,
            'user_id': self.user_id.id,
            'date_start': self.date_start,
            'date': self.date_end,
            'description': (
                f'Commessa generata da preventivo: {estimate.full_name}\n'
                f'Cliente: {estimate.partner_id.name}\n'
                f'Cantiere: {estimate.job_site or ""}\n'
                f'Valore contratto: € {estimate.total_price:,.2f}'
            ),
        })

        # Write custom fields on project
        project.write({
            'sbu_estimate_id': estimate.id,
            'sbu_project_code': self.project_code,
            'sbu_job_site': self.job_site or '',
        })

        # Link project back to estimate
        estimate.project_id = project

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'res_id': project.id,
            'view_mode': 'form',
        }
