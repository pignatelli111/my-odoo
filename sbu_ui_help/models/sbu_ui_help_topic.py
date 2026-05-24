# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SbuUiHelpTopic(models.Model):
    _name = 'sbu.ui.help.topic'
    _description = 'SBU contextual UI help'
    _order = 'model, view_mode, sequence, id'

    name = fields.Char(string='Title', required=True, translate=True)
    active = fields.Boolean(default=True)
    model = fields.Char(
        string='Model',
        required=True,
        index=True,
        help='Technical model name, e.g. sbu.estimate',
    )
    view_mode = fields.Selection(
        selection=[
            ('any', 'Any view'),
            ('list', 'List'),
            ('form', 'Form'),
            ('kanban', 'Kanban'),
            ('search', 'Search'),
        ],
        string='View type',
        default='any',
        required=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    purpose = fields.Html(string='Purpose', translate=True, sanitize=False)
    item_ids = fields.One2many(
        'sbu.ui.help.item',
        'topic_id',
        string='Buttons & tabs',
    )

    @api.model
    def get_help_for_ui(self, model, view_mode=None):
        """Return help payload for the current screen (user language)."""
        if not model:
            return False
        view_key = (view_mode or 'form').replace('tree', 'list')
        topics = self.search([
            ('active', '=', True),
            ('model', '=', model),
            ('view_mode', 'in', ('any', view_key)),
        ], order='sequence, id')
        if not topics:
            return self._generic_help(model, view_key)
        topic = topics[0].with_env(self.env)
        items = topic.item_ids.sorted('sequence')
        return {
            'title': topic.name,
            'purpose': topic.purpose or '',
            'sections': [
                {
                    'type': item.item_type,
                    'title': item.title,
                    'body': item.body or '',
                }
                for item in items
            ],
        }

    @api.model
    def _generic_help(self, model, view_mode):
        return {
            'title': _('Help'),
            'purpose': _(
                '<p>No detailed guide is configured yet for <strong>%(model)s</strong> '
                '(%(view)s view).</p>'
                '<p>Ask your administrator to add content under '
                '<em>Settings → SBU → Context help</em>, or check the Suburban training documents.</p>'
            ) % {'model': model, 'view': view_mode},
            'sections': [],
        }


class SbuUiHelpItem(models.Model):
    _name = 'sbu.ui.help.item'
    _description = 'SBU help line (button, tab, …)'
    _order = 'sequence, id'

    topic_id = fields.Many2one(
        'sbu.ui.help.topic',
        required=True,
        ondelete='cascade',
    )
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
        string='Kind',
        default='button',
        required=True,
    )
    title = fields.Char(string='Label', required=True, translate=True)
    body = fields.Html(string='Explanation', translate=True, sanitize=False)
    technical_key = fields.Char(
        string='Technical key',
        help='Optional: button name, tab name=, or filter name for maintainers.',
    )
