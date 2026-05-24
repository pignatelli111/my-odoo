# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .sbu_test_label_utils import duplicate_custom_field_labels


@tagged('post_install', '-at_install')
class TestSbuBulkWizards(TransactionCase):
    """Bulk apply mixin + estimate-area wizards (Cosimo UX point 3)."""

    BULK_WIZARD_MODELS = (
        'sbu.bulk.estimate.line.wizard',
        'sbu.bulk.estimate.bom.line.wizard',
        'sbu.bulk.estimate.sal.line.wizard',
    )

    def test_bulk_wizard_models_registered(self):
        for name in self.BULK_WIZARD_MODELS:
            self.assertEqual(self.env[name]._name, name)

    def test_bulk_wizard_labels_distinct(self):
        for model in self.BULK_WIZARD_MODELS:
            dups = duplicate_custom_field_labels(self.env, model)
            self.assertEqual(dups, {}, f'{model}: {dups}')

    def test_estimate_line_bulk_apply_cost_family(self):
        partner = self.env['res.partner'].create({'name': 'Bulk partner'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        lines = self.env['sbu.estimate.line'].create([
            {
                'estimate_id': estimate.id,
                'description': 'Row A',
                'pos': 'A1',
            },
            {
                'estimate_id': estimate.id,
                'description': 'Row B',
                'pos': 'B1',
            },
        ])
        wiz = self.env['sbu.bulk.estimate.line.wizard'].with_context(
            active_domain=[('id', 'in', lines.ids)],
        ).create({
            'apply_scope': 'filtered',
            'apply_cost_family': True,
            'cost_family': 'glass',
        })
        wiz.action_apply()
        self.assertEqual(set(lines.mapped('cost_family')), {'glass'})
