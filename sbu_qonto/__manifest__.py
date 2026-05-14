# -*- coding: utf-8 -*-
{
    'name': 'SBU Qonto',
    'version': '19.0.1.0.3',
    'summary': 'Qonto movements import and webhooks; match to Odoo payments/invoices (Phase 6.3)',
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
        'views/sbu_qonto_transaction_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
