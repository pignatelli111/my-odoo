# -*- coding: utf-8 -*-
"""TMS drawing / tavole approval register (Report tav appr TMS)."""
from odoo import api, fields, models


class SbuDrawingRegister(models.Model):
    _name = 'sbu.drawing.register'
    _description = 'SBU drawing approval register'
    _order = 'drawing_code, id'

    project_id = fields.Many2one(
        'project.project',
        string='Project / Job',
        required=True,
        ondelete='cascade',
        index=True,
    )
    prog = fields.Char(string='Prog.')
    item = fields.Char(string='Item')
    num = fields.Char(string='Num')
    revision = fields.Char(string='Rev.')
    reference = fields.Char(string='Reference (RIF)')
    drawing_code = fields.Char(string='Drawing code', index=True)
    name = fields.Char(string='Description', required=True)
    emission_1_date = fields.Date(string='1st emission')
    emission_2_date = fields.Date(string='2nd emission')
    emission_3_date = fields.Date(string='3rd emission')
    last_emission_date = fields.Date(string='Last emission')
    approval_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('issued', 'Issued'),
            ('approved', 'Approved'),
            ('superseded', 'Superseded'),
        ],
        string='Approval status',
        default='draft',
    )
    note = fields.Char(string='Notes')
    block_purchase = fields.Boolean(
        string='Block RFQ until approved',
        default=False,
        help='When set, RFQ creation for linked routes may be blocked until status is Approved.',
    )

    @api.model
    def import_tms_rows(self, project, rows, update_mode='merge'):
        created = updated = 0
        for row in rows:
            code = (row.get('drawing_code') or '').strip()
            if not code:
                continue
            domain = [
                ('project_id', '=', project.id),
                ('drawing_code', '=', code),
            ]
            rev = (row.get('revision') or '').strip()
            if rev:
                domain.append(('revision', '=', rev))
            existing = self.search(domain, limit=1) if update_mode == 'merge' else self.browse()
            vals = {
                'project_id': project.id,
                'prog': row.get('prog') or False,
                'item': row.get('item') or False,
                'num': row.get('num') or False,
                'revision': rev or False,
                'reference': row.get('reference') or False,
                'drawing_code': code,
                'name': row.get('name') or code,
                'emission_1_date': row.get('emission_1_date') or False,
                'emission_2_date': row.get('emission_2_date') or False,
                'emission_3_date': row.get('emission_3_date') or False,
                'last_emission_date': row.get('last_emission_date') or False,
                'approval_state': row.get('approval_state') or 'draft',
                'note': row.get('note') or False,
            }
            if existing:
                existing.write(vals)
                updated += 1
            else:
                self.create(vals)
                created += 1
        return {'created': created, 'updated': updated}
