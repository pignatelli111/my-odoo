# -*- coding: utf-8 -*-
import uuid

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

    def _test_product(self, name, code_prefix='SBU-TST'):
        code = '%s-%s' % (code_prefix, uuid.uuid4().hex[:8])
        return self.env['product.product'].create({
            'name': name,
            'default_code': code,
            'type': 'consu',
            'purchase_ok': True,
        })

    def test_estimate_line_manual_pending_without_dimensions(self):
        line = self._estimate_line()
        self.assertTrue(line.manual_input_pending)
        line.write({'width_mm': 1000, 'height_mm': 2000})
        self.assertFalse(line.manual_input_pending)

    def test_bom_line_pending_when_needs_technical_confirm(self):
        eline = self._estimate_line()
        product = self._test_product('Glass test', 'SBU-VT')
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
        product = self._test_product('Bracket', 'SBU-ST')
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
