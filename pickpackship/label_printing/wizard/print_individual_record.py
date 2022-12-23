# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PrintIndividualRecordLabelCreate(models.TransientModel):
    _name = 'print.individual.record.label.create'
    _description = 'Create Individual Record Label'

    copies = fields.Integer('Number of Copies')

    res_model = fields.Char(string='Model')
    res_ids = fields.Char(string='Record IDs')

    @api.constrains('copies')
    def _check_copies(self):
        if any(r.copies <= 0 for r in self):
            raise ValidationError(_('Number of Copies must be greater than 0.'))

    def _send(self, printing_service):
        """
        Depends on services
        """
        return True

    def send(self):
        self.ensure_one()
        printing_service = self.env['ir.config_parameter'].sudo().get_param('printing.service')
        return self._send(printing_service)
