# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class AmazonFulfillmentMethod(models.Model):
    _name = 'amazon.fulfillment.method'
    _description = "Amazon Fulfillment Method"
    
    name = fields.Char(string='Name', required=True)
    type = fields.Selection([('MFN', 'FBM'),
                             ('AFN', 'FBA')], string='Fulfillment Method', required=True)

class OrderProcessRule(models.Model):
    _inherit = 'order.process.rule'
    
    amazon_fulfillment_method_ids = fields.Many2many('amazon.fulfillment.method', 
                                                     string='Amazon Fulfillment Method')
    
    @api.model
    def _generate_domain_search_rule(self, channel, order):
        domain = super()._generate_domain_search_rule(channel, order)
        if channel.platform == 'amazon':
            domain += [('amazon_fulfillment_method_ids.type', '=', order.amazon_fulfillment_method)]
        return domain
    
    @api.constrains('amazon_fulfillment_method_ids')
    def _check_amazon_fulfillment_methods(self):
        for record in self.filtered(lambda r: r.platform == 'amazon'):
            if not record.amazon_fulfillment_method_ids:
                raise ValidationError(_('Fulfillment Method(s) is required !'))