
import logging
from datetime import datetime
from typing import Any
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter
from .shipstation_api_helper import ShipStationHelper

_logger = logging.getLogger(__name__)


class ShipStationStoreHelper:
    api: ShipStationHelper
    params: dict

    def __init__(self, account):
        self.api = ShipStationHelper.connect_with_account(account)


class ShipStationStoreImporter:
    account: Any
    limit: int = 100
    all_records = False
    helper: ShipStationStoreHelper
    params: dict

    def set_options(self, **options):
        aliases = {
        }
        for k, v in options.items():
            att = aliases.get(k, k)
            setattr(self, att, v)

    def do_import(self):
        self.params = self.prepare_common_params()
        yield from self.get_data(self.params)

    def prepare_common_params(self):
        res = dict(status='any', limit=self.limit, active=True)
        return res

    def get_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
        except Exception as ex:
            _logger.exception("Error while getting all stores: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = ShipStationHelper.connect_with_account(self.account)
        res = api.stores.all(**kw)
        return res


class SingularStoreDataInTrans(common_formatter.DataTrans):

    def __call__(self, store):
        basic_data = self.process_basic_data(store)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, store):
        return {
            'shipstation_store_id': str(store['storeId']),
            'name': store['storeName'],
            'is_shipstation_custom_store': True if not store['marketplaceId'] else False,
        }


class ShipStationStoreImportBuilder:
    products: Any
    transform_store = SingularStoreDataInTrans()

    def prepare(self):
        for store in self.stores:
            store = self.transform_store(store)
            yield store
