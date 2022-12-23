# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class PickingType(models.Model):
    _inherit = "stock.picking.type"

    is_use_operation_type_for_pickings = fields.Boolean('Use Operation Type for Pickings')
