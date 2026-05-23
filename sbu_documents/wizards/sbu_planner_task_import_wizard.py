# -*- coding: utf-8 -*-
"""Import Planner-style task checklist into Odoo project tasks (Cosimo punto 8)."""
import base64
import csv
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SbuPlannerTaskImportWizard(models.TransientModel):
    _name = 'sbu.planner.task.import.wizard'
    _description = 'Import tasks from CSV (Planner export)'

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
    )
    data_file = fields.Binary(string='CSV file', required=True)
    filename = fields.Char(string='Filename')
    delimiter = fields.Char(string='Delimiter', default=',', required=True)
    line_count = fields.Integer(string='Tasks created', readonly=True)

    def _parse_csv_rows(self):
        self.ensure_one()
        raw = base64.b64decode(self.data_file)
        text = raw.decode('utf-8-sig', errors='replace')
        delim = (self.delimiter or ',')[:1]
        reader = csv.reader(io.StringIO(text), delimiter=delim)
        rows = list(reader)
        if not rows:
            raise UserError(_('CSV file is empty.'))
        header = [c.strip().lower() for c in rows[0]]
        col = {}
        for name, aliases in (
            ('title', ('title', 'task name', 'name', 'attività', 'attivita')),
            ('bucket', ('bucket', 'plan', 'board', 'piano')),
            ('due', ('due date', 'due', 'scadenza', 'data')),
            ('email', ('assigned', 'assigned to', 'email', 'assegnato')),
            ('m365_url', ('link', 'url', 'planner link', 'm365')),
            ('description', ('description', 'notes', 'note', 'descrizione')),
        ):
            for i, h in enumerate(header):
                if h in aliases:
                    col[name] = i
                    break
        if 'title' not in col:
            col['title'] = 0
        data = []
        for row in rows[1:]:
            if not any(str(c).strip() for c in row):
                continue
            title = row[col['title']].strip() if col['title'] < len(row) else ''
            if not title:
                continue
            data.append({
                'title': title,
                'bucket': row[col['bucket']].strip() if col.get('bucket') is not None and col['bucket'] < len(row) else '',
                'due': row[col['due']].strip() if col.get('due') is not None and col['due'] < len(row) else '',
                'email': row[col['email']].strip() if col.get('email') is not None and col['email'] < len(row) else '',
                'm365_url': row[col['m365_url']].strip() if col.get('m365_url') is not None and col['m365_url'] < len(row) else '',
                'description': row[col['description']].strip() if col.get('description') is not None and col['description'] < len(row) else '',
            })
        return data

    def action_import(self):
        self.ensure_one()
        rows = self._parse_csv_rows()
        if not rows:
            raise UserError(_('No task rows found in CSV.'))
        Task = self.env['project.task']
        User = self.env['res.users']
        created = 0
        tag_model = 'project.tags' if 'project.tags' in self.env else False
        for row in rows:
            user_ids = []
            if row.get('email'):
                user = User.search([('login', '=', row['email'])], limit=1)
                if not user:
                    user = User.search([('email', '=', row['email'])], limit=1)
                if user:
                    user_ids = [user.id]
            desc_parts = []
            if row.get('bucket'):
                desc_parts.append(_('Planner bucket: %s') % row['bucket'])
            if row.get('description'):
                desc_parts.append(row['description'])
            if row.get('m365_url'):
                desc_parts.append(row['m365_url'])
            vals = {
                'name': row['title'],
                'project_id': self.project_id.id,
                'description': '\n'.join(desc_parts) if desc_parts else False,
            }
            if user_ids:
                vals['user_ids'] = [(6, 0, user_ids)]
            if row.get('m365_url') and 'sbu_m365_task_url' in Task._fields:
                vals['sbu_m365_task_url'] = row['m365_url']
            Task.create(vals)
            created += 1
        self.line_count = created
        self.project_id.message_post(
            body=_('Imported %(n)s task(s) from Planner CSV export.') % {'n': created},
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'res_id': self.project_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
