from odoo import fields, models, api


class SuitableService(models.Model):
    _name = "suitable.service"
    _order = "rate, latest_delivery_date, earliest_delivery_date"

    name = fields.Char(compute="_compute_name", store=True)
    service_name = fields.Char("Service Name")
    carrier_name = fields.Char("Carrier Name")
    id_on_amazon = fields.Char("Service ID on Amazon")
    offer_id_on_amazon = fields.Char("Service Offer ID on Amazon")
    earliest_delivery_date = fields.Date("Earliest Estimated Delivery Date")
    latest_delivery_date = fields.Date("Latest Estimated Delivery Date")
    currency_id = fields.Many2one("res.currency")
    rate = fields.Monetary("Rate")
    picking_id = fields.Many2one("stock.picking")

    @api.depends("service_name", "latest_delivery_date", "rate")
    def _compute_name(self):
        for record in self:
            record.name = f"{record.service_name}; ETA: {record.latest_delivery_date} - {record.currency_id.display_name} {record.rate:.2f}"
