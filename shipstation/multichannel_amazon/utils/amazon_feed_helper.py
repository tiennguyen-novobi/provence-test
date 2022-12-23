
import logging
from typing import Any
from .amazon_api_helper import AmazonHelper
import requests
from datetime import datetime
from xml.etree import ElementTree

_logger = logging.getLogger(__name__)


FEED_ENCODING = 'utf-8'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'

FEED_CONTENT = {
    'POST_INVENTORY_AVAILABILITY_DATA': '_generate_inventory_feed',
    'POST_ORDER_FULFILLMENT_DATA': '_generate_fulfillment_feed',
    'POST_ORDER_ACKNOWLEDGEMENT_DATA': '_generate_order_acknowledgement_feed'
}

class AmazonFeedHelper:
    _api: Any
    channel: object
    
    def __init__(self, channel):
        self.channel = channel
        self._api = AmazonHelper.connect_with_channel(channel)

    def _generate_base_feed(self):
        root = ElementTree.Element(
            'AmazonEnvelope', {'{%s}noNamespaceSchemaLocation' % XSI: 'amzn-envelope.xsd'})
        header = ElementTree.SubElement(root, 'Header')
        ElementTree.SubElement(header, 'DocumentVersion').text = "1.01"
        ElementTree.SubElement(header, 'MerchantIdentifier').text = self.channel.amazon_merchant_token
        return root
    
    def _generate_inventory_feed(self, data):
        """ Build the XML message to update available qty for all products. 
            Data must be a dictionary with this format:
            {
                "sku": "HDN-3232",
                "quantity": 10
            }
        """
        
        root = self._generate_base_feed()
        ElementTree.SubElement(root, 'MessageType').text = 'Inventory'

        for element in data:
            message = ElementTree.SubElement(root, 'Message')
            ElementTree.SubElement(message, 'MessageID').text = str(int(datetime.utcnow().timestamp()))
            ElementTree.SubElement(message, 'OperationType').text = 'Update'
            inventory_node = ElementTree.SubElement(message, 'Inventory')
            ElementTree.SubElement(inventory_node, 'SKU').text = element['sku']
            ElementTree.SubElement(inventory_node, 'Quantity').text = str(element['quantity'])
        return ElementTree.tostring(root, encoding=FEED_ENCODING, method='xml')
    
    def _generate_fulfillment_feed(self, data):
        """ Build the XML message to update available qty for all products. 
            Data must be a dictionary with this format:
            {
                "shipment_id": "WH/OUT/1333",
                "amazon_order_ref": "HDN-3232",
                "fulfillment_date": "2002-05-01T15:36:33-08:00",
                "carrier_name": "UPS",
                "tracking_number": "72282-233-2323",
                "items": [('1233-2323', 10)]
            }
        """
        
        root = self._generate_base_feed()
        ElementTree.SubElement(root, 'MessageType').text = 'OrderFulfillment'
        
        message = ElementTree.SubElement(root, 'Message')
        ElementTree.SubElement(message, 'MessageID').text = str(int(datetime.utcnow().timestamp()))
        order_fulfillment = ElementTree.SubElement(message, 'OrderFulfillment')
        ElementTree.SubElement(order_fulfillment, 'AmazonOrderID').text = data['amazon_order_ref']
        ElementTree.SubElement(order_fulfillment, 'MerchantFulfillmentID').text = str(data['shipment_id'])
        ElementTree.SubElement(order_fulfillment, 'FulfillmentDate').text = data['fulfillment_date']
        
        fulfillment_data = ElementTree.SubElement(order_fulfillment, 'FulfillmentData')
        ElementTree.SubElement(fulfillment_data, 'CarrierName').text = data['carrier_name']
        ElementTree.SubElement(fulfillment_data, 'ShippingMethod').text = data['shipping_method']
        ElementTree.SubElement(fulfillment_data, 'ShipperTrackingNumber').text = data['tracking_number']
       
        for amazon_item_ref, item_quantity in data['items']:
            item = ElementTree.SubElement(order_fulfillment, 'Item')
            ElementTree.SubElement(item, 'AmazonOrderItemCode').text = amazon_item_ref
            ElementTree.SubElement(item, 'Quantity').text = str(int(item_quantity))
        return ElementTree.tostring(root, encoding=FEED_ENCODING, method='xml')
    
    def _generate_order_acknowledgement_feed(self, data):
        root = self._generate_base_feed()
        ElementTree.SubElement(root, 'MessageType').text = 'OrderAcknowledgement'
        
        message = ElementTree.SubElement(root, 'Message')
        ElementTree.SubElement(message, 'MessageID').text = str(int(datetime.utcnow().timestamp()))
        order_acknowledgement = ElementTree.SubElement(message, 'OrderAcknowledgement')
        ElementTree.SubElement(order_acknowledgement, 'AmazonOrderID').text = data
        ElementTree.SubElement(order_acknowledgement, 'StatusCode').text = 'Failure'
        return ElementTree.tostring(root, encoding=FEED_ENCODING, method='xml')
    
    def create_feed_document(self, content_type, feed_type, data):
        feed_document_api = self._api.feed_document
        feed_document = feed_document_api.acknowledge(None)
        feed_document.data = {'contentType': content_type}
        res = feed_document.publish()
        content = ''
        if res.ok():
            content = getattr(self, FEED_CONTENT[feed_type])(data).decode(encoding='utf-8', errors='ignore')
            url = res.data['url']
            requests.put(url, data=content,  headers={'Content-Type': content_type})
        return content, res
    
    def create_feed(self, feed_type, marketplace_ids, feed_document_id):
        feed_api = self._api.feeds
        feed = feed_api.acknowledge(None)
        feed.data = dict(feedType=feed_type, 
                         marketplaceIds=[marketplace_ids], 
                         inputFeedDocumentId=feed_document_id)
        res = feed.publish()
        return res
    
    def get_feed(self, feed_id):
        feed_api = self._api.feeds
        feed = feed_api.acknowledge(feed_id)
        res = feed.get_by_id()
        return res
    
    def get_feed_document(self, feed_document_id):
        feed_document_api = self._api.feed_document
        feed_document = feed_document_api.acknowledge(feed_document_id)
        res = feed_document.get_by_id()
        return res