# -*- coding: utf-8 -*-
"""Shared «apply to filtered list» wizard logic (Cosimo UX point 3)."""
import ast

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SbuBulkApplyMixin(models.AbstractModel):
    _name = 'sbu.bulk.apply.mixin'
    _description = 'Bulk update lines matching list filters or selection'

    apply_scope = fields.Selection(
        [
            ('selection', 'Selected lines only'),
            ('filtered', 'All lines matching list filters'),
        ],
        string='Apply to',
        required=True,
        default='selection',
        help='Use «All lines matching list filters» after setting left-panel filters '
             'and search filters (no need to tick every row).',
    )
    target_count = fields.Integer(
        string='Lines affected',
        compute='_compute_target_count',
    )

    @api.depends('apply_scope')
    def _compute_target_count(self):
        for wiz in self:
            try:
                wiz.target_count = len(wiz._resolve_target_lines(raise_if_empty=False))
            except Exception:
                wiz.target_count = 0

    @api.model
    def _sbu_bulk_default_get(self, res, fields_list):
        """Merge list-action context into wizard defaults."""
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        active_domain = self.env.context.get('active_domain')
        line_model = self._bulk_line_model()
        line_field = self._bulk_line_field()

        if active_model == line_model and active_ids:
            res[line_field] = [(6, 0, active_ids)]
            if active_domain and len(active_ids) > 20:
                res['apply_scope'] = 'filtered'
        parent = self._bulk_parent_default(active_model, active_ids)
        if parent:
            res.update(parent)
        if active_domain and res.get('apply_scope') != 'selection':
            res.setdefault('apply_scope', 'filtered')
        if self.env.context.get('default_apply_scope') == 'filtered':
            res['apply_scope'] = 'filtered'
        return res

    def _bulk_line_model(self):
        raise NotImplementedError

    def _bulk_line_field(self):
        return 'line_ids'

    def _bulk_parent_default(self, active_model, active_ids):
        """Override to set parent document field from form action."""
        return {}

    def _domain_from_context(self):
        raw = self.env.context.get('active_domain')
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return list(raw)
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                return []
            return list(parsed) if isinstance(parsed, (list, tuple)) else []
        return []

    def _bulk_fallback_domain(self):
        """Narrow domain when opened from a parent form without list filters."""
        return []

    def _bulk_domain_safety_terms(self):
        """Domain leaf field names that avoid updating the whole database."""
        return ('id', 'estimate_id', 'request_id', 'sheet_id', 'project_id')

    def _resolve_target_lines(self, raise_if_empty=True):
        self.ensure_one()
        line_field = self._bulk_line_field()
        Line = self.env[self._bulk_line_model()]
        if self.apply_scope == 'filtered':
            domain = self._domain_from_context() or self._bulk_fallback_domain()
            if not domain:
                if raise_if_empty:
                    raise UserError(
                        _('Open this wizard from a filtered list (left panel + filters), '
                          'or choose «Selected lines only» and tick rows.'),
                    )
                return Line.browse()
            lines = Line.search(domain)
            if len(lines) > 500 and not any(
                isinstance(term, (list, tuple))
                and len(term) >= 3
                and term[0] in self._bulk_domain_safety_terms()
                for term in domain
            ):
                raise UserError(
                    _('Filter is too broad (%(n)s lines). Add an estimate, project, '
                      'or document filter before applying bulk changes.', n=len(lines)),
                )
            return lines
        lines = self[line_field]
        if not lines and raise_if_empty:
            raise UserError(
                _('Select at least one line, or use list filters + '
                  '«All lines matching list filters».'),
            )
        return lines

    def _bulk_notification(self, updated):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk update'),
                'message': _('Updated %(n)s line(s).', n=updated),
                'type': 'success',
                'sticky': False,
            },
        }

    def _bulk_require_any_apply(self, flags):
        if not any(flags):
            raise UserError(_('Enable at least one field to apply (checkbox on the left).'))
