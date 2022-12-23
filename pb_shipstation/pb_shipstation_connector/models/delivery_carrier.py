import base64
import json
from json import JSONDecodeError

import requests

from odoo import models, fields, api


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    # Override label name
    shipping_account_id = fields.Many2one('shipping.account', string='Shipping Account', ondelete='set null')

    # Normally just 1 record, same to 'shipping_account_id'
    shipstation_account_ids = fields.Many2many('shipstation.account', relation='rel_shipstation_account_carrier',
                                               string='Accounts')

    # New fields
    is_domestic = fields.Boolean('Domestic', default=False)
    is_international = fields.Boolean('International', default=False)

    # Remove this constraint
    _sql_constraints = [
        ('unique_name', 'CHECK(1=1)', 'This account name has already existed!\nPlease try another name.')]

    def create_or_update_shipping_account(self):
        if not self:
            return

        env = self.env['shipping.account'].with_context(active_test=False)

        for service in self:
            code = service.ss_carrier_code
            name = service.ss_carrier_name
            ss_account_id = service.ss_account_id

            shipping_account = env.search([('code', '=', code), ('ss_account_id', '=', ss_account_id.id)],
                                          limit=1) or env.create({
                'name': name + ' ({})'.format(ss_account_id.name),
                'code': code,
                'provider': 'none',
                'ss_account_id': ss_account_id.id
            })

            service.shipping_account_id = shipping_account

    def format_data_for_message_post(self, data):
        res = ""
        if data.get("serviceCode"):
            res += f"<b>Service Code:</b> {data.get('serviceCode')}<br/>"
        if data.get("weight"):
            res += f"<b>Weight:</b> {data.get('weight').get('value')} {data.get('weight').get('units')}<br/>"
        if data.get("shipTo"):
            res += f"<b>ShipTo Postal Code:</b> {data.get('shipTo').get('postalCode')}</br>"
        return res

    @api.model
    def shipstation_get_rate_and_delivery_time(self, picking, stock_package_type,
                                               package_length, package_width, package_height, weight,
                                               pickup_date, shipping_options, insurance_amount):
        """
        Get rate for shipment
        :return: {
                    'success': Bool,
                    'price': Float,
                    'estimated_date': String,
                    'error_message': String,
                    'warning_message': String,
                 }
        """
        shipstation_account_id_to_use = picking.shipstation_account_id or self.env["shipstation.account"].search([],
                                                                                                                 limit=1)

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic {}".format(
                base64.b64encode(bytes(
                    "{}:{}".format(shipstation_account_id_to_use.api_key, shipstation_account_id_to_use.api_secret),
                    "utf-8")).decode("utf-8"))
        }

        data = {
            "carrierCode": picking.delivery_carrier_id.ss_carrier_code or picking.ss_carrier_code,
            "serviceCode": picking.delivery_carrier_id.ss_service_code,
            "packageCode": picking.default_shipstation_stock_package_type_id.shipper_package_code or None,
            "fromPostalCode": picking.location_id.warehouse_id.partner_id.zip,
            "toState": picking.partner_id.state_id.code,
            "toCountry": picking.partner_id.country_id.code,
            "toPostalCode": picking.partner_id.zip,
            "toCity": picking.partner_id.city,
            "weight": {
                "value": weight,
                "units": picking.weight_unit,
            },
            "dimensions": {
                "units": "inches",
                "length": package_length,
                "width": package_width,
                "height": package_height
            },
            "confirmation": picking.shipstation_fedex_confirmation or None,
            "residential": picking.is_residential_address
        }

        print(headers, shipstation_account_id_to_use.api_key, shipstation_account_id_to_use.api_secret)
        print(data)

        if self._context.get("overrideShipStation", ""):
            if "serviceCode" in self._context:
                data["serviceCode"] = self._context["serviceCode"]
        log = self.env['omni.log'].create({'channel_id': picking.channel_id.id,
                                           'operation_type': 'auto_buy_label',
                                           'res_model': 'sale.order',
                                           'res_id': picking.sale_id.id,
                                           'order_id': picking.sale_id.id})
        try:
            response = requests.request("POST", url="https://ssapi.shipstation.com/shipments/getrates", json=data,
                                        headers=headers)
            if response.status_code == 500:
                log.update({"status": "failed",
                            "message": f"{response.status_code}: {response.reason} - {json.loads(response.text).get('ExceptionMessage', '')}"})
                return {'success': False,
                        'error_message': f"{response.status_code}: {response.reason} - {json.loads(response.text).get('ExceptionMessage', '')}"}
            if response.status_code != 200:
                log.update({"status": "failed", "message": f"{response.status_code}: {response.reason}"})
                return {'success': False, 'error_message': f"{response.status_code}: {response.reason}"}
            response_data = json.loads(response.text)
            print(response_data)
            if not response_data and not self._context.get("overrideShipStation", ""):
                error_message = "The service/package type you chose may not be compatible with the package itself."
                # also suggest compatible services
                second_response = requests.request("POST", url="https://ssapi.shipstation.com/shipments/getrates",
                                                   json={**data, **{"serviceCode": None, "packageCode": None}},
                                                   headers=headers)
                if second_response.status_code == 500:
                    return {'success': False,
                            'error_message': f"{second_response.status_code}: {second_response.reason} - {json.loads(second_response.text).get('ExceptionMessage', '')}"}
                if second_response.status_code != 200:
                    return {'success': False,
                            'error_message': f"{second_response.status_code}: {second_response.reason}"}
                second_response_data = json.loads(second_response.text)
                if not second_response_data:
                    return {'success': False, 'error_message': "No service is compatible with the package, sorry."}
                return {'success': False,
                        'error_message': error_message + " Suggested services: " + ", ".join(s["serviceName"]
                                                                                             for s in
                                                                                             second_response_data) + "."}
            # if no serviceCode is passed, all services should be returned raw
            if not data["serviceCode"]:
                log.unlink()
                return response_data
            log.unlink()
            return {"success": True, "price": response_data[0]["shipmentCost"] + response_data[0]["otherCost"]}
        except JSONDecodeError:
            log.update({"status": "failed", "message": "Response was not in JSON format!"})
            return {'success': False, "error_message": "Response was not in JSON format!"}
        except:
            log.update({"status": "failed", "message": "Cannot get rate at this time, please try again later!"})
            return {'success': False, 'error_message': "Cannot get rate at this time, please try again later!"}

    @api.model
    def shipstation_create_shipment_label(self, picking, stock_package_type,
                                          package_length, package_width, package_height, weight, insurance_options,
                                          pickup_date, shipping_options, label_options, delivery_options):

        """
        Create label
        :return: {
                    'success': Bool,
                    'price': Float,
                    'estimated_date': String,
                    'error_message': String,
                    'warning_message': String,
                    'carrier_tracking_ref': String
                 }
        """

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic {}".format(
                base64.b64encode(bytes("{}:{}".format(self.ss_account_id.api_key, self.ss_account_id.api_secret),
                                       "utf-8")).decode("utf-8"))
        }
        log = self.env['omni.log'].create({'channel_id': picking.channel_id.id,
                                           'operation_type': 'auto_buy_label',
                                           'res_model': 'sale.order',
                                           'res_id': picking.sale_id.id,
                                           'order_id': picking.sale_id.id})

        # try creating with order first
        if picking.sale_id.id_on_shipstation:
            data = {
                "orderId": picking.sale_id.id_on_shipstation,
                "carrierCode": picking.ss_carrier_code,
                "serviceCode": picking.delivery_carrier_id.ss_service_code,
                "packageCode": picking.default_shipstation_stock_package_type_id.shipper_package_code or None,
                "confirmation": picking.shipstation_fedex_confirmation or None,
                "shipDate": picking.shipping_date.strftime('%Y-%m-%d'),
                "weight": {
                    "value": weight,
                    "units": picking.weight_unit,
                },
                "dimensions": {
                    "units": "inches",
                    "length": package_length,
                    "width": package_width,
                    "height": package_height
                },
                "advancedOptions": {
                    "nonMachinable": shipping_options["shipping_non_machinable"],
                    "saturdayDelivery": delivery_options["shipping_saturday_delivery"],
                    "containsAlcohol": shipping_options["shipping_include_alcohol"],
                },
                "testLabel": False
            }

            if picking.shipstation_insurance:
                data["shipstation_insurance"] = {
                    "provider": insurance_options["shipstation_insurance"],
                    "insureShipment": True,
                    "insuredValue": insurance_options["shipstation_insurance_amount"]
                }

            picking.message_post(body=self.format_data_for_message_post(data),
                                 subject="Request body sent to /orders/createlabelfororder")

            try:
                response = requests.request("POST", url="https://ssapi.shipstation.com/orders/createlabelfororder",
                                            json=data,
                                            headers=headers)
                if response.status_code == 500:
                    log.update({"status": "failed",
                                "message": f"{response.status_code}: {response.reason} - {json.loads(response.text).get('ExceptionMessage', '')}"})
                    return {'success': False,
                            'error_message': f"{response.status_code}: {response.reason} - {json.loads(response.text).get('ExceptionMessage', '')}"}
                if response.status_code != 200:
                    log.update({"status": "failed", "message": f"{response.status_code}: {response.reason}"})
                    return {'success': False, 'error_message': f"{response.status_code}: {response.reason}"}
                response_data = json.loads(response.text)
                if not response_data:
                    return {"success": False, "error_message": "Response from ShipStation is empty!"}
                label = self.env["ir.attachment"].create(
                    {"name": f'odoo_{response_data["shipmentId"]}.pdf', "type": "binary",
                     "datas": response_data["labelData"],
                     "res_model": "stock.picking", "res_id": picking.id,
                     'mimetype': 'application/x-pdf'})
                picking.message_post(body="Label created", attachment_ids=[label.id])
                picking.write({"shipment_id_on_shipstation": response_data["shipmentId"]})
                return {"success": True, "price": response_data["shipmentCost"],
                        "carrier_tracking_ref": response_data["trackingNumber"]}
            except JSONDecodeError:
                log.update({"status": "failed", "message": "Response was not in JSON format!"})
                return {'success': False, "error_message": "Response was not in JSON format!"}
            except:
                log.update({"status": "failed", "message": "Cannot get rate at this time, please try again later!"})
                return {'success': False, 'error_message': "Cannot create label at this time, please try again later!"}

        # order has not been exported to SS; buy a standalone label
        warehouse_partner_id = picking.location_id.warehouse_id.partner_id
        data = {
            "carrierCode": picking.ss_carrier_code,
            "serviceCode": picking.delivery_carrier_id.ss_service_code,
            "packageCode": picking.default_shipstation_stock_package_type_id.shipper_package_code or None,
            "shipDate": picking.shipping_date.strftime('%Y-%m-%d'),
            "weight": {
                "value": weight,
                "units": picking.weight_unit,
            },
            "dimensions": {
                "units": "inches",
                "length": package_length,
                "width": package_width,
                "height": package_height
            },
            "shipFrom": {
                "name": "",
                "company": warehouse_partner_id.name,
                "street1": warehouse_partner_id.street,
                "street2": warehouse_partner_id.street2,
                "street3": None,
                "city": warehouse_partner_id.city,
                "state": warehouse_partner_id.state_id.code,
                "postalCode": warehouse_partner_id.zip,
                "country": warehouse_partner_id.country_id.code,
                "phone": warehouse_partner_id.phone,
                "residential": False
            },
            "shipTo": {
                "name": picking.partner_id.name,
                "company": "",
                "street1": picking.partner_id.street,
                "street2": picking.partner_id.street2,
                "street3": None,
                "city": picking.partner_id.city,
                "state": picking.partner_id.state_id.code,
                "postalCode": picking.partner_id.zip,
                "country": picking.partner_id.country_id.code,
                "phone": picking.partner_id.phone,
                "residential": picking.is_residential_address
            },
            "advancedOptions": {
                "nonMachinable": shipping_options["shipping_non_machinable"],
                "saturdayDelivery": delivery_options["shipping_saturday_delivery"],
                "containsAlcohol": shipping_options["shipping_include_alcohol"],
            },
            "testLabel": False
        }

        if picking.shipstation_insurance:
            data["shipstation_insurance"] = {
                "provider": insurance_options["shipstation_insurance"],
                "insureShipment": True,
                "insuredValue": insurance_options["shipstation_insurance_amount"]
            }

        if picking.ss_carrier_code == "fedex":
            data["confirmation"] = picking.shipstation_fedex_confirmation or None
        elif picking.ss_carrier_code == "ups":
            data["confirmation"] = picking.shipstation_ups_confirmation or None
        elif picking.ss_carrier_code == "stamps_com":
            data["confirmation"] = picking.shipstation_usps_confirmation or None

        picking.message_post(body=self.format_data_for_message_post(data),
                             subject="Request body sent to /shipments/createlabel")

        try:
            response = requests.request("POST", url="https://ssapi.shipstation.com/shipments/createlabel",
                                        json=data,
                                        headers=headers)
            if response.status_code == 500:
                log.update({"status": "failed",
                            "message": f"{response.status_code}: {response.reason} - {json.loads(response.text).get('ExceptionMessage', '')}"})
                return {'success': False,
                        'error_message': f"{response.status_code}: {response.reason} - {json.loads(response.text).get('ExceptionMessage', '')}"}
            if response.status_code != 200:
                log.update({"status": "failed", "message": f"{response.status_code}: {response.reason}"})
                return {'success': False, 'error_message': f"{response.status_code}: {response.reason}"}
            response_data = json.loads(response.text)
            if not response_data:
                return {"success": False, "error_message": "Response from ShipStation is empty!"}
            label = self.env["ir.attachment"].create(
                {"name": f'odoo_{response_data["shipmentId"]}.pdf', "type": "binary",
                 "datas": response_data["labelData"],
                 "res_model": "stock.picking", "res_id": picking.id,
                 'mimetype': 'application/x-pdf'})
            picking.message_post(body="Label created", attachment_ids=[label.id])
            picking.write({"shipment_id_on_shipstation": response_data["shipmentId"]})
            return {"success": True, "price": response_data["shipmentCost"],
                    "carrier_tracking_ref": response_data["trackingNumber"]}
        except JSONDecodeError:
            log.update({"status": "failed", "message": "Response was not in JSON format!"})
            return {'success': False, "error_message": "Response was not in JSON format!"}
        except:
            log.update({"status": "failed", "message": "Cannot get rate at this time, please try again later!"})
            return {'success': False, 'error_message': "Cannot create label at this time, please try again later!"}

    @api.model
    def shipstation_void_label(self, picking):
        """
        Void label
        :return: {
                    'success': Bool,
                    'error_message': String,
                    'warning_message': String,
                }
        """

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic {}".format(
                base64.b64encode(bytes("{}:{}".format(self.ss_account_id.api_key, self.ss_account_id.api_secret),
                                       "utf-8")).decode("utf-8"))
        }

        data = {
            "shipmentId": picking.shipment_id_on_shipstation
        }

        try:
            response = requests.request("POST", url="https://ssapi.shipstation.com/shipments/voidlabel",
                                        json=data,
                                        headers=headers)
            if response.status_code == 500:
                return {'success': False,
                        'error_message': f"{response.status_code}: {response.reason} - {json.loads(response.text).get('ExceptionMessage', '')}"}
            if response.status_code != 200:
                return {'success': False, 'error_message': f"{response.status_code}: {response.reason}"}
            response_data = json.loads(response.text)
            if not response_data:
                return {"success": False, "error_message": "Response from ShipStation is empty!"}
            if not response_data["approved"]:
                return {"success": False, "error_message": response_data["message"]}
            picking.message_post(body=f"Shipment #{picking.shipment_id_on_shipstation} has been voided")
            return {"success": True}
        except JSONDecodeError:
            return {'success': False, "error_message": "Response was not in JSON format!"}
        except:
            return {'success': False, 'error_message': "Cannot void label at this time, please try again later!"}
