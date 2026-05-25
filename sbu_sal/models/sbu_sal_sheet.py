from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.sbu_estimate.models.sbu_revision_display import sbu_doc_name_with_revision


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

    def action_add_lines_from_contract(self):
        return self._action_open_contract_line_import_wizard(replace=False)

    def action_replace_lines_from_contract(self):
        return self._action_open_contract_line_import_wizard(replace=True)

    def _action_open_contract_line_import_wizard(self, replace=False):
        self.ensure_one()
        if not self.estimate_id:
            raise UserError(_('Link a source estimate on the project before adding lines.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add lines from contract'),
            'res_model': 'sbu.sal.sheet.line.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sheet_id': self.id,
                'default_replace_existing': replace,
            },
        }

    def _load_selected_contract_lines(self, contract_lines, clear=False):
        """Create SAL sheet lines from selected contractual SAL rows."""
        self.ensure_one()
        if clear:
            self.line_ids.unlink()
        existing = {
            sid for sid in self.line_ids.mapped('estimate_sal_line_id').ids if sid
        }
        SheetLine = self.env['sbu.sal.sheet.line']
        seq_base = max(self.line_ids.mapped('sequence') or [0])
        created = 0
        for sal_line in contract_lines.sorted(
            lambda l: (l.sequence, l.item_ref or '', l.id)
        ):
            if sal_line.id in existing:
                continue
            if sal_line.estimate_id != self.estimate_id:
                continue
            seq_base += 10
            SheetLine.create({
                'sheet_id': self.id,
                'sequence': seq_base,
                'estimate_sal_line_id': sal_line.id,
                'description': sal_line.description or sal_line.item_ref or sal_line.name,
                'contract_amount': sal_line.total_contract,
                'percent_this_sal': 0.0,
            })
            existing.add(sal_line.id)
            created += 1
            if sal_line.retention_percent:
                self.retention_percent = sal_line.retention_percent
        if not created and not clear:
            raise UserError(_('No new lines were added (items may already be on this SAL).'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.sal.sheet',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

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

    def _sbu_sal_build_invoice_ref(self):
        """Customer reference on invoice: SAL, optional CDP, job REV label."""
        self.ensure_one()
        ref_parts = [_('SAL %s') % self.name]
        cert = self._sbu_certificate_to_keep()
        if cert:
            ref_parts.append(_('CDP %s') % cert.name)
        if self.project_id:
            job_label = self.project_id.sbu_revision_label or self.project_id.display_name
            ref_parts.append(_('Job %s') % job_label)
        return ' · '.join(ref_parts)

    def _sbu_sal_sync_invoice_ref(self):
        """Refresh invoice ref when CDP is created after the draft invoice."""
        for sheet in self:
            if sheet.invoice_id:
                sheet.invoice_id.write({'ref': sheet._sbu_sal_build_invoice_ref()})

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
        self._sbu_sal_sync_invoice_ref()
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

    def _sbu_sal_invoice_tax_and_analytic(self, income_account, fiscal_position):
        """Shared taxes, mapped income account, and project analytic for invoice lines."""
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
        return gross_account, taxes, analytic_kw

    def _sbu_sal_append_retention_line(self, commands, fiscal_position, analytic_kw):
        self.ensure_one()
        ret_account = self.company_id.sbu_sal_retention_account_id
        if self.amount_retention <= 0 or not ret_account:
            return commands
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
        return commands

    def _sbu_sal_prepare_invoice_line_commands(self, income_account, fiscal_position):
        """One accounting line per contractual SAL row when sheet lines exist; else aggregate."""
        self.ensure_one()
        contractual = self.line_ids.filtered(lambda l: (l.amount_this_sal or 0.0) > 0)
        if contractual:
            return self._sbu_sal_prepare_invoice_line_commands_contractual(
                income_account, fiscal_position,
            )
        return self._sbu_sal_prepare_invoice_line_commands_aggregate(
            income_account, fiscal_position,
        )

    def _sbu_sal_prepare_invoice_line_commands_contractual(self, income_account, fiscal_position):
        """Cosimo punto 13: invoice lines mirror each SAL contractual row (+ retention)."""
        self.ensure_one()
        gross_account, taxes, analytic_kw = self._sbu_sal_invoice_tax_and_analytic(
            income_account, fiscal_position,
        )
        commands = []
        for sal_line in self.line_ids.sorted('sequence'):
            amount = sal_line.amount_this_sal or 0.0
            if amount <= 0:
                continue
            qty = sal_line.qty_display or 1.0
            price_unit = amount / qty if qty else amount
            parts = []
            if sal_line.item_ref:
                parts.append('[%s]' % sal_line.item_ref)
            if sal_line.description:
                parts.append(sal_line.description)
            if sal_line.uom_label:
                parts.append('(%s)' % sal_line.uom_label)
            name = ' '.join(parts) or _('SAL line')
            commands.append(fields.Command.create({
                'name': name,
                'quantity': qty,
                'price_unit': price_unit,
                'account_id': gross_account.id,
                'tax_ids': [fields.Command.set(taxes.ids)],
                **analytic_kw,
            }))
        if not commands:
            return self._sbu_sal_prepare_invoice_line_commands_aggregate(
                income_account, fiscal_position,
            )
        return self._sbu_sal_append_retention_line(commands, fiscal_position, analytic_kw)

    def _sbu_sal_prepare_invoice_line_commands_aggregate(self, income_account, fiscal_position):
        """Legacy aggregate gross + retention when no per-line amounts."""
        self.ensure_one()
        gross_account, taxes, analytic_kw = self._sbu_sal_invoice_tax_and_analytic(
            income_account, fiscal_position,
        )
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
            return self._sbu_sal_append_retention_line(commands, fiscal_position, analytic_kw)
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
            'ref': self._sbu_sal_build_invoice_ref(),
            'fiscal_position_id': fiscal_position.id if fiscal_position else False,
            'invoice_line_ids': line_commands,
        }
        if self.date and 'invoice_date' in self.env['account.move']._fields:
            move_vals['invoice_date'] = self.date
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
