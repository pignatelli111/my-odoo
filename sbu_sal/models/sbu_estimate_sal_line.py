from datetime import date

from odoo import api, fields, models, _

_FALLBACK_SORT_DATE = date(1970, 1, 1)


class SbuEstimateSalLine(models.Model):
    _inherit = 'sbu.estimate.sal.line'

    sal_sheet_line_ids = fields.One2many(
        'sbu.sal.sheet.line',
        'estimate_sal_line_id',
        string='SAL billing lines',
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Latest customer invoice',
        compute='_compute_finance_documents',
        compute_sudo=False,
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
        compute_sudo=False,
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
        compute_sudo=False,
        store=True,
        readonly=True,
    )
    payment_certificate_id = fields.Many2one(
        'sbu.payment.certificate',
        string='Latest payment certificate',
        compute='_compute_finance_documents',
        compute_sudo=False,
        store=True,
        readonly=True,
    )
    certificate_count = fields.Integer(
        string='CDP count',
        compute='_compute_finance_document_counts',
        compute_sudo=False,
    )
    invoice_count = fields.Integer(
        string='Invoice count',
        compute='_compute_finance_document_counts',
        compute_sudo=False,
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

    @api.model
    def _sbu_format_finance_reference(self, certificates, invoices):
        """Human-readable summary for administration (all CDPs and invoices)."""
        parts = []
        seen_invoice_ids = set()
        cert_key = lambda c: (c.date or _FALLBACK_SORT_DATE, c.id)
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
        inv_key = lambda m: (m.invoice_date or m.date or _FALLBACK_SORT_DATE, m.id)
        for inv in invoices.sorted(key=inv_key, reverse=True):
            if inv.id in seen_invoice_ids:
                continue
            inv_name = inv.name or inv.ref or str(inv.id)
            pay = inv.payment_state
            if pay and pay != 'not_paid':
                inv_name = f'{inv_name} ({pay})'
            parts.append(inv_name)
        return '; '.join(parts) if parts else False

    @api.depends(
        'sal_sheet_line_ids.sheet_id.invoice_id',
        'sal_sheet_line_ids.sheet_id.certificate_ids',
        'sal_sheet_line_ids.sheet_id.certificate_ids.state',
        'sal_sheet_line_ids.sheet_id.certificate_ids.invoice_id',
        'sal_sheet_line_ids.sheet_id.certificate_ids.name',
        'sal_sheet_line_ids.sheet_id.certificate_ids.date',
    )
    def _compute_finance_documents(self):
        for line in self:
            sheets = line.sal_sheet_line_ids.mapped('sheet_id')
            certs = sheets.mapped('certificate_ids')
            invoices = sheets.mapped('invoice_id').filtered('id')
            line.payment_certificate_ids = [(6, 0, certs.ids)]
            line.invoice_ids = [(6, 0, invoices.ids)]
            sorted_certs = certs.sorted(
                key=lambda c: (c.date or _FALLBACK_SORT_DATE, c.id),
                reverse=True,
            )
            sorted_invoices = invoices.sorted(
                key=lambda m: (m.invoice_date or m.date or _FALLBACK_SORT_DATE, m.id),
                reverse=True,
            )
            line.payment_certificate_id = sorted_certs[:1]
            line.invoice_id = sorted_invoices[:1]

    @api.depends('payment_certificate_ids', 'invoice_ids')
    def _compute_finance_document_counts(self):
        for line in self:
            line.certificate_count = len(line.payment_certificate_ids)
            line.invoice_count = len(line.invoice_ids)

    def _sbu_sync_certificate_ref(self):
        """Update Char reference from linked finance docs (not inside a compute method)."""
        for line in self:
            if line.payment_certificate_ids or line.invoice_ids:
                ref = line._sbu_format_finance_reference(
                    line.payment_certificate_ids,
                    line.invoice_ids,
                )
                if ref and line.certificate_ref != ref:
                    line.certificate_ref = ref

    @api.depends(
        'sal_sheet_line_ids.amount_this_sal',
        'sal_sheet_line_ids.sheet_id.state',
        'sal_sheet_line_ids.sheet_id.retention_percent',
        'sal_sheet_line_ids.sheet_id.certificate_ids.state',
        'sal_sheet_line_ids.sheet_id.certificate_ids.amount_retention',
        'total_contract',
        'retention_percent',
        'retention_amount',
    )
    def _compute_billing_summary(self):
        for line in self:
            total = line.total_contract or 0.0
            cap = line.retention_amount or 0.0
            rp = line.retention_percent or 0.0
            sheet_lines = line.sal_sheet_line_ids.filtered(
                lambda sl: sl.sheet_id.state in ('confirmed', 'invoiced')
            )
            billed = sum(sheet_lines.mapped('amount_this_sal'))
            withheld = sum(
                line._sbu_retention_withheld_for_sheet_line(sl)
                for sl in sheet_lines
            )
            remaining = max(total - billed, 0.0)
            line.amount_billed = billed
            line.amount_remaining = remaining
            line.retention_withheld_to_date = withheld
            line.retention_on_unbilled = remaining * rp / 100.0
            line.retention_remaining = max(cap - withheld, 0.0)
            line.billing_progress_pct = (billed / total * 100.0) if total else 0.0

    @api.depends(
        'sal_sheet_line_ids.sheet_id.state',
        'sal_sheet_line_ids.sheet_id.invoice_id',
        'sal_sheet_line_ids.sheet_id.invoice_id.payment_state',
        'sal_sheet_line_ids.sheet_id.certificate_ids.state',
        'payment_certificate_ids.state',
        'invoice_ids.payment_state',
        'estimate_line_ids',
        'cumulative_pct',
        'total_contract',
        'qty_contract',
        'unit_price',
    )
    def _compute_sal_status(self):
        for line in self:
            certs = line.payment_certificate_ids
            invoices = line.invoice_ids
            sheets = line.sal_sheet_line_ids.mapped('sheet_id')

            if certs.filtered(lambda c: c.state == 'paid') or any(
                inv.payment_state == 'paid' for inv in invoices
            ):
                line.sal_status = 'paid'
            elif invoices or sheets.filtered(lambda s: s.state == 'invoiced'):
                line.sal_status = 'invoiced'
            elif sheets.filtered(lambda s: s.state == 'confirmed') or certs.filtered(
                lambda c: c.state == 'issued'
            ):
                line.sal_status = 'approved'
            elif sheets.filtered(lambda s: s.state == 'draft'):
                line.sal_status = 'submitted'
            elif line._sbu_sal_status_is_prepared(line):
                line.sal_status = 'prepared'
            else:
                line.sal_status = 'draft'

    def _sbu_recompute_billing_from_sheet_lines(self):
        self._compute_billing_summary()
        self._compute_sal_status()
        self._compute_finance_documents()
        self._compute_finance_document_counts()
        self._sbu_sync_certificate_ref()

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
