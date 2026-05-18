# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuSalInstall(TransactionCase):
    """Smoke test so Odoo.sh records sbu_sal in the test suite."""

    def test_models_registered(self):
        self.assertTrue(self.env['sbu.sal.sheet']._name)
        self.assertTrue(self.env['sbu.payment.certificate']._name)

    def test_sal_sheet_field_labels_are_distinct(self):
        """Regression: duplicate labels on sbu.sal.sheet form trigger Odoo.sh install WARNING."""
        sheet = self.env['sbu.sal.sheet']
        labels = [
            sheet._fields['line_ids'].string,
            sheet._fields['certificate_ids'].string,
            sheet._fields['certificate_count'].string,
        ]
        self.assertEqual(len(labels), len(set(labels)), labels)

    def test_finance_fields_are_computed(self):
        """Smoke: finance link fields exist and use dedicated compute methods."""
        sal_line = self.env['sbu.estimate.sal.line']
        self.assertEqual(
            sal_line._fields['invoice_id'].compute,
            '_compute_finance_documents',
        )
        self.assertEqual(
            sal_line._fields['certificate_count'].compute,
            '_compute_finance_document_counts',
        )
        self.assertEqual(
            sal_line._fields['invoice_cdp_summary'].compute,
            '_compute_invoice_cdp_summary',
        )
