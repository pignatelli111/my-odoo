# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    sbu_sal_sheet_id = fields.Many2one(
        'sbu.sal.sheet',
        string='SAL sheet',
        copy=False,
        readonly=True,
        index=True,
        ondelete='set null',
    )
    sbu_sal_cdp_name = fields.Char(
        string='CDP reference',
        compute='_compute_sbu_sal_cdp_name',
    )
    sbu_revision_label = fields.Char(
        string='Job REV label',
        compute='_compute_sbu_revision_label',
        store=True,
    )
    sbu_display_label = fields.Char(
        string='Display label',
        compute='_compute_sbu_display_label',
        store=True,
    )

    @api.depends('project_id', 'project_id.sbu_revision_label', 'sbu_sal_sheet_id', 'sbu_sal_sheet_id.sbu_revision_label')
    def _compute_sbu_revision_label(self):
        for move in self:
            label = False
            if move.project_id:
                label = move.project_id.sbu_revision_label
            elif move.sbu_sal_sheet_id:
                label = move.sbu_sal_sheet_id.sbu_revision_label
            move.sbu_revision_label = label

    @api.depends('name', 'ref', 'sbu_revision_label', 'state')
    def _compute_sbu_display_label(self):
        from odoo.addons.sbu_estimate.models.sbu_revision_display import sbu_doc_name_with_revision
        for move in self:
            base = move.name or move.ref or _('Draft')
            if move.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund') and move.sbu_revision_label:
                move.sbu_display_label = sbu_doc_name_with_revision(base, move.sbu_revision_label)
            else:
                move.sbu_display_label = base

    def name_get(self):
        if self.env.context.get('sbu_use_document_name_only'):
            return super().name_get()
        sbu_moves = self.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
            and m.sbu_revision_label
        )
        result = dict(super(AccountMove, self - sbu_moves).name_get())
        for move in sbu_moves:
            result[move.id] = move.sbu_display_label or move.name
        return list(result.items())

    @api.depends('sbu_sal_sheet_id', 'sbu_sal_sheet_id.certificate_ids', 'sbu_sal_sheet_id.certificate_ids.state')
    def _compute_sbu_sal_cdp_name(self):
        for move in self:
            sheet = move.sbu_sal_sheet_id
            if not sheet:
                move.sbu_sal_cdp_name = False
                continue
            cert = sheet._sbu_certificate_to_keep()
            move.sbu_sal_cdp_name = cert.name if cert else False

    def write(self, vals):
        res = super().write(vals)
        touch_moves = self.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund'))
        if vals.get('payment_state'):
            touch_moves._sbu_sal_sync_certificates_payment_state()
        if touch_moves and vals.keys() & {'payment_state', 'state', 'name', 'ref'}:
            touch_moves._sbu_sal_touch_contractual_sal_lines()
        return res

    def _sbu_sal_touch_contractual_sal_lines(self):
        if 'sbu.estimate.sal.line' not in self.env:
            return
        sheets = self.env['sbu.sal.sheet'].search([('invoice_id', 'in', self.ids)])
        sal_lines = sheets.line_ids.mapped('estimate_sal_line_id')
        if sal_lines:
            sal_lines._sbu_recompute_billing_from_sheet_lines()

    def _sbu_sal_sync_certificates_payment_state(self):
        Certificate = self.env['sbu.payment.certificate'].sudo()
        for move in self:
            if move.payment_state != 'paid':
                continue
            certs = Certificate.search(
                [('sal_sheet_id.invoice_id', '=', move.id), ('state', '=', 'issued')]
            )
            if certs:
                certs.write({'state': 'paid'})
                certs._sbu_link_payment_from_invoice()

    def action_print_sbu_sal_detail(self):
        """Print SAL contractual line detail (Cosimo point 13)."""
        self.ensure_one()
        if not self.sbu_sal_sheet_id:
            raise UserError(_('This invoice is not linked to an SBU SAL sheet.'))
        report = self.env.ref('sbu_sal.action_report_sbu_invoice_sal_detail', raise_if_not_found=False)
        if not report:
            raise UserError(_('SAL invoice detail report is not installed.'))
        return report.with_context(discard_logo_check=True).report_action(self)
