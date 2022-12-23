from odoo import models, fields


class ShipStationConfirmOrder(models.TransientModel):
    _name = 'shipstation.confirm.order.wizard'
    _inherit = 'export.shipstation.compose'
    _description = 'ShipStation Confirm Order wizard'

    id_on_shipstation = fields.Integer(related='order_id.id_on_shipstation')

    auto_export = fields.Boolean('Export to ShipStation', default=True)
    auto_update = fields.Boolean('Update on ShipStation', default=True)
    auto_buy_label = fields.Boolean('Buy Shipping Label', default=True)

    def action_confirm_pb(self):
        self.ensure_one()
        order = self.order_id

        # By default, always buy shipping label after confirming an order.
        # Use this context to prevent buying label.
        if not self.auto_buy_label:
            order = order.with_context(no_create_label=1)

        # Export to ShipStation
        if self.auto_export and self.store_id:
            order = order.with_context(export_to_shipstation=self.store_id.id)

        # Confirm this order
        order.action_confirm()
