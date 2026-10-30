# -*- coding: utf-8 -*-
"""Analytic account for every existing SBU job; draft purchase lines pick it up."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    jobs = env['project.project'].with_context(active_test=False).search([('sbu_estimate_id', '!=', False)])
    jobs._sbu_ensure_analytic_account()
    if 'purchase.order.line' in env and jobs:
        lines = env['purchase.order.line'].search([
            ('order_id.project_id', 'in', jobs.ids), ('order_id.state', 'in', ('draft', 'sent')),
        ])
        env.add_to_compute(lines._fields['analytic_distribution'], lines)
    env.flush_all()
