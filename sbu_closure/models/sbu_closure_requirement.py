# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SbuClosureRequirement(models.Model):
    _name = 'sbu.closure.requirement'
    _description = 'SBU project closure checklist line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    document_type_id = fields.Many2one(
        'sbu.closure.document.type',
        string='Document type',
        required=True,
        ondelete='restrict',
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Title',
        required=True,
        help='Usually copied from the document type; may be edited per job.',
    )
    required = fields.Boolean(
        string='Required',
        default=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ('pending', 'To do'),
            ('done', 'Done'),
            ('waived', 'Waived'),
            ('na', 'N/A'),
        ],
        string='Status',
        default='pending',
        tracking=True,
    )
    due_date = fields.Date(string='Due date')
    external_url = fields.Char(
        string='Link',
        help='URL to DOP / certificate / final pack in OneDrive, e-mail archive, or PA portal.',
    )
    note = fields.Text(string='Notes')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'sbu_closure_requirement_attachment_rel',
        'requirement_id',
        'attachment_id',
        string='Attachments',
        help='Final PDFs or signed scans stored in Odoo (optional).',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
    )
    sbu_project_state = fields.Selection(
        related='project_id.sbu_state',
        string='Job state',
        store=False,
        readonly=True,
    )

    _sbu_closure_project_type_uniq = models.Constraint(
        'unique(project_id, document_type_id)',
        'This document type is already listed once for this project.',
    )

    def action_mark_done(self):
        self.filtered(lambda r: r.state == 'pending').write({'state': 'done'})

    def action_mark_pending(self):
        self.write({'state': 'pending'})

    def action_mark_waived(self):
        self.filtered(lambda r: r.state == 'pending').write({'state': 'waived'})

    def action_mark_na(self):
        self.filtered(lambda r: r.state == 'pending').write({'state': 'na'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('document_type_id') and not vals.get('name'):
                dt = self.env['sbu.closure.document.type'].browse(vals['document_type_id'])
                vals['name'] = dt.name
            if vals.get('document_type_id') and 'required' not in vals:
                dt = self.env['sbu.closure.document.type'].browse(vals['document_type_id'])
                vals['required'] = dt.default_required
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('Set the line back to “To do” before deleting it.'))
        return super().unlink()
