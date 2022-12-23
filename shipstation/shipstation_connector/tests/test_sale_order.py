import json
from unittest.mock import patch, Mock
from odoo.addons.omni_manage_channel.tests.utils import get_data_path
from odoo.addons.channel_base_sdk.utils.shipstation_api.resources.order import DataInTrans
from .common import ShipStationTestCommon, tagged, no_commit
from odoo.addons.sale.tests.common import TestSaleCommonBase
from ..utils.shipstation_export_helper import OrderProcessorHelper


@tagged('post_install', 'basic_test', '-at_install')
class TestShipStationSaleOrderGetData(ShipStationTestCommon, TestSaleCommonBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        with patch('odoo.addons.multichannel_product.models.product.ProductProduct.check_unique_default_code'):
            cls.company_data = cls.setup_sale_configuration_for_company(cls.company)
        cls.set_up_partners()
        cls.set_up_sale_orders()

        with open(get_data_path(__file__, 'data/shipstation_orders.json'), 'r') as fp:
            res_order_json = json.load(fp)
        intrans = DataInTrans()
        cls.transformed_orders = intrans(res_order_json)

    @classmethod
    def set_up_partners(cls):
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'partner_a',
        })

    @classmethod
    def set_up_sale_orders(cls):
        cls.order_1 = cls.env['sale.order'].with_context(mail_notrack=True, mail_create_nolog=True).create({
            'partner_id': cls.partner_a.id,
            'partner_invoice_id': cls.partner_a.id,
            'partner_shipping_id': cls.partner_a.id,
            'order_line': [
                (0, 0, {
                    'name': cls.company_data['product_order_cost'].name,
                    'product_id': cls.company_data['product_order_cost'].id,
                    'product_uom_qty': 2,
                    'qty_delivered': 2,
                    'product_uom': cls.company_data['product_order_cost'].uom_id.id,
                    'price_unit': cls.company_data['product_order_cost'].list_price,
                })
            ],
        })

    @no_commit
    def test_get_order_from_shipstation(self):
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

    def test_export_order_to_shipstation(self):
        order_helper = OrderProcessorHelper()
        exporting_data = order_helper(self.order_1, self.shipstation_channel_1)
        exporting_data.pop('name')
        exporting_data.pop('date_order')

        expected_data = {
            'id_on_shipstation': 0,
            'id_on_channel': '',
            'customer': {
                'name': 'partner_a',
                'phone': False,
                'email': False,
                'notes': False
            },
            'tax_amount': 0.0,
            'internal_notes': False,
            'requested_shipping_method': '',
            'items': [
                {
                    'id_on_shipstation': 0,
                    'id_on_channel': '',
                    'product_name': 'product_order_cost',
                    'sku': 'FURN_9999',
                    'unit_price': 280.0,
                    'quantity': 2.0,
                    'tax_amount': 0.0,
                    'weight': {
                        'value': 0.35274,
                        'units': 'ounces'
                    }
                }
            ],
            'bill_to': {
                'name': 'partner_a',
                'street1': '',
                'street2': '',
                'city': '',
                'state_code': '',
                'country_code': 'US',
                'phone': '',
                'zip': '',
                'company': ''
            },
            'ship_to': {
                'name': 'partner_a',
                'street1': '',
                'street2': '',
                'city': '',
                'state_code': '',
                'country_code': 'US',
                'phone': '',
                'zip': '',
                'company': ''
            },
            'advance_options': {
                'store_id': 98765,
                'source': 'Odoo'
            }
        }
        self.assertEqual(expected_data, exporting_data)


