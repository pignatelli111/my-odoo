# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuSalPlanningStatus(TransactionCase):
    def test_sal_status_planning_when_only_sal_percentages(self):
        partner = self.env['res.partner'].create({'name': 'SAL planning partner'})
        est = self.env['sbu.estimate'].create({'partner_id': partner.id})
        sal = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': est.id,
            'description': 'Voce con solo % SAL (nessun foglio SAL)',
            'qty_contract': 1.0,
            'unit_price': 1000.0,
            'sal_1_pct': 100.0,
        })
        self.assertEqual(sal.sal_status, 'planning')

    def test_sal_status_prepared_when_contract_but_no_sal_pct(self):
        partner = self.env['res.partner'].create({'name': 'SAL prepared partner'})
        est = self.env['sbu.estimate'].create({'partner_id': partner.id})
        sal = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': est.id,
            'description': 'Voce senza % SAL',
            'qty_contract': 1.0,
            'unit_price': 500.0,
        })
        self.assertEqual(sal.sal_status, 'prepared')
