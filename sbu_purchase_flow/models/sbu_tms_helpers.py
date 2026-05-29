# -*- coding: utf-8 -*-
"""Shared TMS Excel helpers (UoM mapping, etc.)."""


def resolve_tms_uom(env, uom_code):
    """Map TMS unit label (PZ, ml, …) to uom.uom record."""
    code = (uom_code or '').strip().lower().replace('.', '')
    if not code:
        return env.ref('uom.product_uom_unit', raise_if_not_found=False)
    mapping = {
        'pz': 'uom.product_uom_unit',
        'nr': 'uom.product_uom_unit',
        'cad': 'uom.product_uom_unit',
        'pezzo': 'uom.product_uom_unit',
        'ml': 'uom.product_uom_meter',
        'm': 'uom.product_uom_meter',
        'mt': 'uom.product_uom_meter',
        'kg': 'uom.product_uom_kgm',
    }
    xmlid = mapping.get(code)
    if xmlid:
        uom = env.ref(xmlid, raise_if_not_found=False)
        if uom:
            return uom
    if code in ('mq', 'm2', 'm²'):
        uom = env['uom.uom'].search([
            ('category_id.measure_type', '=', 'area'),
        ], limit=1)
        if uom:
            return uom
    found = env['uom.uom'].search([('name', '=ilike', uom_code.strip())], limit=1)
    return found or env.ref('uom.product_uom_unit', raise_if_not_found=False)
