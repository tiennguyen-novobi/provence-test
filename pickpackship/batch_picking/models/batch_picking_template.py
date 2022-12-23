# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class BatchPickingTemplate(models.Model):
    _name = 'batch.picking.template'

    # General
    name = fields.Char(string='Template Name', required=True)
    process_type = fields.Selection([('pick_then_sort', 'Pick then Sort'),
                                     ('pick_and_sort', 'Pick and Sort'),
                                     ('pick_for_single_item_order', 'Pick for single item order')],
                                    string='Process Type', required=True)
    # Order Criteria
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse")
    order_date_from = fields.Date(string='Order Date (From)')
    order_date_to = fields.Date(string='Order Date (To)')
    delivery_date_from = fields.Date(string='Delivery Date (From)')
    delivery_date_to = fields.Date(string='Delivery Date (End)')
    sales_team_id = fields.Many2one('crm.team', string='Sales Team')
    delivery_carrier_ids = fields.Many2many('delivery.carrier', string='Shipping Method')
    # Order Item Criteria
    max_order_line_to_pick = fields.Float(string='Maximum number of order lines to pick')
    product_id = fields.Many2one('product.product', string='Product')
    max_ordered_qty = fields.Float(string='Maximum Ordered Quantity')
    # Volume
    max_number_of_orders_in_batch = fields.Integer(string='Maximum number of orders in batch')

    @api.onchange('process_type')
    def _onchange_process_type(self):
        if self.process_type == 'pick_for_single_item_order':
            max_order_line_to_pick = 1.0
        else:
            max_order_line_to_pick = 0.0
        self.update({
            'max_order_line_to_pick': max_order_line_to_pick,
            'product_id': False,
            'max_ordered_qty': 0
        })

    _sql_constraints = [
        ('max_number_of_orders_in_batch_positive', 'CHECK (max_number_of_orders_in_batch > 0)',
         'The maximum number of orders in batch must be greater than 0.')
    ]
