from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SbuEstimateReference(models.Model):
    """Structured references / attachments on an estimate (client, technical, supplier)."""
    _name = 'sbu.estimate.reference'
    _description = 'SBU estimate reference / attachment'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    estimate_id = fields.Many2one(
        'sbu.estimate',
        string='Preventivo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    ref_type = fields.Selection(
        selection=[
            ('client_ref', 'Riferimento cliente'),
            ('technical_ref', 'Riferimento tecnico'),
            ('supplier_quote', 'Preventivo fornitore'),
        ],
        string='Tipo',
        required=True,
        default='client_ref',
    )
    name = fields.Char(
        string='Titolo',
        required=True,
    )
    url = fields.Char(string='Link (URL)')
    document_file = fields.Binary(string='File', attachment=True)
    document_filename = fields.Char(string='Nome file')
    note = fields.Text(string='Note')

    @api.constrains('document_file', 'url')
    def _check_document_or_url(self):
        for rec in self:
            has_url = bool(rec.url and rec.url.strip())
            if not rec.document_file and not has_url:
                raise ValidationError(
                    _('Ogni riga deve avere almeno un file allegato oppure un link (URL).')
                )
