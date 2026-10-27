# -*- coding: utf-8 -*-
"""Supplier table per ANACO column for the existing estimates (suppliers left empty)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['sbu.estimate'].search([('line_ids', '!=', False)]).action_sbu_prepare_column_suppliers()
