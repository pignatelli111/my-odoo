{
    'name': 'SBU Integrations',
    'version': '19.0.1.0.0',
    'summary': 'Qonto, Logikal, ReynaPro integrations for Suburban SRL',
    'description': '''
        External system integrations:
        - Qonto: bank statement sync, payment reconciliation
        - Logikal: technical data import/export bridge
        - ReynaPro: technical data bridge
        - Microsoft Teams: webhook notifications
        - Exchange: outbound email
    ''',
    'author': 'SBU Development',
    'category': 'Accounting/Integration',
    'depends': [
        'base',
        'account',
        'sbu_project',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sbu_integrations_views.xml',
        'views/sbu_integrations_menu.xml',
        'data/sbu_integrations_config.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
