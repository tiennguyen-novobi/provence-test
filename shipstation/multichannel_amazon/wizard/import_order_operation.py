# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _

class ImportOrderOperation(models.TransientModel):
    """
    This wizard is used to import orders manually
    """
    _inherit = 'import.order.operation'
    
    def _get_help_text(self):
        text = super()._get_help_text()
        if self.channel_id.platform == 'amazon':
            text = 'Please enter Amazon order IDs on the online store, using commas to separate between values. E.g. 702-7788886-6492238, 111-6168941-2089801'
        return text