# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.sbu_estimate.models.sbu_contract_uom import SBU_CONTRACT_UOM_SELECTION


class SbuSalSheetLineImportWizard(models.TransientModel):
    _name = 'sbu.sal.sheet.line.import.wizard'
    _description = 'Select contractual SAL items to add on customer SAL sheet'

    sheet_id = fields.Many2one(
        'sbu.sal.sheet',
        string='SAL sheet',
        required=True,
        ondelete='cascade',
    )
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Source estimate',
        related='sheet_id.estimate_id',
        readonly=True,
    )
    replace_existing = fields.Boolean(
        string='Replace existing lines',
        help='If set, current SAL lines are removed before adding the selection.',
    )
    import_scope = fields.Selection(
        [
            ('missing', 'Not yet on this SAL'),
            ('all', 'All contractual items'),
        ],
        string='Show',
        required=True,
        default='missing',
    )
    filter_item_ref = fields.Char(
        string='Item ref.',
        help='Filter by item code (contains).',
    )
    filter_sal_status = fields.Selection(
        selection='_selection_sal_status',
        string='Contract status',
    )
    filter_uom_type = fields.Selection(
        selection=SBU_CONTRACT_UOM_SELECTION,
        string='Contract UoM',
    )
    filter_text = fields.Char(
        string='Search text',
        help='Matches voce label, item, or description.',
    )
    line_ids = fields.One2many(
        'sbu.sal.sheet.line.import.wizard.line',
        'wizard_id',
        string='Contractual items',
    )
    available_count = fields.Integer(compute='_compute_counts')
    filtered_count = fields.Integer(
        string='Visible after filters',
        compute='_compute_counts',
    )
    selected_count = fields.Integer(compute='_compute_counts')
    already_on_sheet_count = fields.Integer(
        string='Already on SAL',
        compute='_compute_counts',
    )

    @api.model
    def _selection_sal_status(self):
        return self.env['sbu.estimate.sal.line']._fields['sal_status'].selection

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
        'sheet_id',
        'sheet_id.line_ids.estimate_sal_line_id',
    )
    def _compute_counts(self):
        for wiz in self:
            available = wiz._contract_lines_for_scope()
            linked = wiz._already_on_sheet_ids()
            wiz.available_count = len(available)
            wiz.filtered_count = len(wiz.line_ids)
            wiz.selected_count = len(wiz.line_ids.filtered('selected'))
            wiz.already_on_sheet_count = len(
                wiz.line_ids.filtered(
                    lambda ln: ln.contract_line_id.id in linked
                )
            )

    def _already_on_sheet_ids(self):
        self.ensure_one()
        return {
            sid for sid in self.sheet_id.line_ids.mapped('estimate_sal_line_id').ids if sid
        }

    def _contract_lines_for_scope(self, scope=None):
        self.ensure_one()
        estimate = self.sheet_id.estimate_id
        if not estimate:
            return self.env['sbu.estimate.sal.line'].browse()
        lines = estimate.sal_line_ids
        scope = scope or self.import_scope
        if scope == 'missing':
            linked = self._already_on_sheet_ids()
            lines = lines.filtered(lambda l: l.id not in linked)
        return lines

    def _filtered_contract_lines(self):
        self.ensure_one()
        lines = self._contract_lines_for_scope()
        if self.filter_item_ref:
            needle = self.filter_item_ref.strip().lower()
            lines = lines.filtered(
                lambda l: needle in (l.item_ref or '').lower()
            )
        if self.filter_sal_status:
            lines = lines.filtered(lambda l: l.sal_status == self.filter_sal_status)
        if self.filter_uom_type:
            lines = lines.filtered(lambda l: l.uom_type == self.filter_uom_type)
        if self.filter_text:
            needle = self.filter_text.strip().lower()
            lines = lines.filtered(
                lambda l, self=self: self._line_matches_text(l, needle)
            )
        return lines

    @api.model
    def _line_matches_text(self, line, needle):
        parts = [
            line.name or '',
            line.item_ref or '',
            line.description or '',
        ]
        return any(needle in (p or '').lower() for p in parts)

    def _rebuild_line_list(self, preserve_selection=False, auto_select_new=False):
        self.ensure_one()
        visible = self._filtered_contract_lines()
        selected_ids = set()
        if preserve_selection:
            selected_ids = set(
                self.line_ids.filtered('selected').mapped('contract_line_id').ids
            )
        elif auto_select_new:
            selected_ids = set(visible.ids)
        self.write({
            'line_ids': [(5, 0, 0)] + [
                (0, 0, {
                    'contract_line_id': line.id,
                    'selected': line.id in selected_ids,
                })
                for line in visible.sorted(lambda l: (l.sequence, l.item_ref or '', l.id))
            ],
        })

    def _reload_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add lines from contract'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }

    def action_apply_filters(self):
        self.ensure_one()
        self._rebuild_line_list(preserve_selection=True)
        return self._reload_wizard()

    @api.onchange('import_scope')
    def _onchange_import_scope(self):
        self._rebuild_line_list(preserve_selection=False, auto_select_new=True)

    def action_clear_filters(self):
        self.write({
            'filter_item_ref': False,
            'filter_sal_status': False,
            'filter_uom_type': False,
            'filter_text': False,
        })
        return self.action_apply_filters()

    def action_select_filtered(self):
        self.line_ids.write({'selected': True})

    def action_select_missing_only(self):
        linked = self._already_on_sheet_ids()
        for line in self.line_ids:
            line.selected = line.contract_line_id.id not in linked

    def action_select_all_scope(self):
        self.write({'import_scope': 'all'})
        self._rebuild_line_list(preserve_selection=False, auto_select_new=False)
        self.line_ids.write({'selected': True})
        return self._reload_wizard()

    def action_clear_selection(self):
        self.line_ids.write({'selected': False})

    def action_load(self):
        self.ensure_one()
        if not self.sheet_id.estimate_id:
            raise UserError(_('Link a source estimate on the project before adding lines.'))
        contract_lines = self.line_ids.filtered('selected').mapped('contract_line_id')
        if not contract_lines:
            raise UserError(_('Select at least one contractual item to add.'))
        visible = self._filtered_contract_lines()
        hidden = contract_lines - visible
        if hidden:
            raise UserError(
                _('Some selected items are outside the current filters. '
                  'Click Apply filters or adjust the selection.')
            )
        return self.sheet_id._load_selected_contract_lines(
            contract_lines,
            clear=self.replace_existing,
        )
