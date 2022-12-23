# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class CreateBatchPicking(models.TransientModel):
    _name = 'create.batch.picking'

    batch_picking_template_id = fields.Many2one('batch.picking.template', string='Use Template')
    is_save_batch_picking_template = fields.Boolean(string='Save as new template')
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

    _sql_constraints = [
        ('max_number_of_orders_in_batch_positive', 'CHECK (max_number_of_orders_in_batch > 0)',
         'The maximum number of orders in batch must be greater than 0.')
    ]

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

    @api.onchange('batch_picking_template_id')
    def _onchange_batch_picking_template_id(self):
        batch_picking_template = self.batch_picking_template_id
        if batch_picking_template:
            self.update({
                'name': batch_picking_template.name,
                'process_type': batch_picking_template.process_type,
                'warehouse_id': batch_picking_template.warehouse_id.id,
                'order_date_from': batch_picking_template.order_date_from,
                'order_date_to': batch_picking_template.order_date_to,
                'delivery_date_from': batch_picking_template.delivery_date_from,
                'delivery_date_to': batch_picking_template.delivery_date_to,
                'sales_team_id': batch_picking_template.sales_team_id.id,
                'delivery_carrier_ids': [(6, 0,  batch_picking_template.delivery_carrier_ids.ids)],
                'max_order_line_to_pick': batch_picking_template.max_order_line_to_pick,
                'product_id': batch_picking_template.product_id.id,
                'max_ordered_qty': batch_picking_template.max_ordered_qty,
                'max_number_of_orders_in_batch': batch_picking_template.max_number_of_orders_in_batch
            })

    def _prepare_batch_picking_template_vals(self):
        vals = {
            'name': self.name,
            'process_type': self.process_type,
            'warehouse_id': self.warehouse_id.id,
            'order_date_from': self.order_date_from,
            'order_date_to': self.order_date_to,
            'delivery_date_from': self.delivery_date_from,
            'delivery_date_to': self.delivery_date_to,
            'sales_team_id': self.sales_team_id.id,
            'delivery_carrier_ids': [(6, 0, self.delivery_carrier_ids.ids)],
            'max_order_line_to_pick': self.max_order_line_to_pick,
            'product_id': self.product_id.id,
            'max_ordered_qty': self.max_ordered_qty,
            'max_number_of_orders_in_batch': self.max_number_of_orders_in_batch
        }
        return vals

    def create_batch_picking(self):
        if self.is_save_batch_picking_template:
            # Create new Batch Picking Template
            vals = self._prepare_batch_picking_template_vals()
            self.env['batch.picking.template'].sudo().create(vals)
        # Use SQL to search data
        where_clause = """sp.state = 'assigned'
                AND sp.batch_id IS NULL
                AND spt.is_use_operation_type_for_pickings IS TRUE
        """
        # Filter data in popup
        param = {}
        if self.warehouse_id:
            where_clause += " AND so.warehouse_id = %(warehouse_id)s"
            param.update({'warehouse_id': self.warehouse_id.id})
        if self.sales_team_id:
            where_clause += " AND so.team_id = %(sales_team_id)s"
            param.update({'sales_team_id': self.sales_team_id.id})
        if self.delivery_carrier_ids:
            where_clause += " AND so.carrier_id IN %(delivery_carrier_ids)s"
            param.update({'delivery_carrier_ids': tuple(self.delivery_carrier_ids.ids)})
        if self.order_date_from and self.order_date_to:
            where_clause += " AND so.date_order BETWEEN %(order_date_from)s AND %(order_date_to)s"
            param.update({'order_date_from': self.order_date_from, 'order_date_to': self.order_date_to})
        if self.delivery_date_from and self.delivery_date_to:
            where_clause += " AND so.commitment_date BETWEEN %(delivery_date_from)s AND %(delivery_date_to)s"
            param.update({'delivery_date_from': self.delivery_date_from, 'delivery_date_to': self.delivery_date_to})
        if self.max_order_line_to_pick:
            having_clause = "COUNT(sp.id) <= %(max_order_line_to_pick)s"
            param.update({'max_order_line_to_pick': self.max_order_line_to_pick})
        else:
            having_clause = "COUNT(sp.id) >= 0"
        if self.max_ordered_qty:
            where_clause += " AND sm.product_uom_qty <= %(max_ordered_qty)s"
            param.update({'max_ordered_qty': self.max_ordered_qty})
        if self.product_id:
            where_clause += " AND sm.product_id = %(product_id)s"
            param.update({'product_id': self.product_id.id})
        sql = """
            SELECT sp.id AS pickingID, COUNT(sp.id)
            FROM stock_picking sp
            LEFT JOIN sale_order so ON sp.sale_id = so.id
            LEFT JOIN stock_picking_type spt ON sp.picking_type_id = spt.id
            LEFT JOIN stock_move sm ON sm.picking_id = sp.id
            WHERE (%s)
            GROUP BY sp.id
            HAVING (%s)
            ORDER BY scheduled_date ASC
        """ % (where_clause, having_clause)
        if self.max_number_of_orders_in_batch:
            sql += " LIMIT %(max_number_of_orders_in_batch)s"
            param.update({'max_number_of_orders_in_batch': self.max_number_of_orders_in_batch})
        self.env.cr.execute(sql, param)
        picking_ids = (x[0] for x in self.env.cr.fetchall())
        # Create batch transfer
        batch_id = self.env['stock.picking.batch'].create({
            'user_id': self.env.user.id,
            'company_id': self.env.company.id,
            'process_type': self.process_type,
            'picking_ids': [(6, 0, picking_ids)]
        })
        return {
            'context': self._context,
            'res_model': 'stock.picking.batch',
            'target': 'current',
            'res_id': batch_id.id,
            'type': 'ir.actions.act_window',
            'views': [[self.env.ref('stock_picking_batch.stock_picking_batch_form').id, 'form']],
        }
