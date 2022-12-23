from datetime import datetime
from ..utils.shipstation_api_helper import ShipStationHelper
import json
import logging

_logger = logging.getLogger(__name__)

class RateLimit(Exception):

    def __init__(self, message):
        self.message = json.dumps(message)

    def __str__(self):
        return self.message


class ExportError(BaseException):
    def __init__(self, message):
        if type(message) == str:
            self.message = message
        else:
            self.message = json.dumps(message)

        if self.message == 'null':
            self.message = "Your request is invalid. Please check your request data and try again!"

    def __str__(self):
        return self.message


class OrderProcessorHelper:

    def __call__(self, order, shipstation_store):
        data = self._process_order_data(order, shipstation_store)
        return data

    def _process_order_data(self, order, shipstation_store):
        basic_data = self._process_basic_data(order)
        date_order = shipstation_store.shipstation_account_id.convert_tz(order.date_order, to_utc=False)
        item_data = self._process_order_line_data(order.order_line)
        address_data = self._process_addresses(order)
        advance_options = self._process_advance_options(order, shipstation_store)
        return {
            **basic_data,
            **item_data,
            **address_data,
            **advance_options,
            **dict(date_order=datetime.strftime(date_order, "%Y-%m-%dT%H:%M:%S"))
        }

    def _process_basic_data(self, order):
        vals = {
            'id_on_shipstation': order.id_on_shipstation or 0,
            'id_on_channel': order.id_on_channel or str(order.order_key_shipstation) if order.order_key_shipstation else '',
            'name': order.name,
            'customer': {
                'name': order.partner_id.name,
                'phone': order.partner_id.phone,
                'email': order.partner_id.email,
                'notes': order.customer_message,
            },
            'tax_amount': order.amount_tax,
            'internal_notes': order.staff_notes,
            'requested_shipping_method': order.requested_shipping_method or ''
        }
        return vals

    def _process_order_line_data(self, orderlines):
        lines = []
        for line in orderlines.filtered(lambda l: l.product_id.type in ['product', 'consu']):
            lines.append({
                'id_on_shipstation': line.id_on_shipstation or 0,
                'id_on_channel': line.id_on_channel or str(line.order_line_key_shipstation) if line.order_line_key_shipstation else '',
                'product_name': line.product_id.name,
                'sku': line.product_id.default_code,
                'unit_price': line.price_unit,
                'quantity': line.product_uom_qty,
                'tax_amount': line.price_tax,
                'weight': self._process_weight_data(line.product_id)
            })
        return {'items': lines}

    def _process_weight_data(self, product):
        return {
            'value': product.weight_in_oz,
            'units': 'ounces',
        }

    def _process_addresses(self, order):
        return {
            'bill_to': self._parse_address(order.partner_invoice_id),
            'ship_to': self._parse_address(order.partner_shipping_id)
        }

    def _parse_address(self, contact):
        return {
            'name': contact.name,
            'street1': contact.street or '',
            'street2': contact.street2 or '',
            'city': contact.city or '',
            'state_code': contact.state_id.code or '',
            'country_code': contact.country_id.code or '',
            'phone': contact.phone or '',
            'zip': contact.zip or '',
            'company': contact.company_name or '',
        }

    def _process_advance_options(self, order, shipstation_store):
        vals = {
            'store_id': shipstation_store.shipstation_store_id,
        }
        if order.channel_id.platform != 'shipstation':
            vals['source'] = 'Odoo'

        return {
            'advance_options': vals
        }


class ExporterHelper:
    api: any
    order_processor_helper = OrderProcessorHelper()
    shipstation_store: any

    def __init__(self, shipstation_store):
        self.api = ShipStationHelper.connect_with_account(shipstation_store.shipstation_account_id)
        self.shipstation_store = shipstation_store

    def get_order_status(self, order):
        order = self.api.orders.acknowledge(order.id_on_shipstation)
        res = order.get_by_id()
        if res.ok():
            return res.data.get('status_id')
        else:
            if res.get_status_code() == 404:
                return None
        raise ExportError(res.get_error_message())

    def export(self, order, order_status='awaiting_shipment'):

        ########## PB-20 ##########
        # data with status "cancelled" will be rejected outright by export_single_order_to_shipstation
        # -> must update differently
        # cannot override from a new file because many other files import from this file

        if order_status == "cancelled":
            order_id = str(order.id_on_shipstation)
            res = self.api.orders.acknowledge(order_id).get_by_id()
            data = json.loads(res.last_response.response.text)
            data["orderStatus"] = order_status

            # new issue discovered on 1 Mar 22: billToParty set to my_other_account when returned by API
            # but billToMyOtherAccount is None, which is invalid for an update request
            if data["advancedOptions"]["billToParty"] == "my_other_account" and data["advancedOptions"][
                "billToMyOtherAccount"] is None:
                data["advancedOptions"]["billToParty"] = None
            print(data)
        else:
            data = self.order_processor_helper(order, self.shipstation_store)
            data['order_status'] = order_status
        order = self.api.orders.create_new_with(data)
        res = order.create_or_update_single_order()
        if res.ok():
            return res.data
        elif res.get_status_code() == 429:
            raise RateLimit("Rate limit while exporting orders to ShipStation")
        elif res.get_status_code() == 404:
            raise ExportError("This order has been deleted on ShipStation")
        raise ExportError(res.get_error_message())
