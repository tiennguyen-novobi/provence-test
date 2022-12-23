from odoo.addons.channel_base_sdk.utils import amazon_api as amazon
import logging

_logger = logging.getLogger(__name__)
class RateLimit(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class AmazonHelper:

    @classmethod
    def connect_with_channel(cls, channel):
        credentials = {
            'region': channel.aws_region,
            'refresh_token': channel.sp_refresh_token,
            'client_id': channel.app_client_id,
            'client_secret': channel.app_client_secret,
            'access_key': channel.sp_access_key,
            'secret_access_key': channel.sp_secret_access_key,
        }
        return cls.connect_with_dict(credentials)

    @classmethod
    def connect_with_dict(cls, credentials):
        return amazon.connect_with(credentials)
