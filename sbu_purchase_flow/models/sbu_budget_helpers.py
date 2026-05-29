# -*- coding: utf-8 -*-
"""Helpers for SBU budget-by-cost-family (Cosimo point 11)."""

from collections import defaultdict

from odoo import fields

from odoo.addons.sbu_estimate.models.sbu_account_line_utils import sbu_is_product_line
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
# ANACO catalog codes without a single price_* infer column (kit, osc, …).
SBU_PRODUCT_CODE_FAMILY_OVERRIDES = {
    'SBU-KIT-AVV': 'accessory',
    'SBU-OSC': 'accessory',
    'SBU-CASS': 'accessory',
    'SBU-AUTO': 'accessory',
    'SBU-ZANZ': 'accessory',
    'SBU-TRAS': 'accessory',
    'SBU-COIB': 'accessory',
}
for _field, _code in ANACO_LINE_FIELD_TO_PRODUCT_CODE.items():
    _fam = infer_cost_family_from_price_cost_vals({_field: 1.0})
    if _fam:
        SBU_PRODUCT_CODE_TO_COST_FAMILY[_code.strip().upper()] = _fam
SBU_PRODUCT_CODE_TO_COST_FAMILY.update(SBU_PRODUCT_CODE_FAMILY_OVERRIDES)


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
    vdc = (pr_line.vdc_code or '').strip()
    if vdc:
        fam = pr_line.env['sbu.vdc.catalog'].resolve_cost_family(vdc)
        if fam:
            return fam
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


def sbu_estimate_line_for_pol(pol):
    """ANACO estimate line linked via PR → BOM (ITEM traceability)."""
    pr_line = pol.sbu_pr_line_id
    if not pr_line or not pr_line.source_bom_line_id:
        return False
    return pr_line.source_bom_line_id.estimate_line_id


def sbu_pol_amount_company(pol, amount_field='price_subtotal'):
    """PO line subtotal in company currency."""
    company = pol.company_id or pol.order_id.company_id
    currency = pol.currency_id or pol.order_id.currency_id
    amount = getattr(pol, amount_field, 0.0) or 0.0
    if not amount or not currency or currency == company.currency_id:
        return amount
    order_date = pol.order_id.date_order
    if order_date and hasattr(order_date, 'date'):
        order_date = order_date.date()
    if not order_date:
        order_date = fields.Date.today()
    return currency._convert(amount, company.currency_id, company, order_date)


def sbu_pol_posted_bill_amount(pol, env):
    """Posted vendor bill subtotal (company currency) for a purchase order line."""
    if 'account.move.line' not in env:
        return 0.0
    company = pol.company_id or pol.order_id.company_id
    lines = pol.invoice_lines
    if not lines:
        Aml = env['account.move.line']
        domain = [('purchase_line_id', '=', pol.id)]
        if 'parent_state' in Aml._fields:
            domain.append(('parent_state', '=', 'posted'))
        else:
            domain.append(('move_id.state', '=', 'posted'))
        lines = Aml.search(domain)
    total = 0.0
    for aml in lines.filtered(sbu_is_product_line):
        move = aml.move_id
        if move.state != 'posted' or move.move_type not in ('in_invoice', 'in_refund'):
            continue
        sign = -1.0 if move.move_type == 'in_refund' else 1.0
        amt = aml.price_subtotal or 0.0
        if aml.currency_id and aml.currency_id != company.currency_id:
            amt = aml.currency_id._convert(
                amt, company.currency_id, company, aml.date or move.date,
            )
        total += sign * amt
    return total


def sbu_collect_estimate_line_budget(project, env):
    """Return dict estimate_line_id -> {orders, actual} from PO + vendor bills."""
    totals = defaultdict(lambda: {'orders': 0.0, 'actual': 0.0})
    if not project.sbu_estimate_id:
        return totals
    Pol = env['purchase.order.line']
    pols = Pol.search([
        ('order_id.project_id', '=', project.id),
        ('order_id.state', '!=', 'cancel'),
        ('sbu_pr_line_id', '!=', False),
    ])
    for pol in pols:
        eline = sbu_estimate_line_for_pol(pol)
        if not eline:
            continue
        po = pol.order_id
        if po.state in PO_CONFIRMED_STATES:
            totals[eline.id]['orders'] += sbu_pol_amount_company(pol)
        totals[eline.id]['actual'] += sbu_pol_posted_bill_amount(pol, env)
    return totals


def sbu_sync_estimate_line_budgets(project, env):
    """Write ITEM-style ordini emessi / costi sostenuti on ANACO lines."""
    estimate = project.sbu_estimate_id
    if not estimate:
        return
    totals = sbu_collect_estimate_line_budget(project, env)
    EstimateLine = env['sbu.estimate.line']
    for eline in estimate.line_ids:
        amounts = totals.get(eline.id, {'orders': 0.0, 'actual': 0.0})
        vals = {
            'budget_orders_issued': amounts['orders'],
            'budget_costs_incurred': amounts['actual'],
        }
        if (
            eline.budget_orders_issued != vals['budget_orders_issued']
            or eline.budget_costs_incurred != vals['budget_costs_incurred']
        ):
            eline.write(vals)


def sbu_collect_project_budget(project, env):
    """Return dict cost_family -> {planned, open_pr, po_draft, po_confirmed, actual}."""
    totals = defaultdict(lambda: {
        'planned': 0.0,
        'open_pr': 0.0,
        'po_draft': 0.0,
        'po_confirmed': 0.0,
        'actual': 0.0,
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
                subtotal = sbu_pol_amount_company(pol)
                if po.state in PO_DRAFT_STATES:
                    totals[fam]['po_draft'] += subtotal
                elif po.state in PO_CONFIRMED_STATES:
                    totals[fam]['po_confirmed'] += subtotal
                totals[fam]['actual'] += sbu_pol_posted_bill_amount(pol, env)
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
            subtotal = sbu_pol_amount_company(pol)
            if po.state in PO_DRAFT_STATES:
                totals[fam]['po_draft'] += subtotal
            elif po.state in PO_CONFIRMED_STATES:
                totals[fam]['po_confirmed'] += subtotal
            totals[fam]['actual'] += sbu_pol_posted_bill_amount(pol, env)

    return totals


def sbu_projects_for_budget_refresh(records, env):
    """Projects affected by PO / vendor bill changes."""
    Project = env['project.project']
    projects = Project.browse()
    Po = env['purchase.order']
    for po in records if records._name == 'purchase.order' else Po.browse():
        if po.project_id:
            projects |= po.project_id
    Move = env.get('account.move')
    if not Move:
        return projects
    for move in records if records._name == 'account.move' else Move.browse():
        if move.move_type not in ('in_invoice', 'in_refund'):
            continue
        bill_lines = move.invoice_line_ids if move.is_invoice() else move.line_ids
        for pol in bill_lines.mapped('purchase_line_id'):
            if pol and pol.order_id.project_id:
                projects |= pol.order_id.project_id
    return projects


def sbu_refresh_projects_budget(projects, env):
    """Rebuild family rows and sync estimate line budget columns."""
    Budget = env['sbu.project.budget.family']
    for project in projects:
        if project.sbu_estimate_id:
            Budget.refresh_project(project)
