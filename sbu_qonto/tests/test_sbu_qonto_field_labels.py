# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuQontoFieldLabels(TransactionCase):
    """Regression: duplicate labels on sbu.qonto.transaction fail Odoo.sh builds."""

    def test_qonto_transaction_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.qonto.transaction')
        self.assertEqual(dups, {}, dups)
