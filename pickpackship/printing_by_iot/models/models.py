# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models


class Base(models.AbstractModel):
    _inherit = 'base'

    def _update_printing_action_context(self, printing_service):
        """
        Get context for printing action
        """
        if printing_service == 'iot':
            default_action_report_id = False
            if self._name == 'product.template':
                default_action_report_id = self.env.ref('stock.label_barcode_product_template').id
            elif self._name == 'product.product':
                default_action_report_id = self.env.ref('stock.label_barcode_product_product').id
            elif self._name == 'stock.location':
                default_action_report_id = self.env.ref('label_printing.action_report_location_barcode_zpl').id
            elif self._name == 'stock.move.line':
                default_action_report_id = self.env.ref('label_printing.action_report_move_line_zpl').id
            return {
                'default_action_report_id': default_action_report_id,
                'printing_server_action_id': self._context.get('printing_server_action_id', False)
            }
        return super()._update_printing_action_context(printing_service)

    def _get_printing_action(self, printing_service=None):
        if printing_service == 'iot':
            return {
                'type': 'ir.actions.client',
                'tag': 'action.iot_printing',
                'target': 'new',
                'name': 'Print Label',
            }
        return super()._get_printing_action(printing_service)
