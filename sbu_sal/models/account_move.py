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
