# -*- coding: utf-8 -*-
"""Map ANACO estimate line cost/price columns → catalog products → BOM lines."""
from odoo import _, models

# estimate.line field → product.template default_code
ANACO_LINE_FIELD_TO_PRODUCT_CODE = {
    'price_serramento_cad': 'SBU-SERR',
    'price_oscuramento_cad': 'SBU-OSC',
    'price_accessori_cad': 'SBU-ACC',
    'price_kit_avvolgimento_cad': 'SBU-KIT-AVV',
    'price_cassonetto_cad': 'SBU-CASS',
    'price_automatismo_cad': 'SBU-AUTO',
    'price_zanzariera_cad': 'SBU-ZANZ',
    'price_vetro_cad': 'SBU-VETRO',
    'price_pannello_cad': 'SBU-PANN',
    'price_controtelaio_cad': 'SBU-CT',
    'price_trasformazione_cad': 'SBU-TRAS',
    'price_smontaggio_cad': 'SBU-SMONT',
    'price_nolo_cad': 'SBU-NOLO',
    'cost_coibentazione_cad': 'SBU-COIB',
    'cost_posa_lamiera_lin_cad': 'SBU-POSA-LIN',
    'cost_trasporto_cad': 'SBU-TRASP',
    'cost_tech_pm_cad': 'SBU-PM',
    'cost_cantiere_cad': 'SBU-CANT',
    'cost_extra_cad': 'SBU-EXTRA',
}


class SbuEstimate(models.Model):
    _inherit = 'sbu.estimate'

    def action_generate_bom_from_anaco_costs(self):
        """Rebuild distinta from non-zero ANACO CAD columns on each line."""
        for estimate in self:
            estimate.line_ids.mapped('bom_line_ids').unlink()
            created = estimate._sbu_create_bom_from_anaco_lines()
            estimate.message_post(
                body=_('Distinta: %(n)d componenti generate dai costi/prezzi ANACO.')
                % {'n': created},
            )
        return True

    def _sbu_create_bom_from_anaco_lines(self):
        self.ensure_one()
        Product = self.env['product.product']
        Bom = self.env['sbu.estimate.bom.line']
        codes = list(ANACO_LINE_FIELD_TO_PRODUCT_CODE.values())
        products_by_code = {
            p.default_code: p
            for p in Product.search([('default_code', 'in', codes)])
        }
        seq = 10
        created = 0
        for eline in self.line_ids:
            for fname, code in ANACO_LINE_FIELD_TO_PRODUCT_CODE.items():
                if fname not in eline._fields:
                    continue
                amount = eline[fname] or 0.0
                if amount <= 0:
                    continue
                product = products_by_code.get(code)
                if not product:
                    continue
                Bom.create({
                    'estimate_id': self.id,
                    'estimate_line_id': eline.id,
                    'sequence': seq,
                    'product_id': product.id,
                    'calc_type': 'per_piece',
                    'dimension_source': 'manual',
                    'unit_cost': amount,
                    'uom_id': product.uom_id.id,
                })
                seq += 10
                created += 1
        return created
