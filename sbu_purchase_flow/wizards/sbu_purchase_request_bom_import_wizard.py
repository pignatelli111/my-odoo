# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SbuPurchaseRequestBomImportWizard(models.TransientModel):
    _name = 'sbu.purchase.request.bom.import.wizard'
    _description = 'Select estimate BOM lines to load on purchase request'

    request_id = fields.Many2one(
        'sbu.purchase.request',
        string='Purchase request',
        required=True,
        ondelete='cascade',
    )
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Source estimate',
        related='request_id.estimate_id',
        readonly=True,
    )
    workflow_route = fields.Selection(
        related='request_id.workflow_route',
        readonly=True,
    )
    replace_existing = fields.Boolean(
        string='Replace existing lines',
        help='If set, current request lines are removed before loading the selection.',
    )
    import_scope = fields.Selection(
        [
            ('route', 'Lines matching document route'),
            ('all', 'All estimate BOM lines'),
        ],
        string='Show',
        required=True,
        default='route',
    )
    bom_line_ids = fields.Many2many(
        'sbu.estimate.bom.line',
        'sbu_pr_bom_import_wiz_rel',
        'wizard_id',
        'bom_line_id',
        string='BOM lines to load',
        domain="[('estimate_id', '=', estimate_id)]",
    )
    available_count = fields.Integer(
        string='Available in scope',
        compute='_compute_counts',
    )
    selected_count = fields.Integer(
        string='Selected',
        compute='_compute_counts',
    )
    already_linked_count = fields.Integer(
        string='Already on request',
        compute='_compute_counts',
    )

    @api.depends('import_scope', 'request_id', 'bom_line_ids')
    def _compute_counts(self):
        for wiz in self:
            available = wiz._bom_lines_for_scope()
            linked = wiz._already_linked_bom_ids()
            wiz.available_count = len(available)
            wiz.selected_count = len(wiz.bom_line_ids)
            wiz.already_linked_count = len(available.filtered(lambda b: b.id in linked))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        req_id = (
            self.env.context.get('default_request_id')
            or (self.env.context.get('active_model') == 'sbu.purchase.request'
                and self.env.context.get('active_id'))
        )
        if req_id:
            res['request_id'] = req_id
        if self.env.context.get('default_replace_existing'):
            res['replace_existing'] = True
        req = self.env['sbu.purchase.request'].browse(req_id) if req_id else self.env['sbu.purchase.request']
        if req:
            route_lines = req._candidate_bom_lines_for_import(scope='route')
            if route_lines:
                res['import_scope'] = 'route'
                candidates = route_lines
            else:
                res['import_scope'] = 'all'
                candidates = req._candidate_bom_lines_for_import(scope='all')
            linked = {
                bid for bid in req.line_ids.mapped('source_bom_line_id').ids if bid
            }
            res['bom_line_ids'] = [(6, 0, candidates.filtered(lambda b: b.id not in linked).ids)]
        return res

    def _already_linked_bom_ids(self):
        self.ensure_one()
        return {
            bid for bid in self.request_id.line_ids.mapped('source_bom_line_id').ids if bid
        }

    def _default_selection_ids(self, candidate_lines):
        linked = self._already_linked_bom_ids()
        return candidate_lines.filtered(lambda b: b.id not in linked)

    def _bom_lines_for_scope(self, scope=None):
        self.ensure_one()
        scope = scope or self.import_scope
        return self.request_id._candidate_bom_lines_for_import(scope=scope)

    @api.onchange('import_scope')
    def _onchange_import_scope(self):
        candidates = self._bom_lines_for_scope()
        self.bom_line_ids = self._default_selection_ids(candidates)

    def action_select_route_lines(self):
        self.write({
            'import_scope': 'route',
            'bom_line_ids': [(6, 0, self._bom_lines_for_scope('route').ids)],
        })

    def action_select_all_estimate(self):
        self.write({
            'import_scope': 'all',
            'bom_line_ids': [(6, 0, self._bom_lines_for_scope('all').ids)],
        })

    def action_select_new_only(self):
        candidates = self._bom_lines_for_scope()
        self.bom_line_ids = self._default_selection_ids(candidates)

    def action_clear_selection(self):
        self.bom_line_ids = [(5, 0, 0)]

    def action_load(self):
        self.ensure_one()
        if not self.request_id.estimate_id:
            raise UserError(_('The project has no linked source estimate.'))
        if not self.bom_line_ids:
            raise UserError(_('Select at least one BOM line to load.'))
        return self.request_id._load_selected_bom_lines(
            self.bom_line_ids,
            clear=self.replace_existing,
        )
