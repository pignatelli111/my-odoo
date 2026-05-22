# -*- coding: utf-8 -*-
"""Regression: duplicate field labels on the same model fail Odoo.sh builds."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuPurchaseFieldLabels(TransactionCase):
    """Odoo logs WARNING «have the same label» and Odoo.sh may fail the build."""

    @staticmethod
    def _duplicate_labels(env, model_name):
        Model = env[model_name]
        by_label = {}
        for fname, field in Model._fields.items():
            label = field.string
            if not label:
                continue
            by_label.setdefault(label, []).append(fname)
        return {label: names for label, names in by_label.items() if len(names) > 1}

    def test_purchase_request_labels_distinct(self):
        dups = self._duplicate_labels(self.env, 'sbu.purchase.request')
        self.assertEqual(dups, {}, dups)

    def test_purchase_request_line_labels_distinct(self):
        dups = self._duplicate_labels(self.env, 'sbu.purchase.request.line')
        self.assertEqual(dups, {}, dups)

    def test_purchase_request_offer_labels_distinct(self):
        dups = self._duplicate_labels(self.env, 'sbu.purchase.request.offer')
        self.assertEqual(dups, {}, dups)

    def test_purchase_wizard_labels_distinct(self):
        for model in (
            'sbu.purchase.request.line.bulk.wizard',
            'sbu.purchase.request.create.wizard',
        ):
            dups = self._duplicate_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')
