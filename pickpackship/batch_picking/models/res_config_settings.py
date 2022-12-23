# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    batch_volume = fields.Integer('Batch Volume', default=10, required=1,
                                  config_parameter='batch_picking.batch_volume', help="Maximum number of orders in batch.")
