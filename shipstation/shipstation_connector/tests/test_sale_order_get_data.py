import json
from unittest.mock import patch, Mock
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.channel_base_sdk.utils.shipstation_api.resources.order import DataInTrans
from .common import ShipStationTestCommon, tagged


@tagged('post_install', 'basic_test', '-at_install')
class TestShipStationSaleOrderGetData(ShipStationTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(get_data_path(__file__, 'data/shipstation_orders.json'), 'r') as fp:
            res_order_json = json.load(fp)
        intrans = DataInTrans()
        cls.transformed_orders = intrans(res_order_json)

    @patch('odoo.sql_db.Cursor.commit', autospec=True)
    def test_get_order_from_shipstation(self, mock_commit):
        sale_order_model = self.env['sale.order']

        shipstation_channel = self.shipstation_channel_1

        with patch('odoo.addons.shipstation_connector.utils.shipstation_order_helper.ShipStationOrderImporter.do_import',
                autospec=True) as mock_do_import:
            with patch('odoo.addons.multichannel_order.models.sale_order.SaleOrder.create_jobs_for_synching',
                       autospec=True) \
                    as mock_create_jobs_for_synching:
                mock_do_import.return_value = [Mock(data=self.transformed_orders)]
                sale_order_model.shipstation_import_orders(shipstation_channel.id)
                mock_create_jobs_for_synching.assert_called()

        mock_commit.assert_called()
