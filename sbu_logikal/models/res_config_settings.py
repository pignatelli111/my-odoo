# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_logikal_api_bearer = fields.Char(
        string='Logikal / ReynaPro API bearer',
        config_parameter='sbu.logikal_api_bearer',
        help='Optional Bearer token for the middleware that exposes JSON positions.',
    )
    sbu_logikal_api_path = fields.Char(
        string='Logikal API path',
        config_parameter='sbu.logikal_api_path',
        help='Path appended to base URL (GET), default /positions. Query «project» is set from the import batch.',
    )
