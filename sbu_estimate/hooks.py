# -*- coding: utf-8 -*-
from odoo.tools import config


def _sbu_backfill_bom_estimate_id(env):
    """Set estimate on BOM rows missing preventivo (batched; skip on Odoo.sh test builds)."""
    if config.get('test_enable'):
        return
    Bom = env['sbu.estimate.bom.line'].sudo()
    while True:
        batch = Bom.search([('estimate_id', '=', False)], limit=500)
        if not batch:
            break
        for bom in batch:
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


def _sbu_assign_default_estimate_group(env):
    """Give internal users SBU Estimate User (skipped during Odoo.sh --test-enable)."""
    if config.get('test_enable'):
        return
    group = env.ref('sbu_estimate.group_sbu_estimate_user', raise_if_not_found=False)
    if not group:
        return
    users = env['res.users'].search([('share', '=', False)])
    to_add = users.filtered(lambda u: group not in u.group_ids)
    if to_add:
        to_add.write({'group_ids': [(4, group.id)]})


def post_init_hook(env):
    _sbu_backfill_bom_estimate_id(env)
    _sbu_ensure_uat_products(env)
    _sbu_assign_default_estimate_group(env)
