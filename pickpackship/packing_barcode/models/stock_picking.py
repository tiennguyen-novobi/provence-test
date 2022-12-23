import threading
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_hold = fields.Boolean(string='On Hold', help='The transfer is On Hold can not be selected on Packing process in Barcode app')

    def _action_done(self):
        """
        Override _action_done function on picking for processing single wave
        There are 2 cases need to be concern:
        1. Completing picking for single pickings:
            Odoo will insert new record into single_packing_queue to prevent duplication
            between packers when running packing process
        2. Validating packing for single pickings
            Remove record out of single_packing_queue when user validate pack transfer of single picking manually
        """
        res = super(StockPicking, self)._action_done()
        single_packing_queue_env = self.env['single.packing.queue']
        single_pickings = self.filtered(lambda p: p.state == 'done'
                                        and p.is_single_picking
                                        and p.sequence_code == 'PICK')
        if single_pickings:
            existed_pickings_ids = single_packing_queue_env.search([('picking_id', 'in', single_pickings.ids)]).mapped('picking_id')
            vals = [{'product_id': single_picking.move_lines[0].product_id.id,
                     'picking_id': single_picking.id,
                     'shipping_date': single_picking.scheduled_date,
                     'warehouse_id': single_picking.picking_type_id.warehouse_id.id}
                    for single_picking in single_pickings.filtered(lambda p:p.id not in existed_pickings_ids)]
            single_packing_queue_env.create(vals)

        if not self._context.get('not_delete_picking_in_queue', False):
            single_pack_transfers = self.filtered(lambda p: p.state == 'done'
                                                  and p.is_single_picking
                                                  and p.sequence_code == 'OUT')
            if single_pack_transfers:
                single_pick_transfers = single_pack_transfers.mapped('move_lines.move_orig_ids.picking_id')
                single_packing_queue_env.search([('picking_id', 'in', single_pick_transfers.ids)]).unlink()
        return res

    def unhold_picking(self):
        self.ensure_one()
        pick_transfers = self.mapped('move_lines.move_orig_ids').mapped('picking_id')
        for pick_transfer in pick_transfers:
            if pick_transfer.state == 'done' and pick_transfer.is_single_picking and pick_transfer.sequence_code == 'PICK':
                self.env['single.packing.queue'].insert_record(self)

        pick_ship_transfers = pick_transfers + self
        pick_ship_transfers.write({'is_hold': False})

    def action_hold_shipping(self):
        self.ensure_one()
        pick_ship_transfers = self.mapped('move_lines.move_orig_ids').mapped('picking_id') + self
        pick_ship_transfers.sudo().write({'is_hold': True})
        return True

    def prepare_data_shipping_client_action(self):
        transfers = self.mapped('move_lines.move_orig_ids.picking_id') + self
        picking_bins = ','.join(list(filter(lambda b: b, transfers.mapped('picking_bins'))))

        return {
            'pickingID': self.id,
            'isSinglePicking': self.is_single_picking,
            'shippingID': self.id,
            'shipping_weight': self.weight,
            'ship_date': self.scheduled_date,
            'picking_bins': picking_bins.split(',') if picking_bins else [],
            'order': {
                'id': self.sale_id.id,
                'name': self.sale_id.name,
            },
            'moveLines': [{
                'id': move.id,
                'product': {
                    'id': move.product_id.id,
                    'name': move.product_id.name_get()[0][1]
                },
                'quantity_done': move.quantity_done,
                'demand_qty': move.product_uom_qty,
                'uom': move.product_uom.name
            } for move in self.move_lines]
        }

    @api.model
    def get_transfer_for_shipping(self, barcode, is_single_picking=False, shipping_id=None):
        """
        After scanning the product/pin, get the OUT transfer of this product corresponding the PICK transfers in the batch
        """
        if not self.env.user.warehouse_id:
            raise UserError(_("Please set up warehouse in User Settings"))
        record = self.browse()
        # Search Single Picking on Queue to ensure that don't have duplication between packers
        if shipping_id and is_single_picking:
            self.env['single.packing.queue'].insert_record(shipping_id)
        picking = self.env['single.packing.queue'].get_picking(barcode, self.env.user.warehouse_id.id)
        if picking:
            record = picking.mapped('move_lines.move_dest_ids').mapped('picking_id')[:1]
        if not record:
            domain = [('is_single_picking', '=', False),
                      ('is_hold', '=', False),
                      ('picking_type_id.warehouse_id.id', '=', self.env.user.warehouse_id.id),
                      ('picking_bins', 'ilike', barcode)]
            state_domain = expression.OR([[('state', '=', 'assigned'), ('sequence_code', '=', 'OUT')],
                                          [('state', '=', 'done'), ('sequence_code', '=', 'PICK')]])
            domain = expression.AND([domain, state_domain])

            records = self.sudo().search(domain, order='date_deadline asc')

            for rec in records:
                picking_bins = rec.picking_bins or ''
                if barcode in map(lambda s: s.strip(), picking_bins.split(',')):
                    if rec.sequence_code == 'PICK':
                        rec = rec.mapped('move_lines.move_dest_ids').mapped('picking_id')[:1]
                    if rec.state not in ('cancel', 'done'):
                        record = rec
                        break
        if not record:
            return None

        return record.prepare_data_shipping_client_action()

    def done_and_print_label(self):
        """This method will be called when packer completed packaging for shipment
        Validating shipment will be run in background for performance purpose
        """
        self.ensure_one()
        todo_move_lines = self.move_lines.filtered(lambda m: m.product_uom_qty > m.reserved_availability)
        if todo_move_lines:
            return {
                'success': False,
                'error_message': 'Cannot validate partially picked orders.',
            }

        move_lines = [(1, m.id, {'quantity_done': m.product_uom_qty}) for m in self.move_lines]
        self.sudo().write({'move_lines': move_lines})

        def action_done():
            ctx = {
                'done_ship_transfer': True,
                'not_delete_picking_in_queue': True
            }
            threaded_sending = threading.Thread(target=self.with_context(ctx).async_action_done, kwargs={'ids': self.ids})
            threaded_sending.start()

        self.env.cr.postcommit.add(action_done)

        # Clear picking bins on all picking and packing after printing label
        transfers = self.mapped('move_lines.move_orig_ids').mapped('picking_id') + self
        transfers.sudo().write({'picking_bins': False})

        return {'success': True}

    def get_order_ref(self):
        self.ensure_one()
        return self.origin
