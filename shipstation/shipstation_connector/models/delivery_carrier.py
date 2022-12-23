from odoo import fields, models, api, _


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('shipstation', 'ShipStation')], ondelete={'shipstation': 'set default'})
    ss_account_id = fields.Many2one('shipstation.account', string='ShipStation Account')
    ss_carrier_code = fields.Char(string='Carrier Code')
    ss_carrier_name = fields.Char(string='Carrier Name')
    ss_service_name = fields.Char(string='Service Name')
    ss_service_code = fields.Char(string='Service Code')

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=1000):
        res = super(DeliveryCarrier, self).name_search(name, args, operator, limit)
        if res:
            ids = list(map(lambda r: r[0], res))
            records = self.sudo().browse(ids)
            if records[0].delivery_type == 'shipstation':
                res = [(record.id, record.name, record.ss_carrier_name) for record in records]
        return res
