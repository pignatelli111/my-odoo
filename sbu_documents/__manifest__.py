{
    'name': 'SBU Documents',
    'version': '19.0.1.0.0',
    'summary': 'OneDrive integration and document management for Suburban SRL',
    'description': '''
        OneDrive / Microsoft Graph API integration:
        - Auto-create project folder structure on OneDrive
        - Folder structure matches operational standard
        - Store OneDrive URL on project record
        - Document sync bridge
    ''',
    'author': 'SBU Development',
    'category': 'Document Management',
    'depends': [
        'base',
        'documents',
        'sbu_project',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sbu_documents_views.xml',
        'views/sbu_documents_menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
