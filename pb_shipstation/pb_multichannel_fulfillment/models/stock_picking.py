# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from itertools import groupby

from odoo import api, fields, models, _
from odoo.addons.omni_manage_channel.models.customer_channel import compare_address
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def process_shipment_data_from_channel(self, order, shipment_datas, channel):
        """
        Processing response from channel for shipment
        :param order: Odoo sale.order object, the order created the shipments
        :param shipment_datas: a list of order shipments on channel for that order
                Each element in list has to be included
                'id_on_channel'
                'shipping_address'
                'carrier_tracking_ref'
                'merchant_shipping_carrier'
                'merchant_shipping_cost'
                'requested_carrier'
                'tracking_url'
                'note'
                'items': A list of items with 'order_line_id_on_channel' and 'quantity',
                'shipping_date'
        :return:
        """
        new_shipments = self._get_new_shipments_for_importing(order, shipment_datas) if shipment_datas else []

        ### PB-19 ###
        # remove check on delivery_steps
        # apply the validation process to each picking

        if new_shipments:
            order.with_context(for_synching=True).action_unlock()
            order.re_create_physical_transfer()
        context = self.env.context

        for shipment in new_shipments:
            picking = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
            if not picking:
                raise ValidationError(_('Cannot create shipment in Odoo.'))
            else:
                for p in picking:
                    p = p.with_context(**{**context, **dict(for_synching=True)})
                    update_move_lines = []
                    move_lines = p.move_lines
                    if not move_lines:
                        break
                    for item in shipment['items']:
                        # Seek stock move lines for order line
                        order_line = p._get_matching_order_line_for_importing(item)
                        lines = move_lines.filtered(lambda l: l.product_id.id == order_line.product_id.id).sorted(
                            'product_qty')
                        # In some cases, we have some stock move lines with the same product.
                        # Allocate quantity of that product on shipment to all lines contains that product
                        remaining_qty = item['quantity']
                        for index, move_line in enumerate(lines):
                            if remaining_qty == 0:
                                break
                            if move_line.product_qty < remaining_qty:
                                qty_done = move_line.product_qty
                                if index == len(lines) - 1:
                                    qty_done = remaining_qty
                                remaining_qty = remaining_qty - qty_done
                            else:
                                qty_done = remaining_qty
                                remaining_qty = 0
                            update_move_lines.append((1, move_line.id, {'quantity_done': qty_done}))

                    shipping_address = shipment.get('shipping_address', {})
                    shipping_address_id = p.sale_id.partner_shipping_id.id
                    if shipping_address:
                        # Update shipping address
                        country = self.env['res.country'].sudo().search(
                            [('code', '=ilike', shipping_address['country_iso2'])],
                            limit=1)
                        country_id = country.id

                        state_id = self.env['res.country.state'].sudo().search(
                            [('country_id.code', '=ilike', shipping_address['country_iso2']),
                             '|', ('name', '=', shipping_address['state']), ('code', '=', shipping_address['state'])],
                            limit=1).id

                        name = '%s %s' % (shipping_address['first_name'],
                                          shipping_address['last_name']) if 'first_name' in shipping_address else \
                        shipping_address['name']

                        shipping_address_record = p.sale_id.partner_id.child_ids.filtered(
                            lambda r: (r.type == 'delivery' and compare_address(
                                r, {**shipping_address, **dict(name=name, country_id=country_id, state_id=state_id)},
                                country.code)))

                        if shipping_address_record:
                            shipping_address_id = shipping_address_record[0].id
                        else:
                            shipping_address_id = self.env['res.partner'].sudo().create({'name': name,
                                                                                         'email': shipping_address[
                                                                                             'email'],
                                                                                         'phone': shipping_address[
                                                                                             'phone'],
                                                                                         'street': shipping_address[
                                                                                             'street_1'],
                                                                                         'street2': shipping_address[
                                                                                             'street_2'],
                                                                                         'city': shipping_address[
                                                                                             'city'],
                                                                                         'zip': shipping_address['zip'],
                                                                                         'country_id': country_id,
                                                                                         'state_id': state_id,
                                                                                         'parent_id': p.sale_id.partner_id.id,
                                                                                         'type': 'delivery'}).id
                            self.env.cr.commit()

                    p.update_shipment_info(shipping_address_id, update_move_lines, shipment)
