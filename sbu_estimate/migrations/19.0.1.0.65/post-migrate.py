# -*- coding: utf-8 -*-
"""Backfill contractual SAL line display names after adding field `name`."""


def migrate(cr, version):
    from odoo import api

    env = api.Environment(cr, 1, {})
    SalLine = env['sbu.estimate.sal.line']
    if 'name' not in SalLine._fields:
        return
    while True:
        lines = SalLine.search([('name', '=', False)], limit=500)
        if not lines:
            break
        lines._compute_name()
