# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    default_printer_ids = fields.One2many('default.printer.user', 'user_id', string='Default Printers')
