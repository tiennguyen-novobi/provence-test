
import logging
from typing import Any
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter

_logger = logging.getLogger(__name__)

PRODUCT_TYPE = {
    '1': 'ASIN',
    '2': 'ISBN',
    '3': 'UPC',
    '4': 'EAN'
}
CONDITION = {
    '1': 'UsedLikeNew',
    '2': 'UsedVeryGood',
    '3': 'UsedGood',
    '4': 'UsedAcceptable',
    '5': 'CollectibleLikeNew',
    '6': 'CollectibleVeryGood',
    '7': 'CollectibleGood', 
    '8': 'CollectibleAcceptable',
    '10': 'Refurbished',
    '11': 'New'
}
class SingularProductDataInTrans(common_formatter.DataTrans):

    def __call__(self, product):
        basic_data = self.process_basic_data(product)
        variant_data = self.process_variant_data(product)
        result = {
            **basic_data,
            **variant_data
        }
        return result

    @classmethod
    def process_basic_data(cls, product):
        product_type = PRODUCT_TYPE[product['product-id-type']]
        return {
            'id': product['seller-sku'],
            'name': product['item-name'],
            'sku': product['seller-sku'],
            'price': product['price'],
            'type_id': product_type,
            'condition': CONDITION[product['item-condition']],
            'asin': product['product-id'] if product_type == 'ASIN' else '',
            'isbn': product['product-id'] if product_type == 'ISBN' else '',
            'upc': product['product-id'] if product_type == 'UPC' else '',
            'ean': product['product-id'] if product_type == 'EAN' else '',
            'gcid': product['product-id'] if product_type == 'GCID' else '',
            'fulfillment_channel': 'AFN' if product['fulfillment-channel'] != 'DEFAULT' else 'MFN'
        }
        
    @classmethod
    def process_variant_data(cls, product):
        product_type = PRODUCT_TYPE[product['product-id-type']]
        return {
            'variants': [{
                    'id': f"{product['seller-sku']} - 0",
                    'name': product['item-name'],
                    'sku': product['seller-sku'],
                    'price': product['price'],
                    'type_id': product_type,
                    'condition': CONDITION[product['item-condition']],
                    'asin': product['product-id'] if product_type == 'ASIN' else '',
                    'isbn': product['product-id'] if product_type == 'ISBN' else '',
                    'upc': product['product-id'] if product_type == 'UPC' else '',
                    'ean': product['product-id'] if product_type == 'EAN' else '',
                    'gcid': product['product-id'] if product_type == 'GCID' else '',
                    'fulfillment_channel': 'AFN' if product['fulfillment-channel'] != 'DEFAULT' else 'MFN'
                }]
        }
        

class AmazonProductImportBuilder:
    products: Any
    transform_product = SingularProductDataInTrans()
    
    def prepare(self):
        for product in self.products:
            product = self.transform_product(product)
            yield product