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
        ):
            dups = duplicate_custom_field_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')
