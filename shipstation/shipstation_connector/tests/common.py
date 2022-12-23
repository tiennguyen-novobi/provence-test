import functools
import uuid
from base64 import b64encode

from unittest.mock import Mock, patch

from odoo.tests.common import tagged
from odoo.addons.multichannel_order.tests.common import ChannelOrderTestCommon


class NonDelayableRecordset:
    def __init__(self, recordset):
        self.recordset = recordset

    def __getattr__(self, name):
        if name in self.recordset:
            raise AttributeError
        recordset_method = getattr(self.recordset, name)

        def exe(*args, **kwargs):
            recordset_method(*args, **kwargs)
            return Mock(uuid=str(uuid.uuid4()))

        return exe


def ignore_delay(func):
    def with_delay_side_effect(self, *_args, **_kwargs):
        return NonDelayableRecordset(self)

    @functools.wraps(func)
    def wrapper_ignore_delay(*args, **kwargs):
        with patch('odoo.addons.queue_job.models.base.Base.with_delay',
                   side_effect=with_delay_side_effect, autospec=True):
            res = func(*args, **kwargs)
        return res
    return wrapper_ignore_delay


def no_commit(func):
    @functools.wraps(func)
    def no_commit_wrapper(*args, **kwargs):
        with patch('odoo.sql_db.Cursor.commit', autospec=True):
            res = func(*args, **kwargs)
        return res
    return no_commit_wrapper


@tagged('post_install', 'basic_test', '-at_install')
class ShipStationTestCommon(ChannelOrderTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def _add_channels(cls):
        super()._add_channels()
        test_data = cls.test_data
        shipstation_account_model = cls.env['shipstation.account']
        ecommerce_channel_model = cls.env['ecommerce.channel']

        api_key = 'eyJraWQiOiIzZjVhYTFmNS1hYWE5LTQzM'
        api_secret = 'eyJraWQiOiIzZjVhYTFmNS1hYWE5LTQzM'

        with patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.create_or_update_store',
                   autospec=True), \
                patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.create_or_update_carrier_and_service'):

            shipstation_account_id = shipstation_account_model.create({
                'name': "ShipStation 1",
                'active': True,
                'api_key': api_key,
                'api_secret': api_secret,
            })

        shipstation_channel_1 = ecommerce_channel_model.create({
            'name': 'ShipStation Store 1',
            'platform': 'shipstation',
            'active': True,
            'company_id': test_data['company_1'].id,
            'auto_create_master_product': False,
            'shipstation_account_id': shipstation_account_id.id,
            'shipstation_store_id': 98765,
        })

        test_data.update({
            'shipstation_channel_1': shipstation_channel_1,
        })
        cls.shipstation_account_1 = shipstation_account_id
        cls.shipstation_channel_1 = shipstation_channel_1

    @classmethod
    def _add_customers(cls):
        super()._add_customers()
        test_data = cls.test_data
        customer_channel_model = cls.env['customer.channel']

        customer_shipstation_us_1 = customer_channel_model.create({**cls.shared_data['partner_us_1_data'], **{
            'channel_id': test_data['shipstation_channel_1'].id,
            'id_on_channel': '457509920',
        }})
        customer_shipstation_us_2 = customer_channel_model.create({**cls.shared_data['partner_us_2_data_1'], **{
            'channel_id': test_data['shipstation_channel_1'].id,
            'id_on_channel': '457509935',
        }})

        test_data.update({
            'customer_shipstation_us_1': customer_shipstation_us_1,
            'customer_shipstation_us_2': customer_shipstation_us_2,
        })
