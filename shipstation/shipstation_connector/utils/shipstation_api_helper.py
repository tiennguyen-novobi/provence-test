import logging

from odoo.addons.channel_base_sdk.utils import shipstation_api as shipstation


_logger = logging.getLogger(__name__)


class ShipStationHelper:
    @classmethod
    def connect_with_account(cls, account):
        credentials = {
            'api_key': account.api_key,
            'api_secret': account.api_secret,
        }
        return cls.connect_with_dict(credentials)

    @classmethod
    def connect_with_dict(cls, credentials):
        return shipstation.connect_with(credentials)
