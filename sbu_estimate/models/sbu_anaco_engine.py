# -*- coding: utf-8 -*-
"""ANACO workbook model: the same columns and formulas as the Excel sheet.

Per row (Excel row 13 as example)::

    BB = N + R + V + AB + AD + AF + AH + AJ + AL + AN + AP + AR + AT + AV + AX + AZ   (16 CAD costs)
    BC = BB × H                      BD = BC / I
    BE = BB × $BE$5  (transport)     BG = BB × $BG$5 (technical / PM)
    BI = BB × $BI$5  (site)          BK = BB × $BK$5 (extra)
    BN = BB × BM     (industrial)    BQ = BB × BP    (MOL)
    BS = BB + BE + BG + BI + BK + BN + BQ            BT = BS × H      BU = BT / I

The 16 cost columns sit at the same positions in every ANACO template (REV7, P1002,
SCHIAFFINO…); only their headers change, so the header text of each workbook is kept
on the estimate for display.
"""

# (field, Excel CAD column, Excel TOT column, default label) — Excel order, BB = sum of these.
ANACO_COMPONENTS = (
    ('price_serramento_cad', 'N', 'O', 'Serramento scontato'),
    ('cost_staffame_cad', 'R', 'S', 'ST / LZ - Staffame'),
    ('price_accessori_cad', 'V', 'W', 'Accessorio maniglie e maniglioni'),
    ('price_oscuramento_cad', 'AB', 'AC', 'Oscuramento scontato'),
    ('cost_coibentazione_cad', 'AD', 'AE', 'Pacchetto di coibentazione'),
    ('price_kit_avvolgimento_cad', 'AF', 'AG', 'Kit avvolgimento'),
    ('price_cassonetto_cad', 'AH', 'AI', 'Cassonetto'),
    ('price_automatismo_cad', 'AJ', 'AK', 'Automatismo'),
    ('price_zanzariera_cad', 'AL', 'AM', 'Zanzariera'),
    ('price_vetro_cad', 'AN', 'AO', 'Vetro'),
    ('price_pannello_cad', 'AP', 'AQ', 'Pannello'),
    ('price_controtelaio_cad', 'AR', 'AS', 'Controtelaio'),
    ('price_trasformazione_cad', 'AT', 'AU', 'Trasformazione'),
    ('price_smontaggio_cad', 'AV', 'AW', 'Smontaggio posa ser. e oscur.'),
    ('cost_posa_lamiera_lin_cad', 'AX', 'AY', 'Posa lamiera'),
    ('price_nolo_cad', 'AZ', 'BA', 'Nolo'),
)
ANACO_COMPONENT_FIELDS = tuple(c[0] for c in ANACO_COMPONENTS)

# Excel columns of the derived figures (row 5 holds the percentages BE5…BP5).
ANACO_COL_BB, ANACO_COL_BC, ANACO_COL_BS = 'BB', 'BC', 'BS'
ANACO_OVERHEADS = (
    # (estimate % field, line CAD field, line TOT field, Excel CAD col, Excel TOT col, label)
    ('anaco_pct_transport', 'cost_trasporto_cad', 'cost_trasporto_tot', 'BE', 'BF', 'Trasporto e imballo'),
    ('anaco_pct_tech_pm', 'cost_tech_pm_cad', 'cost_tech_pm_tot', 'BG', 'BH', 'Sviluppo tecnico e PM'),
    ('anaco_pct_site', 'cost_cantiere_cad', 'cost_cantiere_tot', 'BI', 'BJ', 'Presidio cantiere / site mng'),
    ('anaco_pct_extra', 'cost_extra_cad', 'cost_extra_tot', 'BK', 'BL', 'Extra'),
)
ANACO_INSTALLATION_KEYWORD = 'POSA'


def is_installation_label(label):
    return ANACO_INSTALLATION_KEYWORD in (label or '').upper()
