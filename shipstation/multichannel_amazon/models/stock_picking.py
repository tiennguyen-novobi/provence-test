# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import models, _
from datetime import datetime

_logger = logging.getLogger(__name__)

PROVIDER = {
    'usps': 'USPS',
    'fedex': 'FedEx',
    'ups': 'UPS'
}
class Picking(models.Model):
    _inherit = 'stock.picking'

    def amazon_post_record(self, shipment_items):
        """
        Update Order Fulfillment to Amazon
        :return:
        """
        items = []
        data = {
            'shipment_id': self.id,
            'amazon_order_ref': self.sale_id.id_on_channel,
            'fulfillment_date': datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            'carrier_name': PROVIDER.get(self.delivery_carrier_id.delivery_type, self.delivery_carrier_id.delivery_type),
            'tracking_number': self.carrier_tracking_ref if self.carrier_tracking_ref else '',
            'shipping_method': self.delivery_carrier_id.name,
            'items': []
        }
        
        for shipment_item in shipment_items:
            items.append((shipment_item['order_item_id'], shipment_item['quantity']))
            
        data['items'] = items
        feed = self.env['amazon.feed'].create({'feed_type': 'POST_ORDER_FULFILLMENT_DATA',
                                                'channel_id': self.sale_id.channel_id.id,
                                                'res_id': self.id,
                                                'res_model': self._name})
        feed.create_feed_document(content_type='text/xml', data=data)
            
    def amazon_put_record(self, shipment_items, update_items=False):
        """
        Update the shipment on Amazon when it is updated in Odoo
        :return:
        """
        title = 'Cannot update shipment on Amazon'
        self._log_exceptions_on_picking(title, [{
            'title': 'Something went wrong',
            'reason': "Currently, we do not support to update shipment on Amazon"
        }])
            