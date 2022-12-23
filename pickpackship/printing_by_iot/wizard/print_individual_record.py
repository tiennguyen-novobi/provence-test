# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields
import logging


class PrintIndividualRecordLabelCreate(models.TransientModel):
    _inherit = 'print.individual.record.label.create'
    _description = 'Create Individual Record Label'

    iot_device_id = fields.Many2one('iot.device', string='Printer',
                                    help='Select printer')

    action_report_id = fields.Many2one('ir.actions.report',
                                       string='Action Report')

    def _send(self, printing_service):
        if printing_service == 'iot':
            active_ids = list(map(int, self.res_ids.split(',')))
            return self.action_report_id.iot_render(active_ids, {'device_id': self.iot_device_id.id})
        return super()._send(printing_service)
