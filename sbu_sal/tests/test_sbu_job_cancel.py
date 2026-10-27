# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestSbuJobCancel(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.write({'group_ids': [(4, cls.env.ref(xmlid).id) for xmlid in (
            'project.group_project_manager', 'sbu_estimate.group_sbu_estimate_user',
        )]})
        cls.env.company.write({
            'sbu_sal_retention_account_id': cls.company_data['default_account_revenue'].id,
            'sbu_sal_default_tax_ids': [(6, 0, [])],
        })
        cls.manager = new_test_user(
            cls.env, 'job_manager',
            groups='project.group_project_manager,account.group_account_manager',
            company_id=cls.env.company.id, company_ids=[(6, 0, cls.env.company.ids)],
        )

    def _job(self, name='Job'):
        customer = self.env['res.partner'].create({'name': f'{name} customer'})
        estimate = self.env['sbu.estimate'].create({'partner_id': customer.id})
        contract = self.env['sbu.estimate.sal.line'].create({
            'estimate_id': estimate.id, 'item_ref': 'F1', 'description': 'Facade',
            'uom_type': 'mq', 'qty_contract': 100.0, 'unit_price': 250.0,
        })
        project = self.env['project.project'].create({'name': name, 'sbu_estimate_id': estimate.id})
        estimate.write({'state': 'won', 'project_id': project.id})
        sheet = self.env['sbu.sal.sheet'].create({'project_id': project.id, 'retention_percent': 5.0})
        self.env['sbu.sal.sheet.line'].create({
            'sheet_id': sheet.id, 'estimate_sal_line_id': contract.id, 'description': 'Facade',
            'contract_amount': 25000.0, 'percent_this_sal': 10.0,
        })
        return project, estimate, sheet

    def _posted_invoice(self, sheet):
        sheet.action_confirm()
        sheet.action_create_draft_invoice()
        sheet.invoice_id.action_post()
        return sheet.invoice_id

    def _wizard(self, project):
        return self.env['sbu.project.cancel.wizard'].with_user(self.manager).with_context(
            default_project_id=project.id).create({})

    def test_delete_job_with_posted_invoice_is_blocked(self):
        project, _estimate, sheet = self._job('Blocked job')
        invoice = self._posted_invoice(sheet)
        with self.assertRaises(UserError) as err:
            project.unlink()
        self.assertIn(invoice.name, str(err.exception))
        self.assertIn('Cancel job', str(err.exception))

    def test_cancel_job_with_drafts_only(self):
        project, estimate, sheet = self._job('Draft job')
        sheet.action_confirm()
        certificate = sheet.certificate_ids.filtered(lambda c: c.state == 'draft')
        wizard = self._wizard(project)
        actions = {(l.res_model, l.res_id): l.action for l in wizard.line_ids}
        self.assertEqual(actions[('sbu.sal.sheet', sheet.id)], 'cancel')
        self.assertEqual(actions[('sbu.estimate', estimate.id)], 'keep')
        if certificate:
            self.assertEqual(actions[('sbu.payment.certificate', certificate.id)], 'delete')
        wizard.write({'reason': 'Customer withdrew', 'confirm': True})
        wizard.action_cancel_job()
        self.assertEqual(sheet.state, 'cancelled')
        self.assertFalse(certificate.exists())
        self.assertFalse(project.active)
        self.assertEqual(project.sbu_state, 'archived')
        self.assertEqual(estimate.state, 'cancelled')
        self.assertIn('Customer withdrew', project.message_ids[:1].body)

    def test_cancel_job_with_posted_invoice_prepares_credit_note(self):
        project, _estimate, sheet = self._job('Invoiced job')
        invoice = self._posted_invoice(sheet)
        wizard = self._wizard(project)
        line = wizard.line_ids.filtered(lambda l: l.res_model == 'account.move' and l.res_id == invoice.id)
        self.assertEqual(line.action, 'credit_note')
        self.assertEqual(wizard.credit_note_count, 1)
        action = wizard.action_create_credit_notes()
        credit_note = self.env['account.move'].search(action['domain'])
        self.assertEqual(credit_note.move_type, 'out_refund')
        self.assertEqual(credit_note.state, 'draft')
        self.assertEqual(credit_note.reversed_entry_id, invoice)
        wizard.write({'reason': 'Contract terminated', 'confirm': True})
        wizard.action_cancel_job()
        self.assertFalse(project.active)
        self.assertEqual(invoice.state, 'posted', 'posted invoices are never cancelled by the wizard')

    def test_cancel_requires_reason_and_confirmation(self):
        project, _estimate, _sheet = self._job('Unconfirmed job')
        wizard = self._wizard(project)
        with self.assertRaises(UserError):
            wizard.action_cancel_job()
        wizard.confirm = True
        with self.assertRaises(UserError):
            wizard.action_cancel_job()
        self.assertTrue(project.active)

    def test_force_delete_admin_only_and_never_posted_invoices(self):
        project, estimate, sheet = self._job('Forced job')
        approver = new_test_user(
            self.env, 'uat_approver', groups='sbu_estimate.group_sbu_estimate_approver',
            company_id=self.env.company.id, company_ids=[(6, 0, self.env.company.ids)],
        )
        with self.assertRaises(UserError):
            estimate.with_user(approver).action_open_force_delete_wizard()
        invoice = self._posted_invoice(sheet)
        with self.assertRaises(UserError):
            estimate._sbu_force_delete_with_cleanup()
        self.assertEqual(invoice.state, 'posted')
        self.assertTrue(project.exists())
