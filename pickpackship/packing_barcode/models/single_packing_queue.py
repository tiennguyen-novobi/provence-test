import logging

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)

class SinglePackingQueue(models.Model):
    _name = 'single.packing.queue'
    _description = 'Single Packing Queue Task'

    product_id = fields.Many2one('product.product', required=True)
    product_barcode = fields.Char(string='Product Barcode', related='product_id.barcode', store=True)
    picking_id = fields.Integer(string='Picking ID', required=True, copy=False)
    warehouse_id = fields.Integer(string='Warehouse ID', required=True, copy=False)
    shipping_date = fields.Datetime(string='Shipping Date')

    _sql_constraints = [
        ('product_picking_id_uniq',
         'unique(product_id, picking_id)',
         'Picking ID must be unique'),
    ]

    @api.model
    def get_picking(self, product_barcode, warehouse_id):
        """
        Get 1st picking ordered by shipping_date and delete it
        @return: Return the shipping transfer of this picking transfer
        """
        try:
            while True:
                query = """
                    DELETE FROM single_packing_queue
                    WHERE id = (
                      SELECT id
                      FROM single_packing_queue
                      WHERE product_barcode=%s AND warehouse_id=%s
                      ORDER BY shipping_date ASC
                      FOR UPDATE SKIP LOCKED
                      LIMIT 1
                    )
                    RETURNING picking_id;
                """
                self.env.cr.execute(query, (product_barcode, warehouse_id))
                picking_id = self.env.cr.fetchone()[0] or False
                if picking_id:
                    picking = self.env['stock.picking'].browse(int(picking_id))
                    if picking.mapped('move_lines.move_dest_ids').mapped('picking_id'):
                        return picking
                else:
                    return False
        except Exception as e:
            _logger.exception("Something went wrong while getting single wave for packing")
            return False

    @api.model
    def insert_record(self, shipping_id):
        """This method will be called in packing process.
        The main purpose is to insert picking which is getting from shipping transfer into queue
        """
        shipping = self.env['stock.picking'].sudo().browse(int(shipping_id))
        picking = shipping.mapped('move_lines.move_orig_ids').mapped('picking_id')[0]
        self.sudo().create({
            'product_id': picking.move_lines[0].product_id.id,
            'picking_id': picking.id,
            'warehouse_id': shipping.picking_type_id.warehouse_id.id,
            'shipping_date': shipping.scheduled_date
        })
        return True
