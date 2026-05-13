from odoo import models, fields, api


class SbuPurchaseRequestLine(models.Model):
    _name = 'sbu.purchase.request.line'
    _description = 'SBU Purchase Request Line'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'sbu.purchase.request',
        string='Request',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    pos = fields.Char(
        string='Pos.',
        help='POS. — come colonna righe template RDA.',
    )
    name = fields.Char(string='Description', required=True)
    article_code = fields.Char(
        string='Cod. articolo',
        help='COD. ARTICOLO (Excel); se vuoto si può usare il codice prodotto Odoo.',
    )
    dimension_mm = fields.Char(
        string='Dimensione mm',
        help='Es. L=6000 come nel template RDA.',
    )
    utilization = fields.Char(
        string='Utilizzo',
        help='UTILIZZO (montante, profili, …).',
    )
    weight_kg = fields.Float(string='Peso Kg', digits=(16, 3))
    product_id = fields.Many2one('product.product', string='Product')
    product_qty = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure')
    product_uom = fields.Many2one(
        'uom.uom',
        string='Unit of measure',
        required=True,
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False),
    )
    date_required = fields.Date(
        string='Data consegna',
        help='DATA CONSEGNA richiesta (template RDA).',
    )
    destination = fields.Char(
        string='Destinazione',
        help='DESTINATION / DESTINAZIONE (es. lavorazione conto terzi).',
    )
    procurement_mode = fields.Selection(
        [
            ('purchase', 'Acquisto'),
            ('warehouse', 'Magazzino'),
        ],
        string='Approvvigionamento',
        help='MAGAZZINO vs ACQUISTO come ultima colonna del template RDA.',
    )
    note = fields.Char(string='Notes')

    @api.onchange('product_id')
    def _onchange_product_id_article(self):
        for line in self:
            if line.product_id and not line.article_code:
                line.article_code = line.product_id.default_code or ''
