import pytz

from odoo import fields, models, api, _
from ..utils.shipstation_api_helper import ShipStationHelper
from odoo.exceptions import ValidationError
from odoo.addons.channel_base_sdk.utils.common.exceptions import EmptyDataError
from ..utils.shipstation_store_helper import ShipStationStoreImporter, ShipStationStoreImportBuilder
from ..utils.shipstation_carrier_helper import ShipStationCarrierImporter, ShipStationCarrierImportBuilder, ShipStationCarrierHelper
from odoo.tools import safe_eval
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import UserError

SHIPSTATION_CREDENTIAL = ['api_key', 'api_secret']


class ShipStationAutoExportRule(models.Model):
    _name = 'shipstation.auto.export.rule'
    _description = 'ShipStation Auto Export Rule'
    _order = 'sequence'

    sequence = fields.Integer(string='Sequence')
    filter_domain = fields.Char(string='Condition', help="If present, this condition must be satisfied before executing the action rule.")
    account_id = fields.Many2one('shipstation.account', string='ShipStation Account', ondelete='cascade')
    available_store_ids = fields.Many2many(related='account_id.ecommerce_channel_ids')
    store_id = fields.Many2one('ecommerce.channel', domain="[('id','in',available_store_ids)]", required=True, ondelete='cascade')

    def _get_eval_context(self):
        """ Prepare the context used when evaluating python code
            :returns: dict -- evaluation context given to safe_eval
        """
        return {
            'datetime': safe_eval.datetime,
            'dateutil': safe_eval.dateutil,
            'time': safe_eval.time,
            'uid': self.env.uid,
            'user': self.env.user,
        }

    def _generate_domain(self, order):
        self.ensure_one()
        self_sudo = self.sudo()
        domain = ([('id', '=', order.id)] + safe_eval.safe_eval(self_sudo.filter_domain or '[]', self._get_eval_context()))
        return domain

    def _check_rule(self, order):
        self.ensure_one()
        domain = self._generate_domain(order)
        if order.sudo().search(domain):
            return True
        return False


