from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class WavePickingWizard(models.TransientModel):
    _name = 'wave.picking.wizard'
    _description = 'Wave Picking Wizard'

    def _default_number_of_orders_per_wave(self):
        return self.env.user.number_of_orders_per_wave or self.env.user.company_id.number_of_orders_per_wave

    def _default_wave_picking_warehouse_id(self):
        return self.env.user.warehouse_id and self.env.user.warehouse_id.id or False

    wave_type = fields.Selection([
        ('single', 'Single-Item'),
        ('tote', 'Tote'),
        ('order', 'Order')
    ], string='Batch Type', default='order')
    number_of_orders_per_wave = fields.Integer(string='Number of Orders in Batch', default=_default_number_of_orders_per_wave)
    warehouse_id = fields.Many2one('stock.warehouse',
                                   string='Warehouse',
                                   default=_default_wave_picking_warehouse_id,
                                   domain="[('lot_stock_id.usage', '=', 'internal')]")

    @api.constrains('number_of_orders_per_wave')
    def _check_number_of_orders_per_wave(self):
        if self.number_of_orders_per_wave <= 0:
            raise ValidationError(_('Number of Orders in Batch has to be strictly positive.'))

    def wave_creation_confirm(self):
        self.ensure_one()
        if not self.warehouse_id:
            raise ValidationError(_('You must select a warehouse.'))
        new_wave = self.env['stock.picking.batch'].create_wave_picking(self.wave_type, self.warehouse_id.id,
                                                                       self.number_of_orders_per_wave)
        return new_wave.open_wave_picking_client_action()
