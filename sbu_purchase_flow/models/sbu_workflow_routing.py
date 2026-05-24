# -*- coding: utf-8 -*-
"""Map ANACO workflow route codes to SBU purchase request document types."""

# Closed catalog — shown in lists (searchpanel) and create wizard.
SBU_WORKFLOW_ROUTE_SELECTION = [
    ('VC/VS', 'VT / Glass (VC-VS)'),
    ('ZANZ', 'Screens'),
    ('OSC', 'OSC / Blinds'),
    ('ST', 'ST / Brackets'),
    ('PAN', 'PAN / Panels'),
    ('LA', 'LA / Aluminium sheet'),
    ('LZ', 'LZ / Galvanized sheet (metalwork)'),
    ('PRF', 'PRF / Profiles'),
    ('FT/FTF', 'FT / Joinery'),
    ('SE', 'SE / Frames'),
    ('ASS', 'ACO / Assembly (ASS)'),
    ('ACC', 'ACO / Accessories (ACC)'),
    ('GUA', 'ACO / Gaskets (GUA)'),
    ('POS', 'ACP / Installation'),
    ('TRN', 'LDS / Transport'),
    ('PM', 'PM / Project management'),
    ('CNT', 'CNT / Site costs'),
    ('EXT', 'EXT / Extra'),
]

# Routes offered in «Nuovo documento acquisto» (no free-text types).
SBU_WIZARD_ROUTE_SELECTION = [
    ('LA', 'LA — Aluminium sheet'),
    ('LZ', 'LZ — Metalwork / galvanized sheet'),
    ('ST', 'ST — Brackets'),
    ('PAN', 'PAN — Panels'),
    ('OSC', 'OSC — Blinds'),
    ('VC/VS', 'VT — Glass / VC-VS'),
    ('ZANZ', 'Screens'),
    ('PRF', 'PRF — Profiles'),
    ('FT/FTF', 'FT — Joinery'),
    ('SE', 'SE — Frames'),
    ('ASS', 'ACO — Assembly'),
    ('ACC', 'ACO — Accessories'),
    ('GUA', 'ACO — Gaskets'),
    ('POS', 'ACP — Installation'),
    ('TRN', 'LDS — Transport'),
]

WORKFLOW_ROUTE_TO_REQUEST_TYPE = {
    'VC/VS': 'vt',
    'ZANZ': 'vt',
    'OSC': 'vt',
    'ST': 'st',
    'PAN': 'rda',
    'LA': 'rda',
    'LZ': 'fe',
    'PRF': 'rda',
    'FT/FTF': 'rda',
    'SE': 'rda',
    'ASS': 'aco',
    'ACC': 'aco',
    'GUA': 'aco',
    'TRN': 'lds',
    'POS': 'acp',
    'PM': 'other',
    'CNT': 'other',
    'EXT': 'other',
}

# BOM product codes used when splitting glass lines into VT / ZANZ / OSC documents.
_BOM_PRODUCT_ROUTE = {
    'SBU-OSC': 'OSC',
    'SBU-ZANZ': 'ZANZ',
    'SBU-VETRO': 'VC/VS',
}

# Wizard validation: avoid empty / inconsistent headers (Cosimo point 5).
ROUTE_WIZARD_REQUIRES = {
    'LA': {'topic': True, 'need_by': True},
    'LZ': {'topic': True, 'need_by': True},
    'ST': {'need_by': True},
    'PAN': {'topic': True, 'need_by': True},
    'OSC': {'need_by': True},
    'VC/VS': {'need_by': True},
    'ZANZ': {'need_by': True},
    'PRF': {'topic': True},
    'FT/FTF': {'topic': True},
    'SE': {'topic': True},
    'POS': {'need_by': True},
    'TRN': {'need_by': True},
}


def workflow_route_to_request_type(route_code):
    return WORKFLOW_ROUTE_TO_REQUEST_TYPE.get((route_code or '').strip(), 'other')


def normalize_workflow_route(route_code):
    """Return a known route key or False."""
    key = (route_code or '').strip()
    if not key:
        return False
    valid = {code for code, _label in SBU_WORKFLOW_ROUTE_SELECTION}
    return key if key in valid else False


def bom_product_workflow_route(bom_line):
    """Infer sub-route from distinta product (vetro / zanzariere / oscurante)."""
    product = bom_line.product_id
    if not product:
        return False
    code = (product.default_code or '').strip().upper()
    return _BOM_PRODUCT_ROUTE.get(code)


def estimate_line_matches_route(estimate_line, workflow_route):
    """Whether an estimate line contributes BOM rows to this route."""
    route = normalize_workflow_route(workflow_route)
    if not route:
        return False
    if route in ('OSC', 'ZANZ', 'VC/VS'):
        return any(
            bom_product_workflow_route(bom) == route
            for bom in estimate_line.bom_line_ids
            if bom.product_id
        )
    return (estimate_line.workflow_route or '') == route


def collect_workflow_routes_from_estimate(estimate):
    """All routes to create as separate purchase requests (incl. OSC/ZANZ split)."""
    routes = set()
    for eline in estimate.line_ids:
        base = normalize_workflow_route(eline.workflow_route)
        saw_glass_split = False
        for bom in eline.bom_line_ids:
            if not bom.product_id:
                continue
            sub = bom_product_workflow_route(bom)
            if sub:
                routes.add(sub)
                saw_glass_split = True
        if base and base not in ('VC/VS', 'ZANZ', 'OSC'):
            routes.add(base)
        elif base == 'VC/VS' and not saw_glass_split:
            routes.add('VC/VS')
    return sorted(routes)


def workflow_route_display(route_code):
    for code, label in SBU_WORKFLOW_ROUTE_SELECTION:
        if code == route_code:
            return label
    return route_code or ''
