# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSbuColumnSupplier(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.pvc = Partner.create({'name': 'PVC Serramenti', 'supplier_rank': 1})
        cls.glass = Partner.create({'name': 'Vetreria', 'supplier_rank': 1})
        cls.general = Partner.create({'name': 'General supplier', 'supplier_rank': 1})
        customer = Partner.create({'name': 'Column customer'})
        cls.estimate = cls.env['sbu.estimate'].create({'partner_id': customer.id})
        for width in (1000, 1200):
            cls.env['sbu.estimate.line'].create({
                'estimate_id': cls.estimate.id, 'description': f'Window {width}',
                'width_mm': width, 'height_mm': 1500, 'qty': 2,
                'price_serramento_cad': 300.0, 'price_vetro_cad': 80.0, 'price_smontaggio_cad': 60.0,
            })
        cls.estimate._sbu_create_bom_from_anaco_lines()
        cls.project = cls.env['project.project'].create({'name': 'Column job', 'sbu_estimate_id': cls.estimate.id})

    def _row(self, field):
        return self.estimate.column_supplier_ids.filtered(lambda r: r.column_field == field)

    def test_columns_prepared_with_totals(self):
        fields_used = set(self.estimate.column_supplier_ids.mapped('column_field'))
        self.assertTrue({'price_serramento_cad', 'price_vetro_cad', 'price_smontaggio_cad'} <= fields_used)
        self.assertNotIn('price_nolo_cad', fields_used, 'unused columns are not listed')
        self.assertAlmostEqual(self._row('price_vetro_cad').column_total, 80.0 * 2 * 2)

    def test_rfq_split_by_column_supplier(self):
        self._row('price_serramento_cad').partner_id = self.pvc
        self._row('price_vetro_cad').partner_id = self.glass
        boms = self.estimate.item_bom_line_ids
        window_boms = boms.filtered(lambda b: b.product_id == self._row('price_serramento_cad').product_id)
        self.assertTrue(window_boms)
        self.assertEqual(window_boms.vendor_id, self.pvc)

        request = self.env['sbu.purchase.request'].create({
            'project_id': self.project.id,
            'request_type': 'rda',
            'technical_data_state': 'ready_for_po',
            'vendor_id': self.general.id,
            'company_id': self.env.company.id,
        })
        request._load_selected_bom_lines(boms)
        self.assertEqual(
            set(request.line_ids.mapped('vendor_id').ids), {self.pvc.id, self.glass.id},
            'lines of columns without supplier stay empty',
        )
        request.action_create_rfq()
        orders = request.purchase_order_ids
        by_vendor = {po.partner_id: po for po in orders}
        self.assertEqual(set(by_vendor), {self.pvc, self.glass, self.general})

        def products(vendor):
            return set(by_vendor[vendor].order_line.mapped('product_id').ids)

        self.assertEqual(products(self.pvc), {self._row('price_serramento_cad').product_id.id})
        self.assertEqual(products(self.glass), {self._row('price_vetro_cad').product_id.id})
        self.assertEqual(products(self.general), {self._row('price_smontaggio_cad').product_id.id})

    def test_suppliers_kept_when_columns_refresh(self):
        self._row('price_vetro_cad').partner_id = self.glass
        self.estimate.action_sbu_prepare_column_suppliers()
        self.assertEqual(self._row('price_vetro_cad').partner_id, self.glass)
        self.assertEqual(len(self.estimate.column_supplier_ids.filtered(
            lambda r: r.column_field == 'price_vetro_cad')), 1)
