from odoo import models, api, fields

POUND_TO_OUNCE = 16


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('amazon', 'Amazon')], ondelete={'amazon': 'set default'})

    @api.model
    def amazon_void_label(self, picking):
        """
        Void label
        :return: {
                    'success': Bool,
                    'error_message': String,
                    'warning_message': String,
                }
        """

        return picking.amazon_void_label()
