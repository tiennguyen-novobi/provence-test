from odoo import models


class DepositOrder(models.TransientModel):
    _inherit = 'deposit.order'

    def create_deposit(self):
        res = super().create_deposit()
        active_model = self._context.get('active_model', False)
        if res and active_model == 'purchase.order':
            context = res.get('context', {})
            context.update({
                'default_payment_type': 'outbound',
                'default_partner_type': 'supplier',
                'default_purchase_deposit_id': self._context.get('active_id')
            })
            res['context'] = context
        return res
