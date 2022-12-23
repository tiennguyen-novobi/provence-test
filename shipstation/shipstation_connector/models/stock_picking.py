from odoo import fields, models, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    shipstation_account_id = fields.Many2one('shipstation.account', string='ShipStation Account', copy=False)
    id_on_shipstation = fields.Integer(string='ID on ShipStation', readonly=True, copy=False)

    def _prepare_clear_data_for_cancel_shipment(self):
        vals = super()._prepare_clear_data_for_cancel_shipment()
        vals.update({
            'shipstation_account_id': False,
            'id_on_shipstation': False
        })
        return vals

    @api.model
    def process_shipment_data_from_channel(self, sale_id, shipment_datas, channel):
        remaining_shipments = shipment_datas
        context = self.env.context
        if channel.platform == 'shipstation':
            context = {**context, **dict(from_shipstation=True)}
            synced_shipments = sale_id.picking_ids.mapped('id_on_shipstation')
            cancel_shipments = list(filter(lambda s: (s['id_on_shipstation'] in synced_shipments and s['voided']), shipment_datas))
            self.with_context(**context)._process_cancel_shipment_data_from_channel(sale_id, cancel_shipments)
            remaining_shipments = list(filter(lambda s: not s['voided'], shipment_datas))
        super(StockPicking, self.with_context(**context)).process_shipment_data_from_channel(sale_id, remaining_shipments, channel)

    def _sync_missing_shipping_service_from_shipstation(self, carrier_code, service_code):
        shipstation_account = self.sale_id.shipstation_store_id.shipstation_account_id
        shipstation_account.create_or_update_carrier_and_service()
        delivery_carrier = shipstation_account.with_context(active_test=False).delivery_carrier_ids.filtered(lambda e: e.ss_service_code == service_code
                                                                                                             and e.ss_carrier_code == carrier_code)[-1]
        return delivery_carrier

    def _prepare_shipment_info(self, shipping_address_id, update_move_lines, shipment):
        vals = super()._prepare_shipment_info(shipping_address_id, update_move_lines, shipment)
        if 'ss_service_code' in shipment:
            shipstation_account = self.sale_id.shipstation_store_id.shipstation_account_id
            delivery_carrier = shipstation_account.with_context(active_test=False).delivery_carrier_ids.filtered(
                lambda e: e.ss_service_code == shipment['ss_service_code']
                and e.ss_carrier_code == shipment['ss_carrier_code'])[-1]

            if not delivery_carrier:
                delivery_carrier = self._sync_missing_shipping_service_from_shipstation(carrier_code=shipment['ss_carrier_code'], service_code=shipment['ss_service_code'])

            vals.update({
                'delivery_carrier_id': delivery_carrier.id,
                'insurance_cost': shipment['insurance_cost'],
                'shipstation_account_id': shipstation_account.id,
                'shipping_cost': shipment['shipping_cost'],
                'merchant_shipping_carrier': delivery_carrier.ss_carrier_name,
                'carrier_name': delivery_carrier.ss_carrier_name,
                'id_on_shipstation': shipment['id_on_shipstation']
            })

        return vals

    def _get_matching_picking_for_importing(self, shipment_data, states):
        if 'id_on_shipstation' in shipment_data:
            picking = self.filtered(lambda p: (p.id_on_shipstation == shipment_data['id_on_shipstation'] and p.state in states))
        else:
            picking = super()._get_matching_picking_for_importing(shipment_data, states)
        return picking

    def _get_matching_order_line_for_importing(self, item_data):
        if 'id_on_shipstation' in item_data:
            order_line = self.sale_id.order_line.filtered(lambda l: l.id_on_shipstation == item_data['id_on_shipstation'])
        else:
            order_line = super()._get_matching_order_line_for_importing(item_data)
        return order_line

    @api.model
    def _get_new_shipments_for_importing(self, order, shipment_datas):
        if 'id_on_shipstation' in shipment_datas[0]:
            synced_shipments = order.picking_ids.mapped('id_on_shipstation')
            new_shipments = list(filter(lambda s: s['id_on_shipstation'] not in synced_shipments, shipment_datas))
        else:
            new_shipments = super()._get_new_shipments_for_importing(order, shipment_datas)
        return new_shipments

    def mark_synced_with_channel(self, message=None):
        if self.sale_id.channel_id.platform == 'shipstation':
            return True
        return super().mark_synced_with_channel(message)

    def _action_done(self):
        res = super()._action_done()
        if 'from_shipstation' in self.env.context and 'for_synching' in self.env.context:
            for picking in self.filtered(lambda r: r.picking_type_code == 'outgoing'):
                if picking.sale_id.channel_id and picking.sale_id.channel_id.platform != 'shipstation':
                    picking.filtered(lambda sp: not sp.sale_id.has_been_shipped()).\
                        with_delay(eta=5)._post_shipment_to_channel()
        return res
