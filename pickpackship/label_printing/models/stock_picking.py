import logging

from odoo import models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def do_print_picking(self):
        res = super(StockPicking, self).do_print_picking()
        if 'report_name' not in res:
            res['context'] = dict(
                **res['context'],
                do_send_print_picking=True,
                res_id=self.id,
                method='do_print_picking'
            )
            return res

        return self._do_sent_print_picking()

    def _do_sent_print_picking(self):
        self.ensure_one()
        is_sent = self.do_print_shipping_labels()
        if is_sent:
            return {
                'effect': {
                    'type': 'rainbow_man',
                    'message': _("Your request has been sent to the printer."),
                }
            }

    def _send_file(self, printing_service, attachments):
        """
        Depends on selected printing service
        """
        return False

    def do_print_shipping_labels(self):
        self.ensure_one()

        printing_service = self.env['ir.config_parameter'].sudo().get_param('printing.service')

        if not printing_service:
            raise ValidationError(_('Please set up printing service (BarTender, QZ. or IoT Box).'))

        # Shipping labels from carrier
        label_attachments = False
        if self.carrier_tracking_ref:
            messages = self.env['mail.message'].sudo().search([
                ('model', '=', self._name),
                ('res_id', '=', self.id),
                ('body', 'ilike', self.carrier_tracking_ref),
                ('attachment_ids', '!=', False)
            ])
            label_attachments = messages.mapped('attachment_ids')
        if not label_attachments:
            raise UserError(_('There are no label created for this transfer.'))
        return self._send_file(printing_service, label_attachments)

    def do_print_product_labels(self):
        self.ensure_one()
        if self.state == 'done':
            done_move_lines = self.move_line_ids.filtered(lambda ml: float_compare(ml.qty_done, 0.0, precision_digits=2) > 0)
            if done_move_lines:
                return done_move_lines.print_label()
        else:
            raise UserError(_('Label printing not available. Please try again after the transaction is done.'))
        return False
