from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)

class StockLocation(models.Model):
    _inherit = "stock.location"

    travel_path_seq = fields.Integer("Travel Path Sequence")

    def send_email_to_alert(self, action_name, warehouse):
        self.ensure_one()
        warehouse_id = self.env['stock.warehouse'].browse(warehouse.get("id", False))
        partner_to = ','.join([str(id) for id in warehouse_id.warehouse_manager_ids.ids])
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        open_location_url = '{base_url}/web#id={location_id}&model={model}&action={action_id}&active_id={active_id}&view_type={view_type}'.format(
            base_url=base_url,
            location_id=self.id,
            active_id=self.id,
            model="stock.quant",
            action_id=self.env.ref('stock.location_open_quants').id,
            view_type='tree'
        )
        ctx = {
            'partner_to': partner_to,
            'warehouse_name': warehouse.get('name'),
            'open_location_url': open_location_url,
            'action_name': action_name,
            'error_name': 'incorrect' if action_name == 'do cycle count' else 'low'
        }

        template = self.env.user.company_id.send_alert_email_template_id

        if not template:
            template = self.env.ref('wave_picking_barcode.email_template_to_alert')
        template.with_user(self.env.user).with_context(ctx).send_mail(self.id, force_send=False)
        return True
