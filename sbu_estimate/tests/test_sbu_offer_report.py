# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.tests.sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuOfferReport(TransactionCase):
    """Cosimo point 16: structured commercial terms + offer PDF."""

    def test_commercial_term_labels_distinct(self):
        dups = duplicate_custom_field_labels(self.env, 'sbu.estimate.commercial.term')
        self.assertEqual(dups, {}, dups)

    def test_default_terms_and_print_offer(self):
        partner = self.env['res.partner'].create({'name': 'Offer print client'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        self.env.flush_all()
        if not estimate.commercial_term_ids:
            estimate.action_load_default_commercial_terms()
        self.assertGreaterEqual(len(estimate.commercial_term_ids), 5)
        pay = estimate.commercial_term_ids.filtered(
            lambda t: t.term_category == 'payment' and t.choice == 'included'
        )
        self.assertGreaterEqual(len(pay), 2)
        exc = estimate.commercial_term_ids.filtered(
            lambda t: t.term_category == 'exclusion' and t.choice == 'excluded'
        )
        self.assertGreaterEqual(len(exc), 1)
        self.assertGreater(len(pay), 0)
        ret = estimate.commercial_term_ids.filtered(
            lambda t: t.term_category == 'retention' and t.choice == 'included'
        )
        self.assertTrue(ret)
        self.assertGreater(ret[0].percent_value, 0.0)
        estimate.offer_retention_percent = 0.0
        self.assertEqual(
            estimate._sbu_effective_offer_retention_percent(),
            ret[0].percent_value,
        )
        estimate._sbu_sync_offer_retention_from_terms()
        self.assertEqual(estimate.offer_retention_percent, ret[0].percent_value)
        report = self.env.ref('sbu_estimate.action_report_sbu_estimate_offer', raise_if_not_found=False)
        self.assertTrue(report)
        action = estimate.action_print_offer()
        self.assertIn(
            action.get('type'),
            ('ir.actions.report', 'ir.actions.act_window'),
            action,
        )
        if action.get('type') == 'ir.actions.act_window':
            self.fail(
                'Offer print opened layout wizard; set company external layout '
                'or use discard_logo_check in action_print_offer.'
            )
        self.assertEqual(
            action.get('report_name'),
            'sbu_estimate.report_sbu_estimate_offer_document',
        )
