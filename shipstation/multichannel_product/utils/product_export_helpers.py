
import logging
import contextlib

from odoo import api, registry, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GeneralProductExporter:
    DEFAULT_VALUE = object()

    def __init__(self, mapping_template, exported_fields=None, from_master=False):
        self.mapping_template = mapping_template
        self.platform = mapping_template.channel_id.platform
        self.exported_fields = exported_fields or {}
        self.env = mapping_template.env

        self.log_data = {}
        self.export_from_master = from_master
        self.job_uuid = self.env.context.get('job_uuid')
        self.exec = None

    @property
    def is_needed_to_log(self):
        return self.is_running_in_queue_job

    @property
    def is_running_in_queue_job(self):
        return bool(self.job_uuid)

    @property
    def is_posted_successfully(self):
        return bool(self.mapping_template.id_on_channel)

    @property
    def is_product_error(self):
        return self.mapping_template.state == 'error'

    @property
    def is_needed_to_sync_from_channel(self):
        return not self.is_product_error or self.export_from_master

    def push(self):
        with self.monitor_to_log():
            self.ensure_one()
            self.remove_error_mapping_at_the_end_forcefully()
            if self.check_sku():
                self._push_to_channel()
                self.update_prod_alt_sku()
            else:
                self.mark_product_as_sku_missing()

    @contextlib.contextmanager
    def monitor_to_log(self):
        try:
            with self.env.cr.savepoint():
                yield
        except Exception as ex:
            self.exec = ex
            raise
        finally:
            if self.is_needed_to_log:
                self.log()

    def ensure_one(self):
        self.mapping_template.ensure_one()

    def check_sku(self):
        return all(v.default_code for v in self.mapping_template.product_variant_ids)

    def _push_to_channel(self):
        mt = self.mapping_template
        self._post_product()
        if self.is_posted_successfully:
            self._update_images()
            self._post_extra_info()
            self._push_inventory()
            self.mark_product_as_published()
        elif self.is_product_error:
            message = mt.error_message
            raise ValidationError(_(message))

    def _post_product(self):
        res = self._post_platform_specific_product()
        if res != self.DEFAULT_VALUE:
            self.log_data.update({'product': res})

    def _post_platform_specific_product(self):
        mt = self.mapping_template
        cust_method_name = '%s_post_record' % self.platform
        if hasattr(mt, cust_method_name):
            return getattr(mt, cust_method_name)(exported_fields=self.exported_fields)
        return self.DEFAULT_VALUE

    def _update_images(self, *args, **kwargs):
        res = self._update_platform_specific_images(*args, **kwargs)
        if res != self.DEFAULT_VALUE:
            self.log_data.update({'image': res})

    def _update_platform_specific_images(self, *args, **kwargs):
        mt = self.mapping_template
        if mt.channel_id.get_setting('manage_images'):
            cust_method_name = '%s_update_images' % self.platform
            if hasattr(mt, cust_method_name):
                return getattr(mt, cust_method_name)(*args, **kwargs)
        return self.DEFAULT_VALUE

    def _post_extra_info(self):
        res = self._post_platform_specific_extra_info()
        if res != self.DEFAULT_VALUE:
            self.log_data.update({'extra': res})

    def _post_platform_specific_extra_info(self):
        mt = self.mapping_template
        cust_method_name = '%s_post_extra_info' % mt.channel_id.platform
        if hasattr(mt, cust_method_name):
            return getattr(mt, cust_method_name)()
        return self.DEFAULT_VALUE

    def _push_inventory(self):
        mt = self.mapping_template
        if mt.channel_id.is_enable_inventory_sync:
            mt.env['stock.move'].with_context(normal_inventory_update=True).inventory_sync(
                channel_id=mt.channel_id.id,
                product_product_ids=mt.product_tmpl_id.product_variant_ids.ids
            )

    def mark_product_as_published(self):
        self.mapping_template.with_context(update_status=True).sudo().write({
            'is_publish_message_removed': False,
            'state': 'published',
        })

    def update_prod_alt_sku(self):
        mt = self.mapping_template
        for mv in mt.mapped('product_variant_ids'):
            product_alternate_sku = mv.product_product_id.product_alternate_sku_ids.filtered(
                lambda p, sku=mv.default_code: p.name == sku and p.channel_id == mt.channel_id)
            product_alternate_sku.update({'product_channel_variant_id': mv.id})

    def mark_product_as_sku_missing(self):
        self.mapping_template.with_context(update_status=True).update({
            'state': 'error',
            'error_message': 'SKU must be required!'
        })

    def get_default_data_for_log(self):
        mt = self.mapping_template
        return {
            'name': mt.display_name,
            'sku': mt.default_code,
            'variants': [
                {
                    'name': v.display_name,
                    'sku': v.default_code or '',
                }
                for v in mt.product_variant_ids
            ]
        }

    def log(self):
        data, status, message = self._prepare_status_and_data_to_log()
        if self.exec is None:
            def pre_commit_log():
                log = old_env['omni.log'].create(data)
                log.update_status(status, message)
                old_env['omni.log'].flush()

            old_env = self.env
            self.env.cr.precommit.add(pre_commit_log)
        else:
            def post_rollback_log():
                with registry(dbname).cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    log = env['omni.log'].create(data)
                    log.update_status(status, message)

            dbname = self.env.cr.dbname
            context = self.env.context
            uid = self.env.uid
            self.env.cr.postrollback.add(post_rollback_log)

    def _prepare_status_and_data_to_log(self):
        data = self._prepare_data_to_log()
        status, message = self._prepare_status_to_log()
        return data, status, message

    def _prepare_data_to_log(self):
        mt = self.mapping_template
        data = self.log_data or self.get_default_data_for_log()
        result = {
            'datas': data,
            'channel_id': mt.channel_id.id,
            'entity_name': mt.display_name,
            'job_uuid': self.job_uuid,
        }
        if self.export_from_master:
            result.update({
                'operation_type': 'export_master',
                'res_model': mt.product_tmpl_id._name,
                'res_id': mt.product_tmpl_id.id,
            })
        else:
            result.update({
                'operation_type': 'export_mapping',
                'res_model': mt._name,
                'res_id': mt.id,
            })
        return result

    def _prepare_status_to_log(self):
        mt = self.mapping_template
        if self.exec is not None:
            status, message = 'failed', str(self.exec)
        elif self.is_product_error:
            status, message = 'failed', ','.join(mt.mapped('error_message'))
        else:
            status, message = 'done', None
        return status, message

    def remove_error_mapping_at_the_end_forcefully(self):
        self.env.cr.precommit.add(self.remove_error_mapping)

        if self.is_running_in_queue_job:
            def remove_mapping_with_new_cr():
                """As any error occurs, this product is considered as a failure"""
                with registry(dbname).cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    request = env[model].sudo().browse(res_ids)
                    request.exists().unlink()

            dbname = self.env.cr.dbname
            context = self.env.context
            uid = self.env.uid
            model = self.mapping_template._name
            res_ids = self.mapping_template.ids

            self.env.cr.postrollback.add(remove_mapping_with_new_cr)

    def remove_error_mapping(self):
        if self.is_running_in_queue_job and self.is_product_error:
            self.mapping_template.unlink()

    def put(self):
        with self.monitor_to_log():
            self.ensure_one()
            if self.check_sku():
                self._put_to_channel()
            else:
                self.mark_product_as_sku_missing()

    def _put_to_channel(self):
        self._ensure_export_from_mapping_allowed()
        self._put_product()
        self._put_extra_info()
        if self.is_needed_to_sync_from_channel:
            self._sync_data_from_channel()
        self._update_images(update=True)

    def _ensure_export_from_mapping_allowed(self):
        is_allowed = not self.mapping_template.channel_id.can_export_product_from_mapping
        if is_allowed and not self.export_from_master:
            raise ValidationError(_("You cannot export mapping to store."
                                    " Please check your settings in store settings and try again."))

    def _put_product(self):
        res = self._put_platform_specific_product()
        if res != self.DEFAULT_VALUE:
            self.log_data.update({'product_data': res})

    def _put_platform_specific_product(self):
        mt = self.mapping_template
        cust_method_name = '%s_put_record' % self.platform
        if hasattr(mt, cust_method_name):
            return getattr(mt, cust_method_name)(exported_fields=self.exported_fields)
        return self.DEFAULT_VALUE

    def _put_extra_info(self):
        res = self._put_platform_specific_extra_info()
        if res != self.DEFAULT_VALUE:
            self.log_data.update({'extra': res})

    def _put_platform_specific_extra_info(self):
        mt = self.mapping_template
        cust_method_name = '%s_put_extra_info' % self.platform
        if hasattr(mt, cust_method_name):
            return getattr(mt, cust_method_name)()
        return self.DEFAULT_VALUE

    def _sync_data_from_channel(self):
        mt = self.mapping_template
        mt.get_data_from_channel()
        mt.with_context(update_status=True).sudo().write({'is_publish_message_removed': False})

    def put_from_mapping(self):
        with self.monitor_to_log():
            self.ensure_one()
            with self._convert_exception():
                self._put_to_channel()

    @contextlib.contextmanager
    def _convert_exception(self):
        try:
            yield
        except ValidationError:
            raise
        except Exception as ex:
            _logger.exception('Error while exporting product to channel')
            raise ValidationError(_("An error occurred, please try again.\n%s", str(ex)))
