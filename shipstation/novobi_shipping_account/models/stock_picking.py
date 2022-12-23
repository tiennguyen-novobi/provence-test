# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
import base64
import io
import logging
import img2pdf
from functools import reduce
from itertools import groupby
from operator import itemgetter, or_

from PIL import Image
from dateutil import parser
from odoo.addons.novobi_shipping_account.utils.tracking_url import guess_carrier
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class Picking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'shipping.method.mixin']

    carrier_name = fields.Char(
        string='Carrier',
        help='Stores carrier when shipment is created from external source',
        copy=False,
    )
    # Mixin selection fields
    usps_first_class_mail_type = fields.Selection(store=True, copy=False)
    usps_container = fields.Selection(store=True, copy=False)

    tracking_url = fields.Char(string='Tracking Link', copy=False)
    merchant_shipping_cost = fields.Float(string='Merchant Shipping Cost', copy=False)
    merchant_shipping_carrier = fields.Char(string='Shipping Carrier', compute='_compute_merchant_shipping_carrier',
                                            store=True, copy=False, readonly=True)
    currency_id = fields.Many2one('res.currency', related='sale_id.currency_id',
                                  required=False, store=True)
    is_create_label = fields.Boolean(default=False, copy=False)
    is_change_info = fields.Boolean(default=False, copy=False)
    is_change_info_message_removed = fields.Boolean(default=False, copy=False)
    is_carrier_delivered = fields.Boolean(default=False, copy=False)
    is_save_custom_package = fields.Boolean(default=False, copy=False)
    is_package_require_dimensions = fields.Boolean(related='default_stock_package_type_id.is_require_dimensions')

    # Delivery Information
    is_mul_packages = fields.Boolean('Multiple Packages', default=False, copy=False)
    package_size_length = fields.Float('Package Size Length', digits=(16, 2), copy=False,
                                       help='Package Length (in inches)')
    package_size_width = fields.Float('Package Size Width', digits=(16, 2), copy=False,
                                      help='Package Width (in inches)')
    package_size_height = fields.Float('Package Size Height', digits=(16, 2), copy=False,
                                       help='Package Height (in inches)')
    package_shipping_weight = fields.Float(help='Package Shipping Weight (in pounds)',
                                           copy=False)
    package_shipping_weight_oz = fields.Float(help='Package Shipping Weight (in ounces)',
                                              compute='_get_weight_in_oz', inverse='_set_weight_in_oz')

    picking_package_ids = fields.One2many('stock.picking.package', 'picking_id', string='Picking Packages', copy=False)
    remaining_picking_package_weight = fields.Float(help='Package Shipping Weight (in pounds)', digits='Stock Weight',
                                                    compute='_compute_remaining_picking_package_weight')

    shipping_date = fields.Date(string='Ship Date', copy=False)
    shipping_insurance = fields.Selection(selection=[('none', 'None'), ('carrier', 'Carrier')], copy=False,
                                          string='Shipping Insurance')
    shipping_insurance_amount = fields.Monetary('Shipping Insurance Amount', copy=False)

    # Shipping Information
    shipping_cost = fields.Monetary(string='Shipping Cost', copy=False)
    shipping_estimated_date = fields.Char(string='Shipping Estimated Date', copy=False)
    tracking_number = fields.Char(string='Tracking Number', copy=False)
    insurance_cost = fields.Monetary(string='Insurance Cost', copy=False)
    shipping_cost_without_discounts = fields.Monetary(string='Before Discounts', copy=False)
    is_international_delivery = fields.Boolean('Is This Delivery Order International?',
                                               compute="_compute_international_delivery")
    shipment_description = fields.Text('What Are You Shipping?')
    # Other shipping options
    shipping_non_machinable = fields.Boolean(copy=False)
    shipping_require_additional_handling = fields.Boolean(copy=False)
    shipping_change_billing = fields.Boolean(copy=False)
    shipping_customer_account = fields.Char(copy=False)
    shipping_customer_zipcode = fields.Char(copy=False)
    shipping_include_alcohol = fields.Boolean(copy=False)
    shipping_not_notify_marketplace = fields.Boolean(copy=False)
    shipping_include_return_label = fields.Boolean(copy=False)
    shipping_print_postage_on_label = fields.Boolean(copy=False)
    shipping_bill_duty_and_tax = fields.Boolean(copy=False)
    shipping_include_dry_ice = fields.Boolean(copy=False)
    shipping_dry_ice_weight_in_oz = fields.Float(digits=(16, 2), copy=False)
    shipping_cod = fields.Boolean(copy=False)
    shipping_cod_payment_type = fields.Selection(selection=[
        ('any', 'Any'),
        ('cash', 'Cash'),
        ('check', 'MoneyOrderOrCashiersCheck'),
    ], copy=False)
    shipping_cod_amount = fields.Monetary(copy=False)
    shipping_saturday_delivery = fields.Boolean(copy=False)
    shipping_optional_signature = fields.Boolean(copy=False)

    estimated_shipping_rate = fields.Float(string='Estimated Shipping Rate', copy=False)
    estimated_done_date = fields.Char('Estimated Date', copy=False)

    # Display error message
    error_message = fields.Char(readonly=True, copy=False)

    no_shipping_cost = fields.Boolean(help='True if shipping cost is not in response', copy=False, readonly=True,
                                      compute='_compute_no_shipping_cost')
    no_insurance_cost = fields.Boolean(help='True if insurance cost is not in response', copy=False, readonly=True)
    handling_fee = fields.Monetary(string='Handling Charges', help='Handling Charges')
    custom_packaging_name = fields.Char("Custom Package Name", copy=False)
    weight_unit = fields.Selection([
        ('lb', 'lb'),
        ('oz', 'oz')
    ], string='Weight Unit', default='lb')

    def _compute_no_shipping_cost(self):
        for record in self:
            record.no_shipping_cost = True if float_is_zero(record.shipping_cost, precision_digits=2) else False

    def _get_weight_in_oz(self):
        for record in self:
            if record.package_shipping_weight:
                record.package_shipping_weight_oz = record.package_shipping_weight * 16
            else:
                record.package_shipping_weight_oz = 0

    def _set_weight_in_oz(self):
        for record in self:
            if record.package_shipping_weight_oz:
                record.package_shipping_weight = record.package_shipping_weight_oz * 0.0625
            else:
                record.package_shipping_weight = 0

    @api.depends('provider')
    def _compute_merchant_shipping_carrier(self):
        for rec in self:
            # Change Merchant shipping carrier when user change shipment info in channel
            if rec._origin.id:
                rec.merchant_shipping_carrier = dict(
                    rec.env['shipping.account'].sudo()._fields['provider'].selection).get(
                    rec.shipping_account_id.provider)

    @api.depends('package_shipping_weight', 'picking_package_ids')
    def _compute_remaining_picking_package_weight(self):
        for record in self:
            remaining_weight = record.package_shipping_weight - sum(record.picking_package_ids.mapped('weight'))
            record.remaining_picking_package_weight = max(remaining_weight, 0.0)

    @api.depends('picking_type_id', 'picking_type_id.warehouse_id', 'picking_type_id.warehouse_id.partner_id')
    def _compute_international_delivery(self):
        for picking in self:
            ship_from = picking.picking_type_id.warehouse_id.partner_id
            ship_to = picking.partner_id
            if ship_from.country_id and ship_to.country_id:
                picking.is_international_delivery = (
                        ship_from.country_id.id != ship_to.country_id.id)
            else:
                picking.is_international_delivery = False

    @api.onchange('is_save_custom_package')
    def _onchange_custom_packaging_name(self):
        self.ensure_one()
        self.custom_packaging_name = f'{self.package_size_length}"L x {self.package_size_width}"W x {self.package_size_height}"H' if self.is_save_custom_package else False

    @api.onchange('partner_id', 'location_id', 'move_ids_without_package')
    def _onchange_partner_and_location(self):
        self.ensure_one()
        if self.is_create_label:
            self.is_change_info = True
            self.is_change_info_message_removed = False

    @api.onchange('shipping_insurance')
    def _onchange_shipping_insurance(self):
        if self.shipping_insurance not in [False, 'none']:
            self.shipping_insurance_amount = sum(
                line.quantity_done * (line.sale_line_id.price_unit or line.product_id.lst_price)
                for line in self.move_lines)
        else:
            self.shipping_insurance_amount = 0

    @api.onchange('shipping_date')
    def _onchange_shipping_date(self):
        if self.shipping_date and self.shipping_date < fields.Date.today() and 'no_check' not in self.env.context:
            return dict(warning={
                'title': _('Invalid Ship date'),
                'message': _('Ship Date must be greater or equal today.')
            })

    @api.onchange('shipping_account_id')
    def onchange_shipping_account(self):
        self.ensure_one()
        self.is_mul_packages = False
        self.onchange_is_mul_packages()
        self.shipping_insurance = False
        self.handling_fee = self.shipping_account_id.handling_fee
        return super(Picking, self).onchange_shipping_account()

    @api.onchange('is_mul_packages')
    def onchange_is_mul_packages(self):
        handling_fee = self.shipping_account_id.handling_fee
        self.update({
            'picking_package_ids': [(5, 0, 0)],
            'handling_fee': handling_fee
        })

    @api.onchange('shipping_insurance')
    def _onchange_insurance_amount(self):
        self.ensure_one()
        if self.shipping_insurance not in [False, 'none']:
            self.shipping_insurance_amount = self.sale_id.amount_total
        else:
            self.shipping_insurance_amount = 0

    @api.onchange('tracking_url')
    def _onchange_tracking_url(self):
        self.ensure_one()
        self.carrier_tracking_url = self.tracking_url

    @api.onchange('default_stock_package_type_id')
    def _onchange_default_stock_package_type_id(self):
        self.ensure_one()
        self.update({
            'is_save_custom_package': False,
            'custom_packaging_name': False,
        })
        if self.default_stock_package_type_id.is_custom:
            self.update({
                'package_size_length': self.default_stock_package_type_id.length,
                'package_size_width': self.default_stock_package_type_id.width,
                'package_size_height': self.default_stock_package_type_id.height,
            })

    @api.constrains('is_mul_packages', 'picking_package_ids')
    def _check_picking_package_ids(self):
        if any(r.is_mul_packages and len(r.picking_package_ids) == 0 for r in self):
            raise ValidationError(_('Please add at least 1 package.'))

    @api.constrains('shipping_insurance', 'shipping_insurance_amount')
    def _check_shipping_insurance_amount(self):
        if not self.env.context.get('force_validate', False):
            return True
        if any(r.shipping_insurance not in [False, 'none']
               and r.currency_id
               and r.currency_id.compare_amounts(r.shipping_insurance_amount, 0) <= 0
               for r in self):
            raise ValidationError(_('Insurance Amount must be greater than 0.'))

    def _check_shipping_date(self):
        if any(r.shipping_date and r.shipping_date < fields.Date.today() for r in self):
            raise UserError(_('Ship Date must be greater or equal today.'))

    def remove_change_info_message(self):
        self.ensure_one()
        self.write({'is_change_info_message_removed': True})

    def open_website_url(self):
        self.ensure_one()
        if self.carrier_tracking_url:
            return super(Picking, self).open_website_url()
        else:
            match = guess_carrier(self.carrier_tracking_ref)
            if not match:
                raise UserError(
                    _("Your delivery method has no redirect on courier provider's website to track this order."))
            else:
                return {
                    'type': 'ir.actions.act_url',
                    'name': "Shipment Tracking Page",
                    'target': 'new',
                    'url': match.url,
                }

    def check_and_create_custom_package_type(self):
        """
        We do not save package if it is not required to
        We do not save package for shipment with more than one package.
        Package with invalid size should not be saved either
        """
        self.ensure_one()
        if not self.is_mul_packages and self.is_save_custom_package:
            is_invalid_size = all(
                float_is_zero(x, 2)
                for x in (self.package_size_length, self.package_size_width, self.package_size_height)
            )
            if is_invalid_size:
                raise UserError(_("Please provide information for the custom package size"))

            self.create_custom_package_type()

    def create_custom_package_type(self):
        self.ensure_one()
        self.env['stock.package.type'].sudo().create({
            'name': self.custom_packaging_name,
            'length': self.package_size_length,
            'width': self.package_size_width,
            'height': self.package_size_height,
            'is_custom': True,
            'sequence': 1000,
        })

    @api.model
    def _check_package_shipping_weight(self):
        if any(r.picking_type_code == 'outgoing' and r.package_shipping_weight <= 0 and not r.is_mul_packages for r in
               self):
            raise UserError(_('Weight for Shipping must be greater than 0.'))

    @api.model
    def _reset_label_fields(self):
        return {
            'shipping_cost': 0.0,
            'shipping_cost_without_discounts': 0.0,
            'handling_fee': 0.0,
            'no_shipping_cost': False,
            'insurance_cost': 0.0,
            'no_insurance_cost': False,
            'carrier_price': 0.0,
            'package_size_length': 0,
            'package_size_width': 0,
            'package_size_height': 0,
            'estimated_shipping_rate': 0.0,
            'provider': False,
            'shipping_insurance': 'none',
            'shipping_insurance_amount': False,
            'shipping_estimated_date': False,
            'shipping_account_id': False,
            'delivery_carrier_id': False,
            'shipping_date': False,
            'carrier_tracking_ref': False,
            'carrier_tracking_url': False,
            'carrier_id': False,
            'default_stock_package_type_id': False,
            'usps_is_first_class': False,
            'usps_first_class_mail_type': False,
            'usps_container': False,
            'custom_packaging_name': False,

            # Other Shipping Information
            'shipping_non_machinable': False,
            'shipping_require_additional_handling': False,
            'shipping_change_billing': False,
            'shipping_include_alcohol': False,
            'shipping_not_notify_marketplace': False,
            'shipping_include_return_label': False,
            'shipping_bill_duty_and_tax': False,
            'shipping_include_dry_ice': False,
            'shipping_saturday_delivery': False,
            'shipping_cod': False,
            'shipping_optional_signature': False,

            # Additional data for other shipping information
            'shipping_dry_ice_weight_in_oz': False,
            'shipping_cod_amount': False,
            'shipping_customer_account': False,
            'shipping_customer_zipcode': False,
            'shipping_cod_payment_type': False,

            # Remove Flags
            'is_change_info': False,
            'is_mul_packages': False,
            'is_create_label': False,
            "is_save_custom_package": False,
        }

    def reset_label_fields(self):
        self.sudo().write(self._reset_label_fields())
        if self.picking_package_ids:
            self.sudo().picking_package_ids.unlink()

    def check_open_update_done_quantities_form(self, callback):
        self.ensure_one()
        no_quantities_done = all(float_is_zero(move_line.qty_done, precision_digits=move_line.product_uom_id.rounding)
                                 for move_line in
                                 self.move_line_ids.filtered(lambda m: m.state not in ('done', 'cancel')))

        no_reserved_quantities = all(
            float_is_zero(move_line.product_qty, precision_rounding=move_line.product_uom_id.rounding) for move_line in
            self.move_line_ids)

        if no_quantities_done and no_reserved_quantities:
            return False

        context = dict(self.env.context)
        context.update(dict(
            update_done_callback=callback
        ))
        if no_quantities_done and self.state not in ('done', 'cancel'):
            view = self.env.ref('novobi_shipping_account.view_update_done_quantities')
            wiz = self.env['update.done.quantities'].create({'pick_id': self.id})
            return {
                'name': _('Auto update done quantities?'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'update.done.quantities',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                'context': context,
            }
        return False

    ### PB-64 ###
    # delete the validate function as it is not needed
    # by a Hung

    def _set_default_vals_label_form(self):
        vals = {
            'shipping_date': fields.Datetime.to_string(max(self.scheduled_date, fields.Datetime.now())),
            'shipping_cod_payment_type': 'any',
            'handling_fee': self.shipping_account_id.handling_fee
        }
        # Set default for shipping account by carrier_id set on sale order if have
        if self.channel_id.platform == "amazon":
            vals.update({
                "delivery_type": "amazon"
            })
        elif self.carrier_id and self.carrier_id.shipping_account_id:
            vals.update({
                'shipping_account_id': self.carrier_id.shipping_account_id.id,
                'delivery_carrier_id': self.carrier_id.id
            })

        suitable_package_ids, pkg_length, pkg_width, pkg_height = self.env[
            "shipstation.shipping.rule"].find_suitable_packages(self)
        vals.update({
            "default_shipstation_stock_package_type_id": suitable_package_ids[:1].id if suitable_package_ids else False,
            "package_size_length": pkg_length,
            "package_size_width": pkg_width,
            "package_size_height": pkg_height
        })
        total_move_weight = 0
        for ml in self.move_lines:
            # 1 ounc = 0.0625 pound
            if hasattr(ml.product_id, 'weight_in_oz') and ml.product_id.weight_in_oz != 0:
                product_weight_in_lbs = ml.product_id.weight_in_oz * 0.0625
            else:
                weight_uom_lbs_id = self.env.ref('uom.product_uom_lb')
                weight_uom_system_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()

                product_weight_in_lbs = weight_uom_system_id._compute_quantity(ml.product_id.weight,
                                                                               weight_uom_lbs_id, round=False)
            total_product_weight = product_weight_in_lbs * ml.quantity_done if ml.quantity_done else product_weight_in_lbs * ml.product_uom_qty
            total_move_weight += total_product_weight

        vals.update({
            'package_shipping_weight': round(total_move_weight, 3),
        })
        return vals

    def open_create_label_form(self):
        self.ensure_one()
        self = self.sudo()

        if 'validate_do' in self.env.context:
            open_update_done_quantities_form = self.check_open_update_done_quantities_form(
                'confirm_create_shipping_label')
            if open_update_done_quantities_form:
                return open_update_done_quantities_form

        ### PB-XX ###
        ### allow creating label even if no qty is reserved nor done by simply disabling the check
        # self.ensure_ready_to_create_label()
        vals = self._set_default_vals_label_form()
        self.update(vals)

        view = self.env.ref('novobi_shipping_account.view_picking_create_label_form')

        return {
            'name': _('Create Label'),
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

    def ensure_ready_to_create_label(self):
        self.ensure_one()
        no_quantities_done = all(
            float_is_zero(move_line.qty_done, precision_digits=move_line.product_uom_id.rounding)
            for move_line in self.move_line_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        )
        no_reserved_quantities = all(
            float_is_zero(move_line.product_qty, precision_rounding=move_line.product_uom_id.rounding)
            for move_line in self.move_line_ids
        )
        no_reserved_quantities_on_state = no_reserved_quantities and self.state != 'done'

        if no_quantities_done and no_reserved_quantities_on_state:
            raise UserError(_(
                'You cannot create label if no quantities are reserved nor done. '
                'To force the transfer, switch in edit mode and encode the done quantities.'
            ))

    def _prepare_shipping_info_data(self, data):
        estimated_date = data.get('estimated_date')
        try:
            if isinstance(estimated_date, str) and estimated_date != 'N/A':
                estimated_datetime = parser.parse(estimated_date)
                estimated_date = f'{estimated_datetime:%m/%d/%Y}'
        except ValueError:
            _logger.exception('Error while parsing estimated delivery date: %s', estimated_date)
            estimated_date = 'N/A'

        # Shipping cost = -1 means that Carrier does not return any data about shipping cost
        # Shipping cost = N/A will display in UI
        shipping_cost = 0 if not data['price'] else data['price']
        shipping_cost_without_discounts = data.get('price_without_discounts', 0.0)
        no_shipping_cost = True if not data['price'] else False

        vals = {
            'carrier_id': self.delivery_carrier_id.id,
            'is_create_label': True,
            'shipping_cost': shipping_cost,
            'shipping_cost_without_discounts': shipping_cost_without_discounts,
            'shipping_estimated_date': estimated_date or 'N/A',
            'carrier_tracking_ref': data['carrier_tracking_ref'],
            'no_shipping_cost': no_shipping_cost
        }

        if 'package_carrier_tracking_ref' in data:
            pp_ls = zip(self.picking_package_ids.ids, data['package_carrier_tracking_ref'])
            vals.update({
                'picking_package_ids': [(1, ppl[0], {'carrier_tracking_ref': ppl[1]}) for ppl in pp_ls]
            })

        if 'insurance_cost' in data:
            # Insurance cost = -1 means that Carrier does not return any data about insurance
            # Insurance cost = N/A will display in UI
            insurance_cost = 0 if not data['insurance_cost'] else data['insurance_cost']
            no_insurance_cost = True if not data['insurance_cost'] else False
            vals.update({'insurance_cost': insurance_cost, 'no_insurance_cost': no_insurance_cost})

        return vals

    def action_create_label(self):
        self.ensure_one()
        self = self.sudo()
        self._check_package_shipping_weight()
        self._check_shipping_date()

        self.check_and_create_custom_package_type()

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
            'insurance_amount': self.shipping_insurance_amount
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

    def button_void_label(self):
        self.ensure_one()
        self = self.sudo()
        if not self.is_create_label:
            return True

        # Set for_synching to True in order to avoid updating this picking to channel
        # Just need to update this once in reset label fields call
        res = self.delivery_carrier_id.void_label(picking=self)
        if 'error_message' in res and res.get('error_message'):
            raise UserError(_(res['error_message']))

        self.reset_label_fields()
        return True

    def get_carrier_rate(self):
        self.ensure_one()
        self = self.sudo()
        self._check_package_shipping_weight()
        res = self.delivery_carrier_id.get_rate_and_delivery_time(picking=self,
                                                                  stock_package_type=self.default_stock_package_type_id,
                                                                  package_length=self.package_size_length,
                                                                  package_width=self.package_size_width,
                                                                  package_height=self.package_size_height,
                                                                  weight=self.package_shipping_weight,
                                                                  pickup_date=self.shipping_date,
                                                                  shipping_options="",
                                                                  insurance_amount=self.shipping_insurance_amount)
        return res

    def action_cancel(self):
        for record in self.filtered(lambda r: r.is_create_label):
            record.button_void_label()
        return super(Picking, self).action_cancel()

    def get_carrier_label_document(self):
        self.ensure_one()
        attachment_model = self.env['ir.attachment']
        if self.platform != "amazon" and self.carrier_tracking_ref:
            label_attachment = attachment_model.search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id), '|', '|',
                ('name', 'like', '%%%s%%' % self.carrier_tracking_ref),
                ('name', 'like', '%%%s%%' % str(self.shipment_id_on_shipstation)),
                ('name', 'like', '%%%s%%' % str(self.shipment_id_on_amazon))
            ], order='create_date DESC', limit=1)
            return label_attachment, True
        elif self.platform == "amazon" and self.is_create_label:
            label_attachment = attachment_model.search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('name', 'like', '%%%s%%' % str(self.shipment_id_on_amazon))
            ], order='create_date DESC', limit=1)
            if self.partner_id.country_id.code == "US":
                f = open("temp_png.png", "wb")
                f.write(base64.b64decode(label_attachment.datas))
                f.close()
                f = open("temp_png.png", "rb")
                res = img2pdf.convert("temp_png.png")
                f.close()
                return res, False
            return label_attachment, True
        return attachment_model, False

    def do_print_picking(self):
        res = super(Picking, self).do_print_picking()
        if self.picking_type_code == 'outgoing':
            action = self.do_print_picking_for_outgoing()
            if 'report_action' not in res:
                return action
            res['report_action'] = action
        return res

    def do_print_picking_for_outgoing(self):
        self.ensure_one()
        if self.company_id.shipping_label_options == 'wo_packing':
            return self.do_print_picking_shipping_label()
        return self.do_print_picking_shipping_label_and_packing_slip()

    def do_print_picking_shipping_label(self):
        self.ensure_one()
        label_attachment = self.get_carrier_label_document()
        if not label_attachment:
            raise UserError(_('Unable to print label.'))
        return {
            'target': 'new',
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{label_attachment.id}?download=1'
        }

    def do_print_picking_shipping_label_and_packing_slip(self):
        self.ensure_one()
        return {
            'target': 'new',
            'type': 'ir.actions.act_url',
            'url': f'/report/shipping/labels/shipping_label_and_packing_slip?picking_id={self.id}'
        }

    def write(self, vals):
        if 'create_label' in self.env.context:
            return super(Picking, self).write(vals)
        if 'move_lines' in vals and self.is_create_label:
            # Raise Warning when users add or remove move line in Delivery Order
            vals['is_change_info'] = True
            vals['is_change_info_message_removed'] = False

        return super(Picking, self).write(vals)

    @api.model
    def check_carrier_shipment_status(self):
        empty = self.browse()
        non_delivered = self.search([
            ('state', '=', 'done'),
            ('is_create_label', '=', True),
            ('is_carrier_delivered', '=', False)
        ], order='carrier_id')

        delivered_tracking = set()
        for carrier, carrier_group in groupby(non_delivered, key=itemgetter('carrier_id')):
            result = carrier.check_shipment_status(reduce(or_, carrier_group, empty))

            if result and result.get('success') and result.get('result'):
                for tracking, data in result['result'].items():
                    if data and data.get('success') and data.get('delivered'):
                        delivered_tracking.add(tracking)

        delivered = non_delivered.filtered(lambda r: r.carrier_tracking_ref in delivered_tracking)
        delivered.write({'is_carrier_delivered': True})
        return delivered

    def get_origin(self):
        self.ensure_one()
        return self.origin or self.name
