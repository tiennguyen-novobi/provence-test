# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
import logging
from ..utils.amazon_report_helper import AmazonReportHelper
from ..utils.amazon_product_helper import AmazonProductImportBuilder


_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def amazon_get_data(self, channel_id, sync_inventory=False, log_id=False, **options):
        """
        *****Note: Synching will be run in Queue Job. Therefore, we need to concern about "concurrence update" issues
        :return:
        1. Data products
        2. UUIDs of jobs for synching
        """

        return self.amazon_import_products(channel_id, sync_inventory=sync_inventory, log_id=log_id, **options)

    @api.model
    def amazon_import_products(self, channel_id, sync_inventory=False, log_id=False, auto_create_master=True, **options):
        channel = self.env['ecommerce.channel'].browse(channel_id)
        helper = AmazonReportHelper(channel)
        res = helper.create_report(report_type='GET_MERCHANT_LISTINGS_DATA',
                                   marketplace_ids=[channel.amazon_marketplace_id.api_ref])
        if res.ok():
            data = res.data
            self.env['amazon.report'].create({
                'id_on_channel': data['id'],
                'status': data['status'],
                'channel_id': channel_id,
                'report_type': 'GET_MERCHANT_LISTINGS_DATA',
                'auto_create_master': auto_create_master
            })
        return None, []

    @api.model
    def _amazon_import_products(self, channel_id, products, auto_create_master=True):
        def prepare_builder(product):
            res = AmazonProductImportBuilder()
            res.products = product
            return res

        def fetch_product(cor):
            while True:
                try:
                    pro = next(cor)
                    yield pro
                except StopIteration:
                    break

        builder = prepare_builder(products)
        uuids = []
        for product in fetch_product(builder.prepare()):
            uuids.extend(self.create_jobs_for_synching([product], channel_id, auto_create_master=auto_create_master))
        return uuids
