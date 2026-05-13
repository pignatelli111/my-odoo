{
    'name': 'SBU SAL',
    'version': '19.0.1.0.1',
    'summary': 'SAL progress billing and payment certificates for Suburban SRL',
    'author': 'SBU Development',
    'category': 'Accounting',
    'depends': [
        'base',
        'mail',
        'account',
        'project',
        'sbu_estimate',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sbu_sal_sequence.xml',
        'views/sbu_sal_views.xml',
        'views/project_project_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
