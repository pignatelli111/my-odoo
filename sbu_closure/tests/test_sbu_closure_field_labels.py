# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuClosureFieldLabels(TransactionCase):
    def test_closure_models_labels_distinct(self):
        for model in (
            'sbu.closure.requirement',
            'sbu.closure.requirement.bulk.wizard',
        ):
            dups = duplicate_custom_field_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')
