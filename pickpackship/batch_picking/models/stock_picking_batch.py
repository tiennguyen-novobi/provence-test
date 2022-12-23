# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    process_type = fields.Selection([('pick_then_sort', 'Pick then Sort'),
                                     ('pick_and_sort', 'Pick and Sort'),
                                     ('pick_for_single_item_order', 'Pick for single item order')],
                                    string='Process Type')
    processing_in_barcode = fields.Boolean(string='Processing in Barcode')
