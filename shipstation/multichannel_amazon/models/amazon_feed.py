# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from ..utils.amazon_feed_helper import AmazonFeedHelper
import logging
from datetime import datetime, timedelta
from xml.dom import minidom

_logger = logging.getLogger(__name__)

LOG_STATUS_MAP = {
    'CANCELLED': 'failed',
    'DONE': 'done',
    'FATAL': 'failed'
}

class AmazonFeed(models.Model):
    _name = 'amazon.feed'
    _description = 'Amazon Feed'
    _rec_name = 'display_name'
    
    feed_type = fields.Selection([('POST_INVENTORY_AVAILABILITY_DATA', 'Update Quantity Available'),
                                  ('POST_ORDER_FULFILLMENT_DATA', 'Update Fulfillment Data'),
                                  ('POST_ORDER_ACKNOWLEDGEMENT_DATA', 'Order Acknowledgement')], 
                                   string='Report Type', required=True)
    id_on_channel = fields.Char(string='ID on Channel')
    status = fields.Selection([('DRAFT', 'Draft'),
                               ('IN_QUEUE', 'In Queue'),
                               ('IN_PROGRESS', 'In Progress'),
                               ('DONE', 'Done'),
                               ('CANCELLED', 'Cancelled'),
                               ('FATAL', 'Fatal')], string='Status', default='DRAFT')
    channel_id = fields.Many2one('ecommerce.channel', string='Channel', required=True)
    feed_document_id = fields.Char(string='Feed Document ID')
    message = fields.Text(string='Message')
    log_id = fields.Many2one('omni.log', string='Log')
    
    res_id = fields.Integer(string='Res ID')
    res_model = fields.Char(string='Res Model')
    datas = fields.Text(string='Content')
    display_name = fields.Char(string='Display Name', compute='_compute_display_name')
    
    def _compute_display_name(self):
        res, res_lang_id = [], self.env['res.lang']._lang_get(self.env.user.lang)
        feed_types = dict(self._fields['feed_type'].selection)
        for record in self:
            operation = feed_types[self.feed_type]
            formatted_dt = record.create_date.strftime("%s %s" % (res_lang_id.date_format, res_lang_id.time_format))
            display_name = _('%s - %s (UTC)') % (operation, formatted_dt)
            record.display_name = display_name
    
    def create_feed_document(self, content_type, data):
        self.ensure_one()
        helper = AmazonFeedHelper(self.channel_id)
        content, res = helper.create_feed_document(content_type=content_type, 
                                                   feed_type=self.feed_type, 
                                                   data=data)
        content = minidom.parseString(content).toprettyxml(indent="   ")
        if res.ok():
            self.update({'feed_document_id': res.data['id'], 'datas': content})
            self._create_feed()
        else:
            _logger.error(res.get_error_message())
            errors = res.get_error_message()
            if isinstance(errors, dict):
                errors = [errors]
            self.update({'status': 'FATAL',
                         'datas': content,
                         'message': '\n'.join(error.get('message', '') for error in errors)})
            
    def _create_feed(self):
        self.ensure_one()
        helper = AmazonFeedHelper(self.channel_id)
        res = helper.create_feed(feed_type=self.feed_type, 
                                 marketplace_ids=self.channel_id.amazon_marketplace_id.api_ref, 
                                 feed_document_id=self.feed_document_id)
        if res.ok():
            self.update({'status': 'IN_QUEUE',
                         'id_on_channel': res.data['id']})
        else:
            _logger.error(res.get_error_message())
            errors = res.get_error_message()
            if isinstance(errors, dict):
                errors = [errors]
            self.update({'status': 'FATAL',
                         'message': '\n'.join(error.get('message', '') for error in errors)})
            
    @api.model
    def check_status(self):
        reports = self.search([('status', 'in', ['IN_PROGRESS', 'IN_QUEUE'])])
        for report in reports:
            report.with_delay().get_status()
    
    def get_status(self):
        self.ensure_one()
        helper = AmazonFeedHelper(self.channel_id)
        res = helper.get_feed(self.id_on_channel)
        if res.ok():
            data = res.data
            self.update({'status': data['status'],
                         'feed_document_id': data['feed_document_id']})
            
    def check_document_status(self):
        self.ensure_one()
        helper = AmazonFeedHelper(self.channel_id)
        res = helper.get_feed_document(self.feed_document_id)
        if res.ok():
            return {
            'type': 'ir.actions.act_url',
            'url': res.data['url'],
            'target': 'new',
        }
            
    
    def _log_exceptions(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        if self.feed_type == 'POST_ORDER_FULFILLMENT_DATA':
            record._log_exceptions_on_picking('Cannot create/update shipment on Amazon', [])
        
    def write(self, vals):
        res = super().write(vals)
        if 'status' in vals and vals['status'] in ['CANCELLED', 'DONE', 'FATAL']:
            log_status = LOG_STATUS_MAP[vals['status']]
            for record in self.filtered(lambda r: r.log_id):
                record.log_id.update({'status': log_status,
                                      'message': record.message})
                if record.res_id and record.res_model and vals['status'] in ['CANCELLED', 'FATAL']:
                    record._log_exceptions()
        return res
    
    @api.model
    def clear_feed(self):
        days = 10
        deadline = datetime.today() - timedelta(days=days)
        feeds = self.search([("write_date", "<=", deadline)], limit=500)
        if feeds:
            feeds.sudo().unlink()
        return True