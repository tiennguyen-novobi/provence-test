{
    'name': 'IoT Box Printing',
    'version': '14.1.0',
    'summary': 'Printing with IoT Box',
    'author': 'Novobi, LLC',
    'website': 'https://novobi.com',
    'category': 'Inventory',
    'license': 'OPL-1',
    'depends': [
        'label_printing', 'iot'
    ],
    'data': [
        "security/ir.model.access.csv",

        'views/ir_actions_server_views.xml',
        'views/res_users_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'printing_by_iot/static/src/js//**/*'
        ],
        'web.assets_qweb': [
            'printing_by_iot/static/src/xml/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
