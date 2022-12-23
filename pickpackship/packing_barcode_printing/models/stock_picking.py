from odoo import models

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def get_shipping_label_attchments(self):
        self.ensure_one()
        label_attachments = []
        if self.carrier_tracking_ref:
            messages = self.env['mail.message'].sudo().search([
                ('model', '=', self._name),
                ('res_id', '=', self.id),
                ('body', 'ilike', self.carrier_tracking_ref),
                ('attachment_ids', '!=', False)
            ])
            label_attachments = messages.mapped('attachment_ids')
        return label_attachments

    def prepare_data_shipping_client_action(self):
        """Override this method to support for label printing in packaging screen on barcode app
        """
        res = super(StockPicking, self).prepare_data_shipping_client_action()
        label_attachments = self.get_shipping_label_attchments()
        res['labels'] = label_attachments and [attachment.datas for attachment in label_attachments] or False
        return res
