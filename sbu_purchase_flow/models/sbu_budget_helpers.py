# -*- coding: utf-8 -*-
"""Helpers for SBU budget-by-cost-family (Cosimo point 11)."""

from collections import defaultdict

from odoo.addons.sbu_estimate.models.sbu_anaco_bom import ANACO_LINE_FIELD_TO_PRODUCT_CODE
from odoo.addons.sbu_estimate.models.sbu_cost_family import (
    COST_FAMILY_WORKFLOW_ROUTE,
    SBU_COST_FAMILY_SELECTION,
    infer_cost_family_from_price_cost_vals,
)

SBU_BUDGET_WARN_PCT = 90.0
SBU_BUDGET_OVER_PCT = 105.0

WORKFLOW_ROUTE_TO_COST_FAMILY = {
    route: family for family, route in COST_FAMILY_WORKFLOW_ROUTE.items()
}

# Product on distinta row (SBU-SMONT, SBU-VETRO, …) beats facade cost_family on estimate line.
SBU_PRODUCT_CODE_TO_COST_FAMILY = {}
for _field, _code in ANACO_LINE_FIELD_TO_PRODUCT_CODE.items():
    _fam = infer_cost_family_from_price_cost_vals({_field: 1.0})
    if _fam:
        SBU_PRODUCT_CODE_TO_COST_FAMILY[_code.strip().upper()] = _fam


def sbu_cost_family_from_product(product):
    if not product:
        return False
    code = (product.default_code or '').strip().upper()
    return SBU_PRODUCT_CODE_TO_COST_FAMILY.get(code)

OPEN_PR_REQUEST_STATES = ('draft', 'submitted', 'approved')
PO_DRAFT_STATES = ('draft', 'sent', 'to approve')
PO_CONFIRMED_STATES = ('purchase', 'done')


def sbu_cost_family_label(env, family_code):
    if not family_code:
        return '—'
    selection = dict(SBU_COST_FAMILY_SELECTION)
    return selection.get(family_code, family_code)


def sbu_traffic_light_from_pct(pct_engaged, planned):
    if not planned or planned <= 0:
        return 'ok'
    if pct_engaged <= SBU_BUDGET_WARN_PCT:
        return 'ok'
    if pct_engaged <= SBU_BUDGET_OVER_PCT:
        return 'warning'
    return 'over'


def sbu_cost_family_for_pr_line(pr_line):
    """Resolve ANACO cost family from product, BOM / estimate line / workflow route."""
    if not pr_line:
        return 'extra'
    bom = pr_line.source_bom_line_id
    product = pr_line.product_id or (bom.product_id if bom else False)
    fam = sbu_cost_family_from_product(product)
    if fam:
        return fam
    if bom and bom.estimate_line_id and bom.estimate_line_id.cost_family:
        return bom.estimate_line_id.cost_family
    route = pr_line.workflow_route or pr_line.request_id.workflow_route
    if route and route in WORKFLOW_ROUTE_TO_COST_FAMILY:
        return WORKFLOW_ROUTE_TO_COST_FAMILY[route]
    req_type = pr_line.request_id.request_type
    if req_type == 'vt':
        return 'glass'
    if req_type == 'st':
        return 'bracket_st'
    if req_type == 'fe':
        return 'aluminum_sheet'
    return 'extra'


def sbu_pr_line_engaged_amount(pr_line, qty=None):
    """Best-effort line value for open PR (offers → standard price)."""
    qty = qty if qty is not None else (pr_line.qty_remaining or pr_line.product_qty or 0.0)
    offers = pr_line.offer_ids.filtered(lambda o: o.unit_price > 0)
    if offers:
        best = min(offers.mapped('unit_price'))
        return best * qty
    product = pr_line.product_id
    if product:
        return (product.standard_price or 0.0) * qty
    return 0.0


def sbu_collect_project_budget(project, env):
    """Return dict cost_family -> {planned, open_pr, po_draft, po_confirmed}."""
    totals = defaultdict(lambda: {
        'planned': 0.0,
        'open_pr': 0.0,
        'po_draft': 0.0,
        'po_confirmed': 0.0,
    })
    estimate = project.sbu_estimate_id
    if estimate:
        for eline in estimate.line_ids:
            fam = eline.cost_family or 'extra'
            totals[fam]['planned'] += eline.cost_total_tot or 0.0

    PrLine = env['sbu.purchase.request.line']
    Pol = env['purchase.order.line']
    pr_lines = PrLine.search([
        ('request_id.project_id', '=', project.id),
        ('request_id.state', '!=', 'cancelled'),
    ])
    for pr_line in pr_lines:
        fam = sbu_cost_family_for_pr_line(pr_line)
        pols = Pol.search([
            ('sbu_pr_line_id', '=', pr_line.id),
            ('order_id.state', '!=', 'cancel'),
        ])
        if pols:
            for pol in pols:
                po = pol.order_id
                if po.state in PO_DRAFT_STATES:
                    totals[fam]['po_draft'] += pol.price_subtotal or 0.0
                elif po.state in PO_CONFIRMED_STATES:
                    totals[fam]['po_confirmed'] += pol.price_subtotal or 0.0
            if (
                pr_line.request_id.state in OPEN_PR_REQUEST_STATES
                and (pr_line.qty_remaining or 0.0) > 0
            ):
                totals[fam]['open_pr'] += sbu_pr_line_engaged_amount(
                    pr_line, qty=pr_line.qty_remaining
                )
        elif pr_line.request_id.state in OPEN_PR_REQUEST_STATES:
            totals[fam]['open_pr'] += sbu_pr_line_engaged_amount(pr_line)

    # PO lines without PR link (rare): attribute to extra
    Po = env['purchase.order']
    pos = Po.search([
        ('project_id', '=', project.id),
        ('state', '!=', 'cancel'),
    ])
    for po in pos:
        for pol in po.order_line.filtered(lambda l: not l.sbu_pr_line_id):
            fam = 'extra'
            if po.state in PO_DRAFT_STATES:
                totals[fam]['po_draft'] += pol.price_subtotal or 0.0
            elif po.state in PO_CONFIRMED_STATES:
                totals[fam]['po_confirmed'] += pol.price_subtotal or 0.0

    return totals
