# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.sbu_estimate.models.sbu_account_line_utils import sbu_is_product_line

from .sbu_budget_helpers import (
    sbu_cost_family_for_pr_line,
    sbu_cost_family_label,
    sbu_refresh_projects_budget,
)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sbu_purchase_request_id = fields.Many2one(
        'sbu.purchase.request',
        string='SBU purchase request',
        index=True,
        ondelete='set null',
        copy=False,
        help='Purchase request this RFQ/PO was generated from (SBU traceability).',
    )
    sbu_budget_reference = fields.Monetary(
        string='Estimate cost reference',
        compute='_compute_sbu_budget_alert',
        currency_field='currency_id',
        help='BOM cost on linked estimate, else total estimated cost.',
    )
    sbu_budget_variance_pct = fields.Float(
        string='Over budget %',
        compute='_compute_sbu_budget_alert',
        digits=(16, 2),
        help='(PO untaxed − reference) / reference × 100 when reference > 0.',
    )
    sbu_budget_over_limit = fields.Boolean(
        string='Over budget (SBU)',
        compute='_compute_sbu_budget_alert',
        help='True when PO untaxed exceeds preventivo reference by more than 5%%.',
    )

    @api.depends(
        'amount_untaxed',
        'currency_id',
        'project_id',
        'project_id.sbu_estimate_id',
        'project_id.sbu_estimate_id.total_cost',
        'project_id.sbu_estimate_id.line_ids.cost_bom_total',
    )
    def _compute_sbu_budget_alert(self):
        for po in self:
            est = po.project_id.sbu_estimate_id if po.project_id else False
            if not est:
                po.sbu_budget_reference = 0.0
                po.sbu_budget_variance_pct = 0.0
                po.sbu_budget_over_limit = False
                continue
            bom_cost = sum(est.line_ids.mapped('cost_bom_total'))
            reference = bom_cost or est.total_cost or 0.0
            po.sbu_budget_reference = reference
            untaxed = po.amount_untaxed or 0.0
            if reference > 0:
                po.sbu_budget_variance_pct = (untaxed - reference) / reference * 100.0
                po.sbu_budget_over_limit = untaxed > reference * 1.05
            else:
                po.sbu_budget_variance_pct = 0.0
                po.sbu_budget_over_limit = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sbu_purchase_request_id') and not vals.get('project_id'):
                pr = self.env['sbu.purchase.request'].browse(vals['sbu_purchase_request_id'])
                if 'project_id' in self._fields and pr.project_id:
                    vals['project_id'] = pr.project_id.id
        pos = super().create(vals_list)
        for po in pos:
            pr = po.sbu_purchase_request_id
            if pr:
                pr.purchase_order_ids = [(4, po.id)]
        return pos

    def _sbu_user_can_override_budget_po(self):
        self.ensure_one()
        user = self.env.user
        if user.has_group('base.group_system'):
            return True
        if not user.has_group('sbu_purchase_flow.group_sbu_budget_unlock'):
            return False
        project = self.project_id
        return bool(project and project.sbu_budget_po_unlock)

    def _sbu_cost_family_for_po_line(self, pol):
        pr_line = pol.sbu_pr_line_id
        if pr_line:
            return sbu_cost_family_for_pr_line(pr_line)
        return 'extra'

    def _sbu_check_budget_before_confirm(self):
        """Block PO confirm when any affected cost family is over budget (unless admin unlock)."""
        Budget = self.env['sbu.project.budget.family']
        for po in self:
            if not po.project_id or not po.project_id.sbu_estimate_id:
                continue
            if po._sbu_user_can_override_budget_po():
                continue
            Budget.refresh_project(po.project_id)
            over_labels = []
            for pol in po.order_line.filtered(sbu_is_product_line):
                fam = po._sbu_cost_family_for_po_line(pol)
                row = Budget.search([
                    ('project_id', '=', po.project_id.id),
                    ('cost_family', '=', fam),
                ], limit=1)
                if row and row.is_over_budget:
                    over_labels.append(sbu_cost_family_label(self.env, fam))
            if over_labels:
                raise UserError(_(
                    'Cannot confirm this purchase order: budget exceeded for %(families)s '
                    '(engaged above %(pct)s%% of the ANACO estimate for that family). '
                    'Ask a user with «SBU — Sblocco budget acquisti» to review the job budget '
                    'dashboard or enable «Unlock PO over budget» on the project.'
                ) % {
                    'families': ', '.join(sorted(set(over_labels))),
                    'pct': '105',
                })

    def button_confirm(self):
        self._sbu_check_budget_before_confirm()
        res = super().button_confirm()
        projects = self.mapped('project_id').filtered('sbu_estimate_id')
        if projects:
            sbu_refresh_projects_budget(projects, self.env)
        return res

    def action_sbu_refresh_dimensions_from_pr(self):
        """Copy L/H/P + mq from linked RDA lines onto RFQ/PO lines."""
        updated = 0
        for po in self:
            if not po.sbu_purchase_request_id:
                continue
            for pol in po.order_line.filtered('sbu_pr_line_id'):
                pol.write(pol.sbu_pr_line_id._sbu_po_line_dimension_vals())
                updated += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Dimensions updated'),
                'message': _('Updated %(n)s purchase line(s) from the RDA.') % {'n': updated},
                'type': 'success',
                'sticky': False,
            },
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    sbu_pr_line_id = fields.Many2one(
        'sbu.purchase.request.line',
        string='PR line',
        index=True,
        ondelete='set null',
        copy=False,
        help='Source purchase request line when the RFQ was built from an SBU request.',
    )
    sbu_offer_id = fields.Many2one(
        'sbu.purchase.request.offer',
        string='Chosen supplier offer',
        index=True,
        ondelete='set null',
        copy=False,
        help='Supplier quote row selected for this purchase line (traceability).',
    )
    sbu_width_mm = fields.Float(string='L (mm)', digits=(16, 0), copy=False)
    sbu_height_mm = fields.Float(string='H (mm)', digits=(16, 0), copy=False)
    sbu_depth_mm = fields.Float(string='P (mm)', digits=(16, 0), copy=False)
    sbu_sqm_per_piece = fields.Float(string='Sqm/pc', digits=(16, 4), copy=False)
    sbu_sqm_total = fields.Float(string='Sqm total', digits=(16, 4), copy=False)
    sbu_dimension_summary = fields.Char(
        string='Dimensions',
        copy=False,
        help='L×H×P e mq copiati dalla RDA (Cosimo: visibili su RFQ/PO).',
    )
    sbu_utilization = fields.Char(
        string='Utilization',
        copy=False,
        help='UTILIZZO dalla riga RDA (montante, profili, …).',
    )
    sbu_manual_input_pending = fields.Boolean(
        string='Needs manual entry',
        related='sbu_pr_line_id.manual_input_pending',
        store=True,
        readonly=True,
    )
    sbu_manual_input_state = fields.Selection(
        string='Manual input status',
        related='sbu_pr_line_id.manual_input_state',
        store=True,
        readonly=True,
    )
