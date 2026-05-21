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
        """Smoke: finance link fields exist (Odoo 19: do not assert field.compute name)."""
        sal_line = self.env['sbu.estimate.sal.line']
        for fname in (
            'invoice_id',
            'payment_certificate_id',
            'invoice_cdp_summary',
            'certificate_count',
            'invoice_count',
        ):
            field = sal_line._fields[fname]
            self.assertTrue(field.compute, f'{fname} must be computed')
