# -*- coding: utf-8 -*-
from odoo.addons.sbu_qonto.hooks import _sbu_qonto_refresh_transfer_dates


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _sbu_qonto_refresh_transfer_dates(env)
