{
    'name': 'SBU Estimate',
    'version': '19.0.1.0.7',
    'summary': 'Custom estimating engine for Suburban SRL (ANACO → Odoo)',
    'description': '''
        Translates the ANACO Excel estimating tool into Odoo.
        - Estimate header with versioning (REV00, REV01...) and revision chain
        - Optional commercial scenario (base / aggressivo / rischio) and internal approval workflow
        - Structured estimate references: client / technical / supplier (file and/or URL)
        - Optional wizard: import ANACO + Voci Contrattuali_SAL from .xlsx (openpyxl)
        - Line items: B × H → mq; listino prezzi → Sc1/Sc2/Sc3 e Comm. % (sconti successivi) → netto CAD
        - Costi: oneri industriali % su (Coibentazione + Posa); MOL % come indicatore su materiale; totale distinta ITEM a confronto
        - BOM per item with calc types: lump_sum, per_piece, linear, surface, pack
        - SAL contractual items (totale contrattuale in testata; SAL-1…10 max 100%)
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
        'security/sbu_estimate_groups.xml',
        'security/ir.model.access.csv',
        'data/sbu_estimate_sequence.xml',
        'views/sbu_estimate_views.xml',
        'views/sbu_estimate_line_views.xml',
        'views/sbu_estimate_bom_views.xml',
        'views/sbu_estimate_menu.xml',
        'wizards/sbu_estimate_to_project_wizard_views.xml',
        'wizards/sbu_estimate_anaco_import_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['openpyxl'],
    },
}
