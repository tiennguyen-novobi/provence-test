# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from ..utils.amazon_report_helper import AmazonReportHelper
import base64
import csv
from io import StringIO
import requests
from gzip import decompress
from datetime import datetime, timedelta

PROCESS_REPORT_FUNC = {
    'GET_MERCHANT_LISTINGS_DATA': ('product.template', '_amazon_import_products')
}
class AmazonReport(models.Model):
    _name = 'amazon.report'
    _description = 'Amazon Report'
    _rec_name = 'display_name'
    
    report_type = fields.Selection([('GET_MERCHANT_LISTINGS_DATA', 'Active Listings Report')], 
                                   string='Report Type', required=True)
    id_on_channel = fields.Char(string='ID on Channel', required=True)
    status = fields.Selection([('IN_QUEUE', 'In Queue'),
                               ('IN_PROGRESS', 'In Progress'),
                               ('DONE', 'Done'),
                               ('CANCELLED', 'Cancelled'),
                               ('FATAL', 'Fatal')], string='Status')
    channel_id = fields.Many2one('ecommerce.channel', string='Channel', required=True)
    report_document_id = fields.Char(string='Report Document ID')
    
    datas_filename = fields.Char(string='Datas File Name')
    datas = fields.Binary('Content', attachment=True)
    
    display_name = fields.Char(string='Display Name', compute='_compute_display_name')
    auto_create_master = fields.Boolean(string='Auto create master', readonly=True)
    
    def _compute_display_name(self):
        res, res_lang_id = [], self.env['res.lang']._lang_get(self.env.user.lang)
        report_types = dict(self._fields['report_type'].selection)
        for record in self:
            operation = report_types[self.report_type]
            formatted_dt = record.create_date.strftime("%s %s" % (res_lang_id.date_format, res_lang_id.time_format))
            display_name = _('%s - %s (UTC)') % (operation, formatted_dt)
            record.display_name = display_name
    
    @api.model
    def check_status(self):
        reports = self.search([('status', 'in', ['IN_PROGRESS', 'IN_QUEUE'])])
        for report in reports:
            report.with_delay().get_status()
    
    def get_status(self):
        self.ensure_one()
        helper = AmazonReportHelper(self.channel_id)
        res = helper.get_report(self.id_on_channel)
        if res.ok():
            data = res.data
            self.update({'status': data['status'],
                        'report_document_id': data['report_document_id']})
            if data['report_document_id']:
                self.with_delay().get_report_document()

    def get_report_document(self):
        self.ensure_one()
        helper = AmazonReportHelper(self.channel_id)
        res = helper.get_report_document(self.report_document_id)
        if res.ok():
            data = res.data
            response = requests.get(data['url'])
            if 'compressionAlgorithm' in data:
                byte_data = decompress(response.content)
                datas = base64.b64encode(byte_data)
            else:
                datas = base64.b64encode(response.content)
            model, method = PROCESS_REPORT_FUNC[self.report_type]
            report_types = dict(self._fields['report_type'].selection)
            operation = report_types[self.report_type]
            self.update({'datas': datas, 
                         'datas_filename': f'{operation}_{self.create_date.timestamp() * 1000}.csv'})
            getattr(self.env[model].with_delay(), method)(self.channel_id.id, self.tab_delimited_2_dict(),
                                                          auto_create_master=self.auto_create_master)     
        return res

    def tab_delimited_2_dict(self):
        self.ensure_one()
        datas = base64.b64decode(self.datas)
        byte_data = datas.decode(encoding='utf-8', errors='ignore')
        data = list(csv.DictReader(StringIO(byte_data), delimiter='\t'))
        return data
    
    def open_report_document(self):
        self.ensure_one()
        helper = AmazonReportHelper(self.channel_id)
        res = helper.get_report_document(self.report_document_id)
        if res.ok():
            data = res.data
            return {
                'type': 'ir.actions.act_url',
                'url': data['url'],
                'target': 'new',
            }
            
    @api.model
    def clear_report(self):
        days = 10
        deadline = datetime.today() - timedelta(days=days)
        reports = self.search([("write_date", "<=", deadline)], limit=500)
        if reports:
            reports.sudo().unlink()
        return True
    
    def write(self, vals):
        res = super().write(vals)
        if 'status' in vals and vals['status'] in ['DONE', 'CANCELLED', 'FATAL']:
            channels = self.filtered(lambda r: r.report_type == 'GET_MERCHANT_LISTINGS_DATA').mapped('channel_id')
            channels.update({'is_in_syncing': False})
        return res