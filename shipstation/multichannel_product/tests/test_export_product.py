# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import Command

from odoo.addons.multichannel_product.utils.product_export_helpers import GeneralProductExporter

from .common import ChannelOrderTestCommon, tagged, ignore_delay, no_commit


@tagged('post_install', 'basic_test', '-at_install')
class TestExportProduct(ChannelOrderTestCommon):
        
    @ignore_delay
    @no_commit
    def test_export_log_export_master(self):
        def push_side_effect(obj):
            obj.log_data.update(datas)

        datas = {'name': 'Listing Name'}
        wizard = self.env['export.product.composer'].create({
            'product_tmpl_id': self.test_data['master_1'].id,
            'channel_ids': [Command.link(self.test_data['store_1'].id)],
        })
        with patch.object(GeneralProductExporter, '_push_to_channel', autospec=True) as mock_push_action:
            mock_push_action.side_effect = push_side_effect
            action = wizard.with_context(job_uuid='12312312321').export()

        self.env.cr.precommit.run()
        self.env.cr.postrollback.clear()

        product_mapping = self.env['product.channel'].browse(action['res_id'])
        log = self.env['omni.log'].search([('job_uuid', '=', '12312312321')])
        self.assertRecordValues(log, [{
            'datas': datas,
            'channel_id': product_mapping.channel_id.id,
            'operation_type': 'export_master',
            'res_model': 'product.template',
            'res_id': product_mapping.product_tmpl_id.id,
            'entity_name': product_mapping.display_name,
            'job_uuid': '12312312321',
            'status': 'done'
        }])
                
    @ignore_delay
    @no_commit
    def test_export_log_export_mapping(self):
        def put_side_effect(obj):
            obj.log_data.update(datas)

        datas = {'name': 'Listing Name'}
        wizard = self.env['export.product.composer'].create({
            'product_tmpl_id': self.test_data['master_1'].id,
            'channel_ids': [Command.link(self.test_data['store_1'].id)],
        })
        with patch.object(GeneralProductExporter, '_push_to_channel', autospec=True):
            with patch.object(GeneralProductExporter, '_put_to_channel', autospec=True) as mock_put_action:
                action = wizard.export()
                product_mapping = self.env['product.channel'].browse(action['res_id'])
                mock_put_action.side_effect = put_side_effect
                product_mapping.with_context(job_uuid='12312312321').export_from_mapping()

        self.env.cr.precommit.run()
        self.env.cr.postrollback.clear()

        log = self.env['omni.log'].search([('job_uuid', '=', '12312312321')])
        self.assertRecordValues(log, [{
            'datas': datas,
            'channel_id': product_mapping.channel_id.id,
            'operation_type': 'export_mapping',
            'res_model': product_mapping._name,
            'entity_name': product_mapping.display_name,
            'status': 'done',
            'job_uuid': '12312312321',
        }])
