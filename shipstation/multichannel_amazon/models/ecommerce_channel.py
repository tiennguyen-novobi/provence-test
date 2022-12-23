# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

AMAZON_IMPORTED_FIELDS = [
    'Product Name',
    'Seller SKU',
    'ASIN',
    # 'ISBN',
    # 'UPC',
    # 'EAN',
    'Condition',
    'Marketplace',
    'Fulfillment Channel',
    'Your Price',
]

AMAZON_PAYMENT_GATEWAYS = [
    {'code': 'COD', 'name': 'Cash on delivery'},
    {'code': 'CVS', 'name': 'Convenience store'},
    {'code': 'Other', 'name': 'A payment method other than COD and CVS'}
]


def get_credentials(account, code):
    return dict(
        access_key=account['mws_access_key'],
        secret_key=account['mws_secret_key'],
        seller_key=account['mws_seller_key'],
        auth_token=account['mws_auth_token'],
        marketplace=code
    )


class AmazonChannel(models.Model):
    _inherit = 'ecommerce.channel'

    platform = fields.Selection(selection_add=[('amazon', 'Amazon')])

    amazon_marketplace_id = fields.Many2one('amazon.marketplace', "Amazon Marketplace")
    
    sp_access_key = fields.Char(string='Amazon Access Key')
    sp_secret_access_key = fields.Char(string='SP Secret Access Key')
    sp_refresh_token = fields.Text(string='SP Refresh Token')
    aws_region = fields.Selection(string='AWS Region', related='amazon_marketplace_id.aws_region')
    
    fba_warehouse_id = fields.Many2one('stock.warehouse', string='FBA Warehouse')
    amazon_merchant_token = fields.Char(string='Amazon Merchant Token')
    amazon_order_tag_id = fields.Many2one('crm.tag', string='Prime Order Tag')
    
    def _compute_inventory_help_text(self):
        for record in self.filtered(lambda r: r.platform == 'amazon'):
            record.inventory_help_text = """Automatically update your available inventory quantities for merchant fulfilled products"""
        super(AmazonChannel, self.filtered(lambda r: r.platform != 'amazon'))._compute_inventory_help_text()
        
    def _compute_auto_create_master_help_text(self):
        for record in self.filtered(lambda r: r.platform == 'amazon'):
            record.auto_create_master_product_help_text = """Automatically create new product as a single-variation"""
        super(AmazonChannel, self.filtered(lambda r: r.platform != 'amazon'))._compute_auto_create_master_help_text()
                     
    def _compute_master_exported_field_help_text(self):
        for record in self.filtered(lambda r: r.platform == 'amazon'):
            record.master_exported_field_help_text = """Fields exported by default: SKU, Name"""
        super(AmazonChannel, self.filtered(lambda r: r.platform != 'amazon'))._compute_master_exported_field_help_text()
            
    def open_import_product(self):
        action = super(AmazonChannel, self).open_import_product()
        if self.platform == 'amazon':
            action['context'].update({
                'options': ['all_active_products'],
                'fields': AMAZON_IMPORTED_FIELDS,
            })
        return action

    @api.model
    def amazon_get_mapping_views(self):
        parent = self.env.ref('multichannel_amazon.menu_amazon_listings')
        view_ids = [(5, 0, 0),
                    (0, 0, {'view_mode': 'tree', 'view_id': self.env.ref('multichannel_amazon.view_product_channel_amazon_tree').id}),
                    (0, 0, {'view_mode': 'form', 'view_id': self.env.ref('multichannel_amazon.view_amazon_product_channel_form').id})]
        return parent, view_ids

    def amazon_get_listing_form_view_action(self, res_id):
        return {
            'context': self._context,
            'res_model': 'product.channel',
            'target': 'current',
            'name': _('eBay Listing'),
            'res_id': res_id,
            'type': 'ir.actions.act_window',
            'views': [[self.env.ref('multichannel_amazon.view_amazon_product_channel_form').id, 'form']],
        }
    
    def _generate_action_order_view(self, view_ids):
        action = super()._generate_action_order_view(view_ids)
        if self.platform == 'amazon':
            action['search_view_id'] = self.env.ref('multichannel_amazon.view_amazon_sales_order_filter').id
        return action
    
    def get_action_product_mapping_menu(self, res_model, view_ids):
        action = super().get_action_product_mapping_menu(res_model, view_ids)
        if self.platform == 'amazon':
            action['search_view_id'] = self.env.ref('multichannel_amazon.view_amazon_product_channel_search').id
        return action
    
    @api.model
    def amazon_get_order_views(self):
        parent = self.env.ref('multichannel_amazon.menu_amazon_orders')
        view_ids = [(5, 0, 0),
                    (0, 0, {'view_mode': 'tree', 'view_id': self.env.ref('multichannel_amazon.view_all_amazon_orders_tree').id}),
                    (0, 0, {'view_mode': 'form', 'view_id': self.env.ref('multichannel_order.view_store_order_form_omni_manage_channel_inherit').id})]
        return parent, view_ids
    
    # def amazon_get_matching_product(self, id_list, marketplace_id=None, id_type='ASIN'):
    #     """
    #     * Returns a list of products and their attributes, based on a list of ASIN, GCID, SellerSKU, UPC, EAN, ISBN,
    #     and JAN values.

    #     * Throttling
    #         Maximum: Five Id values
    #         Maximum request quota: 20 requests
    #         Restore rate: Five items every second
    #         Hourly request quota: 18000 requests per hour
    #     """
    #     self.ensure_one()
    #     products_api = self._get_mws_connector(mws.Products, get_credentials(self, self.base_marketplace_id.code))
    #     error_message = _("An error was encountered when get matching product from Amazon.")
    #     marketplace_id = marketplace_id or self.base_marketplace_id.api_ref
    #     number_ids = len(id_list) - 1
    #     limit = 9 if id_type == 'ASIN' else 4
    #     ids = []
    #     datas = {}
    #     for index, id in enumerate(id_list):
    #         if len(ids) < limit and index != number_ids:
    #             ids.append(id)
    #             continue
    #         else:
    #             ids.append(id)
    #             data, rate_limit_reached = mwsc.get_matching_product(products_api=products_api,
    #                                                                  marketplaceid=marketplace_id,
    #                                                                  id_type=id_type,
    #                                                                  ids=ids,
    #                                                                  error_message=error_message)
    #             if rate_limit_reached:
    #                 time.sleep(3)
    #                 if not data:
    #                     data, rate_limit_reached = mwsc.get_matching_product(products_api=products_api,
    #                                                                          marketplaceid=marketplace_id,
    #                                                                          id_type=id_type,
    #                                                                          ids=ids,
    #                                                                          error_message=error_message)
    #             ids = []
    #             datas.update(data)
    #     return datas

    # def amazon_list_matching_products(self, query, marketplace_id=None):
    #     """
    #     * Returns a list of template products and their variants, based on query string
    #     # Query string can be product description or identifier (ASIN, ISBN, UPC, EAN)
    #     * Throttling
    #         Maximum: Five Id values
    #         Maximum request quota: 20 requests
    #         Restore rate: Five items every second
    #         Hourly request quota: 18000 requests per hour
    #     """
    #     self.ensure_one()
    #     products_api = self._get_mws_connector(mws.Products, get_credentials(self, self.base_marketplace_id.code))
    #     error_message = _("An error was encountered when list matching products from Amazon.")
    #     marketplace_id = marketplace_id or self.base_marketplace_id.api_ref
    #     data = mwsc.list_matching_products(products_api=products_api,
    #                                        marketplaceid=marketplace_id,
    #                                        query=query,
    #                                        error_message=error_message)

    #     return data

    @api.model
    def _amazon_update_inventory(self, exported_products):
        """
        Update FBM Inventory
        """
        domain = [('channel_id.id', '=', self.id),
                  ('id_on_channel', '!=', False),
                  ('amazon_fulfillment_channel', '=', 'MFN'),
                  ('product_product_id', 'in', exported_products.ids)]

        variants = self.env['product.channel.variant'].sudo().search(domain)
        variants.mapped('free_qty')

        data_inventory_sync = []
        for variant in variants:
            data_inventory_sync.append({'sku': variant.default_code,
                                        'quantity': int(variant.free_qty)})
                
        log = self.env['omni.log'].create({'datas': {'data': data_inventory_sync}, 
                                           'res_ids': ','.join(map(str, variants.mapped('id'))),
                                           'res_model': 'product.channel.variant',
                                           'channel_id': self.id,
                                           'operation_type': 'export_inventory'})
        
        feed = self.env['amazon.feed'].create({'feed_type': 'POST_INVENTORY_AVAILABILITY_DATA',
                                               'channel_id': self.id,
                                               'log_id': log.id})
        feed.create_feed_document(content_type='text/xml',
                                  data=data_inventory_sync)
        
        return []

    def _create_amazon_payment_gateways(self, channel_id):
        for gateway in AMAZON_PAYMENT_GATEWAYS:
            gateway.update({
                'platform': 'amazon',
                'channel_id': channel_id
            })
        self.env['channel.payment.gateway'].create(AMAZON_PAYMENT_GATEWAYS)

    @api.model
    def create(self, vals):
        # No export from master for Amazon
        if vals['platform'] == 'amazon':
            vals.update({
                'can_export_product': False,
                'can_export_product_from_master': False,
                'can_export_product_from_mapping': False,
            })
        res = super().create(vals)
        if res.platform == 'amazon':
            self._create_amazon_payment_gateways(res.id)
        return res

    @api.model
    def amazon_get_default_order_statuses(self):
        return self.env.ref('multichannel_amazon.amazon_order_status_unshipped')
    
    def _generate_default_order_process_rule_vals(self, statuses):
        vals = super()._generate_default_order_process_rule_vals(statuses)
        if self.platform == 'amazon':
            fulfillment_methods = self.env['amazon.fulfillment.method'].search([])
            vals.update({
                'amazon_fulfillment_method_ids': [(6, 0, fulfillment_methods.ids)]
            })
        return vals
    
    def _set_default_order_configuration(self):
        super()._set_default_order_configuration()
        if self.platform == 'amazon':
            default_warehouse = self.env['stock.warehouse'].sudo().search([('company_id.id', '=', self.company_id.id)], limit=1)
            self.update({'fba_warehouse_id': default_warehouse.id})
            
    def _get_order_configuration(self):
        res = super()._get_order_configuration()
        if self.platform == 'amazon':
            res['fba_warehouse_id'] = self.fba_warehouse_id.id
        return res
    
    @api.model
    def _run_import_product(self, channel_id, update_last_sync_product=True, auto_create_master=True, **criteria):
        res = super()._run_import_product(channel_id, update_last_sync_product, auto_create_master, **criteria)
        if self.platform == 'amazon':
            self.update({'is_in_syncing': True})
        return res