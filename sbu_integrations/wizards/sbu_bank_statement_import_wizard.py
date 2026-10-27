# -*- coding: utf-8 -*-
"""Import a bank statement file (CSV or CAMT.053) of any bank into a bank journal, then reconcile."""
import base64
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from odoo.addons.base.models.res_bank import sanitize_account_number
from odoo.addons.sbu_integrations.models.sbu_bank_statement_sync import reconcile_statement_line_with_payment
from odoo.addons.sbu_integrations.services.bank_statement_parser import StatementParseError, parse_statement

PAYMENT_DATE_TOLERANCE = 10  # days between the payment date and the bank date
_MIN_REF_LEN = 4


def _norm(text):
    return re.sub(r'[^0-9A-Z]', '', (text or '').upper())


class SbuBankStatementImportWizard(models.TransientModel):
    _name = 'sbu.bank.statement.import.wizard'
    _description = 'Import a bank statement file (CSV / CAMT.053)'

    journal_id = fields.Many2one(
        'account.journal', string='Bank journal', required=True,
        domain="[('type', '=', 'bank'), ('company_id', 'in', allowed_company_ids)]",
    )
    data_file = fields.Binary(string='Bank file', required=True)
    filename = fields.Char()
    auto_reconcile = fields.Boolean(
        string='Reconcile automatically', default=True,
        help='Match each line with an Odoo payment of the same amount (same customer / supplier, close date) '
             'or with the open invoice / bill whose number is in the description.',
    )
    result_message = fields.Text(readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'account.journal' and self.env.context.get('active_id'):
            res['journal_id'] = self.env.context['active_id']
        return res

    # ── Partner ───────────────────────────────────────────────────────────────
    def _sbu_partner(self, line):
        Bank = self.env['res.partner.bank']
        if line.get('partner_iban'):
            bank = Bank.search([('sanitized_acc_number', '=', sanitize_account_number(line['partner_iban']))], limit=1)
            if bank:
                return bank.partner_id.commercial_partner_id
        if line.get('partner_name'):
            partner = self.env['res.partner'].search([('name', '=ilike', line['partner_name'].strip())], limit=1)
            if partner:
                return partner.commercial_partner_id
        return self.env['res.partner']

    # ── Reconciliation ────────────────────────────────────────────────────────
    def _sbu_match_payment(self, st_line):
        amount = abs(st_line.amount)
        rounding = st_line.currency_id.rounding
        delta = fields.Date.to_date(st_line.date)
        domain = [
            ('company_id', '=', st_line.company_id.id),
            # Community marks a payment "paid" once it pays its invoice: not matched to the bank yet anyway.
            ('state', 'in', ('in_process', 'paid')),
            ('is_matched', '=', False),
            ('payment_type', '=', 'inbound' if st_line.amount > 0 else 'outbound'),
            ('date', '>=', fields.Date.subtract(delta, days=PAYMENT_DATE_TOLERANCE)),
            ('date', '<=', fields.Date.add(delta, days=PAYMENT_DATE_TOLERANCE)),
        ]
        if st_line.partner_id:
            domain.append(('partner_id.commercial_partner_id', '=', st_line.partner_id.id))
        payments = self.env['account.payment'].search(domain).filtered(
            lambda p: float_is_zero(p.amount - amount, precision_rounding=rounding))
        return payments if len(payments) == 1 else self.env['account.payment']

    def _sbu_match_invoice(self, st_line):
        """Open invoice / bill whose number or reference is in the bank description, same amount."""
        text = _norm(' '.join(filter(None, [st_line.payment_ref, st_line.partner_name])))
        if not text:
            return self.env['account.move']
        domain = [
            ('company_id', '=', st_line.company_id.id),
            ('move_type', '=', 'out_invoice' if st_line.amount > 0 else 'in_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ]
        if st_line.partner_id:
            domain.append(('commercial_partner_id', '=', st_line.partner_id.id))
        rounding = st_line.currency_id.rounding
        candidates = self.env['account.move'].search(domain).filtered(lambda m: any(
            len(key) >= _MIN_REF_LEN and key in text for key in (_norm(m.name), _norm(m.ref), _norm(m.payment_reference))
        ) and float_compare(m.amount_residual, abs(st_line.amount), precision_rounding=rounding) == 0)
        return candidates if len(candidates) == 1 else self.env['account.move']

    def _sbu_reconcile(self, st_line):
        """Returns 'payment', 'invoice' or False."""
        payment = self._sbu_match_payment(st_line)
        if payment and self._sbu_reconcile_with(st_line, payment):
            return 'payment'
        move = self._sbu_match_invoice(st_line)
        if not move:
            return False
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids, active_id=move.id,
        ).create({'payment_date': st_line.date, 'journal_id': st_line.journal_id.id, 'amount': abs(st_line.amount)})
        payment = wizard._create_payments()[:1]
        return 'invoice' if self._sbu_reconcile_with(st_line, payment) else False

    def _sbu_reconcile_with(self, st_line, payment):
        if not st_line.partner_id and payment.partner_id:
            st_line.partner_id = payment.partner_id.commercial_partner_id
        return reconcile_statement_line_with_payment(st_line, payment)

    # ── Import ────────────────────────────────────────────────────────────────
    def action_import(self):
        self.ensure_one()
        journal = self.journal_id
        try:
            statement = parse_statement(base64.b64decode(self.data_file), self.filename or '')
        except StatementParseError as err:
            raise UserError(_('This bank file cannot be read: %s', err)) from err
        if not statement['lines']:
            raise UserError(_('No bank movements found in this file.'))
        journal_iban = sanitize_account_number(journal.bank_account_id.acc_number or '')
        if statement['iban'] and journal_iban and statement['iban'] != journal_iban:
            raise UserError(_('This statement is for %(file)s but the journal %(journal)s is %(iban)s: choose the '
                              'right journal.', file=statement['iban'], journal=journal.name, iban=journal_iban))
        journal_currency = journal.currency_id or journal.company_id.currency_id
        if statement['currency'] and statement['currency'] != journal_currency.name:
            raise UserError(_('The file is in %(file)s, the journal in %(journal)s.',
                              file=statement['currency'], journal=journal_currency.name))

        StatementLine = self.env['account.bank.statement.line']
        known = set(StatementLine.search([
            ('journal_id', '=', journal.id), ('sbu_import_ref', 'in', [l['unique_id'] for l in statement['lines']]),
        ]).mapped('sbu_import_ref'))
        new = [l for l in statement['lines'] if l['unique_id'] not in known]
        lines = StatementLine.create([{
            'journal_id': journal.id,
            'date': l['date'],
            'amount': l['amount'],
            'payment_ref': ' — '.join(filter(None, [l['label'], l['ref']])) or '/',
            'partner_name': l['partner_name'],
            'account_number': l['partner_iban'],
            'partner_id': self._sbu_partner(l).id or False,
            'sbu_import_ref': l['unique_id'],
        } for l in new])

        matched = {'payment': 0, 'invoice': 0}
        if self.auto_reconcile:
            for st_line in lines:
                with self.env.cr.savepoint():
                    result = self._sbu_reconcile(st_line)
                if result:
                    matched[result] += 1
        first, last = min(l['date'] for l in statement['lines']), max(l['date'] for l in statement['lines'])
        self.result_message = _(
            '%(new)s bank line(s) imported into %(journal)s (%(start)s → %(end)s), %(dup)s already present.\n'
            'Reconciled: %(pay)s with an existing payment, %(inv)s by paying the invoice / bill in the '
            'description. %(left)s line(s) to reconcile.',
            new=len(lines), journal=journal.name, start=first, end=last, dup=len(statement['lines']) - len(new),
            pay=matched['payment'], inv=matched['invoice'],
            left=len(lines) - matched['payment'] - matched['invoice'],
        )
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bank lines — %s', self.journal_id.name),
            'res_model': 'account.bank.statement.line',
            'view_mode': 'list,form',
            'domain': [('journal_id', '=', self.journal_id.id)],
        }
