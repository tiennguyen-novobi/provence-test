{
    'name': 'Wave Picking Barcode',
    'version': '15.1.0',
    'category': 'Inventory/Inventory',
    'author': 'Novobi',
    'license': 'OPL-1',
    'website': 'https://www.novobi.com',
    'depends': [
        'sale_stock',
        'wave_picking'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        
        'views/res_config_settings_views.xml',
        'views/stock_location_views.xml',
        'views/stock_warehouse_views.xml',
        
        'wizard/wave_picking_wizard_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'wave_picking_barcode/static/src/js/main_menu.js',
            'wave_picking_barcode/static/src/js/client_action/**/*',
            'wave_picking_barcode/static/src/js/order_wave_action/**/*',
            'wave_picking_barcode/static/src/js/sorting_action/**/*',
            'wave_picking_barcode/static/src/js/tote_wave_action/**/*',
            
            'wave_picking_barcode/static/src/scss/**/*',
        ],
        'web.assets_qweb': [
            'wave_picking_barcode/static/src/xml/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
