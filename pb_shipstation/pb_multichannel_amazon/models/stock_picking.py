# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
import base64
import gzip
import json
import logging
import traceback
from datetime import datetime

import requests
from odoo.addons.channel_base_sdk.utils.amazon_api import signature_v4
from odoo.exceptions import UserError

from odoo import models, fields
from odoo.tools import pdf

POUND_TO_OUNCE = 16

_logger = logging.getLogger(__name__)


class Picking(models.Model):
    _inherit = 'stock.picking'

    suitable_service_id = fields.Many2one("suitable.service")
    amazon_insurance = fields.Boolean("Insurance")
    amazon_declared_value = fields.Monetary("Declared Value")
    shipment_id_on_amazon = fields.Char("Shipment ID on Amazon")

    def _get_access_token(self):
        channel_id = self.channel_id
        data_auth = {
            'grant_type': 'refresh_token',
            'refresh_token': channel_id.sp_refresh_token,
            'client_id': channel_id.app_client_id,
            'client_secret': channel_id.app_client_secret
        }
        response = requests.request("POST",
                                    url="https://api.amazon.com/auth/o2/token",
                                    json=data_auth,
                                    headers={"Content-Type": "application/json"})
        return json.loads(response.text)["access_token"] or ""

    def _prepare_item_list(self, access_token, is_international_shipping=False):
        channel_id = self.channel_id
        now = datetime.utcnow()
        headers = {
            'x-amz-date': now.strftime('%Y%m%dT%H%M%SZ'),
            'host': 'sellingpartnerapi-na.amazon.com',
            'user-agent': 'python-requests/2.21.0',
            'x-amz-access-token': access_token
        }
        authorization_headers = signature_v4.get_authorization_headers(
            uri=f"/orders/v0/orders/{self.sale_id.id_on_channel}/orderItems",
            headers=headers,
            params={},
            data="",
            method="GET",
            access_key=channel_id.sp_access_key,
            secret_access_key=channel_id.sp_secret_access_key,
            request_time=now,
            region="us-east-1",
            service="execute-api",
        )
        headers.update(authorization_headers)
        response = requests.request("GET",
                                    url=f"https://sellingpartnerapi-na.amazon.com/orders/v0/orders/{self.sale_id.id_on_channel}/orderItems",
                                    headers=headers)
        if response.status_code != 200:
            raise UserError(f"{response.status_code}: {response.reason}")
        response_data = json.loads(response.text)
        print(response_data)
        if not response_data.get("payload"):
            raise UserError("No items are found for the order.")
        item_list = [{"OrderItemId": item["OrderItemId"], "Quantity": item["QuantityOrdered"]}
                     for item in response_data.get("payload").get("OrderItems")]
        if is_international_shipping:
            item_list = [{**item, **{"ItemLevelSellerInputsList": [
                    {
                        "AdditionalInputFieldName": "COUNTRY_OF_ORIGIN",
                        "AdditionalSellerInput": {
                            "DataType": "STRING",
                            "ValueAsString": "US"
                        }
                    }
                ]}} for item in item_list]
        return item_list

    def _prepare_shipment_request_details(self, access_token, is_international_shipping=False):
        warehouse_partner_id = self.location_id.warehouse_id.partner_id
        data = {
            "AmazonOrderId": self.sale_id.id_on_channel,
            "ItemList": self._prepare_item_list(access_token, is_international_shipping),
            "ShipFromAddress": {
                "Name": warehouse_partner_id.name,
                "AddressLine1": warehouse_partner_id.street,
                "AddressLine2": warehouse_partner_id.street2,
                "Email": warehouse_partner_id.email,
                "City": warehouse_partner_id.city,
                "StateOrProvinceCode": warehouse_partner_id.state_id.code,
                "PostalCode": warehouse_partner_id.zip,
                "CountryCode": warehouse_partner_id.country_id.code,
                "Phone": warehouse_partner_id.phone
            },
            "PackageDimensions": {
                "Length": self.package_size_length,
                "Width": self.package_size_width,
                "Height": self.package_size_height,
                "Unit": "inches"
            },
            "Weight": {
                "Value": self.package_shipping_weight * POUND_TO_OUNCE if self.weight_unit == "lb" else self.package_shipping_weight,
                "Unit": "oz"
            }
        }
        if self.amazon_insurance:
            data["ShipmentRequestDetails"]["DeclaredValue"] = {"CurrencyCode": "USD",
                                                               "Amount": self.amazon_declared_value}
        if not is_international_shipping:
            data["ShippingServiceOptions"] = {
                "DeliveryExperience": "DeliveryConfirmationWithoutSignature",
                "CarrierWillPickUp": False,
            }
        return data

    def amazon_get_rate_and_delivery_time(self):
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
        self.ensure_one()
        channel_id = self.channel_id
        access_token = self._get_access_token()

        now = datetime.utcnow()
        headers = {
            'x-amz-date': now.strftime('%Y%m%dT%H%M%SZ'),
            'host': 'sellingpartnerapi-na.amazon.com',
            'user-agent': 'python-requests/2.21.0',
            'x-amz-access-token': access_token
        }
        data = {"ShipmentRequestDetails": self._prepare_shipment_request_details(access_token, self.partner_id.country_id.code != "US")}
        if self.partner_id.country_id.code != "US":
            data["ShippingOfferingFilter"] = {
                "DeliveryExperience": "DeliveryConfirmationWithSignature",
                "IncludeComplexShippingOptions": True
            }

        authorization_headers = signature_v4.get_authorization_headers(
            uri="/mfn/v0/eligibleShippingServices",
            headers=headers,
            params={},
            data=json.dumps(data),
            method="POST",
            access_key=channel_id.sp_access_key,
            secret_access_key=channel_id.sp_secret_access_key,
            request_time=now,
            region="us-east-1",
            service="execute-api",
        )
        headers.update(authorization_headers)

        try:
            response = requests.request("POST",
                                        url="https://sellingpartnerapi-na.amazon.com/mfn/v0/eligibleShippingServices",
                                        json=data,
                                        headers=headers)
            response_data = json.loads(response.text)
            print(response_data)
            if response.status_code != 200:
                raise UserError(f"{response.status_code}: {response.reason}")
            response_data = json.loads(response.text)
            print(response_data)
            if not response_data.get("payload"):
                raise UserError("No services are compatible with the package.")
            services = response_data.get("payload").get("ShippingServiceList")
            self.env["suitable.service"].search([]).sudo().unlink()
            for service in services:
                suitable_service = self.env["suitable.service"].sudo().create(
                    {"service_name": service["ShippingServiceName"], "carrier_name": service["CarrierName"],
                     "id_on_amazon": service["ShippingServiceId"],
                     "offer_id_on_amazon": service["ShippingServiceOfferId"],
                     "earliest_delivery_date": service["EarliestEstimatedDeliveryDate"][:10],
                     "latest_delivery_date": service["LatestEstimatedDeliveryDate"][:10],
                     "currency_id": self.env["res.currency"].search(
                         [("name", "=", service["Rate"]["CurrencyCode"])]).id,
                     "rate": service["Rate"]["Amount"], "picking_id": self.id})
                self.write({"suitable_service_id": [(4, suitable_service.id)]})
            view = self.env.ref('novobi_shipping_account.view_picking_create_label_form')

            return {
                'name': 'Create Label',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'stock.picking',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': self.id,
                # Any update to channel will need explicitly specifying
                # This is for preventing unnecessary updates
                'context': {**self.env.context, **dict(create_label=True, force_validate=True)},
            }
        except:
            raise UserError("Cannot get rate at the moment. Please try again later!")

    def amazon_create_shipment_label(self):
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
        self.ensure_one()
        self._check_package_shipping_weight()
        self._check_shipping_date()

        self.check_and_create_custom_package_type()
        if not self.suitable_service_id:
            raise UserError("Please select one service to create a label!")
        channel_id = self.channel_id
        access_token = self._get_access_token()

        now = datetime.utcnow()
        headers = {
            'x-amz-date': now.strftime('%Y%m%dT%H%M%SZ'),
            'host': 'sellingpartnerapi-na.amazon.com',
            'user-agent': 'python-requests/2.21.0',
            'x-amz-access-token': access_token
        }

        data = {
            "ShipmentRequestDetails": self._prepare_shipment_request_details(access_token, self.partner_id.country_id.code != "US"),
            "ShippingServiceId": self.suitable_service_id.id_on_amazon,
            "ShippingServiceOfferId": self.suitable_service_id.offer_id_on_amazon
        }
        if self.partner_id.country_id.code != "US":
            data["ShipmentRequestDetails"]["ShippingServiceOptions"] = {
                "DeliveryExperience": "DeliveryConfirmationWithSignature",
                "CarrierWillPickUp": False
            }

        authorization_headers = signature_v4.get_authorization_headers(
            uri="/mfn/v0/shipments",
            headers=headers,
            params={},
            data=json.dumps(data),
            method="POST",
            access_key=channel_id.sp_access_key,
            secret_access_key=channel_id.sp_secret_access_key,
            request_time=now,
            region="us-east-1",
            service="execute-api",
        )
        headers.update(authorization_headers)

        try:
            response = requests.request("POST", url="https://sellingpartnerapi-na.amazon.com/mfn/v0/shipments",
                                        json=data,
                                        headers=headers)
            response_data = json.loads(response.text)
            print(response_data)
            if response.status_code != 200:
                raise UserError(f"{response.status_code}: {response.reason}")
            if not response_data.get("payload"):
                raise UserError("The shipment information returned is empty.")
            shipment_id = response_data.get("payload").get("ShipmentId")
            label_data = response_data.get("payload").get("Label").get("FileContents").get("Contents")
            carrier_tracking_id = response_data.get("payload").get("TrackingId")
            label = self.env["ir.attachment"].create(
                {"name": f'odoo_{shipment_id}.{"png" if self.partner_id.country_id.code == "US" else "pdf"}', "type": "binary",
                 "datas": base64.b64encode(
                     gzip.decompress(base64.b64decode(bytes(label_data, "utf-8")))),
                 "res_model": "stock.picking", "res_id": self.id,
                 'mimetype': 'image/png' if self.partner_id.country_id.code == "US" else 'application/pdf'})
            self.message_post(body="Label created", attachment_ids=[label.id])
            self.write({"shipment_id_on_amazon": shipment_id, 'is_create_label': True,
                        "carrier_tracking_ref": carrier_tracking_id,
                        "shipping_cost": response_data.get("payload").get("ShippingService").get("Rate").get("Amount"),
                        "shipping_estimated_date": response_data.get("payload").get("ShippingService").get(
                            "LatestEstimatedDeliveryDate")[:10]})
        except Exception as e:
            traceback.print_exc()
            raise UserError(f"Cannot create label at this time, please try again later!\n{e}")

    def amazon_void_label(self):
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
        self.ensure_one()
        channel_id = self.channel_id
        access_token = self._get_access_token()

        now = datetime.utcnow()
        headers = {
            'x-amz-date': now.strftime('%Y%m%dT%H%M%SZ'),
            'host': 'sellingpartnerapi-na.amazon.com',
            'user-agent': 'python-requests/2.21.0',
            'x-amz-access-token': access_token
        }

        authorization_headers = signature_v4.get_authorization_headers(
            uri=f"/mfn/v0/shipments/{self.shipment_id_on_amazon}",
            headers=headers,
            params={},
            data="",
            method="DELETE",
            access_key=channel_id.sp_access_key,
            secret_access_key=channel_id.sp_secret_access_key,
            request_time=now,
            region="us-east-1",
            service="execute-api",
        )
        headers.update(authorization_headers)

        try:
            response = requests.request("DELETE",
                                        url=f"https://sellingpartnerapi-na.amazon.com/mfn/v0/shipments/{self.shipment_id_on_amazon}",
                                        headers=headers)
            if response.status_code != 200:
                raise UserError(f"{response.status_code}: {response.reason}")
            response_data = json.loads(response.text)
            if not response_data.get("payload"):
                raise UserError("The shipment information returned is empty.")
            self.message_post(body=f"Shipment {self.shipment_id_on_amazon} has been voided.")
            self.write({"shipment_id_on_amazon": False})
            return {"success": True}
        except:
            return {'success': False, 'error_message': "Cannot void label at this time, please try again later!"}

    def do_print_shipping_labels(self):
        pdf_data_string = list()
        file_names = list()
        for record in self:
            label_attachment, is_attachment = record.get_carrier_label_document()
            if label_attachment:
                label_datas = base64.b64decode(label_attachment.datas) if is_attachment else label_attachment
                pdf_data_string.append(label_datas)
                file_names.append(record.name)
        if not pdf_data_string:
            raise UserError("All the pickings chosen do not have a shipping label attached. Please buy the labels first.")
        merged_attachment = self.env['ir.attachment'].create({
            'type': 'binary',
            'datas': base64.encodebytes(pdf.merge_pdf(pdf_data_string)),
            'name': f'odoo_{"-".join(file_names)}.pdf',
        })

        return {
            'target': 'new',
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{merged_attachment.id}?download=1'
        }
