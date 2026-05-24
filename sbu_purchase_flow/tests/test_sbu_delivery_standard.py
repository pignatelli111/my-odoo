# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuDeliveryStandard(TransactionCase):
    """Delivery rules: isolate from prod DB data (edited standards, extra rules)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Delivery = cls.env['sbu.delivery.standard'].sudo()
        cls._rules_before = cls.Delivery.search([])
        cls._rules_before.write({'active': False})
        cls._test_rules = cls.Delivery.create([
            {
                'name': 'Test LA aluminum path',
                'workflow_route': 'LA',
                'cost_family': 'aluminum_sheet',
                'delivery_pattern': 'via_sistemista_terzista',
                'intermediate_stops': 5,
                'sequence': 1,
            },
            {
                'name': 'Test glass direct',
                'cost_family': 'glass',
                'request_type': 'vt',
                'glass_mode': 'direct',
                'delivery_pattern': 'direct_site',
                'sequence': 2,
            },
            {
                'name': 'Test glass via terzista',
                'cost_family': 'glass',
                'request_type': 'vt',
                'glass_mode': 'via_terzista',
                'delivery_pattern': 'via_terzista',
                'sequence': 3,
            },
            {
                'name': 'Test VC/VS direct',
                'workflow_route': 'VC/VS',
                'cost_family': 'glass',
                'glass_mode': 'direct',
                'delivery_pattern': 'direct_site',
                'sequence': 4,
            },
            {
                'name': 'Test VC/VS via terzista',
                'workflow_route': 'VC/VS',
                'cost_family': 'glass',
                'glass_mode': 'via_terzista',
                'delivery_pattern': 'via_terzista',
                'sequence': 5,
            },
        ])

    @classmethod
    def tearDownClass(cls):
        cls._test_rules.unlink()
        cls._rules_before.write({'active': True})
        super().tearDownClass()

    def _project(self, **extra):
        vals = {
            'name': 'Delivery test job',
            'company_id': self.env.company.id,
        }
        vals.update(extra)
        return self.env['project.project'].create(vals)

    def _pr_line(self, project, request_type='rda', workflow_route='LA', **line_extra):
        pr = self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': request_type,
            'workflow_route': workflow_route,
            'company_id': self.env.company.id,
        })
        vals = {
            'request_id': pr.id,
            'name': 'Test line',
            'product_qty': 1.0,
        }
        vals.update(line_extra)
        return self.env['sbu.purchase.request.line'].create(vals)

    def test_la_line_gets_sistemista_terzista_path(self):
        terzista = self.env['res.partner'].create({'name': 'Terzista Nord', 'is_company': True})
        sistemista = self.env['res.partner'].create({'name': 'Sistemista SpA', 'supplier_rank': 1})
        project = self._project(
            sbu_site_subcontractor_id=terzista.id,
            sbu_system_supplier_id=sistemista.id,
        )
        line = self._pr_line(project, workflow_route='LA')
        self.assertIn('Sistemista SpA', line.destination)
        self.assertIn('Terzista Nord', line.destination)

    def test_glass_direct_skips_terzista(self):
        terzista = self.env['res.partner'].create({'name': 'Terzista Vetro', 'is_company': True})
        project = self._project(
            sbu_site_subcontractor_id=terzista.id,
            sbu_glass_delivery_mode='direct',
        )
        line = self._pr_line(project, request_type='vt', workflow_route='VC/VS')
        self.assertTrue(line.destination)
        self.assertNotIn('Terzista Vetro', line.destination)

    def test_glass_via_terzista_uses_site_subcontractor(self):
        terzista = self.env['res.partner'].create({'name': 'Terzista Unico', 'is_company': True})
        project = self._project(
            sbu_site_subcontractor_id=terzista.id,
            sbu_glass_delivery_mode='via_terzista',
        )
        line = self._pr_line(project, request_type='vt', workflow_route='VC/VS')
        self.assertIn('Terzista Unico', line.destination)

    def test_apply_overwrite_on_request(self):
        project = self._project(sbu_glass_delivery_mode='direct')
        line = self._pr_line(project, request_type='vt', workflow_route='VC/VS')
        line.destination = 'Manual override'
        pr = line.request_id
        pr.action_apply_delivery_standards()
        self.assertNotEqual(line.destination, 'Manual override')
        self.assertTrue(line.destination)
