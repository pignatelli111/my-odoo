# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError

_MAX_LISTED = 10


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _sbu_job_documents(self):
        """Documents linked to the job, as [(record, kind label)].

        Every SBU module adds its own (SAL, purchase requests, purchase orders…). The modules do not all
        depend on each other, so each implementation calls the next one through getattr(super()…).
        """
        self.ensure_one()
        docs = getattr(super(), '_sbu_job_documents', lambda: [])()
        if self.sbu_estimate_id:
            docs.append((self.sbu_estimate_id, _('Estimate')))
        return docs

    def _sbu_fiscal_moves(self):
        """Invoices, vendor bills and credit notes linked to the job."""
        self.ensure_one()
        moves = self.env['account.move']
        for record, _kind in self._sbu_job_documents():
            if record._name == 'account.move':
                moves |= record
        return moves

    def _sbu_protected_moves(self):
        """Fiscal documents that must never disappear: posted, or cancelled after being posted."""
        return self._sbu_fiscal_moves().filtered(
            lambda m: m.state == 'posted' or (m.state == 'cancel' and m.posted_before)
        )

    def _sbu_check_no_protected_moves(self):
        for project in self:
            protected = project._sbu_protected_moves()
            if protected:
                names = ', '.join(protected[:_MAX_LISTED].mapped('display_name'))
                if len(protected) > _MAX_LISTED:
                    names += _(' and %s more', len(protected) - _MAX_LISTED)
                raise UserError(_(
                    'Job %(job)s cannot be deleted: it has posted invoices or vendor bills (%(docs)s).\n'
                    'Posted fiscal documents are cancelled with a credit note, never deleted. '
                    'Use "Cancel job" instead: it cancels the drafts, prepares the credit notes and '
                    'archives the job.',
                    job=project.display_name, docs=names,
                ))

    def unlink(self):
        self._sbu_check_no_protected_moves()
        return super().unlink()

    def action_sbu_open_cancel_job_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cancel job'),
            'res_model': 'sbu.project.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_project_id': self.id},
        }
