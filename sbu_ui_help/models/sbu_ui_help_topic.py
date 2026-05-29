# -*- coding: utf-8 -*-
"""Minimal models so production DB can uninstall sbu_ui_help (addon was removed in 56984a5)."""
from odoo import fields, models


class SbuUiHelpTopic(models.Model):
    _name = 'sbu.ui.help.topic'
    _description = 'SBU contextual UI help'
    _order = 'id'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    model = fields.Char(required=True, index=True)
    view_mode = fields.Selection(
        selection=[
            ('any', 'Any view'),
            ('list', 'List'),
            ('form', 'Form'),
            ('kanban', 'Kanban'),
            ('search', 'Search'),
        ],
        default='any',
        required=True,
    )
    sequence = fields.Integer(default=10)
    purpose = fields.Html(sanitize=False)
    item_ids = fields.One2many('sbu.ui.help.item', 'topic_id')


class SbuUiHelpItem(models.Model):
    _name = 'sbu.ui.help.item'
    _description = 'SBU help line'
    _order = 'sequence, id'

    topic_id = fields.Many2one('sbu.ui.help.topic', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    item_type = fields.Selection(
        selection=[
            ('overview', 'Overview'),
            ('button', 'Button / action'),
            ('tab', 'Tab / notebook page'),
            ('stat', 'Smart button'),
            ('filter', 'Filter / search'),
            ('field', 'Important field'),
            ('menu', 'Menu'),
        ],
        default='button',
        required=True,
    )
    title = fields.Char(required=True)
    body = fields.Html(sanitize=False)
    technical_key = fields.Char()
