# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.sbu_estimate.models.sbu_cost_family import SBU_COST_FAMILY_SELECTION

_BOM_CALC_TYPE_SELECTION = [
    ('lump_sum', 'Lump sum'),
    ('per_piece', 'Per piece'),
    ('linear', 'Linear (m)'),
    ('surface', 'Surface (m²)'),
    ('pack', 'Pack / kit'),
]

_BOM_DATA_PHASE_SELECTION = [
    ('estimate', 'ANACO estimate'),
    ('logikal', 'Logikal draft'),
    ('technical', 'Technical document'),
]


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
    filter_estimate_line_id = fields.Many2one(
        'sbu.estimate.line',
        string='ANACO position',
        domain="[('estimate_id', '=', estimate_id)]",
        help='Limit the list to one estimate line (e.g. F1, F1a).',
    )
    filter_cost_family = fields.Selection(
        selection=SBU_COST_FAMILY_SELECTION,
        string='Cost family',
    )
    filter_workflow_route = fields.Char(
        string='Workflow route',
        help='e.g. LA, VC/VS, ST — matches the ANACO line route.',
    )
    filter_calc_type = fields.Selection(
        selection=_BOM_CALC_TYPE_SELECTION,
        string='Filter: calculation type',
    )
    filter_data_phase = fields.Selection(
        selection=_BOM_DATA_PHASE_SELECTION,
        string='Filter: data phase',
    )
    filter_product_category_id = fields.Many2one(
        'product.category',
        string='Product category',
    )
    filter_text = fields.Char(
        string='Search text',
        help='Matches component label, description, product name or internal reference.',
    )
    line_ids = fields.One2many(
        'sbu.purchase.request.bom.import.wizard.line',
        'wizard_id',
        string='BOM lines',
    )
    available_count = fields.Integer(
        string='Available in scope',
        compute='_compute_counts',
    )
    filtered_count = fields.Integer(
        string='Visible after filters',
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

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wiz in wizards:
            wiz._rebuild_line_list(preserve_selection=False, auto_select_new=True)
        return wizards

    @api.depends(
        'line_ids',
        'line_ids.selected',
        'import_scope',
        'request_id',
        'request_id.line_ids.source_bom_line_id',
    )
    def _compute_counts(self):
        for wiz in self:
            available = wiz._bom_lines_for_scope()
            linked = wiz._already_linked_bom_ids()
            wiz.available_count = len(available)
            wiz.filtered_count = len(wiz.line_ids)
            wiz.selected_count = len(wiz.line_ids.filtered('selected'))
            wiz.already_linked_count = len(
                wiz.line_ids.filtered(lambda ln: ln.bom_line_id.id in linked)
            )

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
            res['import_scope'] = 'route' if route_lines else 'all'
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

    def _filtered_bom_candidates(self):
        """Scope (route / all) intersected with optional wizard filters."""
        self.ensure_one()
        lines = self._bom_lines_for_scope()
        if self.filter_estimate_line_id:
            lines = lines.filtered(
                lambda b: b.estimate_line_id == self.filter_estimate_line_id
            )
        if self.filter_cost_family:
            lines = lines.filtered(
                lambda b: b.estimate_line_id.cost_family == self.filter_cost_family
            )
        if self.filter_workflow_route:
            route = (self.filter_workflow_route or '').strip().upper()
            lines = lines.filtered(
                lambda b: (b.estimate_line_id.workflow_route or '').upper() == route
            )
        if self.filter_calc_type:
            lines = lines.filtered(lambda b: b.calc_type == self.filter_calc_type)
        if self.filter_data_phase:
            lines = lines.filtered(lambda b: b.data_phase == self.filter_data_phase)
        if self.filter_product_category_id:
            lines = lines.filtered(
                lambda b: b.product_category_id == self.filter_product_category_id
            )
        if self.filter_text:
            needle = self.filter_text.strip().lower()
            lines = lines.filtered(
                lambda b, self=self: self._bom_line_matches_text(b, needle)
            )
        return lines

    @api.model
    def _bom_line_matches_text(self, bom, needle):
        parts = [
            bom.name or '',
            bom.description or '',
            bom.product_id.display_name or '',
            bom.product_id.default_code or '',
            bom.estimate_line_id.pos or '',
            bom.estimate_line_id.description or '',
        ]
        return any(needle in (p or '').lower() for p in parts)

    def _rebuild_line_list(self, preserve_selection=False, auto_select_new=False):
        self.ensure_one()
        visible = self._filtered_bom_candidates()
        selected_ids = set()
        if preserve_selection:
            selected_ids = set(
                self.line_ids.filtered('selected').mapped('bom_line_id').ids
            )
        elif auto_select_new:
            selected_ids = set(self._default_selection_ids(visible).ids)
        self.write({
            'line_ids': [(5, 0, 0)] + [
                (0, 0, {
                    'bom_line_id': bom.id,
                    'selected': bom.id in selected_ids,
                })
                for bom in visible
            ],
        })

    def _reload_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Load from estimate BOM'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }

    def action_apply_filters(self):
        """Rebuild the table so it lists only rows matching scope + filters."""
        self.ensure_one()
        self._rebuild_line_list(preserve_selection=True)
        return self._reload_wizard()

    @api.onchange('import_scope')
    def _onchange_import_scope(self):
        self._rebuild_line_list(preserve_selection=False, auto_select_new=True)

    def action_clear_filters(self):
        self.write({
            'filter_estimate_line_id': False,
            'filter_cost_family': False,
            'filter_workflow_route': False,
            'filter_calc_type': False,
            'filter_data_phase': False,
            'filter_product_category_id': False,
            'filter_text': False,
        })
        return self.action_apply_filters()

    def action_select_filtered(self):
        self.ensure_one()
        self.line_ids.write({'selected': True})

    def action_select_filtered_new_only(self):
        self.ensure_one()
        linked = self._already_linked_bom_ids()
        for line in self.line_ids:
            line.selected = line.bom_line_id.id not in linked

    def action_select_same_anaco_position(self):
        self.ensure_one()
        if not self.filter_estimate_line_id:
            raise UserError(_('Set «ANACO position» first, or pick a row and use the list group-by.'))
        for line in self.line_ids:
            line.selected = (
                line.bom_line_id.estimate_line_id == self.filter_estimate_line_id
            )

    def action_select_route_lines(self):
        self.write({'import_scope': 'route'})
        self._rebuild_line_list(preserve_selection=False, auto_select_new=False)
        self.line_ids.write({'selected': True})
        return self._reload_wizard()

    def action_select_all_estimate(self):
        self.write({'import_scope': 'all'})
        self._rebuild_line_list(preserve_selection=False, auto_select_new=False)
        self.line_ids.write({'selected': True})
        return self._reload_wizard()

    def action_select_new_only(self):
        self.ensure_one()
        linked = self._already_linked_bom_ids()
        for line in self.line_ids:
            line.selected = line.bom_line_id.id not in linked

    def action_clear_selection(self):
        self.line_ids.write({'selected': False})

    def action_load(self):
        self.ensure_one()
        if not self.request_id.estimate_id:
            raise UserError(_('The project has no linked source estimate.'))
        bom_lines = self.line_ids.filtered('selected').mapped('bom_line_id')
        if not bom_lines:
            raise UserError(_('Select at least one BOM line to load.'))
        visible = self._filtered_bom_candidates()
        hidden = bom_lines - visible
        if hidden:
            raise UserError(
                _('Some selected lines are outside the current filters. '
                  'Click Apply filters or adjust the selection.')
            )
        return self.request_id._load_selected_bom_lines(
            bom_lines,
            clear=self.replace_existing,
        )
