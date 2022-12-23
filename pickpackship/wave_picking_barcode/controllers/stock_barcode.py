from odoo.http import request
from odoo import http, _

from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController

class StockBarcodeControllerInherit(StockBarcodeController):

    @http.route()
    def main_menu(self, barcode, **kw):
        """ Receive a barcode scanned from the main menu and return the appropriate
            action (open an existing / new picking) or warning.
        """
        ret_open_batch_picking = self.try_open_batch_picking(barcode)
        if ret_open_batch_picking:
            return ret_open_batch_picking

        return super(StockBarcodeControllerInherit, self).main_menu(barcode, **kw)

    def try_open_batch_picking(self, barcode):
        """ If barcode represents a picking, open it
        """
        corresponding_batch_picking = request.env['stock.picking.batch'].search([
            ('name', '=', barcode), ('wave_type', '!=', False)
        ], limit=1)
        if corresponding_batch_picking:
            action = corresponding_batch_picking.open_batch_picking_client_action()
            action['context'] = {'active_id': corresponding_batch_picking.id}
            action = {'action': action}
            return action
        return super(StockBarcodeControllerInherit, self).try_open_batch_picking(barcode)
