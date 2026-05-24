# -*- coding: utf-8 -*-
"""Batched SAL line name backfill (safe on large production DBs during upgrade)."""


def migrate(cr, version):
    if not version:
        return
    from odoo import api

    env = api.Environment(cr, 1, {})
    SalLine = env['sbu.estimate.sal.line']
    if 'name' not in SalLine._fields:
        return
    while True:
        lines = SalLine.search([('name', 'in', (False, ''))], limit=500)
        if not lines:
            break
        lines._compute_name()
