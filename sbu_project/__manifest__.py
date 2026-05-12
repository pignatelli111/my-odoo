{
    'name': 'SBU Project',
    'version': '19.0.1.0.0',
    'summary': 'Project/job container for Suburban SRL',
    'description': '''
        Extends Odoo Project for Suburban SRL:
        - Link to source estimate
        - Project code generation (P{year}_{seq})
        - OneDrive folder URL field
        - Submission sheet tracking
        - Closing checklist
    ''',
    'author': 'SBU Development',
    'category': 'Project',
    'depends': [
        'base',
        'project',
        'sbu_estimate',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sbu_project_views.xml',
        'views/sbu_project_menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
