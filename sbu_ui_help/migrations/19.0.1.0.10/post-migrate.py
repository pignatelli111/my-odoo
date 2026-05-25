# -*- coding: utf-8 -*-
"""Remove help module from DB (no backend JS/RPC after uninstall)."""


def migrate(cr, version):
    if not version:
        return
    from odoo import api

    env = api.Environment(cr, 1, {})
    mod = env['ir.module.module'].search([('name', '=', 'sbu_ui_help')], limit=1)
    if not mod or mod.state != 'installed':
        return
    mod.button_immediate_uninstall()
