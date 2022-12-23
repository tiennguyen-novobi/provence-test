
import logging
import dateutil
import pytz

from typing import Any
from datetime import datetime

from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter

from .amazon_api_helper import AmazonHelper, RateLimit

_logger = logging.getLogger(__name__)


class AmazonOrderHelper:
    _api: Any

    def __init__(self, channel):
        self._api = AmazonHelper.connect_with_channel(channel)

    def get_details(self, order_id):
        result = {
            'customer': {},
            'shipping_address': {},
            'order_line': []
        }
        order_api = self._api.orders
        try:
            # Get Buyer Info
            res = order_api.get_buyer_info(order_id)
            if res.ok():
                result['customer'] = res.data['payload']
            else:
                if res.get_status_code() == 429:
                    raise RateLimit('Rate Limit while getting customer info')
            # Get Order Items
            res = order_api.get_items(order_id)
            if res.ok():
                lines = res.data['payload'].get('OrderItems', [])
                if any(l['IsGift'] not in [False, 'false'] for l in lines):
                    res = order_api.get_items_buyer_info(order_id)
                    if res.ok():
                        datas = res.data['payload']['OrderItems']
                        for e in datas:
                            line = list(filter(lambda l: l['OrderItemId'] == e['OrderItemId'], lines))
                            if line:
                                line[0].update({
                                    'GiftWrapPrice': e.get('GiftWrapPrice', {'CurrencyCode': 'USD', 'Amount': '0.00'}),
                                    'GiftWrapTax': e.get('GiftWrapTax', {'CurrencyCode': 'USD', 'Amount': '0.00'})
                                })
                    else:
                        raise RateLimit('Rate Limit while getting order item buyer info')
                result['order_line'] = lines
                
            else:
                if res.get_status_code() == 429:
                    raise RateLimit('Rate Limit while getting order items')
            # Get Shipping Address
            res = order_api.get_address(order_id)
            if res.ok():
                result['shipping_address'] = res.data['payload'].get('ShippingAddress', {})
            else:
                if res.get_status_code() == 429:
                    raise RateLimit('Rate Limit while getting shipping address')
            return result
        except EmptyDataError:
            pass


