{
    'name': 'Label Printing',
    'version': '14.1.0',
    'summary': 'Printing',
    'author': 'Novobi, LLC',
    'website': 'https://novobi.com',
    'category': 'Inventory',
    'license': 'OPL-1',
    'depends': [
        'sale_stock', 'stock', 'delivery', 'barcodes'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/barcode_zpl_templates.xml',
        'data/config_data.xml',
        'views/res_config_settings_views.xml',
        'views/product_views.xml',
        'views/product_template_views.xml',
        'views/stock_location_views.xml',
        'views/stock_picking_views.xml',
        'wizard/print_individual_record.xml',
        'wizard/print_move_line_record.xml'
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
}
