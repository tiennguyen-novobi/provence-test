import logging

from odoo import models

_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _get_printing_action(self, printing_service=None):
        """
        Override this method to select printing action when the printing happens on stock.move.line
        """
        action = super()._get_printing_action(printing_service)
        if action and action.get('type', '') == 'ir.actions.client':
            return action
        action = self._for_xml_id('label_printing.view_print_move_line_record_label_create_action')
        action.update({
            'views': [(self._get_printing_label_form(printing_service), 'form')],
            'view_id': self._get_printing_label_form(printing_service)
        })
        return action

    def _update_printing_action_context(self, printing_service):
        """
        Override this method to update context for printing action when the printing happens on stock.move.line
        """
        context = super()._update_printing_action_context(printing_service)
        context.update({
            'product_ids': self.mapped('product_id').ids,
            'selected_records': [{
                'id': product.id,
                'name': product.name_get()[0][1],
                'default_copies': sum(self.filtered(lambda l: l.product_id.id == product.id).mapped('qty_done'))
            } for product in self.mapped('product_id')],
            'selected_title': 'Product'
        })
        return context
