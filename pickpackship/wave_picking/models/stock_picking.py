import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    sequence_code = fields.Char(
        related='picking_type_id.sequence_code',
        store=True,
        readonly=True)
    picking_bins = fields.Char(string='Bins', help='Bins are being used to contain the products of the related picking')
    is_single_picking = fields.Boolean('Is Single Picking', copy=True, readonly=True)

    def check_single_product_picking(self):
        product_id = self.mapped('move_lines').mapped('product_id')
        not_single_picking = self.filtered(lambda p: not p.is_single_picking)
        if len(product_id) > 1 or not_single_picking:
            raise UserError('Please ensure all selected transfers must be single product.')
        return product_id

    def check_warehouse_for_picking(self, warehouse_id):
        diff_warehouse_picking = self.filtered(lambda p: p.sale_id.warehouse_id != warehouse_id and p.sale_id)
        if diff_warehouse_picking:
            raise UserError("Please ensure all selected transfers must have the same warehouse.")
        return True

    def calculate_is_single_picking(self):
        for picking in self:
            is_single_picking = False
            move_lines = picking.move_lines
            if len(move_lines) == 1:
                move_line = move_lines[0]
                if move_line.product_uom_qty == 1:
                    is_single_picking = True
            picking.write({
                'is_single_picking': is_single_picking
            })

    def async_action_done(self, ids):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            records = self.sudo().browse(ids)
            for record in records.filtered(lambda r: r.state != 'done'):
                try:
                    record._action_done()
                except Exception as e:
                    _logger.exception("Something went wrong when validating picking in background")
                    pass
            self._cr.commit()
            new_cr.close()
            return {}
