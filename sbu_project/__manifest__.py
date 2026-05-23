{
    'name': 'SBU Project',
    'version': '19.0.1.0.4',
    'summary': 'Project/job UI and menus for Suburban SRL',
    'author': 'SBU Development',
    'category': 'Project',
    'depends': [
        'base',
        'web',
        'project',
        'sbu_estimate',
    ],
    'assets': {
        'web.assets_backend': [
            'sbu_project/static/src/form/sbu_button_box.js',
            'sbu_project/static/src/form/sbu_button_box.scss',
        ],
    },
    'data': [
        'views/project_sbu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
