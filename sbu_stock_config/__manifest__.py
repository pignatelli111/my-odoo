# -*- coding: utf-8 -*-
{
    'name': 'SBU Stock configuration',
    'version': '19.0.1.0.0',
    'summary': 'SBU stock layout: locations, Buy/MTO/internal routes, reception flow (Phase 4.1)',
    'author': 'SBU Development',
    'category': 'Inventory',
    'depends': [
        'stock',
        'purchase_stock',
    ],
    'data': [
        'data/sbu_stock_locations_routes.xml',
    ],
    'post_init_hook': 'hooks.post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
