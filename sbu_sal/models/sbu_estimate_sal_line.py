from odoo import api, fields, models, _


class SbuEstimateSalLine(models.Model):
    _inherit = 'sbu.estimate.sal.line'

    invoice_id = fields.Many2one(
        'account.move',
        string='Latest customer invoice',
        compute='_compute_finance_documents',
        store=True,
        readonly=True,
        copy=False,
    )
    invoice_ids = fields.Many2many(
        'account.move',
        'sbu_estimate_sal_line_invoice_rel',
        'sal_line_id',
        'invoice_id',
        string='Customer invoices',
        compute='_compute_finance_documents',
        store=True,
        readonly=True,
    )
    payment_certificate_ids = fields.Many2many(
        'sbu.payment.certificate',
        'sbu_estimate_sal_line_certificate_rel',
        'sal_line_id',
        'certificate_id',
        string='Payment certificates (CDP)',
        compute='_compute_finance_documents',
        store=True,
        readonly=True,
    )
    payment_certificate_id = fields.Many2one(
        'sbu.payment.certificate',
        string='Latest payment certificate',
        compute='_compute_finance_documents',
        store=True,
        readonly=True,
    )
    certificate_count = fields.Integer(
        string='CDP count',
        compute='_compute_finance_documents',
    )
    invoice_count = fields.Integer(
        string='Invoice count',
        compute='_compute_finance_documents',
    )

    def _sbu_retention_withheld_for_sheet_line(self, sheet_line):
        """Use payment certificate retention when issued/paid; else sheet % × progress."""
        self.ensure_one()
        sheet = sheet_line.sheet_id
        progress = sheet_line.amount_this_sal or 0.0
        if not progress:
            return 0.0
        gross = sheet.amount_gross or 0.0
        if gross and sheet.certificate_ids:
            certs = sheet.certificate_ids.filtered(lambda c: c.state in ('issued', 'paid'))
            if certs:
                cert = certs.sorted(
                    key=lambda c: (c.date or fields.Date.today(), c.id),
                    reverse=True,
                )[0]
                return (cert.amount_retention or 0.0) * (progress / gross)
        return super()._sbu_retention_withheld_for_sheet_line(sheet_line)

    def _sbu_get_linked_sheet_lines(self):
        return self.env['sbu.sal.sheet.line'].search([
            ('estimate_sal_line_id', 'in', self.ids),
        ])

    @api.model
    def _sbu_format_finance_reference(self, certificates, invoices):
        """Human-readable summary for administration (all CDPs and invoices)."""
        parts = []
        seen_invoice_ids = set()
        cert_key = lambda c: (c.date or fields.Date.from_string('1970-01-01'), c.id)
        for cert in certificates.sorted(key=cert_key, reverse=True):
            label = cert.name or _('CDP')
            state_label = dict(cert._fields['state'].selection).get(cert.state, cert.state)
            if state_label:
                label = f'{label} ({state_label})'
            if cert.invoice_id:
                inv_name = cert.invoice_id.name or cert.invoice_id.ref or str(cert.invoice_id.id)
                label = f'{label} → {inv_name}'
                seen_invoice_ids.add(cert.invoice_id.id)
            parts.append(label)
        inv_key = lambda m: (m.invoice_date or m.date or fields.Date.from_string('1970-01-01'), m.id)
        for inv in invoices.sorted(key=inv_key, reverse=True):
            if inv.id in seen_invoice_ids:
                continue
            inv_name = inv.name or inv.ref or str(inv.id)
            pay = inv.payment_state
            if pay and pay != 'not_paid':
                inv_name = f'{inv_name} ({pay})'
            parts.append(inv_name)
        return '; '.join(parts) if parts else False

    @api.depends('total_contract')
    def _compute_finance_documents(self):
        SheetLine = self.env['sbu.sal.sheet.line']
        for line in self:
            sheet_lines = SheetLine.search([('estimate_sal_line_id', '=', line.id)])
            sheets = sheet_lines.mapped('sheet_id')
            certs = sheets.mapped('certificate_ids')
            invoices = sheets.mapped('invoice_id').filtered('id')
            line.payment_certificate_ids = [(6, 0, certs.ids)]
            line.invoice_ids = [(6, 0, invoices.ids)]
            line.certificate_count = len(certs)
            line.invoice_count = len(invoices)
            sorted_certs = certs.sorted(
                key=lambda c: (c.date or fields.Date.from_string('1970-01-01'), c.id),
                reverse=True,
            )
            sorted_invoices = invoices.sorted(
                key=lambda m: (m.invoice_date or m.date or fields.Date.from_string('1970-01-01'), m.id),
                reverse=True,
            )
            line.payment_certificate_id = sorted_certs[:1]
            line.invoice_id = sorted_invoices[:1]
            if certs or invoices:
                line.certificate_ref = line._sbu_format_finance_reference(certs, invoices)

    def _sbu_recompute_billing_from_sheet_lines(self):
        self._compute_billing_summary()
        self._compute_sal_status()
        self._compute_finance_documents()

    def action_view_payment_certificates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment certificates'),
            'res_model': 'sbu.payment.certificate',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payment_certificate_ids.ids)],
            'context': {'create': False},
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('id', 'in', self.invoice_ids.ids),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ],
            'context': {'create': False},
        }

    def action_open_latest_certificate(self):
        self.ensure_one()
        if not self.payment_certificate_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sbu.payment.certificate',
            'res_id': self.payment_certificate_id.id,
            'view_mode': 'form',
        }

    def action_open_latest_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }
