import logging

from odoo import api, fields, models, _
_logger = logging.getLogger(__name__)


class OrderProcessRule(models.Model):
    _inherit = 'order.process.rule'

    @api.model
    def _find_parent(self, order):
        if order.shipstation_parent_id:
            parent_order = self.env['sale.order'].search([('id_on_shipstation', '=', order.shipstation_parent_id)])
            parent_order = self._find_parent(parent_order)
        else:
            parent_order = order
        return parent_order

    def _do_run_create_invoice(self, order):
        if order.shipstation_parent_id:
            parent_order = self._find_parent(order)
            if parent_order.is_invoiced:
                pass
            else:
                super()._do_run_create_invoice(order)
        else:
            super()._do_run_create_invoice(order)

    def _adjust_payment_amount(self, order):
        deposit = order.deposit_ids[0]
        deposit.action_draft()
        deposit.update({'amount': order.amount_total})
        deposit.action_post()

    def _do_run_create_payment(self, order):
        super()._do_run_create_payment(order)
        if order.platform == 'shipstation' and order.deposit_ids:
            if order.deposit_ids[0].amount > order.amount_total:
                self._adjust_payment_amount(order)
