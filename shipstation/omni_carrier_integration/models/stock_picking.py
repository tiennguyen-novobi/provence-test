# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, _

_logger = logging.getLogger(__name__)


class Picking(models.Model):
    _inherit = 'stock.picking'

    # OVERRIDE AND OVERWRITE
    @api.model
    def _process_update_shipment_data_from_channel(self, order, updated_shipments):
        for updated_shipment in updated_shipments:
            picking = order.picking_ids._get_matching_picking_for_importing(updated_shipment, ['assigned', 'done'])
            if picking and picking.carrier_tracking_ref != updated_shipment['carrier_tracking_ref']:
                if not picking.is_create_label:
                    picking.sudo().write({
                        'carrier_tracking_ref': updated_shipment['carrier_tracking_ref'],
                        'merchant_shipping_carrier': updated_shipment['merchant_shipping_carrier'],
                        'tracking_url': updated_shipment['tracking_url'],
                        'shipping_date': updated_shipment['shipping_date'],
                    })
                    picking.mark_synced_with_channel()
                else:
                    picking._log_error_when_update_labeled_shipment_from_channel()

    def _log_error_when_update_labeled_shipment_from_channel(self):
        self.ensure_one()
        title = 'Cannot update change(s) from channel'
        exceptions = [{
            'title': _("Error"),
            'reason': _("You must void label before syncing shipment"),
        }]
        self._log_exceptions_on_picking(title, exceptions)

    def _prepare_shipment_info(self, shipping_address_id, update_move_lines, shipment):
        vals = super(Picking, self)._prepare_shipment_info(shipping_address_id, update_move_lines, shipment)
        vals.update({
            'tracking_url': shipment.get('tracking_url'),
            'merchant_shipping_carrier': shipment.get('merchant_shipping_carrier'),
            'merchant_shipping_cost': shipment.get('merchant_shipping_cost'),
        })
        return vals

    def update_shipment_info(self, shipping_address_id, update_move_lines, shipment):
        self.ensure_one()
        self = self.sudo().with_context(for_synching=True)
        if not self.is_create_label:
            super(Picking, self).update_shipment_info(shipping_address_id, update_move_lines, shipment)
        else:
            self._log_error_when_update_labeled_shipment_from_channel()

    def open_create_label_form(self):
        self.ensure_one()
        self = self.sudo()
        if self.sale_id.channel_id and self.requested_carrier:
            vals = {}
            shipping_method = self.env['shipping.method.channel'].sudo().search([
                ('channel_id', '=', self.sale_id.channel_id.id),
                ('name', '=', self.requested_carrier)
            ], limit=1)
            if shipping_method:
                carrier = shipping_method.delivery_carrier_id
                vals.update({
                    'shipping_account_id': carrier.shipping_account_id.id,
                    'delivery_carrier_id': carrier.id,
                })

            self.update(vals)

        return super(Picking, self).open_create_label_form()

    def get_origin(self):
        self.ensure_one()
        origin = super(Picking, self).get_origin()
        if self.sale_id and self.sale_id.channel_id:
            origin = self.sale_id.channel_order_ref or self.sale_id.name
        return origin

    def _prepare_clear_data_for_cancel_shipment(self):
        res = super()._prepare_clear_data_for_cancel_shipment()
        if self.is_create_label:
            not_clear_fields = {
                'carrier_id',
                'carrier_tracking_ref',
                'requested_carrier',
                'merchant_shipping_carrier',
                'shipping_date',
                'tracking_url',
            }
            res = {k: v for k, v in res.items() if k not in not_clear_fields}
        else:
            res.update({
                'shipping_account_id': False,
                'delivery_carrier_id': False,
                'shipping_cost': 0,
                'insurance_cost': 0,
            })
        return res
