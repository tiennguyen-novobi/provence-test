
import logging
from datetime import datetime
from typing import Any
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter
from .shipstation_api_helper import ShipStationHelper

_logger = logging.getLogger(__name__)


class ShipStationCarrierHelper:
    api: ShipStationHelper
    params: dict
    default_product_id: int

    def __init__(self, account, default_product_id):
        self.api = ShipStationHelper.connect_with_account(account)
        self.default_product_id = default_product_id

    def parse_service_data(self, datas, carrier_name):
        res = []
        for data in datas:
            res.append({
                'name': data['name'],
                'ss_service_name': data['name'],
                'ss_service_code': data['code'],
                'ss_carrier_code': data['carrierCode'],
                'ss_carrier_name': carrier_name,
                'product_id': self.default_product_id,
                "is_domestic": data["domestic"],
                "is_international": data["international"]
            })
        return res

    def _get_carriers(self, carrier_code):
        return self.api.carriers.get_list_services(carrier_code)

    def get_services(self, carrier_code, carrier_name):
        datas = self._get_carriers(carrier_code).data

        # FIX if the carrier returns only 1 service
        if isinstance(datas, dict):
            datas = [datas]
        #######

        return self.parse_service_data(datas, carrier_name)


class ShipStationCarrierImporter:
    account: Any
    limit: int = 100
    all_records = False
    helper: ShipStationCarrierHelper
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
        res = dict(status='any', limit=self.limit)
        return res

    def get_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
        except Exception as ex:
            _logger.exception("Error while getting all carriers: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = ShipStationHelper.connect_with_account(self.account)
        res = api.carriers.all(**kw)
        return res


class SingularCarrierDataInTrans(common_formatter.DataTrans):

    def __call__(self, carrier):
        basic_data = self.process_basic_data(carrier)
        result = {
            **basic_data,
        }
        return result

    @classmethod
    def process_basic_data(cls, carrier):
        return {
            'ss_carrier_name': carrier['name'],
            'ss_carrier_code': carrier['code'],
        }


class ShipStationCarrierImportBuilder:
    products: any
    transform_carrier = SingularCarrierDataInTrans()

    def prepare(self):
        for carrier in self.carriers:
            carrier = self.transform_carrier(carrier)
            yield carrier
