# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, res_ids=None, data=None):
        report_packing_slip = self.env.ref('novobi_shipping_account.action_report_packing_slip')
        if self == report_packing_slip:
            this = self.with_context(report_packing_slip=True)
            return super(IrActionsReport, this)._render_qweb_pdf(res_ids, data)
        return super(IrActionsReport, self)._render_qweb_pdf(res_ids, data)

    @api.model
    def get_paperformat(self):
        if self.env.context.get('report_packing_slip'):
            return self.env.company.packing_slip_size
        return super(IrActionsReport, self).get_paperformat()
