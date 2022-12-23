# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from ..common.api import cache
from ..common.exceptions import MissingRequiredKey
from ..restful.api import RestfulAPI
from ..restful.connection import RestfulConnection
from base64 import b64encode
from .registry import model_registry


class WooCommerceAPI(RestfulAPI):
    """
    WooCommerce API gateway
    """
    app_client_id: str
    app_client_secret: str
    access_token: str

    def update_credentials(self, credentials: dict):
        """
        Extract credentials and store connection
        """
        hostname, app_client_id, app_client_secret = self.extract_credentials(credentials)
        
        access_token = b64encode("{consumer_key}:{consumer_secret}".format(consumer_key=app_client_id,
                                                                          consumer_secret=app_client_secret).encode('utf-8')).decode('utf-8')
                                
        self.connection = self.build_connection(hostname, access_token)

    @classmethod
    def extract_credentials(cls, credentials):
        """
        :param credentials:
            Credentials needed for connecting to channel. It should be something like::

                {
                    'app_client_id': '2khj4821',
                    'app_client_secret': 'f9e21a1945b8fb51bce6fa1595c06405',
                    'secure_url': ''
                }

        :exception MissingRequiredKey:
            raises if the required keys are missing. Required keys: app_client_id, app_client_secret
        """
        try:
            
            return credentials['secure_url'], credentials['app_client_id'], credentials['app_client_secret']                         
        except KeyError as e:
            raise MissingRequiredKey(e) from e

    @classmethod
    def build_connection(cls, hostname: str, access_token: str):
        """
        Build connection from the provided hostname and access token
        """
        hostname = hostname.replace('https://', '') if hostname.startswith('https://') else hostname
        connection = RestfulConnection(
            scheme='https://',
            hostname=hostname if hostname.endswith('/') else f'{hostname}/',
            uri=f'wp-json/wc/',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Basic {access_token}',
            },
        )
        return connection


@cache
def connect_with(credentials: dict):
    """
    Create a gateway for WooCommerce connector
    """
    return WooCommerceAPI(credentials, model_registry)
