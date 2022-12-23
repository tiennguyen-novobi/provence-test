# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import exceptions, fields, models, _

class AmazonMarketplace(models.Model):
    _name = 'amazon.marketplace'
    _description = "Amazon Marketplace"
    _rec_name = 'domain'

    name = fields.Char("Name", required=True, translate=True)
    code = fields.Char("Code", help="The country code in ISO 3166-1 format", required=True)
    domain = fields.Char(
        "Domain", help="The domain name associated with the marketplace", required=True, index=True)
    api_ref = fields.Char(
        "API Identifier", help="The Amazon-defined marketplace reference", required=True, index=True)
    currency_id = fields.Many2one('res.currency')
    fulfillment_center_ref = fields.Selection(selection=[
        ('DEFAULT', 'DEFAULT'),
        ('AMAZON_NA', 'AMAZON_NA'),
        ('AMAZON_EU', 'AMAZON_EU'),
        ('AMAZON_JP', 'AMAZON_JP'),
        ('AMAZON_IN', 'AMAZON_IN'),
    ], string='Fulfillment Center ID')
    
    aws_region = fields.Selection([('us-east-1', 'North America'),
                                   ('eu-west-1', 'Europe'),
                                   ('us-west-2', 'Far East')])
    _sql_constraints = [(
        'unique_api_ref',
        'UNIQUE(api_ref)',
        "There can only exist one marketplace for a given API Identifier."
    )]

    def unlink(self):
        raise exceptions.UserError(_('Amazon marketplaces cannot be deleted.'))
