from odoo import api, models, fields, _


class ProductExportPreview(models.TransientModel):
    _name = 'product.export.preview'
    _description = 'Product Export Preview'
    _rec_name = 'product_id'

    default_code = fields.Char(string='SKU')
    sequence = fields.Integer()
    product_id = fields.Many2one('product.product', string='Product')
    channel_id = fields.Many2one('ecommerce.channel', string='Store')
    product_channel_variant_id = fields.Many2one('product.channel.variant', string='Product Mapping')
    export_product_composer_id = fields.Many2one('export.product.composer')
