# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IotDevice(models.Model):
    _inherit = 'iot.device'

    @api.model
    def get_devices(self, device_type):
        devices = self.search([('type', '=', device_type),
                               ('connected', '=', True)])

        return [{
            'id': device.id,
            'name': device.name,
            'iot_ip': device.iot_id.ip,
            'identifier': device.identifier
        } for device in devices]

    def get_printers(self, server_action_id):
        server_action = self.env['ir.actions.server'].browse(server_action_id)
        printers = default_printer = self.browse()
        if server_action:
            printers = server_action.printer_ids.filtered(lambda p: p.connected)
            default_printer = self.env.user.default_printer_ids.filtered(lambda p:
                               p.server_action_id == server_action and p.connected)[:1].default_printer_id

        return [{
            'id': device.id,
            'name': device.name,
            'iot_ip': device.iot_id.ip,
            'identifier': device.identifier,
            'is_default': device.id == default_printer.id
        } for device in printers]

    def update_default_printer(self, server_action_id, printer_id):
        server_action = self.env['ir.actions.server'].browse(server_action_id)
        default_printer_user = self.env.user.default_printer_ids.filtered(lambda p: p.server_action_id.id == server_action.id)
        if default_printer_user and default_printer_user.default_printer_id.id != printer_id:
            default_printer_user.write({'default_printer_id': printer_id})
        elif not default_printer_user:
            self.env['default.printer.user'].create({
                'user_id': self.env.user.id,
                'server_action_id': server_action_id,
                'default_printer_id': printer_id
            })

        return True
