# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuEstimateFieldLabels(TransactionCase):
    """Regression: duplicate SBU field labels (excludes mail.thread internals)."""

    def test_estimate_models_labels_distinct(self):
        for model in (
            'sbu.estimate',
            'sbu.estimate.line',
            'sbu.estimate.bom.line',
            'sbu.estimate.sal.line',
            'sbu.estimate.commercial.term',
            'sbu.bulk.estimate.line.wizard',
            'sbu.bulk.estimate.bom.line.wizard',
            'sbu.bulk.estimate.sal.line.wizard',
        ):
            dups = duplicate_custom_field_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')

    def test_project_sbu_field_labels_distinct(self):
        dups = duplicate_custom_field_labels(
            self.env, 'project.project', field_prefix='sbu_',
        )
        self.assertEqual(dups, {}, dups)

    def test_all_sbu_registry_models_labels_distinct(self):
        """Catch duplicate labels on any sbu.* model (Odoo.sh install WARNING)."""
        failures = {}
        for model_name in sorted(self.env.registry):
            if not model_name.startswith('sbu.'):
                continue
            dups = duplicate_custom_field_labels(self.env, model_name)
            if dups:
                failures[model_name] = dups
        self.assertEqual(failures, {}, failures)
