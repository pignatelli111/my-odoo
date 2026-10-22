# -*- coding: utf-8 -*-
"""Historical contacts and invoices from a Qonto export (posted, as history)."""
import base64
import csv
import io
import json
import logging
import posixpath
import re

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

from odoo.addons.base.models.res_bank import sanitize_account_number
from odoo.addons.sbu_qonto.services.qonto_invoice_pdf import extract_pdf_text, parse_vat_summary

_logger = logging.getLogger(__name__)

_BATCH_SIZE = 25  # one click stays well under the Odoo.sh request time limit (~45 s)
_SKIP_STATUSES = {'rejected'}
_PAID = 'paid'


def _amount(value):
    if isinstance(value, dict):
        value = value.get('value')
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _vat_key(vat):
    """'IT 12345678901' / '12345678901' → '12345678901'; other countries keep their prefix."""
    key = re.sub(r'[^0-9A-Z]', '', (vat or '').upper())
    if key.startswith('IT') and key[2:].isdigit():
        key = key[2:]
    return key


def _name_key(name):
    return re.sub(r'[^0-9A-Z]', '', (name or '').upper())


class SbuQontoExportImportWizard(models.TransientModel):
    _inherit = 'sbu.qonto.export.import.wizard'

    import_partners = fields.Boolean(string='Suppliers and customers', default=True)
    import_invoices = fields.Boolean(string='Supplier and customer invoices (history)', default=True)
    include_archived = fields.Boolean(
        string='Include archived invoices', default=True,
        help='Qonto "archived" invoices are real documents set aside in Qonto. Rejected ones are never imported.',
    )
    vat_mode = fields.Selection(
        [
            ('tax', 'VAT on lines (from the e-invoice summary)'),
            ('total', 'Totals only, without VAT'),
        ],
        string='VAT', default='tax', required=True,
        help='VAT lines are rebuilt from the e-invoice PDF summary (or Qonto data). '
             'Invoices whose VAT cannot be read are imported at total and flagged "VAT to check".',
    )
    register_payments = fields.Boolean(
        string='Register payments of paid invoices', default=True,
        help='Paid invoices get their payment on the Qonto bank journal and are linked to the Qonto movement.',
    )
    purchase_journal_id = fields.Many2one(
        'account.journal', string='Vendor bills journal',
        domain="[('type', '=', 'purchase'), ('company_id', '=', company_id)]",
        help='Empty: a "Qonto history — purchases" journal is created.',
    )
    sale_journal_id = fields.Many2one(
        'account.journal', string='Customer invoices journal',
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]",
        help='Empty: a "Qonto history — sales" journal is created.',
    )
    payment_journal_id = fields.Many2one(
        'account.journal', string='Qonto bank journal',
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        help='Empty: the bank journal with the Qonto IBAN is used, or a "Qonto" bank journal is created.',
    )
    partners_done = fields.Boolean()
    has_more = fields.Boolean()

    # ── Entry point ───────────────────────────────────────────────────────────
    def _sbu_import_history(self, zf, members):
        messages = super()._sbu_import_history(zf, members)
        self.has_more = False
        if not (self.import_partners or self.import_invoices):
            return messages
        data = self._sbu_load_history_data(zf, members)
        if self.import_partners and not self.partners_done:
            messages.append(self._sbu_import_partners(data))
            self.partners_done = True
        if self.import_invoices:
            messages.append(self._sbu_import_invoices(zf, members, data))
        return messages

    def action_continue(self):
        self.ensure_one()
        return self.action_import()

    def _sbu_json(self, zf, members, name, default=None):
        if name not in members:
            return default if default is not None else []
        return json.loads(zf.read(members[name]).decode('utf-8'))

    def _sbu_files_index(self, zf, members, name, folder):
        """Rows of ``<folder>_files_index.csv`` by Qonto id, and the zip folder holding the files."""
        if name not in members:
            return {}, ''
        path = members[name]
        rows = csv.DictReader(io.StringIO(zf.read(path).decode('utf-8-sig')), delimiter=';')
        return {row['id']: row for row in rows}, posixpath.join(posixpath.dirname(path), folder)

    def _sbu_load_history_data(self, zf, members):
        org = self._sbu_json(zf, members, 'organization.json', {})
        accounts = (org.get('organization') or org).get('bank_accounts') or []
        return {
            'suppliers': self._sbu_json(zf, members, 'supplier_invoices.json'),
            'clients_invoices': self._sbu_json(zf, members, 'client_invoices.json'),
            'clients': self._sbu_json(zf, members, 'clients.json'),
            'beneficiaries': self._sbu_json(zf, members, 'sepa_beneficiaries.json')
            or self._sbu_json(zf, members, 'beneficiaries.json'),
            'own_ibans': {sanitize_account_number(a.get('iban') or '') for a in accounts} - {''},
            'qonto_iban': next((a.get('iban') for a in accounts if 'principale' in (a.get('name') or '').lower()),
                               accounts[0].get('iban') if accounts else False),
        }

    # ── Contacts ──────────────────────────────────────────────────────────────
    def _sbu_find_partner(self, vat=None, name=None):
        Partner = self.env['res.partner'].with_context(active_test=False)
        key = _vat_key(vat)
        if key and len(key) >= 8:
            for partner in Partner.search([('vat', 'ilike', key)]):
                if _vat_key(partner.vat) == key:
                    return partner.commercial_partner_id
        if name:
            nkey = _name_key(name)
            for partner in Partner.search([('name', '=ilike', name.strip()), ('parent_id', '=', False)]):
                if _name_key(partner.name) == nkey:
                    return partner
        return Partner

    def _sbu_country(self, code):
        return self.env['res.country'].search([('code', '=', (code or '').upper())], limit=1) if code else False

    def _sbu_get_or_create_partner(self, name, vat=None, address=None, rank='supplier', extra=None):
        partner = self._sbu_find_partner(vat, name)
        rank_field = f'{rank}_rank'
        if partner:
            if not partner[rank_field]:
                partner[rank_field] = 1
            return partner, False
        address = address or {}
        vals = {
            'name': (name or '').strip() or _('Unknown (Qonto)'),
            'is_company': True,
            rank_field: 1,
            'street': address.get('street_address') or address.get('address'),
            'zip': address.get('zip_code'),
            'city': address.get('city'),
            'country_id': (self._sbu_country(address.get('country_code')) or self.env['res.country']).id,
            'comment': _('Created from the Qonto export.'),
        }
        vals.update(extra or {})
        key = _vat_key(vat)
        if key:
            country = (address.get('country_code') or 'IT').upper()
            vat_value = f'IT{key}' if key.isdigit() and len(key) == 11 and country == 'IT' else key
            try:
                with self.env.cr.savepoint():
                    return self.env['res.partner'].create(dict(vals, vat=vat_value)), True
            except (ValidationError, UserError):
                vals['comment'] = _('Created from the Qonto export. VAT number: %s', vat)
        return self.env['res.partner'].create(vals), True

    def _sbu_add_bank(self, partner, iban, own_ibans):
        iban = sanitize_account_number(iban or '')
        if not iban or iban in own_ibans or len(iban) < 15:
            return False
        Bank = self.env['res.partner.bank'].with_context(active_test=False)
        if Bank.search_count([('sanitized_acc_number', '=', iban), ('partner_id', '=', partner.id)]):
            return False
        try:
            with self.env.cr.savepoint():
                Bank.create({'partner_id': partner.id, 'acc_number': iban})
            return True
        except (ValidationError, UserError):
            return False

    def _sbu_set_optional(self, partner, field, value):
        """Fill an optional field; values the localization rejects (e.g. Codice Fiscale) are skipped."""
        if value and field in partner._fields and not partner[field]:
            try:
                with self.env.cr.savepoint():
                    partner[field] = value
            except (ValidationError, UserError):
                _logger.info('Qonto import: %s %r rejected for %s', field, value, partner.display_name)

    def _sbu_import_partners(self, data):
        created = banks = 0
        own = data['own_ibans']
        seen_suppliers = {}
        for inv in data['suppliers']:
            if inv.get('status') in _SKIP_STATUSES:
                continue
            seller = inv.get('seller') or {}
            snapshot = inv.get('supplier_snapshot') or {}
            name = inv.get('supplier_name') or seller.get('name') or snapshot.get('name')
            vat = inv.get('vat_number') or seller.get('vat_number') or snapshot.get('vat_number')
            if not name:
                continue
            key = _vat_key(vat) or _name_key(name)
            if key in seen_suppliers:
                continue
            partner, new = self._sbu_get_or_create_partner(name, vat, seller.get('address'), 'supplier')
            seen_suppliers[key] = partner
            created += new
            banks += self._sbu_add_bank(partner, snapshot.get('iban'), own)
        for ben in data['beneficiaries']:
            if not ben.get('name'):
                continue
            iban = ben.get('iban') or (ben.get('bank_account') or {}).get('iban')
            partner, new = self._sbu_get_or_create_partner(ben['name'], None, None, 'supplier')
            created += new
            banks += self._sbu_add_bank(partner, iban, own)
            if ben.get('email'):
                self._sbu_set_optional(partner, 'email', ben['email'])
        clients = list(data['clients']) + [
            inv.get('client') for inv in data['clients_invoices'] if isinstance(inv.get('client'), dict)
        ]
        for client in clients:
            if not client or not client.get('name'):
                continue
            address = client.get('billing_address') or {
                'street_address': client.get('address'), 'zip_code': client.get('zip_code'),
                'city': client.get('city'), 'country_code': client.get('country_code'),
            }
            partner, new = self._sbu_get_or_create_partner(
                client['name'], client.get('vat_number') or client.get('tax_identification_number'), address, 'customer',
            )
            created += new
            self._sbu_set_optional(partner, 'email', client.get('email'))
            self._sbu_set_optional(partner, 'l10n_it_codice_fiscale', client.get('tax_identification_number'))
            self._sbu_set_optional(partner, 'l10n_it_pa_index', client.get('recipient_code'))
        return _('%(created)s contact(s) created, %(banks)s bank account(s) added.', created=created, banks=banks)

    # ── Journals and taxes ────────────────────────────────────────────────────
    def _sbu_history_journal(self, journal_type, code, name):
        Journal = self.env['account.journal']
        company = self.company_id
        journal = Journal.search([('company_id', '=', company.id), ('code', '=', code)], limit=1)
        if journal:
            return journal
        template = Journal.search([('company_id', '=', company.id), ('type', '=', journal_type)], limit=1)
        return Journal.create({
            'name': name,
            'code': code,
            'type': journal_type,
            'company_id': company.id,
            'default_account_id': template.default_account_id.id,
        })

    def _sbu_payment_journal(self, data):
        if self.payment_journal_id:
            return self.payment_journal_id
        Journal = self.env['account.journal']
        company = self.company_id
        iban = sanitize_account_number(data.get('qonto_iban') or '')
        if iban:
            journal = Journal.search([
                ('company_id', '=', company.id), ('type', '=', 'bank'),
                ('bank_account_id.sanitized_acc_number', '=', iban),
            ], limit=1)
            if journal:
                return journal
        journal = Journal.search([('company_id', '=', company.id), ('code', '=', 'QNTO')], limit=1)
        if journal:
            return journal
        vals = {'name': 'Qonto', 'code': 'QNTO', 'type': 'bank', 'company_id': company.id}
        if iban:
            vals['bank_acc_number'] = iban
        return Journal.create(vals)

    def _sbu_tax(self, use, rate, nature=None):
        """Plain company VAT for a rate: never reverse charge, split payment, deposit,
        pension fund or withholding taxes (l10n_it names them "22% G RC", "4% INPS"…).
        0% is matched on its exemption nature when the localization provides it."""
        cache = self.env.context.get('sbu_tax_cache')
        key = (use, rate, nature)
        if cache is not None and key in cache:
            return cache[key]
        Tax = self.env['account.tax']
        taxes = Tax.search([
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', use),
            ('amount_type', '=', 'percent'),
            ('amount', '=', rate),
            ('price_include', '=', False),
        ])
        for fname in ('l10n_it_pension_fund_type', 'l10n_it_withholding_type'):
            if fname in Tax._fields:
                taxes = taxes.filtered(lambda t, f=fname: not t[f])
        taxes = taxes.filtered(lambda t: not re.search(
            r'\bRC\b|\bSP\b|\bD\b|INPS|PENS|ENASARCO|RIT|INDETR|\bIND\b|SPLIT|REVERSE|DEPOSIT', (t.name or '').upper()))
        result = Tax
        if taxes and not rate and nature and 'l10n_it_exempt_reason' in Tax._fields:
            result = taxes.filtered(lambda t: t.l10n_it_exempt_reason == nature)[:1]
        if taxes and not result:
            plain = taxes.filtered(lambda t: re.fullmatch(r'\d+(?:[.,]\d+)?%\s*[GS]?', (t.name or '').strip()))
            result = min(plain or taxes, key=lambda t: (not (t.name or '').strip().endswith('G'), len(t.name or ''), t.sequence, t.id))
        if cache is not None:
            cache[key] = result
        return result

    # ── Invoices ──────────────────────────────────────────────────────────────
    def _sbu_vat_lines_supplier(self, inv, pdf_bytes):
        """[(label, net, rate, nature)], source, sdi_id, document_total"""
        total = _amount(inv.get('total_amount'))
        summary = None
        if pdf_bytes and self.vat_mode == 'tax':
            try:
                summary = parse_vat_summary(extract_pdf_text(pdf_bytes))
            except Exception as err:  # noqa: BLE001 — unreadable PDF: fall back to Qonto data
                _logger.info('Qonto invoice %s: PDF not readable (%s)', inv.get('id'), err)
        if summary:
            lines = [(None, line['net'], line['rate'], line['nature']) for line in summary['lines']]
            doc_total = summary['total'] if summary['total'] is not None else sum(
                line['net'] + line['tax'] for line in summary['lines'])
            return lines, 'pdf', summary['sdi_id'], doc_total
        taxes = inv.get('taxes') or []
        if taxes and self.vat_mode == 'tax':
            lines = []
            for tax in taxes:
                rate = float(tax.get('tax_rate') or 0)
                tax_amount = _amount(tax.get('tax_amount'))
                if rate:
                    lines.append((None, round(tax_amount * 100 / rate, 2), rate, None))
            if lines:
                return lines, 'qonto', False, total
        return [(_('Invoice total (VAT not detailed)'), total, None, None)], 'none', False, total

    def _sbu_line_vals(self, use, label, net, rate, nature):
        """Invoice line values; ``sbu_vat_missing`` is popped by the caller (rate without a usable tax)."""
        vals = {'name': label, 'quantity': 1.0, 'price_unit': net, 'tax_ids': [(6, 0, [])], 'sbu_vat_missing': False}
        if rate is not None and self.vat_mode == 'tax':
            tax = self._sbu_tax(use, rate, nature)
            if tax:
                vals['tax_ids'] = [(6, 0, tax.ids)]
            else:
                vals['sbu_vat_missing'] = True
            if not label:
                vals['name'] = (
                    _('Taxable %(rate)s%% %(nature)s', rate=f'{rate:g}', nature=nature or '').strip()
                )
        return vals

    def _sbu_balance_lines(self, move, target_total, label):
        """Add a line for the difference between the computed and the document total (rounding, stamps…)."""
        move.invalidate_recordset(['amount_total'])
        diff = round(target_total - move.amount_total, 2)
        if not float_is_zero(diff, precision_rounding=move.currency_id.rounding):
            move.write({'invoice_line_ids': [(0, 0, {
                'name': label, 'quantity': 1.0, 'price_unit': diff, 'tax_ids': [(6, 0, [])],
            })]})

    def _sbu_attach_pdf(self, zf, move, path):
        if not path or path not in zf.namelist():
            return
        attachment = self.env['ir.attachment'].create({
            'name': posixpath.basename(path),
            'datas': base64.b64encode(zf.read(path)),
            'res_model': 'account.move',
            'res_id': move.id,
        })
        move.with_context(tracking_disable=True).message_main_attachment_id = attachment

    def _sbu_link_movements(self, move, payment, matched):
        ids = [m.get('transaction_id') or m.get('subject_id') for m in matched or [] if isinstance(m, dict)]
        ids = [i for i in ids if i]
        if not ids:
            return self.env['sbu.qonto.transaction']
        movements = self.env['sbu.qonto.transaction'].search([
            ('company_id', '=', self.company_id.id), ('qonto_remote_id', 'in', ids),
        ])
        vals = {'state': 'matched', 'sbu_match_confidence': 'high',
                'sbu_match_hint': _('Linked from the Qonto invoice history.')}
        if move.move_type in ('in_invoice', 'in_refund'):
            vals['match_vendor_bill_id'] = move.id if move.move_type == 'in_invoice' else False
        else:
            vals['match_invoice_id'] = move.id if move.move_type == 'out_invoice' else False
        if payment:
            vals['match_payment_id'] = payment.id
        movements.write(vals)
        return movements

    def _sbu_register_history_payment(self, move, pay_date, journal, paid_amount=None):
        """Pay what was actually paid (withholding tax stays open), at most the residual."""
        amount = move.amount_residual
        if paid_amount:
            amount = min(amount, abs(paid_amount))
        if float_compare(amount, 0.0, precision_rounding=move.currency_id.rounding) <= 0:
            return self.env['account.payment']
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids, active_id=move.id,
        ).create({'payment_date': pay_date, 'journal_id': journal.id, 'amount': amount})
        return wizard._create_payments()[:1]

    def _sbu_payment_date(self, inv, matched, fallback):
        ids = [m.get('transaction_id') for m in matched or [] if isinstance(m, dict)]
        movement = self.env['sbu.qonto.transaction'].search([
            ('company_id', '=', self.company_id.id), ('qonto_remote_id', 'in', ids),
        ], order='transfer_date desc', limit=1) if ids else False
        if movement and movement.transfer_date:
            return movement.transfer_date
        for key in ('paid_at', 'payment_date'):
            if inv.get(key):
                return fields.Date.to_date(str(inv[key])[:10])
        return fallback

    def _sbu_import_invoices(self, zf, members, data):
        self = self.with_context(sbu_tax_cache={})  # noqa: PLW0642 — one tax lookup per rate per batch
        Move = self.env['account.move']
        company = self.company_id
        if not (data['suppliers'] or data['clients_invoices']):
            return _('Invoices: none in this archive.')
        purchase_journal = self.purchase_journal_id or self._sbu_history_journal(
            'purchase', 'QSTA', _('Qonto history — purchases'))
        sale_journal = self.sale_journal_id or self._sbu_history_journal(
            'sale', 'QSTV', _('Qonto history — sales'))
        cache = {}

        def payment_journal():
            if 'journal' not in cache:
                cache['journal'] = self._sbu_payment_journal(data)
            return cache['journal']

        if not self.register_payments:
            payment_journal = None
        supplier_files, supplier_dir = self._sbu_files_index(
            zf, members, 'supplier_invoices_files_index.csv', 'supplier_invoices')
        client_files, client_dir = self._sbu_files_index(
            zf, members, 'client_invoices_files_index.csv', 'client_invoices')

        todo = [('in', inv) for inv in data['suppliers']] + [('out', inv) for inv in data['clients_invoices']]
        done_ids = set(Move.with_context(active_test=False).search([
            ('company_id', '=', company.id), ('sbu_qonto_document_id', 'in', [inv.get('id') for _k, inv in todo]),
        ]).mapped('sbu_qonto_document_id'))
        counters = dict(created=0, already=0, skipped=0, duplicates=0, paid=0, to_check=0, failed=0)
        errors = []
        seen_keys = set()
        processed = 0
        for kind, inv in todo:
            if inv.get('id') in done_ids:
                counters['already'] += 1
                continue
            status = inv.get('status')
            if status in _SKIP_STATUSES or (status == 'archived' and not self.include_archived):
                counters['skipped'] += 1
                continue
            if processed >= _BATCH_SIZE:
                self.has_more = True
                break
            processed += 1
            try:
                with self.env.cr.savepoint():
                    if kind == 'in':
                        move, paid, check, duplicate = self._sbu_create_supplier_invoice(
                            zf, inv, supplier_files, supplier_dir, purchase_journal, payment_journal, seen_keys)
                    else:
                        move, paid, check, duplicate = self._sbu_create_client_invoice(
                            zf, inv, client_files, client_dir, sale_journal, payment_journal)
            except (UserError, ValidationError) as err:
                counters['failed'] += 1
                errors.append(f"{inv.get('invoice_number') or inv.get('number') or inv.get('id')}: {err}")
                continue
            if duplicate:
                counters['duplicates'] += 1
                processed -= 1  # nothing was created: does not use a batch slot
                continue
            counters['created'] += 1
            counters['paid'] += paid
            counters['to_check'] += check
        message = _(
            'Invoices: %(created)s imported (%(paid)s with payment), %(already)s already in Odoo, '
            '%(duplicates)s Qonto duplicates and %(skipped)s rejected/archived skipped, '
            '%(to_check)s with VAT to check, %(failed)s failed.', **counters,
        )
        if errors:
            message += '\n' + '\n'.join(errors[:20])
        if self.has_more:
            message += '\n' + _('More invoices to import: click "Continue".')
        return message

    def _sbu_create_supplier_invoice(self, zf, inv, files, folder, journal, payment_journal, seen_keys):
        seller = inv.get('seller') or {}
        name = inv.get('supplier_name') or seller.get('name') or (inv.get('supplier_snapshot') or {}).get('name')
        vat = inv.get('vat_number') or seller.get('vat_number')
        partner, _new = self._sbu_get_or_create_partner(name or inv.get('file_name'), vat, seller.get('address'), 'supplier')
        total = _amount(inv.get('total_amount'))
        number = inv.get('invoice_number') or False
        inv_date = fields.Date.to_date((inv.get('issue_date') or inv.get('created_at') or '')[:10] or None) \
            or fields.Date.context_today(self)
        dup_key = (partner.id, number, inv_date, round(total, 2))
        if number and dup_key in seen_keys:
            return self.env['account.move'], 0, 0, True
        seen_keys.add(dup_key)
        if number and self.env['account.move'].search_count([
            ('company_id', '=', self.company_id.id), ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('commercial_partner_id', '=', partner.id), ('ref', '=', number),
            ('invoice_date', '=', inv_date), ('state', '!=', 'cancel'),
        ]):
            return self.env['account.move'], 0, 0, True

        row = files.get(inv.get('id')) or {}
        pdf_path = posixpath.join(folder, row['attachment_id']) if row.get('attachment_id') else False
        pdf_bytes = zf.read(pdf_path) if pdf_path and pdf_path in zf.namelist() else None
        lines, vat_source, sdi_id, doc_total = self._sbu_vat_lines_supplier(inv, pdf_bytes)
        refund = bool(inv.get('is_credit_note')) or (doc_total or 0) < 0
        sign = -1 if (doc_total or 0) < 0 else 1
        target = abs(doc_total) if vat_source == 'pdf' else abs(total)
        due = inv.get('due_date') and fields.Date.to_date(inv['due_date'][:10])
        notes = [_('Imported from Qonto (history). Qonto status: %s.', inv.get('status'))]
        if sdi_id:
            notes.append(_('SdI id: %s.', sdi_id))
        if vat_source == 'pdf' and abs(abs(doc_total) - abs(total)) > 0.02:
            notes.append(_('Qonto total %(qonto).2f differs from the document total %(doc).2f.',
                           qonto=total, doc=abs(doc_total)))
        line_vals = [self._sbu_line_vals('purchase', label, sign * net, rate, nature)
                     for label, net, rate, nature in lines]
        if any([vals.pop('sbu_vat_missing') for vals in line_vals]):  # list: pop every line
            vat_source = 'none'
            notes.append(_('Some VAT rates have no matching tax in Odoo: amounts kept, VAT to check.'))
        natures = sorted({n for _l, _n, _r, n in lines if n})
        if natures:
            notes.append(_('VAT nature: %s.', ', '.join(natures)))
        move = self.env['account.move'].create({
            'move_type': 'in_refund' if refund else 'in_invoice',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
            'partner_id': partner.id,
            'ref': number,
            'invoice_date': inv_date,
            'date': inv_date,
            'invoice_date_due': due if due and due >= inv_date else False,
            'currency_id': self.company_id.currency_id.id,
            'narration': ' '.join(notes),
            'sbu_qonto_document_id': inv.get('id'),
            'sbu_qonto_vat_source': vat_source,
            'invoice_line_ids': [(0, 0, vals) for vals in line_vals],
        })
        self._sbu_balance_lines(move, target, _('Other amounts (stamp duty, rounding)'))
        self._sbu_attach_pdf(zf, move, pdf_path)
        move.action_post()
        paid = 0
        payment = self.env['account.payment']
        if payment_journal and inv.get('status') == _PAID:
            payment = self._sbu_register_history_payment(
                move, self._sbu_payment_date(inv, inv.get('matched_transactions'), inv_date), payment_journal(),
                _amount(inv.get('payable_amount')) or total)
            paid = 1 if payment else 0
        self._sbu_link_movements(move, payment, inv.get('matched_transactions'))
        return move, paid, int(vat_source == 'none'), False

    def _sbu_create_client_invoice(self, zf, inv, files, folder, journal, payment_journal):
        client = inv.get('client') or {}
        address = client.get('billing_address') or {}
        partner, _new = self._sbu_get_or_create_partner(
            client.get('name'), client.get('vat_number') or client.get('tax_identification_number'), address, 'customer')
        inv_date = fields.Date.to_date((inv.get('issue_date') or inv.get('created_at') or '')[:10] or None) \
            or fields.Date.context_today(self)
        lines = []
        for item in inv.get('items') or []:
            rate = item.get('vat_rate')
            rate = round(float(rate) * 100, 2) if rate not in (None, '') else None
            label = ' — '.join(filter(None, [item.get('title'), item.get('description')])) or _('Line')
            vals = self._sbu_line_vals('sale', label, _amount(item.get('unit_price')), rate, None)
            vals['quantity'] = float(item.get('quantity') or 1.0)
            lines.append(vals)
        if not lines:
            lines = [self._sbu_line_vals('sale', _('Invoice total'), _amount(inv.get('total_amount')), None, None)]
        missing = any([vals.pop('sbu_vat_missing') for vals in lines])  # list: pop every line
        vat_source = 'none' if missing or self.vat_mode != 'tax' or not inv.get('items') else 'qonto'
        due = inv.get('due_date') and fields.Date.to_date(inv['due_date'][:10])
        move = self.env['account.move'].create({
            'move_type': 'out_refund' if inv.get('invoice_type') == 'credit_note' else 'out_invoice',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
            'partner_id': partner.id,
            'ref': inv.get('number'),
            'payment_reference': inv.get('number'),
            'invoice_date': inv_date,
            'date': inv_date,
            'invoice_date_due': due if due and due >= inv_date else False,
            'currency_id': self.company_id.currency_id.id,
            'narration': _('Imported from Qonto (history). Qonto number %(number)s, e-invoicing status: %(sdi)s.',
                           number=inv.get('number'), sdi=inv.get('einvoicing_status') or '-'),
            'sbu_qonto_document_id': inv.get('id'),
            'sbu_qonto_vat_source': vat_source,
            'invoice_line_ids': [(0, 0, vals) for vals in lines],
        })
        self._sbu_balance_lines(move, _amount(inv.get('total_amount')), _('Other amounts (stamp duty, rounding)'))
        row = files.get(inv.get('id')) or {}
        if row.get('attachment_id'):
            self._sbu_attach_pdf(zf, move, posixpath.join(folder, row['attachment_id']))
        move.action_post()
        paid = 0
        payment = self.env['account.payment']
        if payment_journal and inv.get('status') == _PAID:
            pay_date = self._sbu_payment_date(inv, inv.get('matched_transactions'), inv_date)
            payment = self._sbu_register_history_payment(
                move, pay_date, payment_journal(), _amount(inv.get('amount_paid')) or _amount(inv.get('total_amount')))
            paid = 1 if payment else 0
        self._sbu_link_movements(move, payment, inv.get('matched_transactions'))
        return move, paid, int(vat_source == 'none'), False
