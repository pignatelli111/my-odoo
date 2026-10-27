# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CANCEL_ACTIONS = [
    ('cancel', 'Will be cancelled'),
    ('delete', 'Will be deleted (draft)'),
    ('credit_note', 'Customer credit note needed'),
    ('supplier_credit_note', 'Ask the supplier for a credit note'),
    ('keep', 'Kept as it is'),
]


def _sbu_cancel_action(record):
    """(action, note) for one document of a job being cancelled."""
    model, state = record._name, record['state'] if 'state' in record._fields else False
    if model == 'account.move':
        if state == 'draft':
            return 'cancel', ''
        if state != 'posted':
            return 'keep', ''
        if record.move_type == 'out_invoice':
            if record.payment_state == 'reversed' or record.reversal_move_ids:
                return 'keep', record.env._('Credit note already exists.')
            return 'credit_note', record.env._('Posted invoice: issue a credit note (it is never deleted).')
        if record.move_type == 'in_invoice':
            return 'supplier_credit_note', record.env._('Posted vendor bill: only the supplier can issue the credit note.')
        return 'keep', ''
    if model == 'purchase.order':
        if state in ('draft', 'sent', 'to approve'):
            return 'cancel', ''
        if state == 'purchase':
            if record.invoice_ids or any(p.state == 'done' for p in record.picking_ids):
                return 'keep', record.env._('Already received or billed: handle returns and bills manually.')
            return 'cancel', ''
        return 'keep', ''
    if model == 'stock.picking':
        return ('keep', '') if state in ('done', 'cancel') else ('cancel', '')
    if model == 'sbu.payment.certificate':
        return ('delete', '') if state == 'draft' else ('keep', '')
    if model in ('sbu.sal.sheet', 'sbu.sal.passive.sheet'):
        return ('cancel', '') if state in ('draft', 'confirmed') else ('keep', '')
    if model == 'sbu.purchase.request':
        return ('keep', '') if state in ('done', 'cancelled') else ('cancel', '')
    if model == 'sbu.estimate':
        return 'keep', record.env._('Marked as Cancelled.')
    return 'keep', ''


class SbuProjectCancelWizardLine(models.TransientModel):
    _name = 'sbu.project.cancel.wizard.line'
    _description = 'Cancel job: linked document'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('sbu.project.cancel.wizard', required=True, ondelete='cascade')
    sequence = fields.Integer()
    kind = fields.Char(string='Type', readonly=True)
    res_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    name = fields.Char(string='Document', readonly=True)
    state_label = fields.Char(string='Status', readonly=True)
    action = fields.Selection(CANCEL_ACTIONS, string='What happens', readonly=True)
    note = fields.Char(string='Note', readonly=True)

    def _record(self):
        self.ensure_one()
        return self.env[self.res_model].browse(self.res_id).exists()

    def action_open_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }


