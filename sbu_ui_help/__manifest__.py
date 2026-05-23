{
    'name': 'SBU Context Help',
    'version': '19.0.1.0.0',
    'summary': 'Floating help button (user language) for SBU screens',
    'author': 'SBU Development',
    'category': 'Hidden',
    'depends': [
        'web',
        'sbu_estimate',
        'sbu_purchase_flow',
        'sbu_sal',
        'sbu_project',
        'project',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sbu_ui_help_views.xml',
        'data/sbu_ui_help_topics.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sbu_ui_help/static/src/help/sbu_help.scss',
            'sbu_ui_help/static/src/help/sbu_help_dialog.xml',
            'sbu_ui_help/static/src/help/sbu_help_dialog.js',
            'sbu_ui_help/static/src/help/sbu_help_main.xml',
            'sbu_ui_help/static/src/help/sbu_help_main.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'auto_install': True,
}
