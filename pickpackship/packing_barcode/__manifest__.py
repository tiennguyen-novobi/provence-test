{
    'name': 'Packing Barcode',
    'version': '14.1.0',
    'category': 'Inventory/Barcode',
    'author': 'Novobi',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': [
        'wave_picking_barcode'
    ],
    'data': [
        'security/ir.model.access.csv',
        
        'data/data.xml',
        
        'views/stock_picking_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'packing_barcode/static/src/js/**/*'
        ],
        'web.assets_qweb': [
            'packing_barcode/static/src/xml/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
