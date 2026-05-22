# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.sbu_workflow_routing import (
    ROUTE_WIZARD_REQUIRES,
    SBU_WIZARD_ROUTE_SELECTION,
    workflow_route_to_request_type,
)


class SbuPurchaseRequestCreateWizard(models.TransientModel):
    _name = 'sbu.purchase.request.create.wizard'
    _description = 'Guided purchase document creation (closed route list)'

    project_id = fields.Many2one(
        'project.project',
        string='Commessa',
        required=True,
        ondelete='cascade',
    )
    workflow_route = fields.Selection(
        selection=SBU_WIZARD_ROUTE_SELECTION,
        string='Tipo documento / route',
        required=True,
        help='Elenco chiuso allineato ai template tecnici (LA, LZ, ST, PAN, OSC, …).',
    )
    request_type = fields.Selection(
        selection=[
            ('rda', 'RDA'),
            ('aco', 'ACO'),
            ('acp', 'ACP'),
            ('lds', 'LDS'),
            ('fe', 'FE'),
            ('st', 'ST'),
            ('vt', 'VT'),
            ('other', 'Altro'),
        ],
        string='Tipo Odoo',
        compute='_compute_request_type',
        readonly=True,
    )
    load_from_estimate = fields.Boolean(
        string='Carica righe da distinta preventivo',
        default=True,
        help='Se la commessa ha un preventivo vinto, importa le righe BOM per questa route.',
    )
    need_by_date = fields.Date(string='Data fabbisogno')
    topic = fields.Char(string='Topic / Argomento')
    excel_item = fields.Char(
        string='Item template',
        help='Codice voce Excel (es. LA01, PAN02) per tracciabilità.',
    )
    priority = fields.Selection(
        [
            ('0', 'Normale'),
            ('1', 'Media'),
            ('2', 'Alta'),
            ('3', 'Critica'),
        ],
        string='Priorità',
        default='0',
        required=True,
    )

    @api.depends('workflow_route')
    def _compute_request_type(self):
        for wiz in self:
            wiz.request_type = workflow_route_to_request_type(wiz.workflow_route)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        pid = self.env.context.get('default_project_id') or self.env.context.get('active_id')
        if self.env.context.get('active_model') == 'project.project' and self.env.context.get('active_ids'):
            pid = self.env.context['active_ids'][0]
        if pid:
            res['project_id'] = pid
        return res

    def _validate_required_fields(self):
        self.ensure_one()
        rules = ROUTE_WIZARD_REQUIRES.get(self.workflow_route or '', {})
        if rules.get('topic') and not (self.topic or '').strip():
            raise UserError(
                _('Per la route %s è obbligatorio il campo Topic / argomento.')
                % self.workflow_route,
            )
        if rules.get('need_by') and not self.need_by_date:
            raise UserError(
                _('Per la route %s è obbligatoria la data fabbisogno.')
                % self.workflow_route,
            )
        est = self.project_id.sbu_estimate_id
        if self.load_from_estimate:
            if not est:
                raise UserError(
                    _('Impostare il preventivo vinto sulla commessa prima di caricare righe da distinta.'),
                )
            if est.state != 'won':
                raise UserError(
                    _('Il preventivo collegato deve essere in stato «Vinto» (attuale: %s).')
                    % (est.state,)
                )

    def action_create(self):
        self.ensure_one()
        self._validate_required_fields()
        duplicate = self.env['sbu.purchase.request'].search_count([
            ('project_id', '=', self.project_id.id),
            ('workflow_route', '=', self.workflow_route),
            ('state', 'not in', ('cancelled', 'done')),
        ])
        if duplicate:
            raise UserError(
                _('Esiste già un documento aperto per commessa %s e route %s. '
                  'Usare quello esistente o annullarlo prima di crearne uno nuovo.')
                % (self.project_id.display_name, self.workflow_route),
            )

        company = self.project_id.company_id or self.env.company
        vals = {
            'project_id': self.project_id.id,
            'workflow_route': self.workflow_route,
            'request_type': workflow_route_to_request_type(self.workflow_route),
            'company_id': company.id,
            'priority': self.priority,
            'need_by_date': self.need_by_date,
            'topic': self.topic,
            'excel_item': self.excel_item,
        }
        pr = self.env['sbu.purchase.request'].create(vals)
        if self.load_from_estimate:
            pr._load_lines_from_estimate_bom(clear=True, workflow_route=self.workflow_route)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documento acquisto'),
            'res_model': 'sbu.purchase.request',
            'res_id': pr.id,
            'view_mode': 'form',
            'target': 'current',
        }
