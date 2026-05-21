# -*- coding: utf-8 -*-
"""Ensure approver users inherit SBU UAT cleanup (force-delete button visibility)."""


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    approver = env.ref('sbu_estimate.group_sbu_estimate_approver', raise_if_not_found=False)
    uat = env.ref('sbu_estimate.group_sbu_estimate_uat_cleanup', raise_if_not_found=False)
    if not approver or not uat or uat in approver.implied_ids:
        return
    approver.write({'implied_ids': [(4, uat.id)]})
