# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from typing import Any
from datetime import datetime
from .shipstation_api_helper import ShipStationHelper
from odoo.addons.channel_base_sdk.utils.common import resource_formatter as common_formatter
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError

_logger = logging.getLogger(__name__)


class ShipStationShipmentImporter:
    channel: Any
    order_id: str
    shipment_id: None

    def do_import(self):
        api = ShipStationHelper.connect_with_account(self.channel.shipstation_account_id)
        res = api.shipments.all(orderId=self.order_id, includeShipmentItems=True)
        return res


class ShipStationShipmentImportBuilder:
    shipments: Any

    def prepare(self):
        if isinstance(self.shipments, dict):
            self.shipments = [self.shipments]
        for shipment in self.shipments:
            yield shipment
