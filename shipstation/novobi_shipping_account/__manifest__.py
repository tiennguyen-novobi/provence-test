# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Shipping Account',
    'version': '13.0.1.0.0',
    'category': 'Carrier Integration',
    'author': 'Novobi',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': [
        'delivery',
        'web_widget_selection_group'
    ],
    'data': [
        'data/ir_cron_data.xml',
        'data/report_paperformat_data.xml',
        'data/test_connection_data.xml',

        'security/ir.model.access.csv',

        'views/stock_report_views.xml',

        'views/stock_picking_package_views.xml',
        'views/stock_report_views.xml',
        'views/stock_picking_views.xml',
        'views/res_config_settings_views.xml',
        'views/delivery_view.xml',
        'views/report_packing_slip.xml',
        'views/stock_package_type_views.xml',
        'views/shipping_account_views.xml',

        'wizard/confirm_create_shipping_label.xml',
        'wizard/update_done_quantities_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'assets': {
        'web.assets_backend': [
          'novobi_shipping_account/static/src/js/boolean_button_widget.js',
          'novobi_shipping_account/static/src/js/get_rate_button.js',
          'novobi_shipping_account/static/src/js/custom_radio_selected_value.js',
          'novobi_shipping_account/static/src/js/custom_many2many_checkboxes.js',
          'novobi_shipping_account/static/src/js/custom_groupby_many2many_checkboxes.js',
          'novobi_shipping_account/static/src/js/cancel_create_label_button.js',
          'novobi_shipping_account/static/src/css/style.css',
          'novobi_shipping_account/static/src/scss/stock_picking.scss',
          'novobi_shipping_account/static/src/scss/shipping_account.scss',
        ],
        'web.assets_qweb': [
            'novobi_shipping_account/static/src/xml/templates.xml',
        ],
    },
}
