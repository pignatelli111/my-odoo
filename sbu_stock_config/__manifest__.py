# -*- coding: utf-8 -*-
{
    'name': 'SBU Stock configuration',
    'version': '19.0.1.1.2',
    'summary': 'SBU stock layout + project-linked logistics and job status (Phase 4.1–4.2)',
    'author': 'SBU Development',
    'category': 'Inventory',
    'depends': [
        'stock',
        'purchase_stock',
        'project',
    ],
    'data': [
        'data/sbu_stock_locations_routes.xml',
        'views/stock_picking_views.xml',
        'views/purchase_order_views.xml',
        'views/project_project_logistics_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
