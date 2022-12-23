import json
from unittest.mock import patch, Mock
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from .common import ShipStationTestCommon, tagged, no_commit


@tagged('post_install', 'basic_test', '-at_install')
class TestShipStationAccount(ShipStationTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(get_data_path(__file__, 'data/shipstation_stores.json'), 'r') as fp:
            res_store_json = json.load(fp)
        cls.transformed_stores = res_store_json

        with open(get_data_path(__file__, 'data/shipstation_services.json'), 'r') as fp:
            res_service_json = json.load(fp)
        cls.transformed_services = res_service_json
        cls.transformed_carriers = [{
            "name": "FedEx",
            "code": "fedex",
        }]

    def test_get_store_and_service_after_connect_shipstation_account(self):
        with patch.object(type(self.env['shipstation.account']), 'create_or_update_store', autospec=True) as mock_store, \
                patch.object(type(self.env['shipstation.account']), 'create_or_update_carrier_and_service', autospec=True) as mock_service:
            self.env['shipstation.account'].create({
                'name': "ShipStation 2",
                'api_key': 'eyJraWQiOiIzZjVhYTFmNS1hYWE5LTQzM',
                'api_secret': 'eyJraWQiOiIzZjVhYTFmNS1hYWE5LTQzM',
            })
            mock_store.assert_called_once()
            mock_service.assert_called_once()

    def test_get_store_from_shipstation(self):
        with patch('odoo.addons.shipstation_connector.utils.shipstation_store_helper.ShipStationStoreImporter.do_import', autospec=True) as mock_do_import,\
                patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.check_connection', autospec=True) as mock_check_connection:
            mock_do_import.return_value = [Mock(data=self.transformed_stores[0])]
            self.shipstation_account_1.create_or_update_store()
            self.assertEqual(len(self.shipstation_account_1.ecommerce_channel_ids), 1)
            mock_check_connection.assert_called_once()

    def test_update_store_from_shipstation(self):
        with patch('odoo.addons.shipstation_connector.utils.shipstation_store_helper.ShipStationStoreImporter.do_import', autospec=True) as mock_do_import,\
                patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.check_connection', autospec=True):
            mock_do_import.return_value = [Mock(data=self.transformed_stores[0])]
            self.shipstation_account_1.create_or_update_store()
            self.assertEqual(len(self.shipstation_account_1.ecommerce_channel_ids), 1)

            mock_do_import.return_value = [Mock(data=self.transformed_stores)]
            self.shipstation_account_1.create_or_update_store()
            self.assertEqual(len(self.shipstation_account_1.ecommerce_channel_ids), 2)

    def test_remove_store_from_shipstation(self):
        with patch('odoo.addons.shipstation_connector.utils.shipstation_store_helper.ShipStationStoreImporter.do_import', autospec=True) as mock_do_import,\
                patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.check_connection', autospec=True):
            mock_do_import.return_value = [Mock(data=self.transformed_stores)]
            self.shipstation_account_1.create_or_update_store()
            self.assertEqual(len(self.shipstation_account_1.ecommerce_channel_ids), 2)

            mock_do_import.return_value = [Mock(data=self.transformed_stores[0])]
            self.shipstation_account_1.create_or_update_store()
            self.assertEqual(len(self.shipstation_account_1.ecommerce_channel_ids), 1)

    def test_uncheck_store_on_account_setting(self):
        with patch('odoo.addons.shipstation_connector.utils.shipstation_store_helper.ShipStationStoreImporter.do_import', autospec=True) as mock_do_import, \
                patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.check_connection', autospec=True):
            mock_do_import.return_value = [Mock(data=self.transformed_stores)]
            self.shipstation_account_1.create_or_update_store()
            ecommerce_channels = self.shipstation_account_1.ecommerce_channel_ids
            self.shipstation_account_1.update({'ecommerce_channel_ids': [(6, 0, ecommerce_channels[0].ids)]})
            self.assertEqual(len(self.shipstation_account_1.ecommerce_channel_ids), 1)
            self.assertRecordValues(ecommerce_channels[1], [{'active': False}])

    def test_get_services_from_shipstation(self):
        with patch('odoo.addons.shipstation_connector.utils.shipstation_carrier_helper.ShipStationCarrierImporter.do_import', autospec=True) as mock_get_carriers,\
                patch('odoo.addons.shipstation_connector.utils.shipstation_carrier_helper.ShipStationCarrierHelper._get_carriers', autospec=True) as mock_get_services, \
                patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.check_connection', autospec=True) as mock_check_connection:
            mock_get_carriers.return_value = [Mock(data=self.transformed_carriers)]
            mock_get_services.return_value = Mock(data=self.transformed_services)
            self.shipstation_account_1.create_or_update_carrier_and_service()
            self.assertEqual(len(self.shipstation_account_1.with_context(active_test=False).delivery_carrier_ids), 19)
            mock_check_connection.assert_called_once()

    def test_update_services_from_shipstation(self):
        with patch('odoo.addons.shipstation_connector.utils.shipstation_carrier_helper.ShipStationCarrierImporter.do_import', autospec=True) as mock_get_carriers,\
                patch('odoo.addons.shipstation_connector.utils.shipstation_carrier_helper.ShipStationCarrierHelper._get_carriers', autospec=True) as mock_get_services,\
                patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.check_connection', autospec=True):
            mock_get_carriers.return_value = [Mock(data=self.transformed_carriers)]
            mock_get_services.return_value = Mock(data=self.transformed_services[:18])
            self.shipstation_account_1.create_or_update_carrier_and_service()
            self.assertEqual(len(self.shipstation_account_1.with_context(active_test=False).delivery_carrier_ids), 18)

            mock_get_services.return_value = Mock(data=self.transformed_services)
            self.shipstation_account_1.create_or_update_carrier_and_service()
            self.assertEqual(len(self.shipstation_account_1.with_context(active_test=False).delivery_carrier_ids), 19)

    def test_remove_services_from_shipstation(self):
        with patch('odoo.addons.shipstation_connector.utils.shipstation_carrier_helper.ShipStationCarrierImporter.do_import', autospec=True) as mock_get_carriers,\
                patch('odoo.addons.shipstation_connector.utils.shipstation_carrier_helper.ShipStationCarrierHelper._get_carriers', autospec=True) as mock_get_services,\
                patch('odoo.addons.shipstation_connector.models.shipstation_account.ShipStationAccount.check_connection', autospec=True):
            mock_get_carriers.return_value = [Mock(data=self.transformed_carriers)]
            mock_get_services.return_value = Mock(data=self.transformed_services)
            self.shipstation_account_1.create_or_update_carrier_and_service()
            self.assertEqual(len(self.shipstation_account_1.with_context(active_test=False).delivery_carrier_ids), 19)

            mock_get_services.return_value = Mock(data=self.transformed_services[:18])
            self.shipstation_account_1.create_or_update_carrier_and_service()
            self.assertEqual(len(self.shipstation_account_1.with_context(active_test=False).delivery_carrier_ids), 19)
