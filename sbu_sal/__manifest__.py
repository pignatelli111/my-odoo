{
    'name': 'SBU SAL',
    'version': '19.0.1.0.0',
    'summary': 'SAL progress billing and payment certificates for Suburban SRL',
    'description': '''
        SAL (Stato Avanzamento Lavori) module:
        - SAL header with contractual items
        - Progress % per item, per floor, per orientation
        - Certificato di Pagamento (CDP)
        - Ritenuta a garanzia Art. 16.3
        - Retention tracking and release
        - Invoice generation from SAL
    ''',
    'author': 'SBU Development',
    'category': 'Accounting',
    'depends': [
        'base',
        'account',
        'project',
        'sbu_project',
        'sbu_estimate',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sbu_sal_sequence.xml',
        'views/sbu_sal_views.xml',
        'views/sbu_sal_line_views.xml',
        'views/sbu_payment_certificate_views.xml',
        'views/sbu_sal_menu.xml',
        'report/sbu_sal_report.xml',
        'report/sbu_sal_report_template.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
