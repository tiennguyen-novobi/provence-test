# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import pytz

from typing import Any
from datetime import datetime
from .shipstation_api_helper import ShipStationHelper
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError

_logger = logging.getLogger(__name__)


class ShipStationOrderHelper:
    _api: ShipStationHelper

    def __init__(self, account):
        self._api = ShipStationHelper.connect_with_account(account)

    def cancel(self, id_on_shipstation):
        ack = self._api.orders.acknowledge(id_on_shipstation)
        ack._data._data = {'orderStatus': 'cancelled', 'orderId': id_on_shipstation}
        return ack.create_or_update_single_order()


class ShipStationOrderImporter:
    channel: Any
    ids: list
    from_date: datetime
    to_date: datetime
    limit: int
    all_records = False

    def do_import(self):
        params = self.prepare_common_params()
        yield from self.get_data(params)

    def prepare_common_params(self):
        res = dict(storeId=self.channel.shipstation_store_id)
        tz = pytz.timezone(self.channel.shipstation_account_id.tz or 'UTC')
        if self.from_date:
            now_tz = self.from_date.replace(tzinfo=pytz.utc).astimezone(tz)
            res['modifyDateStart'] = now_tz.isoformat()
        if self.to_date:
            now_tz = self.to_date.replace(tzinfo=pytz.utc).astimezone(tz)
            res['modifyDateEnd'] = now_tz.isoformat()
        return res

    def get_data(self, kw):
        try:
            res = self.get_first_data(kw)
            yield res
            yield from self.get_next_data(res)
        except Exception as ex:
            _logger.exception("Error while getting order: %s", str(ex))
            raise

    def get_first_data(self, kw):
        api = ShipStationHelper.connect_with_account(self.channel.shipstation_account_id)
        if self.ids:
            vals = []
            for id in self.ids:
                ack = api.orders.acknowledge(id.strip())
                try:
                    vals.append(ack.get_by_id().data)
                except EmptyDataError:
                    pass
            res = api.orders.create_collection_with(vals)
        else:
            if self.to_date:
                kw.update(modifyDateEnd=self.to_date.isoformat())
            res = api.orders.all(**kw)
        return res

    def get_next_data(self, res):
        try:
            while res.data:
                res = res.get_next_page()
                yield res
        except EmptyDataError:
            pass


class ShipStationOrderImportBuilder:
    orders: Any

    def prepare(self):
        if isinstance(self.orders, dict):
            self.orders = [self.orders]
        for order in self.orders:
            yield order
