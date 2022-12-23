from odoo import models, fields, api


class ShipStationAccount(models.Model):
    _inherit = 'shipstation.account'

    delivery_carrier_ids = fields.Many2many('delivery.carrier', relation='rel_shipstation_account_carrier',
                                            string='Services')

    def _create_or_update_services(self, carriers):
        services = self._get_services(carriers)
        existed_records = self.env['delivery.carrier'].sudo().with_context(active_test=False).search(
            [('ss_account_id', '=', self.id)])
        if not services:
            self.sudo().write({'delivery_carrier_ids': [(5, 0, 0)]})
            return True

        # Update selected carrier
        delivery_carrier_ids = []
        # Create services on ShipStation in OB
        new_services = []
        available_records = self.env['delivery.carrier'].browse()

        for service in services:
            record = existed_records.filtered(lambda r: r.ss_service_name == service['ss_service_name']
                                                        and r.ss_service_code == service['ss_service_code'])
            if record:
                ### PB-38 ###
                # All services should have active set to True. What decides whether they should appear in the popup
                # is whether they are checked or unchecked by users.
                # Previously all services are marked as inactive.
                record.write({"active": True, "is_domestic": service["is_domestic"],
                              "is_international": service["is_international"]})
                available_records |= record
            else:
                new_services.append(service)

        if new_services:
            new_records = self.env['delivery.carrier'].sudo().create(new_services)
            new_records.write({
                'ss_account_id': self.id,
                'delivery_type': 'shipstation',
                ### PB-38 ###
                # Same reason
                'active': True,
                "is_domestic": service["is_domestic"],
                "is_international": service["is_international"]
            })
            all_records = new_records | available_records
            delivery_carrier_ids += [(4, r.id) for r in all_records]

        if delivery_carrier_ids:
            self.with_context(update_services_list=True).sudo().update({
                'delivery_carrier_ids': delivery_carrier_ids,
            })

    @api.model
    def create(self, vals):
        res = super().create(vals)
        res.delivery_carrier_ids.create_or_update_shipping_account()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_active_account(self):
        super()._unlink_active_account()

        shipping_account_ids = self.mapped('delivery_carrier_ids.shipping_account_id')
        try:
            shipping_account_ids.unlink()
            self.mapped('delivery_carrier_ids').unlink()
        except:
            pass
