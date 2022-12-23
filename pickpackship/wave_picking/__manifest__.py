{
    'name': 'Wave Picking',
    'version': '14.1.0',
    'summary': '',
    'category': 'Inventory/Inventory',
    'author': 'Novobi LLC',
    'license': 'OPL-1',
    'depends': [
        'sale_stock',
        'stock_barcode',
        'stock_picking_batch',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/stock_picking_batch_views.xml',
        'views/res_user_views.xml',
        # 'report/report_picking_batch.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
