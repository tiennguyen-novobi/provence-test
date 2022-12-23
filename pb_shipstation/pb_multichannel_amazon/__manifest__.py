{
    'name': 'PB Amazon Connector',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors',
    'depends': [
        'multichannel_amazon',
        'pb_shipstation_connector',
        'stock_barcode'
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'data/config_data.xml',
        'security/ir.model.access.csv',
        'views/omni_log_views.xml',
        'views/report_packing_slip.xml',
        'views/stock_picking_views.xml',
        'views/order_process_rule_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'pb_multichannel_amazon/static/src/**/*.js',
        ],
        'web.assets_qweb': [
            'pb_multichannel_amazon/static/src/**/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1'
}
