# -*- coding: utf-8 -*-


def _sbu_backfill_bom_estimate_id(env):
    """Set preventivo on existing distinta rows (upgrade + install)."""
    Bom = env['sbu.estimate.bom.line']
    for bom in Bom.search([('estimate_id', '=', False)]):
        if bom.estimate_line_id:
            bom.estimate_id = bom.estimate_line_id.estimate_id


def _sbu_ensure_uat_products(env):
    """Idempotent UAT goods for distinta / RDA testing (Odoo 19: type consu only)."""
    Template = env['product.template'].sudo()
    specs = (
        ('UAT-PROF-01', 'UAT — Profilo alluminio test', 25.0),
        ('UAT-FAST-01', 'UAT — Vite / accessorio test', 0.5),
    )
    for code, name, cost in specs:
        if Template.search([('default_code', '=', code)], limit=1):
            continue
        Template.create({
            'name': name,
            'default_code': code,
            'type': 'consu',
            'purchase_ok': True,
            'sale_ok': False,
            'standard_price': cost,
        })


def post_init_hook(env):
    """Assign SBU Estimate User to internal users so CRM opportunity linking works out of the box."""
    _sbu_backfill_bom_estimate_id(env)
    _sbu_ensure_uat_products(env)
    group = env.ref('sbu_estimate.group_sbu_estimate_user', raise_if_not_found=False)
    if not group:
        return
    users = env['res.users'].search([('share', '=', False)])
    # Odoo 19: groups_id → group_ids on res.users.
    to_add = users.filtered(lambda u: group not in u.group_ids)
    if to_add:
        to_add.write({'group_ids': [(4, group.id)]})
