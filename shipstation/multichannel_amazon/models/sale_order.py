# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import itertools

from datetime import timedelta

from odoo import api, Command, fields, models, _
from odoo.addons.queue_job.exception import RetryableJobError

from ..utils.amazon_order_helper import AmazonOrderHelper, AmazonOrderImporter, AmazonOrderImportBuilder,\
    SingularOrderDataInTrans as TransformOrder, RateLimit

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    asin = fields.Char(string='ASIN')


class SaleOrder(models.Model):
    _inherit = "sale.order"

    amazon_fulfillment_method = fields.Selection([
        ('MFN', "FBM"),
        ('AFN', "FBA")
    ], string="Amazon Fulfillment Method", translate=False, readonly=True)

    @api.model
    def _prepare_order_line(self, channel, line_data):
        res = super()._prepare_order_line(channel, line_data)
        if channel.platform == 'amazon':
            res['asin'] = line_data['asin']
        return res

    @api.model
    def _extend_ecommerce_order_vals(self, channel, order_data):
        res = super()._extend_ecommerce_order_vals(channel, order_data)
        if channel.platform == 'amazon':
            res.update({
                'amazon_fulfillment_method': order_data['fulfillment_channel'],
                'commitment_date': order_data['commitment_date'],
                'is_replacement': order_data['is_replacement'],
                'replaced_id_on_channel': order_data['replaced_order_id']
            })
            if order_data['is_prime']:
                tag_ids = channel.default_order_tag_ids | channel.amazon_order_tag_id
                res.update({
                    'tag_ids': [Command.set(tag_ids.ids)]
                })
        return res

    @api.model
    def amazon_get_data(self, channel_id, ids=None, from_date=None, to_date=None, update=None, all_records=False):
        return self.amazon_import_orders(channel_id, ids or [], from_date, to_date, update, all_records)

    @api.model
    def amazon_import_orders(self, channel_id, ids=None, from_date=None, to_date=None, update=None, all_records=False):
        def prepare_importer(chn, is_manual):
            # limit = 100
            res = AmazonOrderImporter()
            res.channel = chn
            res.ids = ids or []
            # res.limit = limit
            from_date_adj = from_date - timedelta(minutes=10) if from_date else None
            to_date_adj = to_date - timedelta(minutes=10) if to_date else None
            if is_manual:
                res.created_from_date = from_date_adj
                res.created_to_date = to_date_adj
            else:
                res.modified_from_date = from_date_adj
                res.modified_to_date = to_date_adj
            res.all_records = all_records

            return res

        def prepare_builder(order_data):
            res = AmazonOrderImportBuilder()
            res.orders = order_data
            return res

        def fetch_order(gen):
            while True:
                try:
                    order = next(gen)
                    yield order
                except StopIteration:
                    break

        datas, uuids = [], []
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        importer = prepare_importer(channel, self.env.context.get('manual_import'))

        for pulled in importer.do_import():
            if pulled.ok():
                orders = list(itertools.chain(*(single.data['payload'].get('Orders', []) for single in pulled)))
                datas.extend(orders)
                builder = prepare_builder(orders)
                for order_vals in fetch_order(builder.prepare()):
                    uuids.append(self.with_delay()._amazon_import_order_details(channel_id, order_vals).uuid)
                    self._cr.commit()
        return datas, uuids

    @api.model
    def _amazon_import_order_details(self, channel_id, order_vals):
        channel = self.env['ecommerce.channel'].sudo().browse(channel_id)
        helper = AmazonOrderHelper(channel)
        res = helper.get_details(order_vals['id'])
        order_vals.update(res)
        transform_order = TransformOrder()
        order_vals = transform_order(order_vals)
        record = self.sudo().search([('channel_id.id', '=', channel_id),
                                     ('id_on_channel', '=', str(order_vals['id']))], limit=1)

        existed_record = bool(record)  # If sale order has already existed

        try:
            self.create_jobs_for_synching(vals_list=[order_vals],
                                          channel_id=channel_id,
                                          update=existed_record)
        except RateLimit:
            raise RetryableJobError(_('Rate Limit'))
        except Exception as e:
            _logger.exception(str(e))

    @api.model
    def _import_missing_products(self, channel, not_exists_products):
        if channel.platform == 'amazon':
            products = [{
                'product-id-type': '1',
                'product-id': line['product']['asin'],
                'seller-sku': line['product']['sku'],
                'item-name': line['product']['name'],
                'price': line['product']['price'],
                'fulfillment-channel': line['product']['fulfillment_channel'],
                'item-condition': line['product']['condition']
            } for line in not_exists_products]

            uuids = self.env['product.template']._amazon_import_products(channel_id=channel.id,
                                                                         products=products)
        else:
            uuids = super()._import_missing_products(channel, not_exists_products)
        return uuids

    def amazon_cancel_on_channel(self):
        self.ensure_one()
        feed = self.env['amazon.feed'].create({'feed_type': 'POST_ORDER_ACKNOWLEDGEMENT_DATA',
                                               'channel_id': self.channel_id.id})
        feed.create_feed_document(content_type='text/xml', data=self.id_on_channel)
        return True

    @api.model
    def _set_store_warehouse(self, order_data, order_configuration):
        if 'fulfillment_channel' in order_data and order_data['fulfillment_channel'] == 'AFN':
            return order_configuration['fba_warehouse_id']
        return super()._set_store_warehouse(order_data, order_configuration)
