import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def get_customer_partner(self, customer_data):
        if not (self._context.get("is_fba") or customer_data['name']):
            return self
        ### PB-39 ###
        # search for existing contact with email and name
        partner = self.sudo().search(
            [('type', '=', 'contact'), ('email', '=', customer_data['email']), ('email', '!=', False),
             ('name', '=', customer_data['name'])], limit=1)
        if self._context.get("is_fba"):
            # Customer name is not returned for FBA orders
            partner = self.sudo().search(
                [('type', '=', 'contact'), ('email', '=', customer_data['email']), ('email', '!=', False)], limit=1)
        if not partner:
            vals = {'name': customer_data['name'] or f"{self._context.get('channel').default_guest_customer} {self._context.get('order_ref')}",
                    'phone': customer_data.get('phone', ''),
                    'email': customer_data['email'],
                    'street': customer_data.get('street', ''),
                    'street2': customer_data.get('street2', ''),
                    'city': customer_data.get('city', ''),
                    'state_id': customer_data.get('state_id', False),
                    'country_id': customer_data.get('country_id', False),
                    'zip': customer_data.get('zip', ''),
                    'type': 'contact',
                    'customer_rank': 1
                    }
            partner = self.sudo().with_context(mail_create_nosubscribe=True).create(vals)
        return partner
