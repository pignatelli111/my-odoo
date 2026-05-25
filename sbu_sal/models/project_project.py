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
    sbu_billing_contract_total = fields.Monetary(
        string='Contract value (SAL items)',
        compute='_compute_sbu_billing_dashboard',
        currency_field='currency_id',
    )
    sbu_billing_billed = fields.Monetary(
        string='Billed to date',
        compute='_compute_sbu_billing_dashboard',
        currency_field='currency_id',
    )
    sbu_billing_remaining = fields.Monetary(
        string='Remaining to bill',
        compute='_compute_sbu_billing_dashboard',
        currency_field='currency_id',
    )
    sbu_billing_progress_pct = fields.Float(
        string='Billing progress %',
        compute='_compute_sbu_billing_dashboard',
        digits=(16, 2),
    )
    sbu_billing_open_sal_count = fields.Integer(
        string='Open SAL sheets',
        compute='_compute_sbu_billing_dashboard',
    )
    sbu_billing_last_cdp_id = fields.Many2one(
        'sbu.payment.certificate',
        string='Latest CDP',
        compute='_compute_sbu_billing_dashboard',
    )
    sbu_billing_last_invoice_id = fields.Many2one(
        'account.move',
        string='Latest customer invoice',
        compute='_compute_sbu_billing_dashboard',
    )

    def _compute_sbu_sal_sheet_count(self):
        sheet = self.env['sbu.sal.sheet'].sudo()
        for project in self:
            project.sbu_sal_sheet_count = sheet.search_count([('project_id', '=', project.id)])

    def _compute_sbu_sal_passive_sheet_count(self):
        sheet = self.env['sbu.sal.passive.sheet'].sudo()
        for project in self:
            project.sbu_sal_passive_sheet_count = sheet.search_count([('project_id', '=', project.id)])

    @api.depends(
        'sbu_estimate_id',
        'sbu_estimate_id.sal_line_ids.total_contract',
        'sbu_estimate_id.sal_line_ids.amount_billed',
        'sbu_estimate_id.sal_line_ids.amount_remaining',
        'sbu_estimate_id.sal_line_ids.billing_progress_pct',
        'sbu_estimate_id.currency_id',
    )
    def _compute_sbu_billing_dashboard(self):
        Certificate = self.env['sbu.payment.certificate'].sudo()
        Sheet = self.env['sbu.sal.sheet'].sudo()
        Move = self.env['account.move'].sudo()
        for project in self:
            est = project.sbu_estimate_id
            if not est:
                project.sbu_billing_contract_total = 0.0
                project.sbu_billing_billed = 0.0
                project.sbu_billing_remaining = 0.0
                project.sbu_billing_progress_pct = 0.0
                project.sbu_billing_open_sal_count = 0
                project.sbu_billing_last_cdp_id = False
                project.sbu_billing_last_invoice_id = False
                continue
            sal_lines = est.sal_line_ids
            contract = sum(sal_lines.mapped('total_contract'))
            billed = sum(sal_lines.mapped('amount_billed'))
            remaining = sum(sal_lines.mapped('amount_remaining'))
            project.sbu_billing_contract_total = contract
            project.sbu_billing_billed = billed
            project.sbu_billing_remaining = remaining
            project.sbu_billing_progress_pct = (
                (billed / contract * 100.0) if contract else 0.0
            )
            project.sbu_billing_open_sal_count = Sheet.search_count([
                ('project_id', '=', project.id),
                ('state', 'in', ('draft', 'confirmed')),
            ])
            project.sbu_billing_last_cdp_id = Certificate.search(
                [('sal_sheet_id.project_id', '=', project.id)],
                order='date desc, id desc',
                limit=1,
            )
            inv_domain = [
                ('move_type', '=', 'out_invoice'),
                ('state', '!=', 'cancel'),
            ]
            if 'sbu_sal_sheet_id' in Move._fields:
                inv_domain = [
                    ('move_type', '=', 'out_invoice'),
                    ('state', '!=', 'cancel'),
                    '|',
                    ('sbu_sal_sheet_id.project_id', '=', project.id),
                    ('project_id', '=', project.id),
                ]
            elif 'project_id' in Move._fields:
                inv_domain.append(('project_id', '=', project.id))
            project.sbu_billing_last_invoice_id = Move.search(
                inv_domain,
                order='invoice_date desc, id desc',
                limit=1,
            )

    def action_view_sbu_sal_sheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('SAL sheets'),
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
            'name': _('Passive SAL (subcontract)'),
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
        """Contractual SAL lines with billed / remaining / invoice / CDP."""
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

    def action_sbu_billing_dashboard(self):
        """Open job form on billing progress tab (Cosimo point 13 dashboard)."""
        self.ensure_one()
        if not self.sbu_estimate_id:
            raise UserError(_('Link a source estimate on this job first.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Billing progress'),
            'res_model': 'project.project',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'sbu_open_billing_tab': True},
        }

    def action_sbu_customer_invoices(self):
        """Customer invoices linked to this job via SAL."""
        self.ensure_one()
        Move = self.env['account.move']
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '!=', 'cancel'),
        ]
        if 'sbu_sal_sheet_id' in Move._fields:
            domain = [
                ('move_type', '=', 'out_invoice'),
                ('state', '!=', 'cancel'),
                '|',
                ('sbu_sal_sheet_id.project_id', '=', self.id),
                ('project_id', '=', self.id),
            ]
        elif 'project_id' in Move._fields:
            domain.append(('project_id', '=', self.id))
        else:
            domain.append(('invoice_origin', 'ilike', 'SAL'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer invoices (SAL)'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'default_move_type': 'out_invoice'},
        }
