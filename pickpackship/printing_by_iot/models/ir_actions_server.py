# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    printer_ids = fields.Many2many('iot.device', string="Printers", domain=[('type', '=', 'printer')])
