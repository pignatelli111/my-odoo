# -*- coding: utf-8 -*-
{
    'name': 'SBU Revolut',
    'version': '19.0.1.0.0',
    'summary': 'Revolut Business movements import and webhooks; match to Odoo payments/invoices; optional CSV export (Phase 6.4)',
    'author': 'SBU Development',
    'category': 'Accounting',
    'depends': [
        'web',
        'account',
        'mail',
        'base_setup',
        'sbu_integrations',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/sbu_revolut_transaction_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
