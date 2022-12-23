# Copyright © 2020 Novobi, LLC

{
    'name': 'Novobi Inventory Solution: Batch Picking',
    'version': '15.1.0',
    'summary': 'Batch Picking',
    'author': 'Novobi, LLC',
    'website': 'https://novobi.com',
    'category': 'Retail Solution',
    'license': 'OPL-1',
    'depends': [
        'stock', 'delivery', 'stock_picking_batch', 'stock_barcode_picking_batch'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/batch_picking_template_views.xml',
        'views/stock_picking_batch_views.xml',
        'views/stock_picking_type_views.xml',
        'views/sale_order_views.xml',
        'wizard/create_batch_picking.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
