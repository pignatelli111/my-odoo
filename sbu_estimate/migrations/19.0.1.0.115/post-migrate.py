# -*- coding: utf-8 -*-
"""ANACO engine: recompute every estimate line and total with the Excel formulas."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model_name in ('sbu.estimate.line', 'sbu.estimate'):
        Model = env[model_name].with_context(active_test=False)
        records = Model.search([])
        for field in Model._fields.values():
            if field.compute and field.store:
                env.add_to_compute(field, records)
    env.flush_all()
