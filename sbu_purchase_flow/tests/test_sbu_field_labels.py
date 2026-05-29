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
            'sbu.purchase.request.excel.import.wizard',
            'sbu.purchase.request.bom.import.wizard',
            'sbu.project.tms.import.wizard',
        ):
            dups = duplicate_custom_field_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')

    def test_tms_origin_model_labels_distinct(self):
        for model in (
            'sbu.vdc.catalog',
            'sbu.lds.entry',
            'sbu.drawing.register',
        ):
            dups = duplicate_custom_field_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')

    def test_project_tms_stat_count_labels_distinct(self):
        """Regression: stat button counts must not share labels with One2many fields."""
        project = self.env['project.project']
        labels = [
            project._fields['sbu_lds_entry_ids'].string,
            project._fields['sbu_lds_entry_count'].string,
            project._fields['sbu_drawing_register_ids'].string,
            project._fields['sbu_drawing_register_count'].string,
            project._fields['sbu_purchase_request_count'].string,
        ]
        self.assertEqual(len(labels), len(set(labels)), labels)

    def test_project_budget_family_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.project.budget.family')
        self.assertEqual(dups, {}, dups)

    def test_delivery_standard_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.delivery.standard')
        self.assertEqual(dups, {}, dups)
