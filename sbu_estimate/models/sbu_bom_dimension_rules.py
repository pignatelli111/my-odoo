# -*- coding: utf-8 -*-
"""
Rules when generating distinta from ANACO cost columns (Cosimo: stima → tecnico → PO).

- Vetro (SBU-VETRO): mq = 90% of position B×H (stima; Logikal/tecnico can override).
- Zanzariere / oscuranti: effective height = position H + 300 mm (typical rule).
"""

# product.template default_code → BOM generation profile
ANACO_BOM_GENERATION_RULES = {
    'SBU-VETRO': {
        'calc_type': 'surface',
        'dimension_source': 'surface',
        'sqm_coverage_factor': 0.9,
        'height_adjust_mm': 0.0,
        'needs_technical_confirm': True,
        'note': 'Vetro: stima 90% mq posizione (BxH); confermare da disegno/Logikal.',
    },
    'SBU-ZANZ': {
        'calc_type': 'surface',
        'dimension_source': 'surface',
        'sqm_coverage_factor': 1.0,
        'height_adjust_mm': 300.0,
        'needs_technical_confirm': True,
        'note': 'Zanzariere: altezza effettiva = H posizione + 300 mm.',
    },
    'SBU-OSC': {
        'calc_type': 'surface',
        'dimension_source': 'surface',
        'sqm_coverage_factor': 1.0,
        'height_adjust_mm': 300.0,
        'needs_technical_confirm': True,
        'note': 'Oscurante: altezza effettiva = H posizione + 300 mm.',
    },
}

# cost_family on estimate line → same profile when product code not in map
COST_FAMILY_BOM_RULES = {
    'glass': ANACO_BOM_GENERATION_RULES['SBU-VETRO'],
}


def bom_rule_for_product_and_line(product, estimate_line):
    """Return a dict of BOM defaults (may be empty)."""
    code = (product.default_code or '').strip().upper()
    if code in ANACO_BOM_GENERATION_RULES:
        return dict(ANACO_BOM_GENERATION_RULES[code])
    if estimate_line and estimate_line.cost_family:
        fam = estimate_line.cost_family
        if fam in COST_FAMILY_BOM_RULES:
            return dict(COST_FAMILY_BOM_RULES[fam])
    return {}
