# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _

AMAZON_UPDATED_TEMPLATE_FIELDS = ['weight_in_oz', 'depth', 'height', 'width']

AMAZON_IGNORED_FIELDS = ['weight_in_oz', 'depth', 'height', 'width']

AMAZON_UPDATED_VARIANT_FIELDS = ['width', 'height', 'depth', 'weight_in_oz']

_logger = logging.getLogger(__name__)


class ProductChannel(models.Model):
    _inherit = "product.channel"

    asin = fields.Char(string='ASIN')
    
    amazon_product_type_id = fields.Selection([
        ('ASIN', 'ASIN'),
        ('ISBN', 'ISBN'),
        ('EAN', 'EAN'),
        ('UPC', 'UPC'),
        ('GCID', 'GCID')
    ], string='Amazon Product Type ID')
    
    amazon_marketplace_id = fields.Many2one(related='channel_id.amazon_marketplace_id')
    
    amazon_fulfillment_channel = fields.Selection([
        ('MFN', 'Merchant Fulfilled'),
        ('AFN', 'Fulfilled by Amazon')
    ], default='MFN', string='Fulfillment Channel')
    
    amazon_product_condition = fields.Selection([('New', 'New'),
                                      ('UsedLikeNew', 'Used - Like New'),
                                      ('UsedVeryGood', 'Used - Very Good'),
                                      ('UsedGood', 'Used - Good'),
                                      ('UsedAcceptable', 'Used - Acceptable'),
                                      ('CollectibleLikeNew', 'Collectible - Like New'),
                                      ('CollectibleVeryGood', 'Collectible - Very Good'),
                                      ('CollectibleGood', 'Collectible - Good'),
                                      ('CollectibleAcceptable', 'Collectible - Acceptable'),
                                      ('Refurbished', 'Refurbished')], string='Condition')

    def open_on_store(self):
        self.ensure_one()
        if self.channel_id.platform == 'amazon':
            return {
                'type': 'ir.actions.act_url',
                'url': "https://%s%s" % (self.amazon_marketplace_id.domain, '/dp/%s' % self.asin),
                'target': 'new',
            }
        return super().open_on_store()

    @api.model
    def prepare_product_channel(self, product_data, channel_id):
        channel = self.env['ecommerce.channel'].browse(channel_id)
        product_channel_vals = super(ProductChannel, self).prepare_product_channel(product_data, channel_id)
        if channel.platform == 'amazon':
            product_channel_vals.update({
                'amazon_product_type_id': product_data['type_id'],
                'amazon_product_condition': product_data['condition'],
                'asin': product_data.get('asin', ''),
                'isbn': product_data.get('isbn', ''),
                'upc': product_data.get('upc', ''),
                'ean': product_data.get('ean', ''),
                'gcid': product_data.get('gcid', ''),
                'amazon_fulfillment_channel': product_data['fulfillment_channel'],
                'is_visible': True
            })
        return product_channel_vals
    
    @api.model
    def prepare_variant_data(self, variant_data):
        variant_values = super(ProductChannel, self).prepare_variant_data(variant_data)
        if self.channel_id.platform == 'amazon':
            variant_values.update({
                'amazon_product_type_id': variant_data['type_id'],
                'asin': variant_data.get('asin'),
                'isbn': variant_data.get('isbn'),
                'upc': variant_data.get('upc'),
                'ean': variant_data.get('ean'),
                'gcid': variant_data.get('gcid', ''),
                'amazon_product_condition': variant_data.get('condition', False),
                'amazon_fulfillment_channel': variant_data.get('fulfillment_channel', 'MFN')
            })
        return variant_values
