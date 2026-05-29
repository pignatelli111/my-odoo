# -*- coding: utf-8 -*-
"""TMS VdC / Voce di budget catalog (sheet «Vdc» in M.4.3.C RDA workbook)."""
from odoo import api, fields, models, _

from odoo.addons.sbu_estimate.models.sbu_cost_family import SBU_COST_FAMILY_SELECTION


def _guess_cost_family_from_vdc_code(code, name=''):
    """Heuristic map when importing fresh VdC rows without manual mapping."""
    blob = f'{(code or "")} {(name or "")}'.upper()
    rules = (
        ('VETROCAMERA', 'glass'),
        ('VETRI', 'glass'),
        ('VETRO', 'glass'),
        ('VC/', 'glass'),
        ('VS/', 'glass'),
        ('ZANZAR', 'accessory'),
        ('OSCUR', 'accessory'),
        ('FRANGISOLE', 'accessory'),
        ('TENDE', 'accessory'),
        ('ALLUMINIO', 'aluminum_sheet'),
        ('LAMIERAME_ALU', 'aluminum_sheet'),
        ('LAMIERA_FORATA', 'aluminum_sheet'),
        ('ACCIAIO', 'profile'),
        ('CARPENTERIA', 'profile'),
        ('STAF', 'bracket_st'),
        ('ST/', 'bracket_st'),
        ('PANNELLI', 'panel'),
        ('SPANDREL', 'panel'),
        ('OFFICINA', 'accessory'),
        ('ACCESSOR', 'accessory'),
        ('AUTOMAT', 'accessory'),
        ('CASSONET', 'accessory'),
        ('GUAIN', 'gasket'),
        ('SIGILL', 'gasket'),
        ('POSE', 'installation'),
        ('POSA', 'installation'),
        ('ALLESTIMENTO_CANT', 'installation'),
        ('TRASPORT', 'transport'),
        ('IMBALLO', 'transport'),
        ('PROJECT MANAGER', 'technical_pm'),
        ('_PM', 'technical_pm'),
        ('BIM', 'technical_pm'),
        ('PROGETTAZ', 'technical_pm'),
        ('CAPOCANTIERE', 'site_cost'),
        ('CANTIERE', 'site_cost'),
        ('SERRAMENT', 'serramento'),
        ('PROFILI', 'profile'),
        ('GAMMISTA', 'profile'),
    )
    for needle, family in rules:
        if needle in blob:
            return family
    if blob.startswith('E_'):
        return 'extra'
    if blob.startswith('M_'):
        return 'extra'
    if blob.startswith('G_'):
        return 'extra'
    return 'extra'


class SbuVdcCatalog(models.Model):
    _name = 'sbu.vdc.catalog'
    _description = 'SBU TMS VdC budget code'
    _order = 'code'

    code = fields.Char(string='VdC code', required=True, index=True)
    name = fields.Char(string='Description', required=True, translate=True)
    pdc_code = fields.Char(string='Pdc / ledger code')
    pdc_label = fields.Char(string='Pdc label')
    note = fields.Text(string='Notes')
    cost_family = fields.Selection(
        selection=SBU_COST_FAMILY_SELECTION,
        string='Cost family',
        help='Maps TMS VdC to ANACO ITEM budget family for traffic lights.',
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'VdC code must be unique.',
    )

    @api.model
    def resolve_cost_family(self, vdc_code):
        code = (vdc_code or '').strip()
        if not code:
            return False
        row = self.search([('code', '=ilike', code)], limit=1)
        return row.cost_family if row else False

    @api.model
    def sync_from_sheet_rows(self, rows):
        """Upsert catalog from TMS «Vdc» worksheet rows."""
        created = updated = 0
        for row in rows:
            code = (row.get('code') or '').strip()
            name = (row.get('name') or '').strip()
            if not code or code.lower().startswith('vdc'):
                continue
            vals = {
                'name': name or code,
                'pdc_code': row.get('pdc_code') or False,
                'pdc_label': row.get('pdc_label') or False,
                'note': row.get('note') or False,
            }
            existing = self.search([('code', '=ilike', code)], limit=1)
            if existing:
                if not existing.cost_family:
                    vals['cost_family'] = _guess_cost_family_from_vdc_code(code, name)
                existing.write(vals)
                updated += 1
            else:
                vals['code'] = code
                vals['cost_family'] = _guess_cost_family_from_vdc_code(code, name)
                self.create(vals)
                created += 1
        return {'created': created, 'updated': updated}
