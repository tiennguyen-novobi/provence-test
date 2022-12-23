import logging

from odoo import models, _
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def get_wave_by_wave_label(self, barcode):
        wave = self.env['stock.picking.batch'].search([('wave_label', '=', barcode),
                                                       ('wave_type', '=', 'tote'),
                                                       ('state', '=', 'done')], limit=1)

        if not wave:
            return {}
        else:
            wave_products = {}
            products = wave.picking_ids.mapped('move_lines.product_id')
            for product in products:
                for box in product.packaging_ids.filtered(lambda p: p.barcode):
                    wave_products[box.barcode] = {'product_id': product.id, 'qty': box.qty}
                if product.barcode:
                    wave_products[product.barcode] = {'product_id': product.id, 'qty': 1}

            return {
                'id': wave.id,
                'wave_label': wave.wave_label,
                'wave_products': wave_products,
            }

    def get_transfer_for_sorting(self, product_info, barcode, wave_id):
        """
        After scanning the product barcode, get the OUT transfer of this product corresponding the PICK transfers in the batch
        """
        result = {'error_message': False}
        if not wave_id:
            result.update({'error_message': _('You are expected to scan a batch label.')})
            return result

        product_id = qty = None
        if product_info:
            product_id = int(product_info.get('product_id'))
            qty = int(product_info.get('qty'))

        if not product_id:
            wave = self.get_wave_by_wave_label(barcode)
            if wave:
                result.update({'wave': wave})
                return result
            result.update({'error_message': _('You are expected to scan a product')})
            return result

        # Priority, get the move that with the state is Available (fully picked)
        wave = self.env['stock.picking.batch'].browse(int(wave_id))
        product_moves = wave.picking_ids.mapped('move_lines.move_dest_ids').filtered(lambda m: m.product_id.id == product_id)
        moves = product_moves.filtered(lambda m: float_compare(m.reserved_availability, m.quantity_done + qty, 2) >= 0).sorted('state')
        if not moves and product_moves:
            result.update({'error_message': _('This product is fully sorted.')})
            return result
        elif not product_moves:
            result.update({'error_message': _('Cannot find matching order for this item.')})
            return result
        move = moves[0]
        move_line_ids = move.move_line_ids
        if not move_line_ids:
            move_line_ids += self.env['stock.move.line'].create(move._prepare_move_line_vals(quantity=move.product_uom_qty))
        move_line = move_line_ids[0]
        result.update(move_line.prepare_sort_picking_data(qty))
        return result
