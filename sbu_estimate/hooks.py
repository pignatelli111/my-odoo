# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Assign SBU Estimate User to internal users so CRM opportunity linking works out of the box."""
    group = env.ref('sbu_estimate.group_sbu_estimate_user', raise_if_not_found=False)
    if not group:
        return
    users = env['res.users'].search([('share', '=', False)])
    to_add = users.filtered(lambda u: group not in u.groups_id)
    if to_add:
        to_add.write({'groups_id': [(4, group.id)]})
