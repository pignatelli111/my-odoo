# -*- coding: utf-8 -*-
from odoo import fields, models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    sbu_graph_item_id = fields.Char(
        string='Graph item id',
        index=True,
        copy=False,
        help='When set, identifies the OneDrive/SharePoint file this attachment was synced from.',
    )
