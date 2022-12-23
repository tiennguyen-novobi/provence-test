import itertools

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExportProduct(models.TransientModel):
    """
    This wizard is used to select product channel of product template
    """
    _name = 'export.product.composer'
    _description = 'Export Product Composer'

    product_tmpl_id = fields.Many2one('product.template', string='Product Template')
    product_channel_ids = fields.One2many('product.channel', 'product_tmpl_id',
                                          related="product_tmpl_id.product_channel_ids",
                                          string='Products Channel')

    channel_ids = fields.Many2many(
        'ecommerce.channel',
        string='Stores',
        required=True,
        domain=[
            ('platform', '!=', False),
            ('can_export_product_from_master', '=', True),
            ('is_mapping_managed', '=', True),
            ('can_export_product', '=', True),
        ],
    )
    product_product_ids = fields.Many2many('product.product', string='SKUs')
    product_product_count = fields.Integer('Number of master variants', compute='_compute_product_product_count')

    product_preview_ids = fields.One2many(
        'product.export.preview',
        'export_product_composer_id',
        string='SKUs to Export',
        compute='_compute_product_preview_ids',
        readonly=True,
    )

    def _process_product_preview_for_each_channel(self, product_variants, channel):
        channel = channel._origin
        product_previews = []
        for product_variant in product_variants:
            product_alternate_skus = product_variant.product_alternate_sku_ids.filtered(
                lambda p: p.channel_id.id == channel.id)
            if product_alternate_skus:
                for product_alternate in product_alternate_skus:
                    product_previews.append((0, 0, {
                        'default_code': product_alternate.name,
                        'sequence': product_alternate.sequence,
                        'channel_id': channel.id,
                        'product_id': product_variant.id,
                        'product_channel_variant_id': product_alternate.product_channel_variant_id.id
                    }))
            else:
                product_mapping_variants = product_variant.product_channel_variant_ids.filtered(
                    lambda p: p.channel_id.id == channel.id)
                if product_mapping_variants:
                    for product_mapping_variant in product_mapping_variants:
                        product_previews.append((0, 0, {
                            'default_code': product_variant.default_code,
                            'sequence': 0,
                            'channel_id': channel.id,
                            'product_id': product_variant.id,
                            'product_channel_variant_id': product_mapping_variant.id
                        }))
                else:
                    product_previews.append((0, 0, {
                        'default_code': product_variant.default_code,
                        'sequence': 0,
                        'channel_id': channel.id,
                        'product_id': product_variant.id,
                    }))
        return product_previews

    @api.depends('channel_ids')
    def _compute_product_preview_ids(self):
        for record in self:
            if record.product_tmpl_id:
                product_tmpls = record.product_tmpl_id
            elif 'active_ids' in self.env.context and self.env.context['active_ids']:
                product_tmpls = self.env['product.template'].browse(list(map(int, self.env.context['active_ids'])))
            product_previews = []
            product_variants = product_tmpls.mapped('product_variant_ids')

            for channel in record.channel_ids:
                channel_product_previews = self._process_product_preview_for_each_channel(product_variants, channel)
                product_previews.extend(channel_product_previews)

            record.update({
                'product_preview_ids': product_previews
            })

    @api.depends('product_tmpl_id')
    def _compute_product_product_count(self):
        for record in self:
            if record.product_tmpl_id:
                record.product_product_count = len(record.product_tmpl_id.product_variant_ids)
            else:
                record.product_product_count = 0

    @api.model
    def _prepare_exported_vals(self, product_tmpl, channel, map_variant, is_updated):
        product_channels = self.env['product.channel'].browse()
        if is_updated:
            product_channels = product_tmpl.product_channel_ids.filtered(lambda p: p.channel_id == channel)
        vals = product_tmpl.with_context(export_from_master=True)._prepare_product_channel_data(
            channel=channel, update=is_updated, map_variant=map_variant)
        if not is_updated:
            vals.update({
                'product_tmpl_id': product_tmpl.id,
                'channel_id': channel.id,
                'inventory_tracking': False if product_tmpl.type in ['service', 'consu'] else True,
            })
        return product_channels, vals

    def _check_invalid_product(self, channel):
        def get_alt_skus(var, chn):
            return var.product_alternate_sku_ids.filtered(lambda p: p.channel_id == chn)

        product_ids = list(map(int, self.env.context.get('active_ids', [])))
        product_tmpls = self.product_tmpl_id or self.env['product.template'].browse(product_ids)
        for product_tmpl in product_tmpls:
            product_variants = product_tmpl.product_variant_ids
            if not (all(variant.product_channel_variant_ids for variant in product_variants)
                    or all(not variant.product_channel_variant_ids for variant in product_variants))\
                    or len(set(len(get_alt_skus(variant, channel)) or 1 for variant in product_variants)) > 1:
                raise ValidationError(_('Do not support to export for this product!'))

            product_previews = self.product_preview_ids.filtered(
                lambda p: p.product_id.product_tmpl_id == product_tmpl)
            if not all(product_preview.default_code for product_preview in product_previews):
                raise ValidationError(_('SKU is required. Please add Alternate SKU for the selected store.'))

    def prepare_product_channel_data_for_export_separately(self, product_tmpl, channel):
        product_previews = self.product_preview_ids.filtered(
            lambda p: p.product_id.product_tmpl_id == product_tmpl and p.channel_id == channel
        ).sorted(lambda p: (p.product_id.id, -p.sequence))
        product_dict = {}

        for product, g in itertools.groupby(product_previews, key=lambda p: p.product_id):
            product_dict[product] = self.env['product.export.preview'].concat(*list(g))
        return product_dict

    def export(self):
        self.ensure_one()
        exported_mappings = self.env['product.channel'].browse()

        if self.product_tmpl_id:
            for channel in self.channel_ids:
                channel.with_context(active_test=False).ensure_operating()
                self._check_invalid_product(channel)
                product_dict = self.prepare_product_channel_data_for_export_separately(self.product_tmpl_id, channel)
                is_update = bool(self.product_tmpl_id.product_channel_ids.filtered(lambda p: p.channel_id == channel))
                product_previews = self.product_preview_ids.filtered(lambda p: p.channel_id == channel)
                number_of_group = len(product_previews) // len(self.product_tmpl_id.product_variant_ids)
                ctx = self.env.context.copy()
                if number_of_group > 1 or len(self.channel_ids) > 1:
                    ctx['delay_exec'] = True

                for index in range(number_of_group):
                    map_variant = {k: v[index] for k, v in product_dict.items()}
                    product_channels, vals = self._prepare_exported_vals(
                        self.product_tmpl_id, channel, map_variant, is_update)
                    product_channels = product_channels.with_context(**ctx).export_from_master_data(
                        vals=vals,
                        ids=product_channels.ids,
                        channel_id=channel.id,
                        is_created=not is_update,
                    )
                    if 'delay_exec' not in ctx:
                        exported_mappings |= product_channels

        elif 'active_ids' in self.env.context and self.env.context['active_ids']:
            product_ids = list(map(int, self.env.context['active_ids']))
            product_tmpls = self.env['product.template'].browse(product_ids)
            for channel in self.channel_ids:
                self._check_invalid_product(channel)
                for product_tmpl in product_tmpls:
                    product_dict = self.prepare_product_channel_data_for_export_separately(product_tmpl, channel)
                    is_update = bool(product_tmpl.product_channel_ids.filtered(lambda p: p.channel_id == channel))
                    product_previews = self.product_preview_ids.filtered(
                        lambda p: p.product_id.product_tmpl_id == product_tmpl and p.channel_id == channel)
                    for index in range(len(product_previews) // len(product_tmpl.product_variant_ids)):
                        map_variant = {}
                        for k, v in product_dict.items():
                            map_variant[k] = v[index]

                        product_channels, vals = self._prepare_exported_vals(
                            product_tmpl, channel, map_variant, is_update)
                        product_channels.with_context(delay_exec=True).export_from_master_data(
                            vals=vals,
                            ids=product_channels.ids,
                            channel_id=channel.id,
                            is_created=not is_update,
                        )

        return self._return_action_after_process(exported_mappings, self.channel_ids)

    def _return_action_after_process(self, mappings, channels):
        if len(mappings) == 1 and len(channels) == 1:
            cust_method_name = '%s_get_mapping_views' % channels[0].platform
            form_id = False
            if hasattr(channels[0], cust_method_name):
                parent, view_ids = getattr(channels[0], cust_method_name)()
                form_id = view_ids[2][2]['view_id']

            return {
                'name': 'Create Product On Channel',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'product.channel',
                'view_id': form_id,
                'res_id': mappings[:1].id,
                'type': 'ir.actions.act_window',
                'context': {'form_view_initial_mode': 'edit'}
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Notification!'),
                    'message': _('Products are exporting....'),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    @api.onchange('channel_id')
    def onchange_channel_id(self):
        """
        Place for other channels to inherit
        """
        return {}
