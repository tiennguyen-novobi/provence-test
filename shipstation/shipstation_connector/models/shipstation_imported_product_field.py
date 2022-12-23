import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class ShipStationImportedProductField(models.Model):
    _name = 'shipstation.imported.product.field'
    _description = 'ShipStation Imported Product Field'

    api_ref = fields.Char(string='API Ref')
    name = fields.Char(string='Name')
