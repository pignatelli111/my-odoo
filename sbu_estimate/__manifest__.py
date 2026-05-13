{
    'name': 'SBU Estimate',
    'version': '19.0.1.0.0',
    'summary': 'Custom estimating engine for Suburban SRL (ANACO → Odoo)',
    'description': '''
        Translates the ANACO Excel estimating tool into Odoo.
        - Estimate header with versioning (REV00, REV01...)
        - Line items with B x H -> sqm automatic calculation
        - BOM per item with calc types: lump_sum, per_piece, linear, surface, pack
        - Cost and price columns matching ANACO structure
        - SAL contractual items
        - Wizard: Won -> Project creation
    ''',
    'author': 'SBU Development',
    'category': 'Sales/Estimation',
    'depends': [
        'base',
        'mail',
        'sale_management',
        'crm',
        'project',
        'mrp',
        'purchase',
        'account',
        'uom',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sbu_estimate_sequence.xml',
        'views/sbu_estimate_views.xml',
        'views/sbu_estimate_line_views.xml',
        'views/sbu_estimate_bom_views.xml',
        'views/sbu_estimate_menu.xml',
        'wizards/sbu_estimate_to_project_wizard_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
