import logging

from odoo.addons.omni_manage_channel.utils.common import AddressUtils

from odoo import api, models, fields

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Change request: allow editing of validity_date in every state
    validity_date = fields.Date(readonly=False)

    @api.model
    def _get_customer_addresses_from_order_data(self, order_data) -> tuple:
        ########## PB-39 ##########
        # Get contact customer as well
        address_types = (
            'customer' if order_data.get('fulfillment_channel') == 'AFN' else "customer_data", 'billing_address',
            'shipping_address')
        contact_types = ('contact', 'invoice', 'delivery')
        addresses = ()
        for address_type, contact_type in zip(address_types, contact_types):
            address = order_data.get(address_type)
            if address:
                address = {k: v or False for k, v in address.items()}
                country = AddressUtils.get_country_record(self.env,
                                                          address.get('country_code', address.get('country_id', '')))
                state = AddressUtils.get_state_record_by_code_or_name(
                    self.env,
                    country=country,
                    state_code=address.get('state_code', ''),
                    state_name=address.get('state_name', ''),
                )
                addresses += ({
                                  'name': address.get('name'),
                                  'company': address.get('company', ''),
                                  'phone': address.get('phone'),
                                  'email': address.get('email') or order_data.get('customer').get(
                                      'BuyerEmail') if order_data.get('fulfillment_channel') in ['MFN', 'AFN'] else '',
                                  'street': address.get('street'),
                                  'street2': address.get('street2'),
                                  'city': address.get('city'),
                                  'zip': address.get('zip'),
                                  'country_id': country.id,
                                  'state_id': state.id,
                                  'type': contact_type
                              },)
            else:
                addresses += (None,)
        return addresses

    @api.model
    def _prepare_imported_order(
            self, order_data, channel_id,
            no_waiting_product=None, auto_create_master=True, search_on_mapping=True):

        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)

        order_configuration = channel.get_setting('order_configuration')

        fulfillment_status = self._get_order_status_channel(status=order_data.get('status_id'), channel=channel,
                                                            type='fulfillment')
        payment_status = self._get_order_status_channel(status=order_data.get('payment_status_id'), channel=channel,
                                                        type='payment')

        ########## PB-39 ##########
        # Extract contact info as well

        customer_channel, partner, contact_info, invoice_info, shipping_info = self.get_customer_info(
            channel_id, order_data)

        order_number = f"{order_configuration['order_prefix']}{order_data['channel_order_ref']}" if order_configuration[
            'order_prefix'] else order_data['channel_order_ref']

        customer_channel, partner, partner_invoice, partner_shipping = \
            customer_channel.with_context(is_fba=order_data.get('fulfillment_channel') == "AFN", channel=channel,
                                          order_ref=order_data["id"]).determine_customer(channel, contact_info,
                                                                                         invoice_info, shipping_info,
                                                                                         order_number)
        name = order_number
        # For Amazon orders: name: from sequence; customer ref: ID on channel
        if order_data.get("fulfillment_channel") == "AFN":
            name = self.env['ir.sequence'].next_by_code('fba.order')
        elif order_data.get("fulfillment_channel") == "MFN":
            name = self.env['ir.sequence'].next_by_code('fbm.order')

        order_data.update({
            'name': name,
            'client_order_ref': order_data.get('channel_order_ref'),
            'partner_id': partner.id,
            'partner_invoice_id': partner_invoice.id,
            'partner_shipping_id': partner_shipping.id,
            'updated_shipping_address_id': partner_shipping.id,
            'customer_channel_id': customer_channel.id if customer_channel else False,
            'picking_policy': order_configuration['shipping_policy'],
            'team_id': order_configuration['sales_team_id'],
            'order_status_channel_id': fulfillment_status.id,
            'payment_status_channel_id': payment_status.id,
            'warehouse_id': self._set_store_warehouse(order_data, order_configuration),
            'company_id': order_configuration['company_id'],
            'pricelist_id': self._get_pricelist(order_data, partner, order_configuration['company_id'])
        })

        waiting_job, products = self._find_order_items(
            order_data, channel, no_waiting_product, auto_create_master, search_on_mapping)

        if waiting_job:
            # Waiting for importing product firstly
            return None
        return self._process_order_data(order_data, order_configuration, channel, products, search_on_mapping)
