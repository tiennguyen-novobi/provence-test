from odoo import models, fields, api, _


class CustomsDocumentation(models.AbstractModel):
    _name = 'customs.documentation'
    _description = 'Custom Documentation'
    
    # ---Common Fields---#
    name = fields.Char('Customs Documentation')
    picking_id = fields.Many2one('stock.picking')
    ship_from_id = fields.Many2one('res.partner', string='Ship From')
    ship_to_id = fields.Many2one('res.partner', string='Ship To')
    same_info_as_ship_to = fields.Boolean('Use this information for Sold To?', default=True)
    sold_to_id = fields.Many2one('res.partner', string='Sold To Address')


class CustomsDocumentationLine(models.AbstractModel):
    _name = 'customs.documentation.line'
    _description = 'Custom Documentation Line'
    
    # Common fields
    currency_id = fields.Many2one('res.currency', string="Currency")
    picking_id = fields.Many2one('stock.picking', ondelete="cascade")
    product_id = fields.Many2one('product.product', string='Description of Goods')
