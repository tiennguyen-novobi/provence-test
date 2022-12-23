from odoo import api, fields, models, _

class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _default_number_of_orders_per_wave(self):
        return self.env.user.company_id.number_of_orders_per_wave or 10

    @api.model
    def _default_warehouse_id(self):
        return self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
    
    number_of_orders_per_wave = fields.Integer(string='Number of orders per Batch',
        default=_default_number_of_orders_per_wave, 
        help='Number of orders per Batch used on creating batch picking from Barcode. If it is zero, we will use the configuration in Setting app.')
    warehouse_id = fields.Many2one('stock.warehouse',
                                   string='Warehouse',
                                   domain="[('lot_stock_id.usage', '=', 'internal')]",
                                   default=_default_warehouse_id,
                                   help='The warehouse will be used when creating the batch picking from the Barcode app.')