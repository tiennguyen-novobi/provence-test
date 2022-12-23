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
        if self.channel_id.platform == 'shipstation':
            text = 'Please enter ShipStation order IDs, using commas to separate between values. E.g. 328164584, 327492202'
        return text
