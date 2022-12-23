# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class DefaultPrinterUser(models.Model):
    _name = 'default.printer.user'
    _description = 'Default Printer per User'

    user_id = fields.Many2one('res.users', string='User')
    server_action_id = fields.Many2one('ir.actions.server', string='Server Action')
    default_printer_id = fields.Many2one('iot.device', string='Default Printer', domain=[('type', '=', 'printer')])
    model_id = fields.Many2one('ir.model', string='Model', related='server_action_id.model_id')
    iot_id = fields.Many2one('iot.box', string='IoT Box', related='default_printer_id.iot_id')
    connected = fields.Boolean(string='Status', related='default_printer_id.connected')
