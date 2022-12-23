from odoo import models, fields, api


class ShippingAccount(models.Model):
    _inherit = 'shipping.account'

    code = fields.Char('Code')
    ss_account_id = fields.Many2one('shipstation.account', string='ShipStation Account')
    carrier_ids = fields.One2many('delivery.carrier', 'shipping_account_id', string='Shipping Services')
