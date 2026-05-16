# -*- coding: utf-8 -*-
"""Cost family / category for ANACO estimate lines (downstream workflow routing)."""

SBU_COST_FAMILY_SELECTION = [
    ('serramento', 'Serramento / window system'),
    ('glass', 'Glass'),
    ('panel', 'Panel'),
    ('bracket_st', 'Bracket / ST'),
    ('profile', 'Profile / PF / PRF'),
    ('accessory', 'Accessory'),
    ('gasket', 'Gasket'),
    ('aluminum_sheet', 'Aluminum sheet / LA'),
    ('zinc_sheet', 'Zinc sheet / LZ'),
    ('assembly', 'Assembly / ASS'),
    ('frame_window', 'Frame / window / SE'),
    ('transport', 'Transport'),
    ('installation', 'Installation'),
    ('technical_pm', 'Technical / PM'),
    ('site_cost', 'Site cost'),
    ('extra', 'Extra'),
]

# Longest prefixes first (position codes such as PAN, PRF, FTF).
_POS_PREFIX_TO_COST_FAMILY = (
    ('PRF', 'profile'),
    ('PAN', 'panel'),
    ('ASS', 'assembly'),
    ('FTF', 'serramento'),
    ('FT', 'serramento'),
    ('LA', 'aluminum_sheet'),
    ('LZ', 'zinc_sheet'),
    ('ST', 'bracket_st'),
    ('VC', 'glass'),
    ('VS', 'glass'),
    ('PF', 'profile'),
    ('SE', 'frame_window'),
)


def infer_cost_family_from_pos(pos):
    """Guess cost family from ANACO position / item code prefix."""
    pos_u = (pos or '').strip().upper()
    if not pos_u:
        return False
    for prefix, family in _POS_PREFIX_TO_COST_FAMILY:
        if pos_u.startswith(prefix):
            return family
    return False


def infer_cost_family_from_price_cost_vals(line_vals):
    """Guess cost family from populated ANACO price/cost columns on import."""
    if line_vals.get('price_vetro_cad'):
        return 'glass'
    if line_vals.get('price_pannello_cad'):
        return 'panel'
    if line_vals.get('price_serramento_cad') or line_vals.get('price_controtelaio_cad'):
        return 'serramento'
    if line_vals.get('price_accessori_cad'):
        return 'accessory'
    if line_vals.get('cost_trasporto_cad') or line_vals.get('price_nolo_cad'):
        return 'transport'
    if line_vals.get('cost_tech_pm_cad'):
        return 'technical_pm'
    if line_vals.get('cost_cantiere_cad'):
        return 'site_cost'
    if line_vals.get('cost_extra_cad'):
        return 'extra'
    if line_vals.get('cost_posa_lamiera_lin_cad') or line_vals.get('price_smontaggio_cad'):
        return 'installation'
    return False
