# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _send_file(self, printing_service, attachments):
        """
        Depends on selected printing service
        """
        if printing_service == 'iot':
            return {
                'type': 'ir.actions.client',
                'tag': 'action.iot_printing',
                'target': 'new',
                'name': 'Print Shipping Label',
                'context': {
                    'labels': [attachment.datas for attachment in attachments],
                    'print_file': True,
                    'printing_server_action_id': self._context.get('printing_server_action_id', False)
                }
            }
        return super()._send_file(printing_service, attachments)
