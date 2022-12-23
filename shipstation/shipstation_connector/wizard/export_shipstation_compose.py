from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ExportShipStationCompose(models.TransientModel):
    _name = 'export.shipstation.compose'
    _description = 'Export ShipStation Compose'
    _order = 'sequence'

    def _default_shipstation_account_id(self):
        shipstation_accounts = self.env['shipstation.account'].search([])
        return shipstation_accounts[0].id if shipstation_accounts else False

    sequence = fields.Integer(string='Sequence')
    order_id = fields.Many2one('sale.order', string='Order')
    is_exported_to_shipstation = fields.Boolean(string='Is exported to ShipStation')
    order_ids = fields.Many2many('sale.order', string='Orders')
    shipstation_account_id = fields.Many2one('shipstation.account', string='ShipStation Account', default=_default_shipstation_account_id)
    store_id = fields.Many2one('ecommerce.channel', string='Store')

    @api.onchange('shipstation_account_id')
    def _onchange_shipstation_account_id(self):
        all_stores = self.shipstation_account_id.ecommerce_channel_ids
        stores = all_stores.filtered(lambda e: e.is_shipstation_custom_store)
        self.store_id = stores[0].id if stores else False
        return {'domain': {'store_id': [('id', 'in', all_stores.ids)]}}

    def single_export_order(self):
        self.order_id.export_single_order_to_shipstation(self.store_id)

    def multi_export_order(self):
        if any(order.state in ('draft', 'done', 'cancel') for order in self.order_ids):
            raise UserError(_("Cannot export orders within (Draft, Done, Canceled) status. Please check the selected orders and try again!"))
        self.order_ids.shipstation_export_orders(self.store_id, self.order_ids.ids)

    def export_to_shipstation(self):
        if self.order_id:
            self.single_export_order()
        else:
            self.multi_export_order()
        return True
