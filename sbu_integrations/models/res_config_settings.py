from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sbu_graph_tenant_id = fields.Char(
        string='Microsoft Graph tenant ID',
        config_parameter='sbu.graph_tenant_id',
    )
    sbu_graph_client_id = fields.Char(
        string='Microsoft Graph client ID',
        config_parameter='sbu.graph_client_id',
    )
    sbu_qonto_org = fields.Char(
        string='Qonto organisation',
        config_parameter='sbu.qonto_org',
    )
    sbu_logikal_base_url = fields.Char(
        string='Logikal API base URL',
        config_parameter='sbu.logikal_base_url',
    )