class ShipStationAccount(models.Model):
    _name = 'shipstation.account'
    _description = 'ShipStation Account'

    name = fields.Char(string='ShipStation Account')
    active = fields.Boolean(string='Active')
    display_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', compute='_compute_display_status')
    api_key = fields.Char(string='ShipStation API Key', required=True)
    api_secret = fields.Char(string='ShipStation API Secret', required=True)

    ecommerce_channel_ids = fields.Many2many('ecommerce.channel', string='E-commerce Channels', domain="[('shipstation_account_id', '=', id)]")
    number_of_services = fields.Integer(string='Number of Services', compute='_get_number_of_services')
    delivery_carrier_ids = fields.Many2many('delivery.carrier', string='Services')
    auto_export_order = fields.Boolean(string='Auto Export Order', default=False)
    auto_export_rule_ids = fields.One2many('shipstation.auto.export.rule', 'account_id', string='Auto Export Rules')
    tz = fields.Selection(_tz_get, string='Timezone', default=False, required=True, help='Timezone should be the same as in Display Options in ShipStation')

    @api.depends('delivery_carrier_ids', 'delivery_carrier_ids.active')
    def _get_number_of_services(self):
        for record in self:
            record.number_of_services = len(record.with_context(active_test=False).delivery_carrier_ids)

    def convert_tz(self, date, to_utc=True):
        self.ensure_one()
        tz = pytz.timezone(self.tz)
        if to_utc:
            res = date.replace(tzinfo=tz).astimezone(pytz.utc)
        else:
            res = date.replace(tzinfo=pytz.utc).astimezone(tz)
        return res

    def _create_or_update_stores(self, stores):
        existed_records = self.env['ecommerce.channel'].sudo().with_context(active_test=False).search(
            [('shipstation_account_id', '=', self.id)])
        if not stores:
            self.sudo().write({'ecommerce_channel_ids': [(5, 0, 0)]})
            existed_records.sudo().write({'active': False})
            return True

        active_records = self.env['ecommerce.channel'].browse()  # records is active
        new_stores = []
        for store in stores:
            record = existed_records.filtered(lambda r: r.shipstation_store_id == int(store['shipstation_store_id']))
            if record:
                record.sudo().write(store)
                active_records |= record
            else:
                new_stores.append(store)

        archive_records = existed_records

        # Unarchive store
        if active_records:
            active_records.sudo().write({'active': True})
            archive_records = existed_records - active_records

        if archive_records:
            archive_records.sudo().write({'active': False})

        if new_stores:
            for store in new_stores:
                store.update({
                    'platform': 'shipstation',
                    'is_mapping_managed': False,
                    'can_export_product': False,
                    'can_export_product_from_master': False,
                    'can_export_product_from_mapping': False,
                    'shipstation_account_id': self.id,
                })
            records = self.env['ecommerce.channel'].sudo().create(new_stores)
            active_records |= records

        self.sudo().write({
            'ecommerce_channel_ids': [(6, 0, active_records.ids)],
        })

    def create_or_update_store(self):
        self.check_connection()

        def prepare_importer(account):
            res = ShipStationStoreImporter()
            res.account = account
            return res

        def prepare_builder(store_data):
            res = ShipStationStoreImportBuilder()
            if isinstance(store_data, dict):
                store_data = [store_data]
            res.stores = store_data
            return res

        def fetch_order(gen):
            while True:
                try:
                    store = next(gen)
                    yield store
                except StopIteration:
                    break
        store_list_datas = []
        importer = prepare_importer(self)
        for pulled in importer.do_import():
            try:
                if pulled.data:
                    builder = prepare_builder(pulled.data)
                    vals_list = list(fetch_order(builder.prepare()))
                    store_list_datas += vals_list
            except EmptyDataError:
                continue

        self._create_or_update_stores(store_list_datas)

    def _get_services(self, carriers):
        default_product_id = self.env.ref('shipstation_connector.product_product_shipstation').id
        services = []
        shipstation_carrier_helper = ShipStationCarrierHelper(self, default_product_id)
        for carrier in carriers:
            res = shipstation_carrier_helper.get_services(carrier['ss_carrier_code'], carrier['ss_carrier_name'])
            services.extend(res)
        return services

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
                available_records |= record
            else:
                new_services.append(service)

        if new_services:
            new_records = self.env['delivery.carrier'].sudo().create(new_services)
            new_records.write({
                'ss_account_id': self.id,
                'delivery_type': 'shipstation',
                'active': False
            })
            all_records = new_records | available_records
            delivery_carrier_ids += [(4, r.id) for r in all_records]

        if delivery_carrier_ids:
            self.with_context(update_services_list=True).sudo().update({
                'delivery_carrier_ids': delivery_carrier_ids,
            })

    def create_or_update_carrier_and_service(self):
        self.check_connection()

        def prepare_importer(account):
            res = ShipStationCarrierImporter()
            res.account = account
            return res

        def prepare_builder(carrier_data):
            res = ShipStationCarrierImportBuilder()
            if isinstance(carrier_data, dict):
                carrier_data = [carrier_data]
            res.carriers = carrier_data
            return res

        def fetch_carrier(gen):
            while True:
                try:
                    carrier = next(gen)
                    yield carrier
                except StopIteration:
                    break
        carriers = []
        importer = prepare_importer(self)
        for pulled in importer.do_import():
            try:
                if pulled.data:
                    builder = prepare_builder(pulled.data)
                    vals_list = list(fetch_carrier(builder.prepare()))
                    carriers += vals_list
            except EmptyDataError:
                continue
        self._create_or_update_services(carriers)

    def _update_shipping_account_info(self):
        self.ensure_one()
        self.create_or_update_store()
        self.create_or_update_carrier_and_service()

    @api.model
    def create(self, vals):
        vals['active'] = True
        res = super().create(vals)
        res._update_shipping_account_info()
        return res

    def write(self, vals):
        """
        Override to update the status of ShipStation stores when updating setting in ShipStation Account
        """
        res = super().write(vals)
        if any(key in SHIPSTATION_CREDENTIAL for key in SHIPSTATION_CREDENTIAL):
            self.check_connection()
        if 'ecommerce_channel_ids' in vals and 'no_update' not in self.env.context:
            active_stores = self.mapped('ecommerce_channel_ids')
            all_stores = self.env['ecommerce.channel'].sudo().with_context(active_test=False).search([('shipstation_account_id', 'in', self.ids)])
            archived_stores = all_stores - active_stores
            active_stores.update({'active': True})
            archived_stores.update({'active': False})
        return res

    def toggle_active(self):
        res = super().toggle_active()
        if self.active:
            self._update_shipping_account_info()
        self.with_context(active_test=False).ecommerce_channel_ids.update({'active': self.active})
        return res

    @api.depends('active')
    def _compute_display_status(self):
        for record in self:
            record.display_status = 'active' if record.active else 'inactive'

    def check_connection(self):
        self.ensure_one()
        api = ShipStationHelper.connect_with_account(self)
        res = api.stores.all()
        if res.ok():
            return {
                'effect': {
                    'type': 'rainbow_man',
                    'message': _("Everything is correctly set up!"),
                }
            }
        else:
            raise ValidationError(_("Connecting to ShipStation unsuccessfully."))

    def update_configured_store(self):
        self.create_or_update_store()

    def action_open_service_list(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('shipstation_connector.action_shipstation_service_lists')
        action['name'] = self.name
        action['res_id'] = self.id
        return action

    def _search_auto_export_rule(self, order):
        self.ensure_one()
        for rule in self.auto_export_rule_ids:
            if rule._check_rule(order):
                return rule, rule.store_id
        return None, None

    def check_auto_export_rule(self, order):
        self.ensure_one()
        return self._search_auto_export_rule(order)

    @api.ondelete(at_uninstall=False)
    def _unlink_active_account(self):
        if any(record.active for record in self):
            raise UserError(_('You cannot delete an active account.'))
        self.env['ecommerce.channel'].search([('shipstation_account_id', 'in', self.ids)]).unlink()
