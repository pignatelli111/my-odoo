# -*- coding: utf-8 -*-
{
    'name': 'SBU Revolut',
    'version': '19.0.2.0.0',
    'summary': 'Revolut Business: OAuth connection, multi-account import, signed webhooks, '
               'invoice matching and approved supplier payments',
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
        'security/sbu_revolut_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/sbu_revolut_transaction_views.xml',
        'views/sbu_revolut_payment_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
