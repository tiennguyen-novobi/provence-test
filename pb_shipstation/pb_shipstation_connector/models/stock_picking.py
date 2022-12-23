# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from urllib.parse import quote

from odoo.exceptions import UserError

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class Picking(models.Model):
    _inherit = 'stock.picking'

    shipstation_account_id = fields.Many2one('shipstation.account', string='ShipStation Account', ondelete='set null')

    shipstation_account_delivery_carrier_ids = fields.Many2many("delivery.carrier",
                                                                related='shipstation_account_id.delivery_carrier_ids',
                                                                string='Shipping Services', copy=False)

    default_shipstation_stock_package_type_id = fields.Many2one('stock.package.type',
                                                                string='Package Type',
                                                                domain="['|', ('package_carrier_type', '=', ss_carrier_code), ('is_custom', '=', True)]",
                                                                copy=False)

    ss_carrier_code = fields.Char(related="delivery_carrier_id.ss_carrier_code")
    ss_carrier_name = fields.Selection(
        [("fedex", "FedEx"), ("stamps_com", "Stamps.com/USPS"), ("dhl_express_worldwide", "DHL"),
         ("ups_walleted", "UPS")],
        string="Carrier")

    shipstation_usps_confirmation = fields.Selection(
        [("none", "No Confirmation"), ("delivery", "Delivery"), ("signature", "Signature"),
         ("adult_signature", "Adult Signature")], string="Confirmation")
    shipstation_fedex_confirmation = fields.Selection(
        [("none", "Service Default"), ("delivery", "No Signature"), ("signature", "Indirect Signature"),
         ("adult_signature", "Adult Signature"), ("direct_signature", "Direct Signature")], string="Confirmation")
    shipstation_ups_confirmation = fields.Selection(
        [("none", "Online"), ("delivery", "Delivery"), ("signature", "Signature"),
         ("adult_signature", "Adult Signature")], string="Confirmation")
    shipstation_dhl_worldwide_confirmation = fields.Selection([("none", "Electronic Signature")], string="Confirmation")

    shipstation_insurance = fields.Selection(
        [("none", "None"), ("shipsurance", "Shipsurance"), ("carrier", "Carrier"), ("provider", "External")],
        string="Insurance")
    shipstation_insurance_amount = fields.Monetary(string="Amount to insure")

    shipment_id_on_shipstation = fields.Integer(string="Shipment ID on ShipStation")
    package_size_length = fields.Float('Package Size Length', digits=(16, 2), copy=False,
                                       help='Package Length (in inches). Dimensions are required for Amazon shipments.')

    platform = fields.Selection(related="sale_id.channel_id.platform", store=True)

    def action_create_label(self):
        self.ensure_one()
        self = self.sudo()
        self._check_package_shipping_weight()
        self._check_shipping_date()

        self.check_and_create_custom_package_type()

        ### PB-34 ###
        # add some options for ShipStation request
        shipping_options = {
            'shipping_non_machinable': self.shipping_non_machinable,
            'shipping_require_additional_handling': self.shipping_require_additional_handling,
            'shipping_change_billing': self.shipping_change_billing,
            'shipping_include_alcohol': self.shipping_include_alcohol,
            'shipping_not_notify_marketplace': self.shipping_not_notify_marketplace
        }
        label_options = {
            'shipping_include_return_label': self.shipping_include_return_label,
            'shipping_bill_duty_and_tax': self.shipping_bill_duty_and_tax,
            'shipping_include_dry_ice': self.shipping_include_dry_ice,
        }
        delivery_options = {
            'shipping_saturday_delivery': self.shipping_saturday_delivery,
            'shipping_cod': self.shipping_cod
        }
        insurance_options = {
            'insurance_provider': self.shipping_insurance,
            'insurance_amount': self.shipping_insurance_amount,
            "shipstation_insurance": self.shipstation_insurance,
            "shipstation_insurance_amount": self.shipstation_insurance_amount
        }

        res = self.delivery_carrier_id.create_shipment_label(picking=self,
                                                             stock_package_type=self.default_stock_package_type_id,
                                                             package_length=self.package_size_length,
                                                             package_width=self.package_size_width,
                                                             package_height=self.package_size_height,
                                                             weight=self.package_shipping_weight,
                                                             pickup_date=self.shipping_date,
                                                             shipping_options=shipping_options,
                                                             label_options=label_options,
                                                             delivery_options=delivery_options,
                                                             insurance_options=insurance_options)

        if 'error_message' in res and res.get('error_message'):
            raise UserError(_("Error: %s") % res['error_message'])

        vals = self._prepare_shipping_info_data(res)

        # Force update to channel if possible
        context = dict(self.env.context)
        self.with_context(context).update(vals)

        if self.env.context.get('validate_do'):
            return self.with_context(context).button_validate()
        return True

    def _get_shipstation_barcode_string(self):
        self.ensure_one()
        return quote(f"^#^{hex(int(self.sale_id.id_on_channel)).upper()[2:]}^")
