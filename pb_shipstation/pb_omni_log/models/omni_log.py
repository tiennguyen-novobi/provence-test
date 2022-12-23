import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class OmniLog(models.Model):
    _inherit = 'omni.log'

    operation_type = fields.Selection(selection_add=[('auto_buy_label', 'Auto Buy Label')])
