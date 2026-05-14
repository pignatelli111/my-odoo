# -*- coding: utf-8 -*-
{
    'name': 'SBU Mail / Attachment Ingest',
    'version': '19.0.1.0.1',
    'summary': 'Optional email aliases on RFQ/PO; supplier/project routes forward to purchase (Phase 7.2)',
    'author': 'SBU Development',
    'category': 'Discuss',
    'depends': [
        'mail',
        'purchase',
        'project',
        'sbu_purchase_flow',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'views/sbu_mail_ingest_route_views.xml',
        'views/project_project_views.xml',
        'data/mail_ingest_menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
