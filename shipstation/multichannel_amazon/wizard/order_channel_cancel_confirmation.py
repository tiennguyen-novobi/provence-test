# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
from odoo import models, _
class OrderChannelCancelConfirmation(models.TransientModel):
    _inherit = 'order.channel.cancel.confirmation'

    def button_confirm(self):
        super().button_confirm()
        if self.sale_order_id.channel_id.platform == 'amazon':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Notification!'),
                    'message': _('Sent cancellation request to Amazon. It will take a few minutes to process your request.'),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            } 

    