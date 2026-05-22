from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SbuSalSheet(models.Model):
    """Progress billing sheet (SAL) linked to a project."""
    _name = 'sbu.sal.sheet'
    _description = 'SBU SAL / Progress billing sheet'
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
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='estimate_id.partner_id',
        store=True,
        readonly=True,
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Customer invoice',
        copy=False,
        readonly=True,
        tracking=True,
    )
    date = fields.Date(string='SAL date', default=fields.Date.today, tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('invoiced', 'Invoiced'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    retention_percent = fields.Float(
        string='Retention %',
        digits=(16, 2),
        default=5.0,
        help='Withholding / retention on gross amount (e.g. garanzia).',
    )
    line_ids = fields.One2many(
        'sbu.sal.sheet.line',
        'sheet_id',
        string='SAL lines',
    )
    certificate_ids = fields.One2many(
        'sbu.payment.certificate',
        'sal_sheet_id',
        string='Payment certificates (CDP)',
    )
    certificate_count = fields.Integer(
        string='CDP count',
        compute='_compute_certificate_count',
    )
    amount_gross = fields.Monetary(
        string='Gross amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_retention = fields.Monetary(
        string='Retention',
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
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    invoice_post_override = fields.Selection(
        selection=[
            ('company', 'Use company default'),
            ('draft', 'Always keep invoice in draft'),
            ('posted', 'Always post invoice'),
        ],
        string='Invoice posting',
        default='company',
        help='Overrides the company default for this SAL only (draft vs posted customer invoice).',
    )
    invoice_tax_ids = fields.Many2many(
        'account.tax',
        'sbu_sal_sheet_invoice_tax_rel',
        'sheet_id',
        'tax_id',
        string='Invoice taxes',
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'parent_of', company_id)]",
        help='Optional. If empty, company SAL default sale taxes apply, then fiscal position mapping.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sbu.sal.sheet') or _('New')
        return super().create(vals_list)

    @api.depends('line_ids.amount_this_sal', 'retention_percent')
    def _compute_amounts(self):
        for rec in self:
            gross = sum(rec.line_ids.mapped('amount_this_sal'))
            rec.amount_gross = gross
            rec.amount_retention = gross * (rec.retention_percent or 0.0) / 100.0
            rec.amount_net = gross - rec.amount_retention

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('state', 'retention_percent', 'invoice_id')):
            sal_lines = self.line_ids.mapped('estimate_sal_line_id')
            if sal_lines:
                sal_lines._sbu_recompute_billing_from_sheet_lines()
        return res

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    @api.depends('certificate_ids')
    def _compute_certificate_count(self):
        for sheet in self:
            sheet.certificate_count = len(sheet.certificate_ids)

    def _sbu_certificate_to_keep(self):
        """Prefer paid, then issued, else newest CDP on this sheet."""
        self.ensure_one()
        certs = self.certificate_ids
        keep = certs.filtered(lambda c: c.state == 'paid')[:1]
        if not keep:
            keep = certs.filtered(lambda c: c.state == 'issued')[:1]
        if not keep:
            keep = certs.sorted(
                key=lambda c: (c.date or fields.Date.today(), c.id),
                reverse=True,
            )[:1]
        return keep

    def action_cleanup_duplicate_certificates(self):
        """Delete extra CDPs on this SAL (UAT cleanup). Keeps one: paid > issued > newest."""
        self.ensure_one()
        certs = self.certificate_ids
        if len(certs) <= 1:
            raise UserError(_('This SAL has only one payment certificate (nothing to remove).'))
        keep = self._sbu_certificate_to_keep()
        to_remove = certs - keep
        removed_count = len(to_remove)
        to_remove.with_context(sbu_force_certificate_unlink=True).unlink()
        sal_lines = self.line_ids.mapped('estimate_sal_line_id')
        if sal_lines:
            sal_lines.action_refresh_sal_finance_links()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CDPs cleaned up'),
                'message': _('Kept %s; removed %s duplicate certificate(s).') % (
                    keep.name,
                    removed_count,
                ),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_certificates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment certificates'),
            'res_model': 'sbu.payment.certificate',
            'view_mode': 'list,form',
            'domain': [('sal_sheet_id', '=', self.id)],
            'context': {
                'default_sal_sheet_id': self.id,
                'default_project_id': self.project_id.id,
                'default_currency_id': self.currency_id.id,
                'default_amount_gross': self.amount_gross,
                'default_retention_percent': self.retention_percent,
            },
        }

    def action_create_certificate(self):
        self.ensure_one()
        if self.state not in ('confirmed', 'invoiced'):
            raise UserError(_('Confirm the SAL before creating a payment certificate.'))
        existing_draft = self.certificate_ids.filtered(lambda c: c.state == 'draft')[:1]
        if existing_draft:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sbu.payment.certificate',
                'res_id': existing_draft.id,
                'view_mode': 'form',
                'target': 'current',
            }
        cert = self.env['sbu.payment.certificate'].create({
            'sal_sheet_id': self.id,
            'project_id': self.project_id.id,
            'currency_id': self.currency_id.id,
            'amount_gross': self.amount_gross,
            'retention_percent': self.retention_percent,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.payment.certificate',
            'res_id': cert.id,
            'view_mode': 'form',
        }

    def _sbu_sal_effective_invoice_post_mode(self):
        self.ensure_one()
        if self.invoice_post_override == 'company':
            return self.company_id.sbu_sal_invoice_post_default or 'draft'
        return self.invoice_post_override

    def _sbu_sal_prepare_invoice_line_commands(self, income_account, fiscal_position):
        """Gross + retention lines (taxes on gross) when retention > 0; else single gross (= net) line."""
        self.ensure_one()
        base_taxes = self.invoice_tax_ids or self.company_id.sbu_sal_default_tax_ids
        gross_account = income_account
        if fiscal_position:
            gross_account = fiscal_position.map_account(income_account)
            taxes = fiscal_position.map_tax(base_taxes)
        else:
            taxes = base_taxes

        analytic_kw = {}
        project = self.project_id
        aa = project.account_id if project else False
        if aa and 'analytic_distribution' in self.env['account.move.line']._fields:
            analytic_kw['analytic_distribution'] = {str(aa.id): 100.0}

        commands = []
        ret_account = self.company_id.sbu_sal_retention_account_id
        if self.amount_retention > 0 and ret_account:
            gross_line = {
                'name': _('SAL %s — progress (gross)') % self.name,
                'quantity': 1.0,
                'price_unit': self.amount_gross,
                'account_id': gross_account.id,
                'tax_ids': [fields.Command.set(taxes.ids)],
                **analytic_kw,
            }
            commands.append(fields.Command.create(gross_line))
            ret_acc = fiscal_position.map_account(ret_account) if fiscal_position else ret_account
            ret_line = {
                'name': _('Retention (withholding) — %s') % self.name,
                'quantity': 1.0,
                'price_unit': -self.amount_retention,
                'account_id': ret_acc.id,
                'tax_ids': [fields.Command.clear()],
                **analytic_kw,
            }
            commands.append(fields.Command.create(ret_line))
        else:
            net_line = {
                'name': _('SAL %s — progress billing') % self.name,
                'quantity': 1.0,
                'price_unit': self.amount_net,
                'account_id': gross_account.id,
                'tax_ids': [fields.Command.set(taxes.ids)],
                **analytic_kw,
            }
            commands.append(fields.Command.create(net_line))
        return commands

    def action_create_draft_invoice(self):
        """Create a customer invoice from the SAL: taxes, fiscal position, analytic to project; post per policy."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Confirm the SAL before creating an invoice.'))
        if not self.partner_id:
            raise UserError(_('The linked estimate has no customer; set a client on the estimate first.'))
        if self.invoice_id:
            raise UserError(_('An invoice is already linked to this SAL.'))
        if not self.amount_net or self.amount_net <= 0:
            raise UserError(_('Net payable must be greater than zero.'))
        if self.amount_retention > 0 and not self.company_id.sbu_sal_retention_account_id:
            raise UserError(
                _('Configure the SAL retention account on the company before invoicing a SAL with retention.')
            )
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            raise UserError(_('Configure a sales journal for this company.'))
        account = journal.default_account_id
        if not account:
            raise UserError(_('Set a default income account on the sales journal %s.') % journal.display_name)

        Fiscal = self.env['account.fiscal.position'].with_company(self.company_id)
        fiscal_position = Fiscal._get_fiscal_position(self.partner_id)
        line_commands = self._sbu_sal_prepare_invoice_line_commands(account, fiscal_position)

        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.name,
            'ref': _('SAL %s') % self.name,
            'fiscal_position_id': fiscal_position.id if fiscal_position else False,
            'invoice_line_ids': line_commands,
        }
        if 'project_id' in self.env['account.move']._fields:
            move_vals['project_id'] = self.project_id.id
        if 'sbu_sal_sheet_id' in self.env['account.move']._fields:
            move_vals['sbu_sal_sheet_id'] = self.id

        move = self.env['account.move'].with_company(self.company_id).create(move_vals)
        self.write({'invoice_id': move.id, 'state': 'invoiced'})

        if self._sbu_sal_effective_invoice_post_mode() == 'posted':
            move.action_post()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_print_invoice_sal_detail(self):
        """PDF with one row per contractual SAL line (Cosimo point 13)."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('Create the customer invoice before printing the SAL detail layout.'))
        report = self.env.ref('sbu_sal.action_report_sbu_invoice_sal_detail', raise_if_not_found=False)
        if not report:
            raise UserError(_('SAL invoice detail report is not installed.'))
        return report.with_context(discard_logo_check=True).report_action(self.invoice_id)
