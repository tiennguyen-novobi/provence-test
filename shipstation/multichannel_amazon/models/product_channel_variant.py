# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductChannelVariant(models.Model):
    _inherit = "product.channel.variant"

    asin = fields.Char(string='ASIN')
    amazon_product_type_id = fields.Selection([
        ('ASIN', 'ASIN'),
        ('ISBN', 'ISBN'),
        ('EAN', 'EAN'),
        ('UPC', 'UPC'),
        ('GCID', 'GCID')
    ], string='Amazon Product Type ID')

    amazon_product_condition = fields.Selection([
        ('New', 'New'),
        ('UsedLikeNew', 'Used - Like New'),
        ('UsedVeryGood', 'Used - Very Good'),
        ('UsedGood', 'Used - Good'),
        ('UsedAcceptable', 'Used - Acceptable'),
        ('CollectibleLikeNew', 'Collectible - Like New'),
        ('CollectibleVeryGood', 'Collectible - Very Good'),
        ('CollectibleGood', 'Collectible - Good'),
        ('CollectibleAcceptable', 'Collectible - Acceptable'),
        ('Refurbished', 'Refurbished')
    ], string='Condition')
    amazon_fulfillment_channel = fields.Selection([
        ('MFN', 'Merchant Fulfilled'),
        ('AFN', 'Fulfilled by Amazon')
    ], default='MFN', string='Fulfillment Channel')
    
    amazon_marketplace_id = fields.Many2one(related='channel_id.amazon_marketplace_id')
    
    @api.constrains(
        'asin',
        'default_code',
    )
    def _check_asin_sku_marketplace(self):
        if 'for_synching' not in self.env.context:
            for record in self:
                existed_records = self.sudo().search([
                    ('channel_id.id', '=', record.channel_id.id),
                    ('asin', '=', record.asin),
                    ('default_code', '=', record.default_code),
                    ('amazon_marketplace_id.id', '=', record.amazon_marketplace_id.id)
                ], limit=2)
                if len(existed_records) > 1:
                    raise ValidationError(_('The combination of SKU, ASIN and Marketplace must be unique'))

    def _compute_free_qty(self):
        fba_records = self.filtered(lambda r: r.channel_id.platform == 'amazon' and r.amazon_fulfillment_channel == 'AFN')
        for record in fba_records:
            record.free_qty = 0
        super(ProductChannelVariant, self - fba_records)._compute_free_qty()
