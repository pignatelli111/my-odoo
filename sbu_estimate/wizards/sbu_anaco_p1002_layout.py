# -*- coding: utf-8 -*-
"""P1002 REV03 ANACO column layout (from ANACO_P1002_25_CON_REV03_EIALL+ALL_P1.xlsx row 3–4)."""
import re

# 1-based columns — validated on P1002 workbook (not REV7 AX=50 posa / BC=staffame confusion).
P1002_COL_COST_BB = 54  # Costo materiale lavorato e posato CAD
P1002_COL_COST_BC = 55  # … TOT
P1002_ANACO_PRICE_MAP = {
    'price_serramento_cad': 14,  # N — often 0; BS drives sell price
    'price_accessori_cad': 22,  # V Accessorio maniglie CAD
    'price_oscuramento_cad': 28,  # AB LA CAD
    'price_kit_avvolgimento_cad': 32,  # AF alluminio sistema
    'price_automatismo_cad': 38,  # AL
    'price_vetro_cad': 40,  # AN
    'price_pannello_cad': 42,  # AP
    'price_controtelaio_cad': 44,  # AR
    'price_trasformazione_cad': 46,  # AT alluminio
    'price_nolo_cad': 52,  # AZ
    'price_cassonetto_cad': 34,  # AH acciaio — may be 0 on wood lines
}
P1002_ANACO_COST_MAP = {
    'cost_coibentazione_cad': 30,  # AD
    'cost_staffame_cad': 16,  # P ST/LZ staffame CAD
    'cost_posa_lamiera_lin_cad': 48,  # AV Posa SER e FAC CAD
    'cost_trasporto_cad': 57,  # BE
    'cost_tech_pm_cad': 59,  # BG
    'cost_cantiere_cad': 61,  # BI
    'cost_extra_cad': 63,  # BK
}


def _header_compact(text):
    return re.sub(r'[\s._\-/%]+', '', (text or '').strip().upper())


def is_p1002_anaco_layout(cell_str_merged, sh_vals, sh_form=None):
    """Detect P1002 template from row 3–5 labels or job code."""
    sh_form = sh_form or sh_vals
    probes = (
        (3, 54),
        (3, 55),
        (5, 3),
    )
    for row, col in probes:
        t = _header_compact(cell_str_merged(sh_vals, sh_form, row, col))
        if 'P1002' in t:
            return True
        if row == 3 and col == 54 and 'COSTO' in t and 'MATERIALE' in t:
            return True
    return False


def p1002_anaco_import_maps():
    """Return (price_map, cost_map, bb_col, bc_col) for P1002."""
    return (
        dict(P1002_ANACO_PRICE_MAP),
        dict(P1002_ANACO_COST_MAP),
        P1002_COL_COST_BB,
        P1002_COL_COST_BC,
    )
