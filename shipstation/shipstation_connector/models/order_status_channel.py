from odoo import fields, models, api, _


class OrderStatusChannel(models.Model):
    _inherit = 'order.status.channel'

    platform = fields.Selection(selection_add=[('shipstation', 'ShipStation')], ondelete={'shipstation': 'set default'})
