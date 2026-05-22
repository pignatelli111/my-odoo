# -*- coding: utf-8 -*-
"""Regression: duplicate field labels on the same model fail Odoo.sh builds."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuPurchaseFieldLabels(TransactionCase):
    """Odoo logs WARNING «have the same label» and Odoo.sh may fail the build."""

    def test_purchase_request_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.purchase.request')
        self.assertEqual(dups, {}, dups)

    def test_purchase_request_line_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.purchase.request.line')
        self.assertEqual(dups, {}, dups)

    def test_purchase_request_offer_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.purchase.request.offer')
        self.assertEqual(dups, {}, dups)

    def test_purchase_wizard_labels_distinct(self):
        for model in (
            'sbu.purchase.request.line.bulk.wizard',
            'sbu.purchase.request.create.wizard',
        ):
            dups = duplicate_custom_field_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')

    def test_project_budget_family_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.project.budget.family')
        self.assertEqual(dups, {}, dups)
