{
    'name': 'ShipStation Connector',
    'version': '15.1.0',
    'category': 'ShipStation Connector',
    'author': 'Novobi',
    'website': 'https://www.novobi.com',
    'depends': [
        'multichannel_order',
        'novobi_shipping_account'
    ],
    'data': [
        'data/shipstation_imported_product_field.xml',
        'data/queue_job_config_data.xml',
        'data/shipstation_order_status.xml',
        'data/menu_data.xml',
        'data/delivery_shipstation.xml',

        'security/ir.model.access.csv',

        'views/res_config_setting_views.xml',
        'views/shipstation_account_views.xml',
        'views/sale_order_views.xml',
        'views/omnichannel_dashboard_views.xml',
        'views/stock_picking_views.xml',
        'views/shipstation_auto_export_rule_views.xml',

        'wizard/export_shipstation_compose_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'OPL-1',
}
