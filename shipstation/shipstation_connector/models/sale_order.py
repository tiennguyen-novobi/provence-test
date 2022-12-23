# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError
from odoo.addons.multichannel_order.models.sale_order import ShipmentImportError
from odoo.addons.queue_job.exception import RetryableJobError

from ..utils.shipstation_order_helper import ShipStationOrderImporter, ShipStationOrderImportBuilder, ShipStationOrderHelper
from ..utils.shipstation_shipment_helper import ShipStationShipmentImporter, ShipStationShipmentImportBuilder
from ..utils.shipstation_export_helper import ExporterHelper, ExportError, OrderProcessorHelper, RateLimit

_logger = logging.getLogger(__name__)


SHIPSTATION_ORDER_STATUS = {
    'awaiting_payment': 'shipstation_connector.shipstation_order_status_awaiting_payment',
    'awaiting_shipment': 'shipstation_connector.shipstation_order_status_awaiting_payment',
    'shipped': 'shipstation_connector.shipstation_order_status_shipped',
    'on_hold': 'shipstation_connector.shipstation_order_status_on_hold',
    'cancelled': 'shipstation_connector.shipstation_order_status_cancelled',
}


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    id_on_shipstation = fields.Integer(string='ID on ShipStation', readonly=True, copy=False)
    order_line_key_shipstation = fields.Char(string='Order Line Key on ShipStation', copy=False)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    shipstation_store_id = fields.Many2one('ecommerce.channel',
                                           string='ShipStation Store', copy=False,
                                           ondelete='restrict',
                                           help='The ShipStation Store is used for placing shipment', readonly=True)

    shipstation_account_id = fields.Many2one(related='shipstation_store_id.shipstation_account_id', copy=False)

    shipstation_order_status_id = fields.Many2one(
        'order.status.channel', string='Status on Store', copy=False, readonly=True,
        help='The status of order on ShipStation', domain=[('platform', '=', 'shipstation')])

    id_on_shipstation = fields.Integer(string='ID on ShipStation', readonly=True, copy=False)
    order_key_shipstation = fields.Char(string='Order Key on ShipStation', copy=False)
    shipstation_parent_id = fields.Integer(string='Parent Order ID on ShipStation', readonly=True, copy=False)
    is_invoiced = fields.Boolean(string='Is Invoiced', compute='_compute_is_invoiced', copy=False)

    def _compute_is_invoiced(self):
        for record in self:
            record.is_invoiced = False
            if record.id_on_shipstation:
                order_lines = record.order_line.filtered(lambda x: not x.is_discount and not x.is_coupon
                                                         and not x.is_tax
                                                         and not x.is_other_fees and not x.is_handling
                                                         and not x.is_wrapping and not x.is_delivery
                                                         and not x.is_downpayment and not x.display_type)
                if any(line.qty_invoiced > line.product_uom_qty for line in order_lines):
                    record.is_invoiced = True

    @api.depends('is_invoiced')
    def _get_invoice_status(self):
        super()._get_invoice_status()
        for order in self:
            if order.shipstation_parent_id and order.is_invoiced:
                order.invoice_status = 'no'
            else:
                super()._get_invoice_status()

    @api.model
    def shipstation_get_data(self, channel_id, ids=[], from_date=None, to_date=None, update=None, all_records=False):
        return self.shipstation_import_orders(channel_id, ids, from_date, to_date, update, all_records)

    @api.model
    def shipstation_do_import_orders(self, channel, ids, from_date=None, to_date=None, update=None, all_records=False):
        def prepare_importer(channel):
            res = ShipStationOrderImporter()
            res.channel = channel
            res.ids = ids
            res.from_date = from_date
            res.to_date = to_date
            res.all_records = all_records
            return res

        def prepare_builder(order_data):
            res = ShipStationOrderImportBuilder()
            res.orders = order_data
            return res

        def fetch_order(gen):
            while True:
                try:
                    order = next(gen)
                    order['channel_date_created'] = channel.shipstation_account_id.convert_tz(order['channel_date_created'], to_utc=True)
                    yield order
                except StopIteration:
                    break

        importer = prepare_importer(channel)
        list_orders = []
        for pulled in importer.do_import():
            try:
                if pulled.data:
                    builder = prepare_builder(pulled.data)
                    vals_list = list(fetch_order(builder.prepare()))
                    list_orders.extend(vals_list)
                else:
                    if pulled.last_response and not pulled.last_response.ok():
                        _logger.error('Error while importing orders: %s',
                                      pulled.last_response.get_error())
                        channel.sudo().disconnect()
            except EmptyDataError:
                continue
        return list_orders

    def shipstation_create_or_update_parent_order(self, parent_id, channel):
        vals_list = self.shipstation_do_import_orders(channel, [str(parent_id)])
        if vals_list:
            order_vals = vals_list[0]
            if order_vals['shipstation_parent_id']:
                self.shipstation_create_or_update_parent_order(order_vals['shipstation_parent_id'], channel)
            order_data = self._prepare_imported_order(
                order_data=vals_list[0],
                channel_id=channel.id,
                auto_create_master=channel.auto_create_master_product,
                search_on_mapping=False
            )
            record = self.sudo().search([('channel_id.id', '=', channel.id),
                                         ('id_on_channel', '=', str(order_vals['id']))], limit=1)
            if record:
                self._update_in_queue_job(order_data, channel.id)
            else:
                self.with_context(for_synching=True).create(order_data)

    @api.model
    def shipstation_import_orders(self, channel_id, ids=[], from_date=None, to_date=None, update=None,
                                  all_records=False):
        uuids = []
        datas = []
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        vals_list = self.shipstation_do_import_orders(channel, ids, from_date, to_date, update, all_records)
        for order_vals in vals_list:
            record = self.sudo().search([('channel_id.id', '=', channel_id),
                                         ('id_on_channel', '=', str(order_vals['id']))], limit=1)
            # If a record is already existed
            existed_record = True if record else False
            if order_vals['shipstation_parent_id']:
                self.shipstation_create_or_update_parent_order(order_vals['shipstation_parent_id'], channel)

            uuids.extend(self.create_jobs_for_synching(vals_list=[order_vals],
                                                       channel_id=channel_id,
                                                       update=existed_record))

            self._cr.commit()
        return datas, uuids

    def shipstation_get_order_shipments(self, shipment_id=None):
        """
        Get shipments on Order.
        The result from this function will be called after order and order lines already created.

        An order on ShipStation can have multiple shipment. And each shipment can have different shipping addresses
        :return: Create delivery orders for sale order
        """
        self.ensure_one()
        datas = []
        error_message = None
        StockPicking = self.env['stock.picking']
        try:
            for shipment_data in self.shipstation_import_shipments(shipment_id):
                datas.append(shipment_data)
            if datas and self.state == 'draft':
                self.action_confirm()
            StockPicking.process_shipment_data_from_channel(self, datas, self.shipstation_store_id)
        except Exception as e:
            _logger.exception("Error when importing shipments from ShipStation")
            error_message = str(e)
        return datas, error_message

    def _prepare_shipment_import_log_vals(self, res_model, shipment):
        if 'id_on_shipstation' in shipment:
            shipment['id_on_channel'] = shipment['id_on_shipstation']
        return super()._prepare_shipment_import_log_vals(res_model, shipment)

    def shipstation_import_shipments(self, shipment_id=None):
        self.ensure_one()

        def prepare_importer():
            res = ShipStationShipmentImporter()
            res.channel = self.shipstation_store_id
            res.order_id = self.id_on_shipstation
            res.shipment_id = shipment_id
            return res

        def prepare_builder(shipment_data):
            res = ShipStationShipmentImportBuilder()
            if isinstance(shipment_data, dict):
                shipment_data = [shipment_data]
            res.shipments = shipment_data
            return res

        def fetch_shipment(gen):
            yield from gen

        importer = prepare_importer()
        for pulled in importer.do_import():
            if pulled.ok():
                if pulled.data:
                    builder = prepare_builder(pulled.data)
                    yield from fetch_shipment(builder.prepare())
            else:
                raise ShipmentImportError(pulled.get_error_message())

    def export_to_shipstation(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('shipstation_connector.export_to_shipstation_action')
        shipstation_accounts = self.env['shipstation.account'].search([])
        action.update({
            'context': {
                'default_order_id': self.id,
                'default_shipstation_account_id': self.shipstation_account_id.id or shipstation_accounts[-1].id,
                'default_store_id': self.shipstation_store_id.id,
                'default_is_exported_to_shipstation': True if self.id_on_shipstation else False
            }
        })
        return action

    def multi_export_to_shipsation(self):
        order_ids = self.env.context['active_ids']
        action = self.env["ir.actions.actions"]._for_xml_id('shipstation_connector.export_to_shipstation_action')
        orders = self.browse(order_ids)
        action.update({
            'context': {
                'default_order_ids': [(6, 0, order_ids)],
                'default_is_exported_to_shipstation': True if all(e for e in orders.mapped('id_on_shipstation')) else False
            },
        })
        return action

    def _check_order_status_on_shipstation(self):
        self.ensure_one()
        export_helper = ExporterHelper(self.shipstation_store_id)
        try:
            order_status = export_helper.get_order_status(self)
            return order_status
        except ExportError as e:
            raise ValidationError(_('Something went wrong when getting status of order'))

    def _prepare_shipstation_order_data(self, shipstation_store, data):
        vals_items = []
        for order_line in self.order_line.filtered(lambda line: line.product_id.type in ['product', 'consu']):
            line = list(filter(lambda l: l['sku'] == order_line.product_id.default_code, data['lines']))
            vals_items.append((1, order_line.id, {'id_on_shipstation': int(line[-1]['id_on_channel'])}))

        return {
            'id_on_shipstation': int(data['id']),
            'shipstation_store_id': shipstation_store.id,
            'order_line': vals_items,
            'shipstation_order_status_id': self.env.ref(SHIPSTATION_ORDER_STATUS[data['status_id']]).id
        }

    def _shipstation_validate_export_data(self):
        self.ensure_one()
        for field in ['street', 'city', 'state_id', 'country_id', 'zip']:
            if not self.partner_invoice_id[field]:
                raise ValidationError(_('Street, City, State, Zip code, Country are required fields. Please check the invoice address and try again.'))
            if not self.partner_shipping_id[field]:
                raise ValidationError(_('Street, City, State, Zip code, Country are required fields. Please check the delivery address and try again.'))

    def export_single_order_to_shipstation(self, shipstation_store):
        try:
            if self.id_on_shipstation:
                order_status = self._check_order_status_on_shipstation()
                if order_status in ['on_hold', 'cancelled']:
                    raise ValidationError(_("This order has been on hold or cancelled on ShipStation"))
                if order_status == 'shipped':
                    raise ValidationError(_("This order has been shipped. Your changes cannot be updated to ShipStation."))
                if order_status is None:
                    order_line = [(1, line.id, {'id_on_shipstation': False}) for line in self.order_line.filtered(lambda l: l.id_on_shipstation)]
                    self.update({'id_on_shipstation': False,
                                 'order_line': order_line})
                # If order was exported before, we don't allow user to change to another store
                shipstation_store = self.shipstation_store_id

            export_helper = ExporterHelper(shipstation_store)
            self._shipstation_validate_export_data()
            res = export_helper.export(self)

            vals = self._prepare_shipstation_order_data(shipstation_store, res)

            self.write(vals)

        except RateLimit as e:
            if 'job_uuid' in self.env.context:
                raise RetryableJobError("Retry exporting orders")
            else:
                raise ValidationError(e)
        except ExportError as e:
            raise ValidationError(_('Cannot export order to ShipStation: %s' % str(e)))

    @api.model
    def shipstation_export_orders(self, shipstation_store, ids):
        order_processor_helper = OrderProcessorHelper()
        orders = self.browse(ids)
        for order in orders:
            # If order was exported before, we don't allow user to change to another store
            data = order_processor_helper(order, order.shipstation_store_id or shipstation_store)

            log = self.env['omni.log'].create({'datas': data,
                                               'channel_id': shipstation_store.id,
                                               'operation_type': 'export_order',
                                               'res_model': 'sale.order',
                                               'res_id': order.id,
                                               'order_id': order.id})

            job_uuid = order.with_context(log_id=log.id).with_delay().export_single_order_to_shipstation(shipstation_store).uuid
            log.update({'job_uuid': job_uuid})

    @api.model
    def _check_imported_order_data(self, channel, order_data):
        """
        Override this function for importing orders from ShipStation.
        If the order was imported by Odoo, we don't allow to update order information from ShipStation.
        We are expecting that the changes should be done on the source of order

        In this case, we only check if shipments are created on ShipStation
        """
        res = super()._check_imported_order_data(channel, order_data)
        if channel.platform == 'shipstation' and order_data.get('source', '') == 'Odoo':
            domain = [('id_on_shipstation', '=', order_data['id']), ('shipstation_store_id', '=', channel.id)]
            order = self.search(domain, limit=1)
            order.shipstation_get_order_shipments()
            return False
        return res

    @api.model
    def _prepare_imported_order(
            self, order_data, channel_id,
            no_waiting_product=None, auto_create_master=True, search_on_mapping=True):
        vals = super()._prepare_imported_order(order_data, channel_id, no_waiting_product, auto_create_master, search_on_mapping)
        if 'platform' in order_data and order_data['platform'] == 'shipstation':
            vals.update({
                'id_on_shipstation': order_data['id'],
                'shipstation_store_id': channel_id,
                'order_key_shipstation': str(order_data['order_key']),
                'shipstation_parent_id': order_data['shipstation_parent_id'],
            })
        return vals

    @api.model
    def _prepare_order_line(self, channel, line_data):
        vals = super()._prepare_order_line(channel, line_data)
        if channel.platform == 'shipstation':
            vals.update({
                'id_on_shipstation': int(line_data['id_on_channel']),
                'order_line_key_shipstation': str(line_data['order_line_key'])
            })
        return vals

    def cancel_on_shipstation(self):
        self.ensure_one()
        order_status = self._check_order_status_on_shipstation()

        if order_status == 'shipped':
            raise ValidationError(_("You cannot cancel the shipped orders on ShipStation."))

        try:
            helper = ExporterHelper(self.shipstation_store_id)
            res = helper.export(self, order_status='cancelled')
        except ExportError as e:
            raise ValidationError(e)

        self.update({
            'id_on_shipstation': False,
            'shipstation_store_id': False
        })

    def shipstation_cancel_on_channel(self):
        self.ensure_one()
        try:
            self.cancel_on_shipstation()
            return True
        except ValidationError as e:
            title = 'Cannot cancel order on ShipStation'
            exceptions = [{'title': 'Cannot cancel order on ShipStation', 'reason': str(e)}]
            _logger.exception("Something went wrong while cancelling order on ShipStation: %s", str(e))
            self._log_exceptions_on_order(title, exceptions)
            return False

    def action_confirm(self):
        """
        Override to export to ShipStation automatically
        """
        res = super().action_confirm()
        shipstation_accounts = self.env['shipstation.account'].search([('auto_export_order', '=', True)])
        for shipstation_account in shipstation_accounts:
            rule, shipstation_store = shipstation_account.check_auto_export_rule(self)
            if shipstation_store:
                self.shipstation_export_orders(shipstation_store, self.ids)
        return res
