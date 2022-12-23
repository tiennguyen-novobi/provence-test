# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api

class PrintIndividualRecordLabelCreate(models.TransientModel):
    _name = 'print.move.line.record.label.create'
    _inherit = 'print.individual.record.label.create'
    _description = 'Print Stock Move Line'

    product_id = fields.Many2one('product.product', string='Products', required=True)

    def _send(self, printing_service):
        res_ids = self.res_ids.split(',')
        active_ids = list(map(int, res_ids))
        move_lines = self.env['stock.move.line'].browse(active_ids)
        move_lines = move_lines.filtered(lambda l: l.product_id.id == self.product_id.id)
        self.update({
            'res_ids': ','.join(str(x) for x in move_lines.ids)
        })
        return super()._send(printing_service)
