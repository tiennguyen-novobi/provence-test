{
    'name': 'Amazon Connector',
    'version': '15.1.0',
    'summary': '',
    'author': 'Novobi LLC',
    'category': 'E-commerce Connectors',
    'depends': [
        'omni_manage_channel',
        'multichannel_product',
        'multichannel_fulfillment',
        'multichannel_order',
        'omni_log'
    ],
    'data': [
        'security/ir.model.access.csv',

        'data/amazon_order_status.xml',
        'data/amazon_marketplace_data.xml',  
        'data/amazon_fulfillment_method_data.xml',      
        'data/queue_job_config_data.xml',
        'data/menu_data.xml',
        'data/cron_jobs_data.xml',
        'data/product_imported_field_data.xml',
        'data/product_exported_field_data.xml',
        'data/resource_import_operation_type_data.xml',

        'views/amazon_marketplace_views.xml',
        'views/amazon_report_views.xml',
        'views/amazon_feed_views.xml',
        'views/ecommerce_channel_views.xml',
        'views/order_process_rule_views.xml',
        'views/product_channel_views.xml',
        'views/sale_order_views.xml',
        'views/omnichannel_dashboard_views.xml',

        'wizard/import_product_composer.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'assets': {
        'web.assets_backend': [
            'multichannel_amazon/static/src/scss/style.scss',
            'multichannel_amazon/static/src/js/action_aws_matching_products.js',
        ],
        'web.assets_qweb': [
            'multichannel_amazon/static/src/xml/aws_matching_products_template.xml',
            'multichannel_amazon/static/src/xml/custom_amazon_templates.xml',
        ],
    },
    'license': 'OPL-1'
}

