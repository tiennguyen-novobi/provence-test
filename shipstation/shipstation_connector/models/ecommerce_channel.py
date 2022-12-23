from odoo import fields, models, api, _
from odoo.exceptions import UserError


class EcommerceChannel(models.Model):
    _inherit = 'ecommerce.channel'

    platform = fields.Selection(selection_add=[('shipstation', 'ShipStation')])

    shipstation_account_id = fields.Many2one('shipstation.account', string='ShipStation Account')
    shipstation_api_key = fields.Char(string='ShipStation API Key', related='shipstation_account_id.api_key')
    shipstation_api_secret = fields.Char(string='ShipStation API Secret', related='shipstation_account_id.api_secret')

    is_shipstation_custom_store = fields.Boolean(string='ShipStation Custom Store', default=False)
    shipstation_store_id = fields.Integer(string='ShipStation Store ID')
    shipstation_imported_product_field_ids = fields.Many2many('shipstation.imported.product.field',
                                                              string='ShipStation Imported Product Fields',
                                                              readonly=True)

    def _compute_master_exported_field_help_text(self):
        for record in self.filtered(lambda r: r.platform == 'shipstation'):
            record.master_exported_field_help_text = """Fields exported by default: Name, SKU, UPC, Price, Images, Weight, Item Options"""
        super(EcommerceChannel, self.filtered(lambda r: r.platform != 'shipstation'))._compute_master_exported_field_help_text()

    @api.model
    def create(self, vals):
        if vals['platform'] == 'shipstation':
            product_fields = self.env['shipstation.imported.product.field'].sudo().search([])
            vals['shipstation_imported_product_field_ids'] = [(6, 0, product_fields.ids)]
        return super().create(vals)

    def _shipstation_update_active_status(self, active):
        stores = self.filtered(lambda r: r.platform == 'shipstation')
        if stores:
            if not active:
                stores.shipstation_account_id.with_context(no_update=True).update(
                    {'ecommerce_channel_ids': [(3, store.id, 0) for store in stores]})
            else:
                for store in stores:
                    store.shipstation_account_id.with_context(no_update=True).update(
                        {'ecommerce_channel_ids': [(4, store.id, 0)]})

    def _shipstation_check_invalid_store(self, status):
        if status:
            shipstation_accounts = self.filtered(lambda r: r.platform == 'shipstation').mapped('shipstation_account_id')
            if any(not account.active for account in shipstation_accounts):
                raise UserError(_('Cannot re-connect this store. The ShipStation account is inactive.'))

    def write(self, vals):
        """Hide Order Menus when archived stores on ShipStation
        """
        res = super().write(vals)
        if 'active' in vals:
            self._shipstation_check_invalid_store(vals['active'])
            self._shipstation_update_active_status(vals['active'])
        return res

    @api.model
    def shipstation_get_order_views(self):
        parent = self.env.ref('shipstation_connector.menu_shipstation_orders')
        view_ids = [(5, 0, 0),
                    (0, 0, {'view_mode': 'tree', 'view_id': self.env.ref('multichannel_order.view_all_store_orders_tree').id}),
                    (0, 0, {'view_mode': 'form', 'view_id': self.env.ref('multichannel_order.view_store_order_form_omni_manage_channel_inherit').id})]
        return parent, view_ids

    @api.model
    def shipstation_get_default_order_statuses(self):
        return self.env.ref('shipstation_connector.shipstation_order_status_awaiting_shipment')

    def open_log_export_order(self):
        action = self._get_base_log_action()
        action.update({
            'domain': [('channel_id.id', '=', self.id), ('operation_type', '=', 'export_order')],
            'display_name': f'{self.name} - Logs - Order Export',
            'views': [
                (self.env.ref('omni_log.export_order_log_view_tree').id, 'list'),
                (self.env.ref('omni_log.export_order_log_view_form').id, 'form')
            ]
        })
        return action
