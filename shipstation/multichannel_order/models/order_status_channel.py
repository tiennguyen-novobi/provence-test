# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class OrderStatusChannel(models.Model):
    _name = 'order.status.channel'
    _description = 'Status of order on Channel'
    _rec_name = 'display_name'

    name = fields.Char(string='Name', required=True)
    id_on_channel = fields.Char(string='ID on Channel', required=False)
    display_name = fields.Char(compute='_get_display_name')
    title = fields.Char(string='Title')
    platform = fields.Selection(selection=[('none', 'None')],
                                string='Platform',
                                readonly=False,
                                required=True, default='none')
    type = fields.Selection([('fulfillment', 'Fulfillment Status'),
                             ('payment', 'Payment Status')], default='fulfillment', required=True)
    active = fields.Boolean(default=True)

    def _get_display_name(self):
        for record in self:
            record.display_name = record.title or record.name.title()
            if record.display_name == 'Cancelled':
                record.display_name = 'Canceled'