class AmazonOrderImporter:
    channel: Any
    ids: list
    created_from_date: datetime = None
    created_to_date: datetime = None
    modified_from_date: datetime = None
    modified_to_date: datetime = None

    def do_import(self):
        params = self.prepare_common_params()
        yield from self.get_data(params)

    def prepare_common_params(self):
        ### For PB only, pull FBM orders only
        # There should be a setting
        res = {
            'MarketplaceIds': self.channel.amazon_marketplace_id.api_ref,
            'FulfillmentChannels': 'MFN',
        }
        if self.ids:
            res.update(AmazonOrderIds=','.join(self.ids))
        else:
            if self.created_from_date:
                res.update(CreatedAfter=self.format_datetime(self.created_from_date))
            elif self.modified_from_date:
                res.update(LastUpdatedAfter=self.format_datetime(self.modified_from_date))
            if self.created_to_date:
                res.update(CreatedBefore=self.format_datetime(self.created_to_date))
            elif self.modified_to_date:
                res.update(LastUpdatedBefore=self.format_datetime(self.modified_to_date))
        return res

    @classmethod
    def format_datetime(cls, value):
        return value.replace(second=0).isoformat(sep='T')

    def get_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
            yield from self.get_next_data(res, MarketplaceIds=self.channel.amazon_marketplace_id.api_ref)
        except Exception as ex:
            _logger.exception("Error while getting order: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = AmazonHelper.connect_with_channel(self.channel)
        res = api.orders.all(**kw)
        return res

    @classmethod
    def get_next_data(cls, res, **kwargs):
        while res and res.data:
            res = res.get_next_page(MarketplaceIds=kwargs.get("MarketplaceIds"))
            yield res


class SingularOrderDataInTrans(common_formatter.DataTrans):

    def __call__(self, order):
        basic_data = self.process_basic_data(order)
        order_line_data = self.process_order_line_data(order)
        addresses = self.process_addresses(order)
        other_lines = self.process_other_lines(order)
        result = {
            **basic_data,
            **order_line_data,
            **addresses,
            **other_lines
        }
        return result

    @classmethod
    def process_basic_data(cls, order):
        order.update({
            'customer_id': 0,
            'channel_order_ref': order['customer_reference'],
            'channel_date_created': order['date_order'],
            'status_id': order['status'],
            'name': order['id'],
        })
        return order
        
    @classmethod
    def process_order_line_data(cls, order):
        lines = []
        for line in order['order_line']:
            try:
                price_unit = round(float(line['ItemPrice']['Amount']) / float(line['QuantityOrdered']), 2) if 'ItemPrice' in line else 0
            except ZeroDivisionError:
                price_unit = 0
            lines.append({
                'id_on_channel': line['OrderItemId'],
                'name': line.get('Title', ''),
                'product_id': None,
                'variant_id': None,
                'sku': line.get('SellerSKU', ''),
                'quantity': float(line['QuantityOrdered']),
                'price': price_unit,
                'asin': line['ASIN'],
                'product': {
                    'asin': line['ASIN'],
                    'sku': line.get('SellerSKU'),
                    'name': line.get('Title', ''),
                    'price': price_unit,
                    'fulfillment_channel': order['fulfillment_channel'],
                    'condition': f"{line.get('ConditionId', '')}{line.get('ConditionSubtypeId', '')}" if line.get('ConditionSubtypeId') else f"{line.get('ConditionId', '')}"
                }
            })                        
        return {'lines': lines}
    
    @classmethod
    def process_addresses(cls, order):
        result = {
            'billing_address': {},
            'shipping_address': {},
        }
        shipping_address = order['shipping_address']
        address_types = ('billing_address', 'shipping_address')
        address_keys = ('billing', 'shipping')
        
        datas = {
            'billing': dict(shipping_address),
            'shipping': shipping_address
        }
        datas['billing']['Name'] = order['customer'].get('BuyerName', '')            
        for address_type, address_key in zip(address_types, address_keys):
            address = datas[address_key]
            if address:
                phone = address.get('Phone', '')
                if 'ext' in phone:
                    phone = phone[0: phone.index('ext')].strip()
                result[address_type] = {
                    'name': address['Name'],
                    'street': address.get('AddressLine1', ''),
                    'street2': address.get('AddressLine2', ''),
                    'city': address.get('City', ''),
                    'state_code': address.get('StateOrRegion', ''),
                    'country_code': address.get('CountryCode', ''),
                    'email': '',
                    'phone': phone,
                    'zip': address.get('PostalCode', ''),
                    'company':  '',
                }
        return result
    
    @classmethod
    def process_other_lines(cls, order):
        """
        Process other fees such as discount, coupons of the order
        """
        discount_amount = 0.0
        shipping_cost = 0.0
        other_fees_cost = 0.0
        tax_amount = 0.0
        wrapping_cost = 0.0
        for line in order['order_line']:
            discount_amount += float(line.get('ShippingDiscount', {}).get('Amount', 0.0)) + float(line.get('PromotionDiscount', {}).get('Amount', 0.0)) + float(line.get('CODFeeDiscount', {}).get('Amount', 0.0))
            shipping_cost += float(line.get('ShippingPrice', {}).get('Amount', 0.0)) 
            other_fees_cost += float(line.get('CODFee', {}).get('Amount', 0.0)) 
            tax_amount += float(line.get('ItemTax', {}).get('Amount', 0.0)) + float(line.get('ShippingTax', {}).get('Amount', 0.0)) + float(line.get('ShippingDiscountTax', {}).get('Amount', 0.0)) + float(line.get('PromotionDiscountTax', {}).get('Amount', 0.0)) + float(line.get('GiftWrapTax', {}).get('Amount', 0.0)) 
            wrapping_cost += float(line.get('GiftWrapPrice', {}).get('Amount', 0.0)) 
        return {'discount_amount': discount_amount,
                'shipping_cost': shipping_cost,
                'other_fees_cost': other_fees_cost,
                'wrapping_cost': wrapping_cost,
                'taxes': [{'name': 'Tax', 'amount': tax_amount}]}


class AmazonOrderImportBuilder:
    orders: Any

    def prepare(self):
        for order in self.orders:
            order = self.transform_order(order)
            yield order

    @classmethod
    def transform_order(cls, order):
        is_replacement = order.get('IsReplacementOrder', False)
        if isinstance(is_replacement, str) and is_replacement in ['False', 'false']:
            is_replacement = False
        else:
            is_replacement = bool(is_replacement)
        return {
            'id': str(order['AmazonOrderId']),
            'date_order': dateutil.parser.parse(order['PurchaseDate']).astimezone(pytz.utc).replace(tzinfo=None),
            'customer_reference': str(order['AmazonOrderId']),
            'customer_message': '',
            'customer_id': 0,
            'payment_gateway_code': order.get('PaymentMethod', ''),
            'status': order['OrderStatus'],
            'requested_shipping_method': order.get('ShipServiceLevel', ''),
            'fulfillment_channel': order.get('FulfillmentChannel', ''),
            'commitment_date': dateutil.parser.parse(order.get('LatestShipDate', '')).astimezone(pytz.utc).replace(tzinfo=None),
            'is_prime': order.get('IsPrime', ''),
            'is_replacement': is_replacement,
            'replaced_order_id': order.get('ReplacedOrderId', '')
        }
