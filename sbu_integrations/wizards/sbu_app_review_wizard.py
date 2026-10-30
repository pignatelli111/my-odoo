# -*- coding: utf-8 -*-
"""Review the installed Odoo apps: needed by SBU? holding data? what else depends on them? (read-only)."""
import logging
from collections import defaultdict

from odoo import SUPERUSER_ID, Command, _, api, fields, models

_logger = logging.getLogger(__name__)

RECOMMENDATIONS = [
    ('sbu', 'SBU module'),
    ('required', 'Keep — needed by SBU'),
    ('in_use', 'Keep — holds data'),
    ('candidate', 'Candidate to uninstall'),
]


class SbuAppReviewLine(models.TransientModel):
    _name = 'sbu.app.review.line'
    _description = 'Installed app review line'
    _order = 'sequence, name'

    wizard_id = fields.Many2one('sbu.app.review.wizard', required=True, ondelete='cascade')
    sequence = fields.Integer()
    name = fields.Char(string='App', readonly=True)
    technical_name = fields.Char(string='Technical name', readonly=True)
    recommendation = fields.Selection(RECOMMENDATIONS, readonly=True)
    needed_by = fields.Char(string='Needed by (SBU)', readonly=True)
    user_records = fields.Integer(string='Records entered by users', readonly=True)
    also_removed = fields.Char(string='Also removed if uninstalled', readonly=True)


class SbuAppReviewWizard(models.TransientModel):
    _name = 'sbu.app.review.wizard'
    _description = 'Review installed apps'

    line_ids = fields.One2many('sbu.app.review.line', 'wizard_id', string='Installed apps', readonly=True)
    candidate_count = fields.Integer(compute='_compute_candidate_count')

    @api.depends('line_ids.recommendation')
    def _compute_candidate_count(self):
        for wizard in self:
            wizard.candidate_count = len(wizard.line_ids.filtered(lambda l: l.recommendation == 'candidate'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'line_ids' in fields_list:
            res['line_ids'] = [Command.create(vals) for vals in self._sbu_review()]
        return res

    @api.model
    def _sbu_dependency_graph(self, installed):
        deps = defaultdict(set)
        for dep in self.env['ir.module.module.dependency'].sudo().search([('module_id', 'in', installed.ids)]):
            deps[dep.module_id.name].add(dep.name)
        return deps

    @staticmethod
    def _closure(roots, graph):
        seen, stack = set(), list(roots)
        while stack:
            name = stack.pop()
            for nxt in graph.get(name, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    @api.model
    def _sbu_user_records(self, module_name):
        """Records created by people (not by Odoo / data files) in the models this module defines."""
        model_ids = self.env['ir.model.data'].sudo().search([
            ('module', '=', module_name), ('model', '=', 'ir.model'),
        ]).mapped('res_id')
        total = 0
        for ir_model in self.env['ir.model'].sudo().browse(model_ids).exists():
            Model = self.env.get(ir_model.model)
            if Model is None or Model._abstract or Model._transient or not Model._auto or 'create_uid' not in Model._fields:
                continue
            try:
                total += Model.sudo().with_context(active_test=False).search_count([('create_uid', '!=', SUPERUSER_ID)])
            except Exception as err:  # noqa: BLE001 — one odd model must not break the review
                _logger.info('App review: cannot count %s: %s', ir_model.model, err)
        return total

    @api.model
    def _sbu_review(self):
        Module = self.env['ir.module.module'].sudo()
        installed = Module.search([('state', '=', 'installed')])
        graph = self._sbu_dependency_graph(installed)
        reverse = defaultdict(set)
        for name, deps in graph.items():
            for dep in deps:
                reverse[dep].add(name)
        sbu_modules = {m.name for m in installed if m.name.startswith('sbu_')}
        needed = defaultdict(set)
        for sbu in sbu_modules:
            for dep in self._closure([sbu], graph):
                needed[dep].add(sbu)
        order = {key: index for index, (key, _label) in enumerate(RECOMMENDATIONS)}
        rows = []
        for module in installed.filtered('application'):
            name = module.name
            dependents = self._closure([name], reverse)
            apps_removed = sorted(
                m.shortdesc for m in installed if m.name in dependents and m.application and m.name not in sbu_modules
            )
            sbu_removed = sorted(dependents & sbu_modules)
            if name in sbu_modules:
                recommendation, records = 'sbu', 0
            elif needed.get(name):
                recommendation, records = 'required', 0
            else:
                records = self._sbu_user_records(name)
                recommendation = 'in_use' if records else 'candidate'
            rows.append({
                'sequence': order[recommendation],
                'name': module.shortdesc,
                'technical_name': name,
                'recommendation': recommendation,
                'needed_by': ', '.join(sorted(needed.get(name, ())))[:250],
                'user_records': records,
                'also_removed': ', '.join(sbu_removed + apps_removed)[:250],
            })
        return sorted(rows, key=lambda r: (r['sequence'], r['name']))


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_sbu_review_installed_apps(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Installed apps review'),
            'res_model': 'sbu.app.review.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
