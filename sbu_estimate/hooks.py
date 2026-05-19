# -*- coding: utf-8 -*-


def _sbu_backfill_bom_estimate_id(env):
    """Set preventivo on existing distinta rows (upgrade + install)."""
    Bom = env['sbu.estimate.bom.line']
    for bom in Bom.search([('estimate_id', '=', False)]):
        if bom.estimate_line_id:
            bom.estimate_id = bom.estimate_line_id.estimate_id


def post_init_hook(env):
    """Assign SBU Estimate User to internal users so CRM opportunity linking works out of the box."""
    _sbu_backfill_bom_estimate_id(env)
    group = env.ref('sbu_estimate.group_sbu_estimate_user', raise_if_not_found=False)
    if not group:
        return
    users = env['res.users'].search([('share', '=', False)])
    # Odoo 19: groups_id → group_ids on res.users.
    to_add = users.filtered(lambda u: group not in u.group_ids)
    if to_add:
        to_add.write({'group_ids': [(4, group.id)]})
