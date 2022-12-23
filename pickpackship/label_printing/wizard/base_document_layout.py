# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
from odoo import models


class BaseDocumentLayout(models.TransientModel):
    _inherit = 'base.document.layout'

    def document_layout_save(self):
        res = super(BaseDocumentLayout, self).document_layout_save()
        ctx = self.env.context
        # Look for overridden printing function and call it instead
        if ctx.get('do_send_print_picking'):
            res_id, method = ctx.get('res_id'), ctx.get('method')
            if res_id and method:
                record = self.env['stock.picking'].browse(res_id)
                if hasattr(record, method):
                    res = getattr(record, method)()
        return res
