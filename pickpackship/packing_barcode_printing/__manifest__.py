{
    'name': 'Packing Barcode Printing',
    'version': '14.1.0',
    'category': 'Inventory/Barcode',
    'author': 'Novobi',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': [
        'packing_barcode',
        'label_printing',
        'printing_by_iot',
    ],
    'data': [
        'data/data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'packing_barcode_printing/static/src/js/**/*'
        ],
        'web.assets_qweb': [
            'packing_barcode_printing/static/src/xml/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
