# -*- coding: utf-8 -*-
"""Backfill contractual SAL line display names after adding field `name`."""


def migrate(cr, version):
    from odoo import api

    env = api.Environment(cr, 1, {})
    SalLine = env['sbu.estimate.sal.line']
    if 'name' not in SalLine._fields:
        return
    lines = SalLine.search([])
    if lines:
        lines._compute_name()
