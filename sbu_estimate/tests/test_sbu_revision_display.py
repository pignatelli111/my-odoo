# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.sbu_estimate.models.sbu_revision_display import (
    sbu_estimate_revision_label,
    sbu_revision_sort_key,
)


@tagged('post_install', '-at_install')
class TestSbuRevisionDisplay(TransactionCase):

    def test_revision_sort_key(self):
        self.assertEqual(sbu_revision_sort_key('REV00'), 0)
        self.assertEqual(sbu_revision_sort_key('REV01'), 1)
        self.assertEqual(sbu_revision_sort_key('REV02'), 2)
        self.assertLess(sbu_revision_sort_key('REV01'), sbu_revision_sort_key('REV02'))

    def test_estimate_label_includes_rev_and_date(self):
        partner = self.env['res.partner'].create({'name': 'Rev Client'})
        est = self.env['sbu.estimate'].create({
            'partner_id': partner.id,
            'name': 'PTEST-REV',
            'revision': 'REV02',
            'date': '2026-05-20',
            'job_site': 'BLACKROCK',
        })
        label = sbu_estimate_revision_label(est)
        self.assertIn('REV02', label)
        self.assertIn('2026-05-20', label)
        self.assertIn('BLACKROCK', label)
        self.assertEqual(est.sbu_display_label, label)

    def test_latest_revision_flag(self):
        partner = self.env['res.partner'].create({'name': 'Chain Client'})
        e0 = self.env['sbu.estimate'].create({
            'partner_id': partner.id,
            'name': 'PCHAIN',
            'revision': 'REV00',
        })
        e1 = self.env['sbu.estimate'].create({
            'partner_id': partner.id,
            'name': 'PCHAIN',
            'revision': 'REV01',
            'previous_revision_id': e0.id,
        })
        e0.invalidate_recordset(['sbu_is_latest_revision'])
        self.assertTrue(e1.sbu_is_latest_revision)
        self.assertFalse(e0.sbu_is_latest_revision)

    def test_project_label_from_estimate(self):
        partner = self.env['res.partner'].create({'name': 'Job Client'})
        est = self.env['sbu.estimate'].create({
            'partner_id': partner.id,
            'name': 'PJOB',
            'revision': 'REV01',
            'date': '2026-05-15',
            'job_site': 'Site A',
        })
        project = self.env['project.project'].create({
            'name': '[P0099_2026] Site A',
            'sbu_project_code': 'P0099_2026',
            'sbu_job_site': 'Site A',
            'sbu_estimate_id': est.id,
            'company_id': self.env.company.id,
        })
        self.assertIn('REV01', project.sbu_revision_label)
        self.assertIn('2026-05-15', project.sbu_revision_label)
        self.assertIn('P0099_2026', project.sbu_revision_label)
        name = dict(project.name_get())[project.id]
        self.assertEqual(name, project.sbu_revision_label)
