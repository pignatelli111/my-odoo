# -*- coding: utf-8 -*-
from odoo import api, fields, models


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
        string='Preventivo cost reference',
        compute='_compute_sbu_budget_alert',
        currency_field='currency_id',
        help='Distinta BOM cost on linked preventivo, else total estimated cost.',
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
        return super().create(vals_list)


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
