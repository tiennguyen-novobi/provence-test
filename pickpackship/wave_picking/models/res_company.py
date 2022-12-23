from odoo import fields, models

class Company(models.Model):
    _inherit = 'res.company'

    number_of_orders_per_wave = fields.Integer(string='Number of orders per batch',
                                               default=10, help='Number of orders per batch in Pick')
