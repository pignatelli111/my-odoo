# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.sbu_estimate.hooks import (
        _sbu_backfill_bom_estimate_id,
        _sbu_ensure_uat_products,
    )

    _sbu_backfill_bom_estimate_id(env)
    _sbu_ensure_uat_products(env)
