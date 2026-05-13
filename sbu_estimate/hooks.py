"""
Post-install hook for sbu_estimate.
Creates custom UoM categories and units after all modules are loaded.
"""


def post_init_hook(env):
    """Create SBU-specific units of measure after module installation."""
    UomCategory = env['uom.category']
    Uom = env['uom.uom']

    # ── Category: SBU Lunghezza ───────────────────────────────────────────────
    categ_length = UomCategory.search([('name', '=', 'SBU Lunghezza')], limit=1)
    if not categ_length:
        categ_length = UomCategory.create({'name': 'SBU Lunghezza'})

    # m (reference)
    if not Uom.search([('name', '=', 'm (SBU)'), ('category_id', '=', categ_length.id)], limit=1):
        uom_m = Uom.create({
            'name': 'm (SBU)',
            'category_id': categ_length.id,
            'factor': 1.0,
            'uom_type': 'reference',
            'rounding': 0.001,
        })
    else:
        uom_m = Uom.search([('name', '=', 'm (SBU)'), ('category_id', '=', categ_length.id)], limit=1)

    # mm (smaller than m)
    if not Uom.search([('name', '=', 'mm'), ('category_id', '=', categ_length.id)], limit=1):
        Uom.create({
            'name': 'mm',
            'category_id': categ_length.id,
            'factor': 1000.0,
            'uom_type': 'smaller',
            'rounding': 1.0,
        })

    # ml (metri lineari): same physical unit as m — do not create a second
    # reference UoM in the same category (Odoo rejects multiple references).

    # ── Category: SBU Area ────────────────────────────────────────────────────
    categ_area = UomCategory.search([('name', '=', 'SBU Area')], limit=1)
    if not categ_area:
        categ_area = UomCategory.create({'name': 'SBU Area'})

    # mq (reference for area)
    if not Uom.search([('name', '=', 'mq'), ('category_id', '=', categ_area.id)], limit=1):
        Uom.create({
            'name': 'mq',
            'category_id': categ_area.id,
            'factor': 1.0,
            'uom_type': 'reference',
            'rounding': 0.001,
        })

    # ── Category: SBU Varie ───────────────────────────────────────────────────
    categ_misc = UomCategory.search([('name', '=', 'SBU Varie')], limit=1)
    if not categ_misc:
        categ_misc = UomCategory.create({'name': 'SBU Varie'})

    # rot — rotolo
    if not Uom.search([('name', '=', 'rot'), ('category_id', '=', categ_misc.id)], limit=1):
        Uom.create({
            'name': 'rot',
            'category_id': categ_misc.id,
            'factor': 1.0,
            'uom_type': 'reference',
            'rounding': 1.0,
        })
