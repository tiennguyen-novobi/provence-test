from odoo import fields, models

class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    warehouse_manager_ids = fields.Many2many('res.partner', string='Warehouse Managers')
