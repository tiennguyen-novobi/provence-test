import logging

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    wave_label = fields.Char(readonly=True, index=True, string='Batch Label')

    def action_open_batch_picking(self):
        """
        Inherit Odoo function to open the form view of the wave batch
        """
        self.ensure_one()
        if self.wave_type:
            action = self.open_wave_picking()
        else:
            action = super(StockPickingBatch, self).action_open_batch_picking()
        return action

    def can_be_done(self):
        """
        Check if wave can be done to clear wave label. The batch can be done when:
            In the batch, the all OUT transfers (with state is READY) corresponding to PICK transfer
            MUST BE qty done >= product_uom_ty
        """
        self.ensure_one()
        can_be_done = True
        ready_move_lines = self.picking_ids\
            .mapped('move_lines.move_dest_ids.picking_id').filtered(lambda p: p.state == 'assigned')\
            .mapped('move_line_ids')
        if not ready_move_lines or ready_move_lines.filtered(lambda ml: float_compare(ml.product_uom_qty, ml.qty_done, 2) > 0):
            can_be_done = False
        return can_be_done

    def clear_wave_label(self):
        self.ensure_one()
        if not self.can_be_done():
            raise ValidationError(_('There are some items need to be sorted before wave can be done. Please check again!'))
        self.write({'wave_label': False})

    @api.model
    def create_wave_picking(self, wave_type, warehouse_id, limit):
        picking_ids = self.get_pickings(wave_type, warehouse_id, limit)
        if picking_ids:
            new_wave = self.create({'picking_ids': [(6, 0, picking_ids)],
                                    'user_id': self.env.user.id,
                                    'wave_type': wave_type,
                                    'warehouse_id': warehouse_id})
            new_wave.action_confirm()
            return new_wave
        else:
            raise UserError(_('Found no transfers in system'))

    def assign_wave_label(self, wave_label):
        self.ensure_one()
        wave_id = self.search([('wave_label', '=', wave_label), ('wave_type', '=', 'tote'), ('state', '=', 'done')], limit=1)
        result = {'error_message': False}
        if wave_id:
            result['error_message'] = "This wave label has been assigned to another the wave. Please scan another one."
        else:
            self.write({'wave_label': wave_label})

        return result

    def update_wave_picking(self, location_id, product_id, qty):
        """This method is called when pickers scan item and update to wave
        Odoo will select the proper move lines in wave to assign picked quantity depends on location_id and product_id
        There are 2 usecases for updating picked quantity
            - increasing picked quantity (qty > 0). Move lines will be updated done quantity until the demand and done quantity are equal
            - decreasing picked quantity (qty <= 0). Move lines will be updated done quantity until done quantity is zero

        Args:
            location_id (int): the location ID
            product_id (int): the product ID
            qty (float): the picked quantity

        Returns:
            dict: the information of move lines assigned picked quantity
        """
        self.ensure_one()
        if qty is None:
            qty = 0
        move_lines = self.picking_ids.mapped('move_line_ids').filtered(lambda ml: ml.product_id.id == int(product_id)
                                                                       and ml.location_id.id == int(location_id))

        if qty > 0:
            move_lines = move_lines.sorted(key=lambda m: m.id)
            for move_line in move_lines.filtered(lambda ml: float_compare(ml.product_uom_qty, ml.qty_done, precision_digits=2) > 0):
                if float_is_zero(qty, precision_digits=2):
                    break
                increased_qty = min(qty, move_line.product_uom_qty - move_line.qty_done)
                qty -= increased_qty
                qty_done = increased_qty + move_line.qty_done

                move_line.sudo().update({'qty_done': qty_done})
        else:
            move_lines = move_lines.sorted(key=lambda ml: ml.id, reverse=True)
            for move_line in move_lines.filtered(lambda ml: not float_is_zero(ml.qty_done, precision_digits=2)):
                if float_is_zero(qty, precision_digits=2):
                    break
                qty_done = move_line.qty_done + qty
                if qty_done < 0:
                    qty_done = 0
                    qty += move_line.qty_done
                else:
                    qty = 0
                move_line.sudo().update({'qty_done': qty_done})
        try:
            return {
                'name': move_lines[0].product_id.name_get()[0][1],
                'demand_qty': sum(move_lines.mapped('product_uom_qty')),
                'id': product_id,
                'uom': move_lines[0].product_id.uom_id.name,
                'qty_done': sum(move_lines.mapped('qty_done')),
                'location_id': int(location_id),
            }
        except Exception as e:
            _logger.error("Having error when updating %s" % e)
            return None

    def prepare_wave_picking_data(self):
        """This method is called for preparing data on barcode screen
        Return values will be a tuple contains the neccessary information of wave which are used in barcode app
        The element in tuple are
        1. warehouse (dict): {
            'id': warehouse id
            'name': warehouse name
        }
        2. locations: list of locations (recordset) which are sorted by travel_path_seq
        3. pickings (dict): {
            key: picking ID
            value: a list of dictionary contains {
                'move_lines': [{
                    'move_line_id': move line ID,
                    'product': {
                        'id': product ID,
                        'barcode': product barcode
                    },
                    'qty_done': done quantity,
                    'reserved_qty': reserved quantity
                }]
                'order_id': order ID of picking
            }
        }
        4. barcode_to_product: a dict to map barcode to product
        5. barcode_to_box: a dict to map barcode on box to product
        6. product_settings: a dict contains the information of all products on wave
            key: product ID
            value: {
                'name': product name,
                'id': product ID,
                'barcode': product barcode
            }
        7. data: a dict contains the information of picked products on each location
            key: location ID
            value : {
                'move_lines': [{
                    'product': {
                        'id': product ID,
                        'name': product name,
                        'barcode': product barcode,
                        'uom': UoM name,
                        'tracking': tracking type of product
                    },
                    'reserved_qty': reserved quantity,
                    'qty_done': done quantity,
                    'picking': {
                        'id': picking ID,
                        'name': picking name,
                        'origin': source document,
                        'sale_id': order ID
                    },
                    'move_line_id': move line ID,
                    'location_id': location ID,
                    'lot_name': lot name
                }]
            }
        """
        self.ensure_one()
        pickings = self.mapped('picking_ids')
        if not pickings:
            raise UserError("There are no transfers on this batch")
        move_lines = pickings.mapped('move_line_ids')
        warehouse = {
            'id': self.warehouse_id.id,
            'name': self.warehouse_id.name
        }
        locations = move_lines.mapped('location_id').sorted(key=lambda l: (l.travel_path_seq, l.id))
        data = {}
        pickings = {}
        barcode_to_product = {}
        product_settings = {}
        barcode_to_box = {}
        package_ids = move_lines.mapped('product_id').mapped('packaging_ids')
        for package_id in package_ids:
            barcode_to_box[package_id.barcode] = {'product_id': package_id.product_id.id, 'qty': package_id.qty}

        for location in locations:
            data.setdefault(location.id, {'move_lines': [], 'products': {}})
            loc_move_lines = move_lines.filtered(lambda x: x.location_id.id == location.id)
            for loc_move_line in loc_move_lines:

                product = loc_move_line.product_id
                picking = loc_move_line.picking_id
                barcode_to_product[loc_move_line.product_id.barcode] = {'id': product.id,
                                                                        'qty': 1}
                product_settings[product.id] = {
                    'id': product.id,
                    'barcode': product.barcode,
                    'name': product.name_get()[0][1]
                }

                data[location.id]['products'].setdefault(product.id, {'demand_qty': 0,
                                                                      'name': product.name_get()[0][1],
                                                                      'id': product.id,
                                                                      'qty_done': 0,
                                                                      'uom': product.uom_id.name,
                                                                      'location_id': location.id})
                data[location.id]['products'][product.id]['demand_qty'] += loc_move_line.product_uom_qty
                data[location.id]['products'][product.id]['qty_done'] += loc_move_line.qty_done

                data[location.id]['move_lines'].append({
                    'product': {
                        'id': product.id,
                        'name': product.name_get()[0][1],
                        'barcode': product.barcode,
                        'uom': product.uom_id.name,
                        'tracking': product.tracking
                    },
                    'reserved_qty': loc_move_line.product_uom_qty,
                    'qty_done': loc_move_line.qty_done,
                    'picking': {
                        'id': picking.id,
                        'name': picking.name,
                        'origin': picking.origin,
                        'sale_id': picking.sale_id.id
                    },
                    'move_line_id': loc_move_line.id,
                    'location_id': location.id,
                    'lot_name': loc_move_line.lot_id.name if loc_move_line.qty_done > 0 else False

                })
                pickings.setdefault(picking.id, {'move_lines': [],
                                                 'order_id': picking.sale_id.id})
                pickings[picking.id]['move_lines'].append({
                    'move_line_id': loc_move_line.id,
                    'product': {
                        'id': loc_move_line.product_id.id,
                        'barcode': loc_move_line.product_id.barcode
                    },
                    'qty_done': loc_move_line.qty_done,
                    'reserved_qty': loc_move_line.product_uom_qty,
                })
        return warehouse, locations, pickings, barcode_to_product, barcode_to_box, product_settings, data

    def open_wave_picking(self):
        self.ensure_one()
        if self.wave_type == 'single':
            action = self.env.ref('wave_picking.action_stock_picking_single_wave').read()[0]
        elif self.wave_type == 'order':
            action = self.env.ref('wave_picking.action_stock_picking_order_wave').read()[0]
        else:
            action = self.env.ref('wave_picking.action_stock_picking_tote_wave').read()[0]

        action['view_mode'] = 'form'
        action['views'] = [(k, v) for k, v in action['views'] if v == 'form']
        action['res_id'] = self.id
        return action

    def open_wave_picking_client_action(self):
        """This method is called when opening barcode screen for wave

        Returns:
            dict: action client value
        """
        self.ensure_one()
        if self.wave_type == 'order':
            action = self.env.ref('wave_picking_barcode.order_wave_picking_barcode_client_action').read()[0]
            action['display_name'] = _('Order Pickings')
        else:
            action = self.env.ref('wave_picking_barcode.tote_wave_picking_barcode_client_action').read()[0]
            if self.wave_type == 'single':
                action['display_name'] = _('Single-Item Pickings')
            else:
                action['display_name'] = _('Tote Pickings')
        warehouse, locations, pickings, barcode_to_product, barcode_to_box, product_settings, data = self.prepare_wave_picking_data()
        orders = [{'id': order.id, 'name': order.name} for order in self.picking_ids.mapped('sale_id')]

        order_tote_bins = {}
        for order in self.picking_ids.mapped('sale_id'):
            transfers = self.picking_ids.filtered(lambda p: p.sale_id.id == order.id and p.picking_bins)
            picking_bins = []
            for transfer in transfers:
                picking_bins.extend(transfer.picking_bins.split(','))
            order_tote_bins[order.id] = picking_bins

        params = {
            'model': self._name,
            'title': self.name,
            'warehouse': warehouse,
            'locations': [{'id': location.id, 'name': location.name, 'barcode': location.barcode} for location in locations],
            'datas': data,
            'orders': orders,
            'pickings': pickings,
            'barcode_to_product': barcode_to_product,
            'barcode_to_box': barcode_to_box,
            'product_settings': product_settings,
            'wave': {'id': self.id, 'wave_type': self.wave_type, 'is_manually_create': self.is_manually_create},
            'order_tote_bins': order_tote_bins
        }
        action = dict(action, target='fullscreen', params=params)
        action['context'] = {'active_id': self.id}
        return dict(action, target='fullscreen', params=params)

    def open_batch_picking_client_action(self):
        """This method will be called to open barcode screen when clicking on the record in kanban view

        Returns:
            dict: action value
        """
        self.ensure_one()
        if self.wave_type:
            action = self.open_wave_picking_client_action()
        else:
            action = self.env.ref('stock_barcode_picking_batch.stock_barcode_picking_batch_client_action').read()[0]
            action['params'] = {
                'model': 'stock.picking.batch',
                'picking_batch_id': self.id,
            }
            action['context'] = {
                'active_id': self.id
            }
        return action

    def clear_batch_picking(self, cancel_batch=False):
        self.ensure_one()
        move_lines = self.picking_ids.mapped('move_line_ids')
        move_lines.write({'qty_done': 0})
        # Clear bins assigned to picking
        self.picking_ids.sudo().write({'picking_bins': False})
        if cancel_batch:
            self.write({
                'picking_ids': [(5, 0, 0)],
                'state': 'cancel'
            })
