# -*- coding: utf-8 -*-
{
    'name': 'SBU Stock configuration',
    'version': '19.0.1.1.4',
    'summary': 'SBU stock layout + project-linked logistics, services/subcontract hints (Phase 4.3)',
    'author': 'SBU Development',
    'category': 'Inventory',
    'depends': [
        'stock',
        'purchase_stock',
        'project',
    ],
    'data': [
        'data/sbu_stock_locations_routes.xml',
        'data/sbu_ddt_sequence.xml',
        'report/sbu_ddt_report.xml',
        'views/stock_picking_views.xml',
        'views/purchase_order_views.xml',
        'views/project_project_logistics_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
