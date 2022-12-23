from odoo.tools import float_compare

from odoo import fields, models, api

OUNCE_TO_KILOGRAM = 0.0283495
POUND_TO_KILOGRAM = 0.45359237


class ShipstationShippingRule(models.Model):
    _name = "shipstation.shipping.rule"
    _order = "sequence, id"

    sequence = fields.Integer(string='Priority', default=20)

    product_weight_oz = fields.Float(string="Product Weight (oz)", digits='Stock Weight')
    product_weight_kg = fields.Float(string="Product Weight (kg)", compute="_compute_product_weight_kg",
                                     inverse="_inverse_product_weight_kg", digits='Stock Weight')
    product_qty_min = fields.Float(string="Min Product Qty", digits='Product Unit of Measure')
    product_qty_max = fields.Float(string="Max Product Qty", digits='Product Unit of Measure')
    pkg_weight_min = fields.Float(string="Min Package Weight (kg)", compute="_compute_pkg_weight_min", readonly=True)
    pkg_weight_max = fields.Float(string="Max Package Weight (kg)", compute="_compute_pkg_weight_max", readonly=True)

    pkg_length = fields.Float(string="Length (in)")
    pkg_width = fields.Float(string="Width (in)")
    pkg_height = fields.Float(string="Height (in)")

    package_ids = fields.Many2many("stock.package.type", string="Packages Used")

    @api.depends("product_weight_oz")
    def _compute_product_weight_kg(self):
        for record in self:
            record.product_weight_kg = record.product_weight_oz * OUNCE_TO_KILOGRAM

    def _inverse_product_weight_kg(self):
        for record in self:
            record.product_weight_oz = record.product_weight_kg / OUNCE_TO_KILOGRAM

    @api.depends("product_weight_oz", "product_qty_min")
    def _compute_pkg_weight_min(self):
        for record in self:
            record.pkg_weight_min = record.product_weight_oz * record.product_qty_min * OUNCE_TO_KILOGRAM

    @api.depends("product_weight_oz", "product_qty_max")
    def _compute_pkg_weight_max(self):
        for record in self:
            record.pkg_weight_max = record.product_weight_oz * record.product_qty_max * OUNCE_TO_KILOGRAM

    def is_rule_satisfied(self, picking) -> bool:
        # all products must have weight <= product weight and demand qty <= max
        # should not compare with min as total weight may not allow for a smaller package
        for ml in picking.move_lines:
            if float_compare(ml.product_id.weight, self.product_weight_kg, precision_digits=self.env['decimal.precision'].precision_get('Stock Weight')) > 0 or float_compare(
                    ml.product_uom_qty, self.product_qty_max, precision_digits=self.env['decimal.precision'].precision_get('Product Unit of Measure')) > 0:
                return False
        # total pkg weight must be lower than max
        # package_shipping_weight is in pounds
        return float_compare(picking.package_shipping_weight * POUND_TO_KILOGRAM, self.pkg_weight_max,
                             precision_digits=self.env['decimal.precision'].precision_get('Stock Weight')) <= 0

    def find_suitable_packages(self, picking):
        for rule in self.search([]):
            if rule.is_rule_satisfied(picking):
                return rule.package_ids, rule.pkg_length, rule.pkg_width, rule.pkg_height

        # FIX - if no rule is satisfied
        return False, 0, 0, 0

