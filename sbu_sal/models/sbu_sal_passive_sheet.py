from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.sbu_estimate.models.sbu_estimate_line import _successive_discount_factor

from odoo.addons.sbu_estimate.models.sbu_revision_display import sbu_doc_name_with_revision


class SbuSalPassiveSheet(models.Model):
    """Passive progress billing (SAL passivo) for subcontractors / installation."""
    _name = 'sbu.sal.passive.sheet'
    _description = 'SBU passive SAL / subcontract progress sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project / Job',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Source estimate',
        related='project_id.sbu_estimate_id',
        store=True,
        readonly=True,
    )
    sbu_revision_label = fields.Char(
        string='Job REV label',
        related='project_id.sbu_revision_label',
        store=True,
        readonly=True,
    )
    sbu_display_label = fields.Char(
        string='Display label',
        compute='_compute_sbu_display_label',
        store=True,
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Subcontractor / vendor',
        required=True,
        tracking=True,
        help='Subcontractor for installation (posa) or general subcontract.',
    )
    subcontract_scope = fields.Selection(
        [
            ('posa', 'Installation (posa)'),
            ('subappalto', 'General subcontract'),
            ('mixed', 'Mixed'),
        ],
        string='Scope',
        default='posa',
        required=True,
        tracking=True,
    )
    period_label = fields.Char(
        string='Period',
        help='e.g. SAL 3 — May 2026',
        tracking=True,
    )
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Vendor bill',
        copy=False,
        readonly=True,
        tracking=True,
    )
    date = fields.Date(string='SAL date', default=fields.Date.today, tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('invoiced', 'Billed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    retention_percent = fields.Float(
        string='Retention %',
        digits=(16, 2),
        default=0.0,
        help='Optional withholding on the subcontractor bill.',
    )
    line_ids = fields.One2many(
        'sbu.sal.passive.line',
        'sheet_id',
        string='Passive SAL lines',
    )
    amount_gross = fields.Monetary(
        string='Gross amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_retention = fields.Monetary(
        string='Retention amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_net = fields.Monetary(
        string='Net payable',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    budget_total = fields.Monetary(
        string='Total POS budget',
        compute='_compute_budget_total',
        store=True,
        currency_field='currency_id',
        help='Sum of ANACO installation/subcontract budgets on this sheet.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('sbu.sal.passive.sheet') or _('New')
                )
        return super().create(vals_list)

    @api.depends('name', 'sbu_revision_label')
    def _compute_sbu_display_label(self):
        for sheet in self:
            sheet.sbu_display_label = sbu_doc_name_with_revision(
                sheet.name,
                sheet.sbu_revision_label,
            ) or sheet.name

    def name_get(self):
        if self.env.context.get('sbu_use_document_name_only'):
            return super().name_get()
        return [(rec.id, rec.sbu_display_label or rec.name) for rec in self]

    @api.depends('line_ids.budget_amount')
    def _compute_budget_total(self):
        for rec in self:
            rec.budget_total = sum(rec.line_ids.mapped('budget_amount'))

    @api.depends('line_ids.amount_this_sal', 'retention_percent')
    def _compute_amounts(self):
        for rec in self:
            gross = sum(rec.line_ids.mapped('amount_this_sal'))
            rec.amount_gross = gross
            rec.amount_retention = gross * (rec.retention_percent or 0.0) / 100.0
            rec.amount_net = gross - rec.amount_retention

    @api.model
    def _sbu_posa_budget_amount(self, eline):
        """Budget slice for passive SAL: posa column, installation family, or site cost."""
        qty = eline.qty or 1.0
        disc = _successive_discount_factor(
            eline.discount_sc1,
            eline.discount_sc2,
            eline.discount_sc3,
        )
        posa = eline.cost_posa_lamiera_lin_cad or 0.0
        if posa > 0:
            return posa * disc * qty
        if eline.cost_family == 'installation':
            return eline.cost_after_discounts_tot or eline.cost_total_tot or 0.0
        if eline.cost_family == 'site_cost':
            cant = eline.cost_cantiere_cad or 0.0
            if cant > 0:
                return cant * disc * qty
        return 0.0

    @api.model
    def _sbu_passive_line_is_candidate(self, eline):
        if (eline.cost_posa_lamiera_lin_cad or 0.0) > 0:
            return True
        if eline.cost_family in ('installation', 'site_cost'):
            return self._sbu_posa_budget_amount(eline) > 0
        return False

    @api.model
    def _sbu_passive_category_for_line(self, eline):
        if (eline.cost_posa_lamiera_lin_cad or 0.0) > 0:
            return 'posa_lin'
        if eline.cost_family == 'installation':
            return 'posa_lin'
        if eline.cost_family == 'site_cost':
            return 'posa_cantiere'
        return 'subappalto'

    def action_confirm(self):
        for sheet in self:
            for line in sheet.line_ids:
                total = (line.percent_prior_sal or 0.0) + (line.percent_this_sal or 0.0)
                if total > 100.01:
                    raise UserError(
                        _('Cannot confirm: cumulative progress on «%s» is %.2f%% (max 100%%).')
                        % (line.description, total)
                    )
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_load_posa_budget_from_estimate(self):
        """Load installation/subcontract budget lines from the linked ANACO estimate."""
        self.ensure_one()
        if not self.estimate_id:
            raise UserError(_('Link a project with a source estimate before loading the budget.'))
        if self.line_ids:
            raise UserError(_('Remove existing lines before reloading from the estimate.'))
        commands = []
        for eline in self.estimate_id.line_ids:
            if not self._sbu_passive_line_is_candidate(eline):
                continue
            budget = self._sbu_posa_budget_amount(eline)
            if budget <= 0:
                continue
            commands.append((0, 0, {
                'estimate_line_id': eline.id,
                'category': self._sbu_passive_category_for_line(eline),
                'description': eline.name or eline.description or eline.pos,
                'budget_amount': budget,
            }))
        if not commands:
            raise UserError(
                _(
                    'No installation or subcontract budget found on estimate %s '
                    '(check POS / installation cost family / site costs).'
                )
                % self.estimate_id.display_name
            )
        self.write({'line_ids': commands})
        return True

    def _sbu_passive_prepare_bill_line_commands(self, expense_account, fiscal_position):
        self.ensure_one()
        analytic_kw = {}
        project = self.project_id
        aa = project.account_id if project else False
        if aa and 'analytic_distribution' in self.env['account.move.line']._fields:
            analytic_kw['analytic_distribution'] = {str(aa.id): 100.0}

        purchase_taxes = self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', self.company_id.id),
        ], limit=2)
        if fiscal_position:
            expense_account = fiscal_position.map_account(expense_account)
            purchase_taxes = fiscal_position.map_tax(purchase_taxes)

        commands = []
        if self.amount_retention > 0 and len(self.line_ids) > 1:
            for line in self.line_ids:
                if not line.amount_this_sal:
                    continue
                net_line = line.amount_this_sal * (1.0 - (self.retention_percent or 0.0) / 100.0)
                commands.append(fields.Command.create({
                    'name': '%s — %s' % (self.name, line.description),
                    'quantity': 1.0,
                    'price_unit': net_line,
                    'account_id': expense_account.id,
                    'tax_ids': [fields.Command.set(purchase_taxes.ids)],
                    **analytic_kw,
                }))
        elif self.line_ids:
            for line in self.line_ids.filtered(lambda l: l.amount_this_sal):
                net_unit = line.amount_this_sal
                if self.retention_percent:
                    net_unit *= 1.0 - (self.retention_percent or 0.0) / 100.0
                commands.append(fields.Command.create({
                    'name': '%s — %s' % (self.name, line.description),
                    'quantity': 1.0,
                    'price_unit': net_unit,
                    'account_id': expense_account.id,
                    'tax_ids': [fields.Command.set(purchase_taxes.ids)],
                    **analytic_kw,
                }))
        else:
            commands.append(fields.Command.create({
                'name': _('Passive SAL %s — progress') % self.name,
                'quantity': 1.0,
                'price_unit': self.amount_net,
                'account_id': expense_account.id,
                'tax_ids': [fields.Command.set(purchase_taxes.ids)],
                **analytic_kw,
            }))
        return commands

    def action_create_vendor_bill(self):
        """Create a vendor bill (in_invoice) from confirmed passive SAL."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Confirm the passive SAL before creating a vendor bill.'))
        if not self.vendor_id:
            raise UserError(_('Select the subcontractor / vendor.'))
        if self.vendor_bill_id:
            raise UserError(_('A vendor bill is already linked to this passive SAL.'))
        if not self.amount_net or self.amount_net <= 0:
            raise UserError(_('Net payable must be greater than zero.'))
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            raise UserError(_('Configure a purchase journal for this company.'))
        account = journal.default_account_id
        if not account:
            raise UserError(
                _('Set a default expense account on purchase journal %s.') % journal.display_name
            )

        Fiscal = self.env['account.fiscal.position'].with_company(self.company_id)
        fiscal_position = Fiscal._get_fiscal_position(self.vendor_id)
        line_commands = self._sbu_passive_prepare_bill_line_commands(account, fiscal_position)

        move_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.vendor_id.id,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'invoice_date': self.date or fields.Date.today(),
            'invoice_origin': self.name,
            'ref': _('Passive SAL %s') % self.name,
            'fiscal_position_id': fiscal_position.id if fiscal_position else False,
            'invoice_line_ids': line_commands,
        }
        if 'project_id' in self.env['account.move']._fields:
            move_vals['project_id'] = self.project_id.id

        move = self.env['account.move'].with_company(self.company_id).create(move_vals)
        self.write({'vendor_bill_id': move.id, 'state': 'invoiced'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def action_view_vendor_bill(self):
        self.ensure_one()
        if not self.vendor_bill_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor bill'),
            'res_model': 'account.move',
            'res_id': self.vendor_bill_id.id,
            'view_mode': 'form',
        }
