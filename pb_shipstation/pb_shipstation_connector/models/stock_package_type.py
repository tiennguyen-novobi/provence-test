from odoo import fields, models


class PackageType(models.Model):
    _inherit = 'stock.package.type'

    package_carrier_type = fields.Selection(
        selection_add=[('fedex', 'FedEx'), ('stamps_com', 'Stamps.com/USPS'), ("dhl_express_worldwide", "DHL"),
                       ("ups_walleted", "UPS")])