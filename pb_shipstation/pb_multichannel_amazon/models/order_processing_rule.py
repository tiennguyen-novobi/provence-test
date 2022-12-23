# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class OrderProcessRule(models.Model):
    _inherit = 'order.process.rule'

    auto_buy_label = fields.Boolean(string="Auto Buy Label")

    def _do_run_rule(self, order):
        super(OrderProcessRule, self)._do_run_rule(order.with_context(auto_buy=self.auto_buy_label))

    @api.onchange("is_order_confirmed")
    def _onchange_is_order_confirmed(self):
        if not self.is_order_confirmed:
            self.auto_buy_label = False
