{
    'name': 'SBU Estimate',
    'version': '19.0.1.0.112',
    'summary': 'Custom estimating engine for Suburban SRL (ANACO → Odoo)',
    'description': (
        'Translates the ANACO Excel estimating tool into Odoo. '
        'Features: estimate versioning (REV00, REV01) and revision chain; optional commercial scenario '
        'and internal approval workflow; client/technical/supplier references; xlsx import of ANACO '
        'and SAL lines (openpyxl); line items with mq, discounts, and net CAD; industrial costs and MOL; '
        'BOM per item (lump_sum, per_piece, linear, surface, pack); SAL contractual totals; '
        'wizard to create a project from a won estimate.'
    ),
    'author': 'SBU Development',
    'category': 'Sales/Estimation',
    'depends': [
        'base',
        'mail',
        'sale_management',
        'sales_team',
        'crm',
        'project',
        'mrp',
        'purchase',
        'account',
        'uom',
    ],
    'data': [
        'security/sbu_estimate_groups.xml',
        'security/sbu_estimate_crm_access.xml',
        'security/ir.model.access.csv',
        'data/sbu_estimate_sequence.xml',
        'data/sbu_estimate_uat_products.xml',
        'data/sbu_product_catalog.xml',
        'data/sbu_estimate_server_actions.xml',
        # Wizard actions must load before views that reference %(…action…)d
        'wizards/sbu_estimate_to_project_wizard_views.xml',
        'wizards/sbu_estimate_anaco_import_wizard_views.xml',
        'wizards/sbu_estimate_force_delete_wizard_views.xml',
        'wizards/sbu_bulk_wizard_views.xml',
        'views/sbu_bulk_list_views.xml',
        'views/sbu_estimate_views.xml',
        'views/sbu_estimate_line_views.xml',
        'views/sbu_estimate_sal_line_views.xml',
        'views/sbu_estimate_bom_views.xml',
        'views/sbu_estimate_menu.xml',  # after bulk actions in sbu_bulk_list_views.xml
        'report/sbu_estimate_offer_report.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'post_init_hook': 'post_init_hook',
}
