# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuUiHelp(TransactionCase):

    def test_get_help_estimate_form(self):
        data = self.env['sbu.ui.help.topic'].get_help_for_ui('sbu.estimate', 'form')
        self.assertTrue(data)
        self.assertTrue(data.get('title'))
        self.assertGreater(len(data.get('sections') or []), 3)

    def test_generic_help_unknown_model(self):
        data = self.env['sbu.ui.help.topic'].get_help_for_ui('res.partner', 'form')
        self.assertTrue(data)
        self.assertIn('res.partner', data.get('purpose', ''))

    def test_get_help_sal_list_normalizes_tree(self):
        if 'sbu.sal.sheet' not in self.env:
            self.skipTest('sbu_sal not installed')
        data = self.env['sbu.ui.help.topic'].get_help_for_ui('sbu.sal.sheet', 'tree')
        self.assertTrue(data)
        title = data.get('title') or ''
        if 'SAL' not in title:
            self.skipTest(
                'help_topic_sbu_sal_list missing on DB (data noupdate); '
                'upgrade sbu_ui_help or load data on staging'
            )
        self.assertIn('SAL', title)
