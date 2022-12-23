import threading
import logging

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    wave_type = fields.Selection([
        ('single', 'Single-Item'),
        ('tote', 'Tote'),
        ('order', 'Order')], string='Batch Type', copy=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse',
                                   domain="[('lot_stock_id.usage', '=', 'internal')]", copy=True)
    product_id = fields.Many2one('product.product', 'Product',
                                 domain="[('type', '=', 'product')]", copy=True)
    is_manually_create = fields.Boolean(
        string='Is Manually Create?', default=False, copy=False,
        help="This is the technical field set to true when creating a new batch picking in Inventory app")

    @api.onchange('product_id', 'wave_type', 'warehouse_id')
    def onchange_product_id(self):
        self.ensure_one()

        picking_domain = [
            ('sale_id.warehouse_id', '=', self.warehouse_id.id),
            ('sequence_code', '=', 'PICK'),
            ('state', '=', 'assigned'),
            ('batch_id', '=', False),
        ]
        if self.wave_type == 'single' and self.product_id:
            picking_domain.extend([
                ('is_single_picking', '=', True),
                ('move_ids_without_package.product_id', '=', self.product_id.id),
            ])
        elif self.wave_type == 'single':
            picking_domain.extend([
                ('is_single_picking', '=', True),
            ])

        res = {'domain': {'picking_ids': picking_domain}}
        if self.picking_ids:
            res['warning'] = {
                'title': 'Warning',
                'message': 'Please remove existing transfers before adding new ones.'
            }
        self.update({'picking_type_id': False})
        return res

    def action_confirm(self):
        if self.wave_type:
            self.check_wave_picking()
        return super(StockPickingBatch, self).action_confirm()

    def force_validate(self, cancel_backorder=False, auto_create=False):
        try:
            not_done_pickings = self.picking_ids.filtered(lambda p: p.state != 'done')

            done_pickings = backorder_pickings = not_picked_pickings = self.env['stock.picking']

            for picking in not_done_pickings:
                moves = picking.mapped('move_lines')
                if all([float_is_zero(m.quantity_done, precision_digits=2) for m in moves]):
                    not_picked_pickings += picking
                elif all([float_compare(m.product_uom_qty, m.quantity_done, 2) == 0 for m in moves]):
                    done_pickings += picking
                else:
                    backorder_pickings += picking

            new_batch = self.env['stock.picking.batch']

            not_done_pickings = not_picked_pickings + backorder_pickings

            not_done_moves_data = [{
                'product': {
                    'id': move.product_id.id,
                    'name': move.product_id.name_get()[0][1],
                },
                'demand_qty': move.product_uom_qty,
                'quantity_done': move.quantity_done,
                'origin': move.picking_id.origin,
                'uom': move.product_id.uom_id.name
            } for move in not_done_pickings.mapped('move_lines').filtered(
                lambda m: float_compare(m.product_uom_qty, m.quantity_done, 2) > 0)]

            if backorder_pickings:
                boc = self.env['stock.backorder.confirmation'].sudo().create({
                    'pick_ids': [(6, 0, backorder_pickings.ids)],
                    'backorder_confirmation_line_ids': [(0, 0, {'to_backorder': True, 'picking_id': backorder_picking.id}) for backorder_picking in backorder_pickings]})
                boc = boc.with_context(button_validate_picking_ids=backorder_pickings.ids)
                if cancel_backorder:
                    boc.process_cancel_backorder()
                else:
                    boc.process()

            if done_pickings:
                def action_done():
                    threaded_sending = threading.Thread(target=done_pickings.async_action_done, kwargs={'ids': done_pickings.ids})
                    threaded_sending.start()

                self.env.cr.postcommit.add(action_done)

            if auto_create:
                remaining_pickings = backorder_pickings.mapped('backorder_ids') + not_picked_pickings

                if remaining_pickings:
                    remaining_pickings.action_assign()
                    new_batch = self.copy({'picking_ids': [(6, 0, remaining_pickings.filtered(lambda r: r.state == 'assigned').ids)],
                                           'user_id': self.env.user.id})

                    new_batch.action_confirm()
            else:
                not_picked_pickings.write({'batch_id': False})

            self.write({'state': 'done'})

            return {
                'success': True,
                'error': False,
                'new_batch_id': new_batch.id,
                'not_done_moves_data': not_done_moves_data
            }

        except Exception as e:
            _logger.info(e)
            return {'error': True, 'success': False, 'error_message': e}

    def get_pickings(self, wave_type, warehouse_id, limit, product_id=False, existing_pickings_ids=[]):
        where_clause = """so.warehouse_id = %s
                      AND sp.sequence_code = 'PICK'
                      AND sp.state = 'assigned'
                      AND sp.batch_id IS NULL"""

        if wave_type == 'single' and product_id:
            where_clause += """ AND sm.product_id = %s
                                AND sp.is_single_picking IS TRUE"""
            params = (warehouse_id, product_id, limit,)
            if existing_pickings_ids:
                where_clause += " AND sp.id NOT IN %s"
                params = (warehouse_id, product_id, tuple(existing_pickings_ids), limit,)

            query = """
                SELECT sp.id
                FROM stock_picking AS sp
                LEFT JOIN sale_order AS so ON so.id = sp.sale_id
                LEFT JOIN stock_move AS sm ON sm.picking_id = sp.id
                WHERE {}
                ORDER BY so.commitment_date ASC
                LIMIT %s
            """.format(where_clause)
        elif wave_type == 'single':
            where_clause += """ AND sp.is_single_picking IS TRUE"""
            params = (warehouse_id, limit,)
            if existing_pickings_ids:
                where_clause += " AND sp.id NOT IN %s"
                params = (warehouse_id, tuple(existing_pickings_ids), limit,)

            query = """
                WITH
                  single_pickings AS (
                    SELECT sp.id AS pickingID
                    FROM stock_picking AS sp
                    LEFT JOIN sale_order AS so ON so.id = sp.sale_id
                    WHERE {}),
                  top_product AS (
                    SELECT sm.product_id AS productID,
                    COUNT(sp.id) as number_of_pickings
                    FROM stock_picking AS sp
                    LEFT JOIN stock_move AS sm ON sm.picking_id = sp.id
                    WHERE sp.id IN (SELECT * FROM single_pickings)
                    GROUP BY productID
                    ORDER BY number_of_pickings DESC
                    LIMIT 1)

                SELECT sp.id
                FROM stock_picking AS sp
                LEFT JOIN stock_move AS sm ON sm.picking_id = sp.id
                LEFT JOIN sale_order AS so ON so.id = sp.sale_id
                WHERE sm.product_id IN (SELECT productID FROM top_product)
                      AND sp.id IN (SELECT * FROM single_pickings)
                ORDER BY so.commitment_date ASC
                LIMIT %s
            """.format(where_clause)
        else:
            where_clause += """ AND (sp.is_single_picking IS FALSE OR sp.is_single_picking IS NULL)"""
            params = (warehouse_id, limit,)
            if existing_pickings_ids:
                where_clause += " AND sp.id NOT IN %s"
                params = (warehouse_id, tuple(existing_pickings_ids), limit,)

            query = """
                SELECT sp.id
                FROM stock_picking AS sp
                LEFT JOIN sale_order AS so ON so.id = sp.sale_id
                WHERE {}
                ORDER BY so.commitment_date ASC
                LIMIT %s
            """.format(where_clause)

        self.env.cr.execute(query, params)
        query_result = self.env.cr.fetchall()
        picking_ids = [int(row[0]) for row in query_result]
        return picking_ids

    def auto_select_pickings(self):
        self.ensure_one()
        self.check_wave_picking()
        pickings_limit = self.env.user.company_id.number_of_orders_per_wave
        picking_ids = self.get_pickings(
            self.wave_type,
            self.warehouse_id.id,
            pickings_limit,
            product_id=self.product_id and self.product_id.id or False,
            existing_pickings_ids=self.picking_ids.ids)
        if not picking_ids:
            raise UserError('Found no transfers in system')

        vals = {'picking_ids': [(4, picking_id) for picking_id in picking_ids]}
        if self.wave_type == 'single' and not self.product_id:
            pickings = self.env['stock.picking'].browse(picking_ids)
            product_id = pickings.check_single_product_picking()
            vals['product_id'] = product_id.id
        self.write(vals)
        return True

    def check_wave_picking(self):
        for rec in self:
            rec.picking_ids.check_warehouse_for_picking(rec.warehouse_id)
            if rec.wave_type == 'single':
                product_id = rec.picking_ids.check_single_product_picking()
                product_id and product_id != rec.product_id and rec.write({'product_id': product_id.id})
        return True