class SbuProjectCancelWizard(models.TransientModel):
    _name = 'sbu.project.cancel.wizard'
    _description = 'Cancel a job without deleting fiscal documents'

    project_id = fields.Many2one('project.project', string='Job', required=True, readonly=True)
    line_ids = fields.One2many('sbu.project.cancel.wizard.line', 'wizard_id', string='Linked documents')
    reason = fields.Text(string='Reason')
    confirm = fields.Boolean(string='I confirm: cancel the drafts listed above and archive the job')
    credit_note_count = fields.Integer(compute='_compute_counts')
    supplier_credit_note_count = fields.Integer(compute='_compute_counts')

    @api.depends('line_ids.action')
    def _compute_counts(self):
        for wizard in self:
            wizard.credit_note_count = len(wizard.line_ids.filtered(lambda l: l.action == 'credit_note'))
            wizard.supplier_credit_note_count = len(
                wizard.line_ids.filtered(lambda l: l.action == 'supplier_credit_note'))

    @api.model
    def _sbu_line_commands(self, project):
        order = {key: index for index, (key, _label) in enumerate(CANCEL_ACTIONS)}
        seen, rows = set(), []
        for record, kind in project._sbu_job_documents():
            if (record._name, record.id) in seen:
                continue
            seen.add((record._name, record.id))
            action, note = _sbu_cancel_action(record)
            state = record['state'] if 'state' in record._fields else ''
            state_label = dict(record._fields['state']._description_selection(self.env)).get(state, state) \
                if 'state' in record._fields else ''
            rows.append({
                'sequence': order[action],
                'kind': kind,
                'res_model': record._name,
                'res_id': record.id,
                'name': record.display_name,
                'state_label': state_label,
                'action': action,
                'note': note,
            })
        return [Command.create(row) for row in sorted(rows, key=lambda r: (r['sequence'], r['kind'], r['name']))]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        project = self.env['project.project'].browse(res.get('project_id') or self.env.context.get('active_id'))
        if project and 'line_ids' in fields_list:
            res['project_id'] = project.id
            res['line_ids'] = self._sbu_line_commands(project)
        return res

    def action_create_credit_notes(self):
        """Draft credit notes for the posted customer invoices, to be checked and posted by accounting."""
        self.ensure_one()
        invoices = self.env['account.move'].browse(
            self.line_ids.filtered(lambda l: l.action == 'credit_note').mapped('res_id')
        ).exists()
        if not invoices:
            raise UserError(_('There are no posted customer invoices left to credit.'))
        today = fields.Date.context_today(self)
        credit_notes = invoices._reverse_moves([
            {
                'ref': _('Cancellation of %(invoice)s — job %(job)s', invoice=inv.name, job=self.project_id.display_name),
                'date': today,
                'invoice_date': today,
            }
            for inv in invoices
        ])
        self.project_id.message_post(body=_(
            'Draft credit notes prepared for the job cancellation: %s. Check and post them in Accounting.',
            ', '.join(credit_notes.mapped('display_name')),
        ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Credit notes to check'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', credit_notes.ids)],
            'target': 'current',
        }

    def _sbu_apply_line(self, line):
        record = line._record()
        if not record:
            return
        if line.action == 'delete':
            record.unlink()
        elif record._name == 'account.move':
            record.button_cancel()
        elif record._name == 'purchase.order':
            record.button_cancel()
        else:
            record.action_cancel()

    def action_cancel_job(self):
        self.ensure_one()
        if not self.confirm:
            raise UserError(_('Tick the confirmation box to cancel the job.'))
        if not (self.reason or '').strip():
            raise UserError(_('Write the reason of the cancellation (kept in the job history).'))
        project = self.project_id
        done, failed = [], []
        for line in self.line_ids.filtered(lambda l: l.action in ('cancel', 'delete')):
            try:
                with self.env.cr.savepoint():
                    self._sbu_apply_line(line)
                done.append(f'{line.kind} {line.name}')
            except UserError as err:
                failed.append(f'{line.kind} {line.name}: {err.args[0] if err.args else err}')
        estimate = project.sbu_estimate_id
        if estimate and estimate.state != 'cancelled':
            estimate.state = 'cancelled'
        open_fiscal = self.line_ids.filtered(lambda l: l.action in ('credit_note', 'supplier_credit_note'))
        body = Markup('<p><b>%s</b></p><p>%s</p>') % (_('Job cancelled'), self.reason)
        if done:
            body += Markup('<p>%s</p><ul>%s</ul>') % (
                _('Cancelled / removed:'), Markup('').join(Markup('<li>%s</li>') % d for d in done))
        if open_fiscal:
            body += Markup('<p>%s</p><ul>%s</ul>') % (
                _('Fiscal documents kept (credit note to handle):'),
                Markup('').join(Markup('<li>%s — %s</li>') % (l.name, l.note) for l in open_fiscal))
        if failed:
            body += Markup('<p class="text-danger">%s</p><ul>%s</ul>') % (
                _('Not cancelled (do it manually):'), Markup('').join(Markup('<li>%s</li>') % f for f in failed))
        project.message_post(body=body)
        if estimate:
            estimate.message_post(body=body)
        project.with_context(sbu_job_cancelled=True).write({'sbu_state': 'archived', 'active': False})
        _logger.info('Job %s cancelled by %s', project.display_name, self.env.user.login)
        message = _('Job %(job)s archived: %(n)s document(s) cancelled.', job=project.display_name, n=len(done))
        if failed:
            message += ' ' + _('%s could not be cancelled: see the job history.', len(failed))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Job cancelled'),
                'message': message,
                'type': 'warning' if failed or open_fiscal else 'success',
                'sticky': bool(failed),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
