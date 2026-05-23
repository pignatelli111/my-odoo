# -*- coding: utf-8 -*-
{
    'name': 'SBU Project closure (DOP / certifications)',
    'version': '19.0.1.0.5',
    'summary': 'Document object types, closure checklists, and links to project chiusura (Phase 6.5)',
    'author': 'SBU Development',
    'category': 'Project',
    'depends': [
        'base',
        'mail',
        'project',
        'sbu_estimate',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sbu_closure_document_type_data.xml',
        'views/sbu_closure_document_type_views.xml',
        'views/project_closure_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
