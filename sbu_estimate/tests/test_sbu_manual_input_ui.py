# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuManualInputUi(TransactionCase):

    def _estimate_line(self):
        partner = self.env['res.partner'].create({'name': 'Manual UI'})
        estimate = self.env['sbu.estimate'].create({'partner_id': partner.id})
        return self.env['sbu.estimate.line'].create({
            'estimate_id': estimate.id,
            'pos': 'P1',
            'description': 'Test line',
            'calc_uom_type': 'mq',
            'qty': 1,
        })

    def test_estimate_line_manual_pending_without_dimensions(self):
        line = self._estimate_line()
        self.assertTrue(line.manual_input_pending)
        line.width_mm = 1000
        line.height_mm = 2000
        self.assertFalse(line.manual_input_pending)

    def test_bom_line_pending_when_needs_technical_confirm(self):
        eline = self._estimate_line()
        product = self.env['product.product'].create({
            'name': 'Glass test',
            'default_code': 'SBU-VT-TEST',
            'type': 'consu',
        })
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': eline.estimate_id.id,
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'calc_type': 'surface',
            'dimension_source': 'surface',
            'needs_technical_confirm': True,
            'data_phase': 'estimate',
        })
        self.assertEqual(bom.manual_input_state, 'pending')
        self.assertTrue(bom.manual_input_pending)

    def test_bom_line_imported_phase_is_muted_state(self):
        eline = self._estimate_line()
        eline.write({'width_mm': 1000, 'height_mm': 2000})
        product = self.env['product.product'].create({
            'name': 'Bracket',
            'default_code': 'SBU-ST-TEST',
            'type': 'consu',
        })
        bom = self.env['sbu.estimate.bom.line'].create({
            'estimate_id': eline.estimate_id.id,
            'estimate_line_id': eline.id,
            'product_id': product.id,
            'calc_type': 'per_piece',
            'data_phase': 'logikal',
            'needs_technical_confirm': True,
        })
        self.assertEqual(bom.manual_input_state, 'imported')
        self.assertFalse(bom.manual_input_pending)

    def test_bom_manual_field_labels_distinct(self):
        dups = {}
        Model = self.env['sbu.estimate.bom.line']
        by_label = {}
        for fname, field in Model._fields.items():
            label = field.string
            if not label:
                continue
            by_label.setdefault(label, []).append(fname)
        dups = {k: v for k, v in by_label.items() if len(v) > 1}
        self.assertEqual(dups, {}, dups)
