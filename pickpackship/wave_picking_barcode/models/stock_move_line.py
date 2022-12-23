import logging

from odoo import models
from odoo.osv import expression

_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def update_picking_bins(self, picking_bins):
        self.ensure_one()
        pickings = self.move_id.mapped('picking_id')
        pickings.sudo().update({'picking_bins': picking_bins})
        return True

    def prepare_sort_picking_data(self, qty=0):
        self.ensure_one()
        move_line_data = {
            'move_line_id': self.id,
            'order_name': self.picking_id.sale_id.name,
            'product_name': self.product_id.name_get()[0][1],
            'demand_qty': self.product_uom_qty,
            'qty_done': self.qty_done,
            'product_id': self.product_id.id,
            'uom': self.product_id.uom_id.name,
            'picking_bins': self.picking_id.picking_bins or '',
            'updated_qty_done': self.qty_done + qty,
            'picked_status': 'Fully Picked' if self.picking_id.state in ('assigned', 'done') else 'Partially Picked',
        }
        return move_line_data

    def update_sorted_move_line(self, qty, bin_barcode, wave_id):
        self.ensure_one()
        result = {'error_message': False, 'line_data': None, 'wave_can_be_done': False}
        picking = self.picking_id
        #
        # Check if bin barcode was used before. Bin may be assigned when
        # 1. Sorter use it for sorting on OUT transfers
        # 2. Picker use it for sorting while processing order waves on PICK transfers
        #
        domain = [('picking_bins', 'ilike', bin_barcode), ('is_single_picking', '=', False), ('id', '!=', picking.id)]
        state_domain = expression.OR([[('state', 'in', ['assigned', 'waiting', 'confirmed']), ('sequence_code', '=', 'OUT')],
                                      [('state', '=', 'done'), ('sequence_code', '=', 'PICK')]])

        domain = expression.AND([domain, state_domain])
        checked_packings = self.env['stock.picking'].search(domain)

        if checked_packings.filtered(lambda p: bin_barcode in p.picking_bins.split(',')):
            result.update({'error_message': 'Bin %s is being used for order %s' % (bin_barcode, checked_packings[0].sale_id.name)})
            return result

        if not picking.picking_bins:
            picking_bins = bin_barcode
        else:
            picking_bins = ','.join(list(set(picking.picking_bins.split(',') + [bin_barcode])))

        picking.update({
            'picking_bins': picking_bins,
            'move_line_ids': [(1, self.id, {'qty_done': qty})],
        })

        wave = self.env['stock.picking.batch'].browse(int(wave_id))
        result.update({'line_data': self.prepare_sort_picking_data(), 'wave_can_be_done': wave.can_be_done()})
        return result

    def update_scanning_qty(self, location_id, qty_done, lot_id=False):
        self.ensure_one()
        move_line = self
        if self.lot_id and self.lot_id.id != lot_id and lot_id:
            move = self.move_id.sudo()
            vals = move._prepare_move_line_vals()
            vals.update({
                'lot_id': lot_id,
                'location_id': location_id,
                'qty_done': qty_done
            })
            move_line = self.sudo().create(vals)
        else:
            if lot_id and not self.lot_id:
                self.sudo().write({'qty_done': qty_done, 'lot_id': lot_id})
            else:
                self.sudo().write({'qty_done': qty_done})

        return {
            'qty_done': move_line.qty_done,
            'lot_name': move_line.lot_id.name if move_line.qty_done > 0 else '',
            'id': move_line.id,
            'lot_id': move_line.lot_id.id
        }

    def reset_picking_bins(self, bin_barcode, qty):
        self.ensure_one()
        picking = self.picking_id
        vals = {
            'move_line_ids': [(1, self.id, {'qty_done': self.qty_done - qty})],
        }
        picking_bins = list(set(picking.picking_bins.split(',')))
        if bin_barcode and bin_barcode in picking_bins:
            picking_bins.remove(bin_barcode)
            vals['picking_bins'] = ','.join([str(elem) for elem in picking_bins]) if picking_bins else ''

        picking.write(vals)
        return self.prepare_sort_picking_data(qty)
