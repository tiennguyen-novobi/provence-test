from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    number_of_orders_per_wave = fields.Integer(
        string='Number of orders per Batch',
        related='company_id.number_of_orders_per_wave',
        help='Number of orders per Batch in Pick',
        readonly=False)
