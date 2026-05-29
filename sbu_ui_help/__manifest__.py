{
    'name': 'SBU Context Help (uninstall stub)',
    'version': '19.0.1.0.10',
    'summary': 'Stub only so production DB can start; uninstall via SQL (see docs/ODOO_SH_REAL_SQL_FIX.md)',
    'author': 'SBU Development',
    'category': 'Hidden',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
