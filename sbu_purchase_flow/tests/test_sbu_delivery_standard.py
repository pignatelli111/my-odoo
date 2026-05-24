# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Valid sbu.purchase.request.workflow_route selection keys (not free text).
ROUTE_LA = 'LA'
ROUTE_VC = 'VC/VS'


@tagged('post_install', '-at_install')
class TestSbuDeliveryStandard(TransactionCase):
    """Delivery rules: test rules at sequence 1 win over default data (seq 10+)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom = cls.env.ref('uom.product_uom_unit')
        cls.product = cls.env['product.product'].create({
            'name': 'Delivery test product',
            'type': 'consu',
            'purchase_ok': True,
        })

    def setUp(self):
        super().setUp()
        Delivery = self.env['sbu.delivery.standard'].sudo()
        self._qa_rules = Delivery.create([
            {
                'name': 'QA LA path (test)',
                'workflow_route': ROUTE_LA,
                'delivery_pattern': 'via_sistemista_terzista',
                'intermediate_stops': 5,
                'sequence': 1,
            },
            {
                'name': 'QA glass direct (test)',
                'workflow_route': ROUTE_VC,
                'cost_family': 'glass',
                'glass_mode': 'direct',
                'delivery_pattern': 'direct_site',
                'sequence': 1,
            },
            {
                'name': 'QA glass via terzista (test)',
                'workflow_route': ROUTE_VC,
                'cost_family': 'glass',
                'glass_mode': 'via_terzista',
                'delivery_pattern': 'via_terzista',
                'sequence': 2,
            },
        ])

    def tearDown(self):
        if getattr(self, '_qa_rules', None):
            self._qa_rules.unlink()
        super().tearDown()

    def _project(self, **extra):
        vals = {
            'name': 'Delivery test job',
            'company_id': self.env.company.id,
        }
        vals.update(extra)
        return self.env['project.project'].create(vals)

    def _pr_line(self, project, request_type='rda', workflow_route=ROUTE_LA, **line_extra):
        pr = self.env['sbu.purchase.request'].create({
            'project_id': project.id,
            'request_type': request_type,
            'workflow_route': workflow_route,
            'company_id': self.env.company.id,
        })
        vals = {
            'request_id': pr.id,
            'name': 'Test line',
            'product_id': self.product.id,
            'product_uom': self.uom.id,
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
        line = self._pr_line(project, workflow_route=ROUTE_LA)
        self.assertTrue(line.destination, line.destination)
        self.assertIn('Sistemista SpA', line.destination)
        self.assertIn('Terzista Nord', line.destination)

    def test_glass_direct_skips_terzista(self):
        terzista = self.env['res.partner'].create({'name': 'Terzista Vetro', 'is_company': True})
        project = self._project(
            sbu_site_subcontractor_id=terzista.id,
            sbu_glass_delivery_mode='direct',
        )
        line = self._pr_line(project, request_type='vt', workflow_route=ROUTE_VC)
        self.assertTrue(line.destination)
        self.assertNotIn('Terzista Vetro', line.destination)

    def test_glass_via_terzista_uses_site_subcontractor(self):
        terzista = self.env['res.partner'].create({'name': 'Terzista Unico', 'is_company': True})
        project = self._project(
            sbu_site_subcontractor_id=terzista.id,
            sbu_glass_delivery_mode='via_terzista',
        )
        line = self._pr_line(project, request_type='vt', workflow_route=ROUTE_VC)
        self.assertTrue(line.destination)
        self.assertIn('Terzista Unico', line.destination)

    def test_apply_overwrite_on_request(self):
        project = self._project(sbu_glass_delivery_mode='direct')
        line = self._pr_line(project, request_type='vt', workflow_route=ROUTE_VC)
        line.destination = 'Manual override'
        pr = line.request_id
        pr.action_apply_delivery_standards()
        self.assertNotEqual(line.destination, 'Manual override')
        self.assertTrue(line.destination)
