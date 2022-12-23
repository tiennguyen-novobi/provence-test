{
    'name': 'PB ShipStation Connector',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors',
    'depends': [
        'shipstation_connector',
        'pb_multichannel_order'
    ],
    'data': [
        "security/ir.model.access.csv",
        "data/usps_package_data.xml",
        "data/fedex_package_data.xml",
        "data/ups_package_data.xml",
        "data/dhl_package_data.xml",
        "views/stock_picking_views.xml",
        "views/shipstation_account_views.xml",
        'views/delivery_carrier_views.xml',
        'views/shipstation_menu.xml',
        'views/stock_package_type_view.xml',
        "views/shipstation_shipping_rule_view.xml",
        'views/sale_order_views.xml',
        'wizard/shipstation_confirm_order_views.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1'
}