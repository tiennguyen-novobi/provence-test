# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class EcommerceChannel(models.Model):
    _inherit = 'ecommerce.channel'

    def open_auto_buy_label_log(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', '=', 'auto_buy_label')],
            'display_name': f'{self.name} - Logs - Auto Buy Label',
            'views': [
                (self.env.ref('pb_omni_log.auto_buy_label_log_view_tree').id, 'list'),
                (self.env.ref('pb_omni_log.auto_buy_label_log_view_form').id, 'form')
            ],
            'context': {
                'include_platform': True,
                'search_default_draft': 1,
                'search_default_failed': 1
            },
        })
        return action
