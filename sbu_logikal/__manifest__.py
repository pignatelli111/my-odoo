# -*- coding: utf-8 -*-
{
    'name': 'SBU Logikal / ReynaPro',
    'version': '19.0.1.0.0',
    'summary': 'File or API bridge from Logikal/ReynaPro exports into products, estimate BOM, or MRP BOM (Phase 7.1)',
    'author': 'SBU Development',
    'category': 'Technical',
    'depends': [
        'base',
        'mail',
        'mrp',
        'product',
        'project',
        'sbu_estimate',
        'sbu_integrations',
    ],
    'data': [
        'data/sbu_logikal_sequence.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/sbu_logikal_product_map_views.xml',
        'views/sbu_logikal_import_views.xml',
        'views/project_project_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
