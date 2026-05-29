# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class SbuEstimateForceDelete(models.Model):
    _inherit = 'sbu.estimate'

    def _sbu_check_uat_force_delete_access(self):
        if self.env.user.has_group('sbu_estimate.group_sbu_estimate_uat_cleanup'):
            return
        if self.env.user.has_group('base.group_system'):
            return
        raise UserError(
            _(
                'Only users in «SBU UAT cleanup» (or Administrators) can delete test '
                'preventivi with commessa / SAL. Ask an admin to assign the group on your user.'
            )
        )

    def action_open_force_delete_wizard(self):
        self._sbu_check_uat_force_delete_access()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Elimina test (completo)'),
            'res_model': 'sbu.estimate.force.delete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_estimate_ids': [fields.Command.set(self.ids)],
            },
        }

    def _sbu_force_delete_with_cleanup(self):
        """Remove linked UAT documents, then delete preventivo(s). Returns count removed."""
        self._sbu_check_uat_force_delete_access()
        count = len(self)
        for estimate in self:
            project = estimate.project_id
            if project:
                estimate._sbu_force_cleanup_project(project)
            estimate.with_context(sbu_force_estimate_unlink=True).write({
                'state': 'draft',
                'project_id': False,
            })
            estimate.with_context(sbu_force_estimate_unlink=True).unlink()
        return count

    def _sbu_force_cleanup_project(self, project):
        """Cancel/remove SBU documents on a test commessa before project delete."""
        self.ensure_one()
        env = self.env(su=True)

        if 'sbu.sal.sheet' in env:
            sheets = env['sbu.sal.sheet'].search([('project_id', '=', project.id)])
            for sheet in sheets:
                self._sbu_force_cleanup_sal_sheet(sheet)

        if 'purchase.order' in env:
            pos = env['purchase.order'].search([('project_id', '=', project.id)])
            for po in pos:
                self._sbu_force_cancel_purchase_order(po)

        if 'sbu.purchase.request' in env:
            prs = env['sbu.purchase.request'].search([('project_id', '=', project.id)])
            for pr in prs.filtered(lambda r: r.state != 'cancelled'):
                if hasattr(pr, 'action_cancel'):
                    pr.action_cancel()

        try:
            project.unlink()
        except UserError as err:
            raise UserError(
                _(
                    'Could not delete project %(project)s: %(msg)s. '
                    'Cancel remaining documents manually, then retry.'
                )
                % {'project': project.display_name, 'msg': err.args[0]}
            ) from err

    def _sbu_force_cleanup_sal_sheet(self, sheet):
        env = self.env(su=True)
        if 'sbu.payment.certificate' in env:
            certs = sheet.certificate_ids
            if certs:
                certs.with_context(sbu_force_certificate_unlink=True).unlink()
        move = sheet.invoice_id
        if move:
            self._sbu_force_cancel_account_move(move)
        sheet.write({'state': 'draft', 'invoice_id': False})
        sheet.unlink()

    def _sbu_force_cancel_account_move(self, move):
        env = self.env(su=True)
        move = move.sudo()
        if move.state == 'draft':
            move.unlink()
            return
        if move.state == 'posted':
            if hasattr(move, 'button_cancel'):
                move.button_cancel()
            return
        if move.state == 'cancel':
            if hasattr(move, 'button_draft'):
                try:
                    move.button_draft()
                    move.unlink()
                except UserError:
                    pass

    def _sbu_force_cancel_purchase_order(self, po):
        po = po.sudo()
        if po.state in ('cancel',):
            return
        if po.state in ('draft', 'sent', 'to approve'):
            if hasattr(po, 'button_cancel'):
                po.button_cancel()
            return
        if po.state in ('purchase', 'done'):
            for picking in po.picking_ids:
                if picking.state not in ('cancel', 'done'):
                    picking.action_cancel()
            if hasattr(po, 'button_cancel'):
                try:
                    po.button_cancel()
                except UserError:
                    pass
